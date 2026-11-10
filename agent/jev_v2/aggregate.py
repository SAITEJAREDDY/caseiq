"""Scored decision records -> aggregate report, per decision type. Reuses
Phase 6's generic statistical helpers directly wherever a decision record
exposes the (confidence, correct) shape those helpers already expect --
no reimplementation of calibration/bootstrap math (spec section 52's "do
not create a second incompatible evaluation framework").
"""
import statistics
from math import ceil
from collections import defaultdict

from agent.eval_v2.aggregate import _bootstrap_ci, _mean, brier_and_ece, calibration_table, false_confident_rate
from agent.jev_v2.config import (
    AUTOMATION_THRESHOLDS,
    FALSE_CONFIDENT_THRESHOLD,
    JEV_PRICE_PER_M_INPUT_USD,
    JEV_PRICE_PER_M_OUTPUT_USD,
    LLM_PRICE_PER_M_INPUT_USD,
    LLM_PRICE_PER_M_OUTPUT_USD,
    PRICING_VERSION,
    TARGET_ERROR_RATES,
)
from agent.jev_v2.scoring import NO_CAUSAL_CHANGE_KEY


def _conf(r):
    return r["scoring"].get("predicted_confidence")


def _correct(r):
    return r["scoring"].get("correct")


def confusion_and_f1(records: list) -> dict:
    pairs = [
        (r["scoring"]["ground_truth_value"], r["scoring"]["predicted_value"])
        for r in records
        if r["scoring"].get("predicted_value") is not None and r["scoring"].get("ground_truth_value") is not None
    ]
    if not pairs:
        return {"confusion_matrix": {}, "macro_f1": None, "per_class": {}}
    matrix = defaultdict(lambda: defaultdict(int))
    for t, p in pairs:
        matrix[t][p] += 1
    classes = sorted({t for t, _ in pairs} | {p for _, p in pairs}, key=str)
    per_class, f1s = {}, []
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[t][c] for t in classes if t != c)
        fn = sum(matrix[c][p] for p in classes if p != c)
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall) > 0) else 0.0
        per_class[c] = {"precision": precision, "recall": recall, "f1": f1, "support": sum(matrix[c].values())}
        f1s.append(f1)
    return {"confusion_matrix": {t: dict(p) for t, p in matrix.items()}, "macro_f1": statistics.fmean(f1s) if f1s else None, "per_class": per_class}


def candidate_recall_summary(records: list) -> dict:
    with_known = [r for r in records if r["scoring"].get("candidate_answer_present") is not None]
    n = len(with_known)
    present_n = sum(1 for r in with_known if r["scoring"]["candidate_answer_present"])
    end_to_end = [r["scoring"]["correct"] for r in with_known if r["scoring"].get("correct") is not None]
    conditional = [r["scoring"]["correct_given_present"] for r in with_known if r["scoring"].get("correct_given_present") is not None]
    return {
        "n_with_known_candidate_set": n,
        "candidate_recall": (present_n / n) if n else None,
        "end_to_end_accuracy": (_mean([1.0 if c else 0.0 for c in end_to_end])) if end_to_end else None,
        "conditional_accuracy_given_present": (_mean([1.0 if c else 0.0 for c in conditional])) if conditional else None,
        "avg_candidate_count": _mean([len(r.get("candidates") or {}) for r in with_known]),
        "median_candidate_count": statistics.median([len(r.get("candidates") or {}) for r in with_known]) if with_known else None,
        "p90_candidate_count": _percentile([len(r.get("candidates") or {}) for r in with_known], 0.90),
    }


def _percentile(values: list, quantile: float):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, ceil(quantile * len(ordered)) - 1)]


def failure_source_decomposition(records: list, candidate_key: str = "candidate_answer_present") -> dict:
    """Separate candidate omissions from model errors without blending them."""
    out = {"candidate_missing": 0, "candidate_present_jev_wrong": 0, "candidate_present_jev_correct": 0, "jev_wrong_high_confidence": 0}
    for r in records:
        scoring = r.get("scoring") or {}
        present = scoring.get(candidate_key)
        if present is None and candidate_key == "primary_candidate_present":
            present = scoring.get("ground_truth_value") in (r.get("candidates") or {})
        elif present is None and candidate_key == "acceptable_candidate_present":
            present = scoring.get("candidate_answer_present")
        correct = scoring.get("correct")
        if present is False:
            out["candidate_missing"] += 1
        elif present is True and correct is True:
            out["candidate_present_jev_correct"] += 1
        elif present is True and correct is False:
            out["candidate_present_jev_wrong"] += 1
        if correct is False and (_conf(r) or 0) >= FALSE_CONFIDENT_THRESHOLD:
            out["jev_wrong_high_confidence"] += 1
    return out


def owning_team_metrics(records: list) -> dict:
    def primary_present(r):
        # v1 records predate the explicit field; their scalar primary truth is
        # enough to derive it without changing their stored outputs.
        return r["scoring"].get("primary_candidate_present", r["scoring"].get("ground_truth_value") in (r.get("candidates") or {}))

    def acceptable_present(r):
        return r["scoring"].get("acceptable_candidate_present", r["scoring"].get("candidate_answer_present"))

    def rate(values):
        known = [v for v in values if v is not None]
        return _mean([1.0 if v else 0.0 for v in known]) if known else None

    primary_conditional = [
        r["scoring"].get("primary_correct_given_present", r["scoring"].get("correct") if primary_present(r) else None)
        for r in records
    ]
    acceptable_conditional = [
        r["scoring"].get("acceptable_correct_given_present", r["scoring"].get("acceptable_match") if acceptable_present(r) else None)
        for r in records
    ]
    return {
        "primary_candidate_recall": rate([primary_present(r) for r in records]),
        "acceptable_candidate_recall": rate([acceptable_present(r) for r in records]),
        "primary_accuracy": rate([r["scoring"].get("correct") for r in records]),
        "acceptable_accuracy": rate([r["scoring"].get("acceptable_match") for r in records]),
        "conditional_primary_accuracy": rate(primary_conditional),
        "conditional_acceptable_accuracy": rate(acceptable_conditional),
        "failure_decomposition_primary": failure_source_decomposition(records, "primary_candidate_present"),
        "failure_decomposition_acceptable": failure_source_decomposition(records, "acceptable_candidate_present"),
    }


def decision_cost_usd(rec: dict):
    """Cost of one decision from the provider-returned token counts (summed over
    every attempt for the LLM). Prices are the versioned assumptions in
    config.py; None when the record carries no usage (e.g. an API error)."""
    usage = rec.get("usage") or {}
    tokens_in, tokens_out = usage.get("input_tokens"), usage.get("output_tokens")
    if tokens_in is None:
        return None
    if "jev_model" in rec:
        price_in, price_out = JEV_PRICE_PER_M_INPUT_USD, JEV_PRICE_PER_M_OUTPUT_USD
    else:
        price_in, price_out = LLM_PRICE_PER_M_INPUT_USD, LLM_PRICE_PER_M_OUTPUT_USD
    return (tokens_in * price_in + (tokens_out or 0) * price_out) / 1_000_000


def efficiency_summary(records: list) -> dict:
    latencies = [r.get("latency_ms") for r in records if r.get("latency_ms") is not None]
    input_tokens = [(r.get("usage") or {}).get("input_tokens") for r in records if (r.get("usage") or {}).get("input_tokens") is not None]
    output_tokens = [(r.get("usage") or {}).get("output_tokens") for r in records if (r.get("usage") or {}).get("output_tokens") is not None]
    costs = [c for c in (decision_cost_usd(r) for r in records) if c is not None]
    total_cost = sum(costs)
    return {
        "mean_latency_ms": _mean(latencies), "total_input_tokens": sum(input_tokens), "total_output_tokens": sum(output_tokens),
        "mean_input_tokens": _mean(input_tokens), "mean_output_tokens": _mean(output_tokens),
        "p50_latency_ms": statistics.median(latencies) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "total_cost_usd": total_cost, "cost_per_decision_usd": (total_cost / len(costs)) if costs else None,
        "cost_per_1000_decisions_usd": (total_cost / len(costs) * 1000) if costs else None,
        "pricing_version": PRICING_VERSION,
    }


def contract_summary(records: list) -> dict:
    """Output-contract reliability. Jev returns native typed results, so it has
    no parse/option failures by construction (only transport errors); the LLM
    baseline is tracked attempt by attempt (JEV-018) and never silently repaired."""
    n = len(records)
    out = {"n_decisions": n, "request_or_api_errors": sum(1 for r in records if r.get("status") == "error")}
    tracked = [r for r in records if "first_attempt_valid" in r]
    if not tracked:
        ok = sum(1 for r in records if r.get("status") == "ok" and not r.get("contract_failure"))
        out.update({"native_typed_output": True, "first_attempt_valid": ok, "first_attempt_valid_rate": (ok / n) if n else None,
                    "repair_required": 0, "repair_succeeded": 0, "unrecoverable_failures": n - ok, "first_attempt_failure_kinds": {}})
        return out
    kinds = defaultdict(int)
    for r in tracked:
        if r.get("first_attempt_failure"):
            kinds[r["first_attempt_failure"]] += 1
    out.update({
        "native_typed_output": False,
        "first_attempt_valid": sum(1 for r in tracked if r["first_attempt_valid"]),
        "first_attempt_valid_rate": sum(1 for r in tracked if r["first_attempt_valid"]) / len(tracked),
        "repair_required": sum(1 for r in tracked if r["repair_required"]),
        "repair_succeeded": sum(1 for r in tracked if r.get("repair_succeeded") is True),
        "unrecoverable_failures": sum(1 for r in tracked if r["unrecoverable_failure"]),
        "first_attempt_failure_kinds": dict(kinds),
    })
    return out


def strict_first_attempt_accuracy(records: list):
    """Every decision counts; a decision whose FIRST attempt broke the output
    contract counts as wrong even if a repair later produced a valid answer.
    Equals plain accuracy for Jev (native typed output, no failures)."""
    n = len(records)
    if not n:
        return None
    hits = 0
    for r in records:
        valid = r["first_attempt_valid"] if "first_attempt_valid" in r else (r.get("status") == "ok" and not r.get("contract_failure"))
        if valid and r["scoring"].get("correct") is True:
            hits += 1
    return hits / n


def trivial_baselines(records: list, decision_type: str) -> dict:
    """Context for reading an accuracy number: what a rule that ignores the
    evidence would score on these same decisions."""
    truths = [r["scoring"].get("ground_truth_value") for r in records if r["scoring"].get("ground_truth_value") is not None]
    if not truths:
        return {}
    counts = defaultdict(int)
    for t in truths:
        counts[t] += 1
    label, top = max(counts.items(), key=lambda kv: (kv[1], str(kv[0])))
    out = {"majority_class": str(label), "majority_class_accuracy": top / len(truths), "n": len(truths)}
    if decision_type == "causal_change":
        hits = sum(1 for r in records if (r["candidate_meta"].get("newest_change_id") or NO_CAUSAL_CHANGE_KEY) == r["scoring"]["ground_truth_value"])
        out["newest_change_else_none_accuracy"] = hits / len(records)
    return out


def accuracy_by_candidate_set_size(records: list) -> dict:
    buckets = {"2-4": (2, 4), "5-8": (5, 8), "9-16": (9, 16), "17+": (17, 10**9)}
    out = {}
    for label, (lo, hi) in buckets.items():
        group = [r for r in records if r.get("candidates") and lo <= len(r["candidates"]) <= hi]
        correct = [r["scoring"]["correct"] for r in group if r["scoring"].get("correct") is not None]
        out[label] = {"n": len(group), "accuracy": (_mean([1.0 if c else 0.0 for c in correct])) if correct else None}
    return out


def automation_coverage(records: list) -> list:
    total = len(records)
    scored = [r for r in records if _conf(r) is not None and _correct(r) is not None]
    rows = []
    for threshold in AUTOMATION_THRESHOLDS:
        eligible = [r for r in scored if _conf(r) >= threshold]
        n = len(eligible)
        correct_n = sum(1 for r in eligible if r["scoring"]["correct"])
        rows.append({
            "threshold": threshold, "coverage": (n / total) if total else None, "n_eligible": n,
            "accuracy_among_eligible": (correct_n / n) if n else None, "error_rate": ((n - correct_n) / n) if n else None,
        })
    return rows


def target_error_coverage(records: list) -> dict:
    total = len(records)
    scored = sorted((r for r in records if _conf(r) is not None and _correct(r) is not None), key=lambda r: -_conf(r))
    out = {}
    for target in TARGET_ERROR_RATES:
        best_n, cum_wrong = 0, 0
        for i, r in enumerate(scored, start=1):
            if not r["scoring"]["correct"]:
                cum_wrong += 1
            if cum_wrong / i <= target:
                best_n = i
        out[str(target)] = {"max_coverage_at_or_below_target": (best_n / total) if total else None, "n": best_n, "n_total_scored": len(scored)}
    return out


def noul_confusion_metrics(records: list) -> dict:
    pairs = [(r["scoring"]["ground_truth_value"], r["scoring"]["predicted_value"]) for r in records if r["scoring"].get("predicted_value") is not None]
    tp = sum(1 for t, p in pairs if t and p)
    tn = sum(1 for t, p in pairs if not t and not p)
    fp = sum(1 for t, p in pairs if not t and p)
    fn = sum(1 for t, p in pairs if t and not p)
    n = len(pairs)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if (precision and recall and (precision + recall)) else None
    return {
        "n": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
        "false_positive_rate": (fp / (fp + tn)) if (fp + tn) else None, "false_negative_rate": (fn / (fn + tp)) if (fn + tp) else None,
        "accuracy": ((tp + tn) / n) if n else None,
    }


def noul_raw_probability_calibration(records: list) -> dict:
    """Proper calibration of the RAW P(yes), not the chosen-answer
    confidence (spec section 32: 'for binary/Noul: bucket predicted
    probability and compare to observed frequency')."""
    pairs = [
        (r["scoring"]["raw_probability_for_true"], r["scoring"]["ground_truth_value"])
        for r in records
        if r["scoring"].get("raw_probability_for_true") is not None
    ]
    if not pairs:
        return {"brier_score": None, "n": 0, "reliability_table": []}
    brier = _mean([(p - (1.0 if y else 0.0)) ** 2 for p, y in pairs])
    buckets = defaultdict(list)
    for p, y in pairs:
        buckets[min(int(p * 10), 9)].append((p, y))
    table = []
    for b in range(10):
        items = buckets.get(b, [])
        table.append({
            "bucket": f"{b / 10:.1f}-{(b + 1) / 10:.1f}", "n": len(items),
            "mean_predicted_p": _mean([p for p, _ in items]) if items else None,
            "observed_freq": (sum(1 for _, y in items if y) / len(items)) if items else None,
        })
    return {"brier_score": brier, "n": len(pairs), "reliability_table": table}


def causal_change_recency_analysis(records: list) -> dict:
    """Spec section 14: was the selected change simply the newest one, and
    does accuracy hold up when the true causal change is NOT the newest.

    evaluator v2.1: the "older than a distractor" group now requires the true
    change to have actually been OFFERED as a candidate. Before, a candidate
    MISS (true change absent, one distractor present) was counted here as an
    older-cause case with accuracy 0 (JEV-024). Stored v2 reports keep the old
    value; comparisons re-aggregate both sides with this definition."""
    relevant = [r for r in records if r["scoring"].get("num_candidate_changes")]
    newest_is_causal = [r for r in relevant if r["scoring"].get("true_causal_change_is_newest")]
    older_is_causal = [
        r for r in relevant
        if r["scoring"]["ground_truth_value"] != NO_CAUSAL_CHANGE_KEY
        and r["scoring"]["ground_truth_value"] in (r.get("candidates") or {})
        and not r["scoring"].get("true_causal_change_is_newest")
    ]

    def acc(group):
        vals = [r["scoring"]["correct"] for r in group if r["scoring"].get("correct") is not None]
        return _mean([1.0 if v else 0.0 for v in vals]) if vals else None

    return {
        "selected_is_newest_change_rate": _mean([1.0 if r["scoring"].get("selected_is_newest_change") else 0.0 for r in relevant]),
        "accuracy_when_true_causal_change_is_newest": acc(newest_is_causal),
        "accuracy_when_true_causal_change_is_older_than_distractor": acc(older_is_causal),
        "n_newest_is_causal": len(newest_is_causal), "n_older_is_causal": len(older_is_causal),
    }


def causal_change_recency_categories(records: list) -> dict:
    """The four groups the JEV-013 rerun must report, plus the one they leave
    out: A true change is the newest candidate; B true change is older than at
    least one distractor (a strictly later-started candidate exists; equal
    timestamps count as A); C no causal change exists; D two or more real
    change candidates were offered (cuts across A/B/C); E the true change was
    not offered at all (a candidate miss, never blamed on the model)."""
    def group_stats(group):
        scored = [r for r in group if r["scoring"].get("correct") is not None]
        return {
            "n": len(group),
            "accuracy": _mean([1.0 if r["scoring"]["correct"] else 0.0 for r in scored]) if scored else None,
            "n_correct": sum(1 for r in scored if r["scoring"]["correct"]),
            "selected_newest_rate": _mean([1.0 if r["scoring"].get("selected_is_newest_change") else 0.0 for r in group]) if group else None,
            "selected_none_rate": _mean([1.0 if r["scoring"].get("predicted_value") == NO_CAUSAL_CHANGE_KEY else 0.0 for r in group]) if group else None,
        }

    cats = {"A_true_is_newest": [], "B_true_older_than_a_distractor": [], "C_no_causal_change": [], "E_true_change_not_offered": []}
    multi = []
    for r in records:
        truth = r["scoring"].get("ground_truth_value")
        meta = r.get("candidate_meta") or {}
        starts = meta.get("change_started_ats") or {}
        if truth == NO_CAUSAL_CHANGE_KEY:
            key = "C_no_causal_change"
        elif truth in starts:
            truth_ts = starts[truth] or ""
            later = any((ts or "") > truth_ts for cid, ts in starts.items() if cid != truth)
            key = "B_true_older_than_a_distractor" if later else "A_true_is_newest"
        else:
            key = "E_true_change_not_offered"
        cats[key].append(r)
        if (meta.get("num_real_change_candidates") or 0) >= 2:
            multi.append((key, r))

    def selected_distractor(r):
        predicted, truth = r["scoring"].get("predicted_value"), r["scoring"].get("ground_truth_value")
        return predicted is not None and predicted != NO_CAUSAL_CHANGE_KEY and predicted != truth

    def distractor_available(r):
        truth = r["scoring"].get("ground_truth_value")
        return any(cid != truth for cid in ((r.get("candidate_meta") or {}).get("change_started_ats") or {}))

    with_prediction = [r for r in records if r["scoring"].get("predicted_value") is not None]
    available = [r for r in with_prediction if distractor_available(r)]
    out = {name.split("_")[0]: {"label": name, **group_stats(group)} for name, group in cats.items()}
    out["D_multiple_recent_changes"] = {
        "label": "D_multiple_recent_changes", **group_stats([r for _, r in multi]),
        "by_true_category": {name.split("_")[0]: group_stats([r for k, r in multi if k == name]) for name in cats},
    }
    out["no_causal_change_accuracy"] = group_stats(cats["C_no_causal_change"])["accuracy"]
    out["false_positive_rate_when_no_causal_change"] = (1 - out["no_causal_change_accuracy"]) if out["no_causal_change_accuracy"] is not None else None
    out["distractor_selection_rate_all_decisions"] = _mean([1.0 if selected_distractor(r) else 0.0 for r in with_prediction]) if with_prediction else None
    out["distractor_selection_rate_when_a_distractor_was_offered"] = _mean([1.0 if selected_distractor(r) else 0.0 for r in available]) if available else None
    out["n_decisions_with_a_distractor_offered"] = len(available)
    return out


def slice_by_stratification(records: list) -> dict:
    out = {}
    for dim in ("difficulty_archetype", "evidence_sufficiency"):
        by_value = defaultdict(list)
        for r in records:
            by_value[r["stratification"].get(dim)].append(r)
        out[dim] = {
            str(value): {
                "n": len(group),
                "accuracy": _mean([1.0 if g["scoring"]["correct"] else 0.0 for g in group if g["scoring"].get("correct") is not None]),
                "mean_confidence": _mean([_conf(g) for g in group if _conf(g) is not None]),
            }
            for value, group in sorted(by_value.items(), key=lambda kv: str(kv[0]))
        }
    return out


def build_report(records: list) -> dict:
    by_type = defaultdict(list)
    for r in records:
        by_type[r["decision_type"]].append(r)

    report = {}
    for dt, recs in by_type.items():
        primitive = recs[0]["primitive_type"]
        n = len(recs)
        block = {
            "n_decisions": n,
            "primitive_type": primitive,
            "n_errors": sum(1 for r in recs if r.get("status") == "error"),
            "n_contract_failures": sum(1 for r in recs if r.get("contract_failure")),
            "accuracy": _mean([1.0 if r["scoring"]["correct"] else 0.0 for r in recs if r["scoring"].get("correct") is not None]),
            "acceptable_match_rate": _mean([1.0 if r["scoring"]["acceptable_match"] else 0.0 for r in recs if r["scoring"].get("acceptable_match") is not None]),
            "calibration_table": calibration_table(recs, _conf, _correct),
            "brier_and_ece": brier_and_ece(recs, _conf, _correct),
            "false_confident": false_confident_rate(recs, _conf, _correct),
            "bootstrap_ci_accuracy": _bootstrap_ci(recs, _correct),
            "automation_coverage": automation_coverage(recs),
            "target_error_coverage": target_error_coverage(recs),
            "slices": slice_by_stratification(recs),
            "efficiency": efficiency_summary(recs),
            "failure_decomposition": failure_source_decomposition(recs),
            "strict_first_attempt_accuracy": strict_first_attempt_accuracy(recs),
            "contract": contract_summary(recs),
            "trivial_baselines": trivial_baselines(recs, dt),
        }
        if primitive == "choice":
            block.update(confusion_and_f1(recs))
            block["candidate_recall"] = candidate_recall_summary(recs)
            block["accuracy_by_candidate_set_size"] = accuracy_by_candidate_set_size(recs)
        if primitive == "noul":
            block["noul_metrics"] = noul_confusion_metrics(recs)
            block["raw_probability_calibration"] = noul_raw_probability_calibration(recs)
        if dt == "causal_change":
            block["recency_analysis"] = causal_change_recency_analysis(recs)
            block["recency_categories"] = causal_change_recency_categories(recs)
        if dt == "owning_team":
            block["owning_team_metrics"] = owning_team_metrics(recs)
        report[dt] = block
    return report
