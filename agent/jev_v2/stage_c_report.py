"""Stage C validation analysis, exactly as pre-registered in
docs/JEV_STAGE_C_PROTOCOL.md. Read-only over stored experiments: no API,
graph or hidden-truth call (it only reads the already-scored records).

Usage:
    python3 -m agent.jev_v2.stage_c_report \
        --jev-val <exp id> --llm-val <exp id> \
        --jev-dev <exp id> --llm-dev <exp id> \
        [--causal-dev <exp id> ...] [--out-dir DIR]

Every definition (groups, failure categories, slice flag, bins, delta labels,
capability rubric) is fixed by the protocol; none is tuned on validation.
"""
import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path

from agent.eval_v2.aggregate import _bootstrap_ci
from agent.jev_v2.aggregate import (
    _percentile,
    automation_coverage,
    build_report,
    causal_change_recency_categories,
    confusion_and_f1,
    owning_team_metrics,
    target_error_coverage,
)
from agent.jev_v2.compare_jev_llm import _key, build_comparison
from agent.jev_v2.config import AUTOMATION_THRESHOLDS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, FALSE_CONFIDENT_THRESHOLD, TARGET_ERROR_RATES
from agent.jev_v2.registry import load_decisions, load_experiment

PRIMITIVES = ["issue_category", "root_cause", "causal_change", "owning_team", "evidence_sufficiency", "incident_relationship"]
LOW_CONFIDENCE = 0.50
SLICE_MIN_N = 30
SLICE_GAP_FLAG = 0.10
Z = 1.96
SUFFICIENCY_ORDER = {"insufficient": 0, "partially_sufficient": 1, "sufficient": 2}


# ── small statistics ────────────────────────────────────────────────────────────
def wilson(k: int, n: int):
    if n == 0:
        return None, None
    p = k / n
    denom = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / denom
    half = Z * sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff(k_dev: int, n_dev: int, k_val: int, n_val: int) -> dict:
    """Validation minus dev, hybrid-score 95% interval for independent proportions."""
    if not n_dev or not n_val:
        return {"diff": None, "ci_low": None, "ci_high": None}
    p1, p2 = k_dev / n_dev, k_val / n_val
    l1, u1 = wilson(k_dev, n_dev)
    l2, u2 = wilson(k_val, n_val)
    d = p2 - p1
    return {"diff": d, "ci_low": d - sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), "ci_high": d + sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)}


def ratio_ci(k_dev: int, n_dev: int, k_val: int, n_val: int, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict:
    """Validation/dev ratio of proportions, seeded parametric bootstrap. Not a model score."""
    if not n_dev or not n_val or k_dev == 0:
        return {"ratio": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    p1, p2 = k_dev / n_dev, k_val / n_val
    ratios = []
    for _ in range(resamples):
        a = sum(rng.random() < p1 for _ in range(n_dev)) / n_dev
        b = sum(rng.random() < p2 for _ in range(n_val)) / n_val
        if a > 0:
            ratios.append(b / a)
    ratios.sort()
    if not ratios:
        return {"ratio": p2 / p1, "ci_low": None, "ci_high": None}
    return {"ratio": p2 / p1, "ci_low": ratios[int(0.025 * len(ratios))], "ci_high": ratios[min(len(ratios) - 1, int(0.975 * len(ratios)))]}


def delta_label(delta: dict, n_dev: int, n_val: int, lower_is_better: bool = False) -> str:
    """Protocol reading of a dev-to-validation difference. For a lower-is-better metric (false-confident
    rate) the direction is inverted: an interval wholly below 0 is an improvement (post-run label fix,
    JEV-029; no number changes)."""
    if delta["diff"] is None or min(n_dev, n_val) < SLICE_MIN_N:
        return "insufficient sample"
    worse, better = ("material degradation", "improvement")
    if lower_is_better:
        worse, better = better, worse
    if delta["ci_high"] < 0:
        return worse
    if delta["ci_low"] > 0:
        return better
    return "plausible sampling variation"


# ── record helpers ────────────────────────────────────────────────────────────────
def _by_type(records: list) -> dict:
    out = defaultdict(list)
    for r in records:
        out[r["decision_type"]].append(r)
    return out


def _kn(records: list, field: str = "correct") -> tuple:
    vals = [r["scoring"].get(field) for r in records if r["scoring"].get(field) is not None]
    return sum(1 for v in vals if v), len(vals)


def _acc_block(records: list, field: str = "correct") -> dict:
    k, n = _kn(records, field)
    ci = _bootstrap_ci(records, lambda r: r["scoring"].get(field))
    return {"k": k, "n": n, "accuracy": (k / n) if n else None, "ci_low": ci.get("ci_low"), "ci_high": ci.get("ci_high")}


def _conf(r):
    return r["scoring"].get("predicted_confidence")


def _false_confident(records: list) -> dict:
    scored = [r for r in records if _conf(r) is not None and r["scoring"].get("correct") is not None]
    flagged = [r for r in scored if not r["scoring"]["correct"] and _conf(r) >= FALSE_CONFIDENT_THRESHOLD]
    lo, hi = wilson(len(flagged), len(scored))
    return {"count": len(flagged), "n": len(scored), "rate": (len(flagged) / len(scored)) if scored else None, "ci_low": lo, "ci_high": hi}


# ── candidate generalization ─────────────────────────────────────────────────────
def candidate_stats(records: list, decision_type: str) -> dict:
    sizes = [len(r.get("candidates") or {}) for r in records if r.get("candidates")]
    out = {
        "n": len(records),
        "avg_candidates": statistics.fmean(sizes) if sizes else None,
        "median_candidates": statistics.median(sizes) if sizes else None,
        "p90_candidates": _percentile(sizes, 0.90),
    }
    if decision_type == "owning_team":
        acceptable_absent = sum(1 for r in records if r["scoring"].get("acceptable_candidate_present") is False)
        primary_absent = sum(1 for r in records if r["scoring"].get("primary_candidate_present") is False)
        out.update({"acceptable_absent": acceptable_absent, "primary_absent": primary_absent,
                    "acceptable_recall": 1 - acceptable_absent / len(records), "primary_recall": 1 - primary_absent / len(records),
                    "recall": 1 - acceptable_absent / len(records)})
    else:
        absent = sum(1 for r in records if r["scoring"].get("candidate_answer_present") is False)
        out.update({"absent": absent, "recall": 1 - absent / len(records)})
    return out


# ── slices ──────────────────────────────────────────────────────────────────────────
def _slice_stats(group: list) -> dict:
    k, n = _kn(group)
    confs = [_conf(r) for r in group if _conf(r) is not None]
    scored = [r for r in group if _conf(r) is not None and r["scoring"].get("correct") is not None]
    hc_wrong = sum(1 for r in scored if not r["scoring"]["correct"] and _conf(r) >= FALSE_CONFIDENT_THRESHOLD)
    acc = (k / n) if n else None
    mean_conf = statistics.fmean(confs) if confs else None
    return {"n": len(group), "accuracy": acc, "mean_confidence": mean_conf, "high_conf_error_rate": (hc_wrong / len(scored)) if scored else None,
            "confidence_minus_accuracy": (mean_conf - acc) if (acc is not None and mean_conf is not None) else None, "small": len(group) < SLICE_MIN_N}


def slices(records: list, dim: str) -> dict:
    groups = defaultdict(list)
    for r in records:
        groups[r["stratification"].get(dim) or "unknown"].append(r)
    out = {name: _slice_stats(g) for name, g in sorted(groups.items())}
    overall = _slice_stats(records)["confidence_minus_accuracy"]
    for name, s in out.items():
        s["flag_confidence_does_not_track_accuracy"] = bool(
            not s["small"] and overall is not None and s["confidence_minus_accuracy"] is not None and s["confidence_minus_accuracy"] - overall >= SLICE_GAP_FLAG)
    return out


def size_bins(records: list) -> dict:
    with_cands = [r for r in records if r.get("candidates")]
    sizes = sorted({len(r["candidates"]) for r in with_cands})
    if len(sizes) <= 1:
        return {"note": "no variation in candidate-set size" if sizes else "no candidate sets", "bins": {}}
    if len(sizes) <= 6:
        edges = {str(s): (s, s) for s in sizes}
    else:
        ordered = sorted(len(r["candidates"]) for r in with_cands)
        cut1, cut2 = ordered[len(ordered) // 3], ordered[2 * len(ordered) // 3]
        edges = {f"<={cut1}": (min(sizes), cut1), f"{cut1 + 1}-{cut2}": (cut1 + 1, cut2), f">{cut2}": (cut2 + 1, max(sizes))}
    bins = {}
    for label, (lo, hi) in edges.items():
        group = [r for r in with_cands if lo <= len(r["candidates"]) <= hi]
        if not group:  # terciles collapse when one size dominates; an empty bin (e.g. "13-12") carries no information
            continue
        present = [r for r in group if r["scoring"].get("candidate_answer_present")]
        bins[label] = {"n": len(group), "accuracy": _acc_block(group)["accuracy"], "conditional_accuracy": _acc_block(present)["accuracy"], "n_present": len(present)}
    if len(bins) == 1:
        return {"note": f"candidate-set size is effectively constant (sizes {sizes[0]}-{sizes[-1]}; one dominant size)", "bins": bins}
    return {"note": None, "bins": bins}


# ── automation ─────────────────────────────────────────────────────────────────────
def automation(records: list) -> dict:
    rows = automation_coverage(records)
    for row in rows:
        row["deferred"] = None if row["coverage"] is None else 1 - row["coverage"]
    targets = target_error_coverage(records)
    scored = sorted((r for r in records if _conf(r) is not None and r["scoring"].get("correct") is not None), key=lambda r: -_conf(r))
    for label, row in targets.items():
        n = row["n"]
        wrong = sum(1 for r in scored[:n] if not r["scoring"]["correct"])
        row["observed_error"] = (wrong / n) if n else None
        row["error_upper_95"] = wilson(wrong, n)[1] if n else None
    return {"thresholds": rows, "target_error": targets}


# ── failure taxonomy ───────────────────────────────────────────────────────────────
def failures(records: list, decision_type: str) -> dict:
    counts = Counter()
    for r in records:
        s = r["scoring"]
        conf = _conf(r)
        if r.get("status") == "error" or r.get("contract_failure"):
            counts["invalid_output_or_api_error"] += 1
            continue
        if decision_type == "incident_relationship":
            truth, pred = s.get("ground_truth_value"), s.get("predicted_value")
            if truth == pred:
                counts["correct_low_confidence" if (conf is not None and conf < LOW_CONFIDENCE) else "correct"] += 1
            elif pred and not truth:
                counts[f"false_attribution__{s.get('incident_relationship', 'none')}"] += 1
                if conf is not None and conf >= FALSE_CONFIDENT_THRESHOLD:
                    counts["wrong_high_confidence"] += 1
            else:
                counts["missed_incident"] += 1
                if conf is not None and conf >= FALSE_CONFIDENT_THRESHOLD:
                    counts["wrong_high_confidence"] += 1
            continue
        present = s.get("candidate_answer_present")
        if present is False:
            counts["candidate_missing"] += 1
            continue
        if s.get("correct"):
            counts["correct_low_confidence" if (conf is not None and conf < LOW_CONFIDENCE) else "correct"] += 1
            continue
        # wrong with the true answer available
        if conf is not None and conf >= FALSE_CONFIDENT_THRESHOLD:
            counts["wrong_high_confidence"] += 1
        else:
            counts["wrong_lower_confidence"] += 1
        if decision_type == "causal_change":
            if s.get("false_positive"):
                counts["causal__false_positive_on_no_change_case"] += 1
            elif s.get("missed"):
                counts["causal__none_chosen_when_true_change_offered"] += 1
            elif s.get("distractor_selected"):
                counts["causal__wrong_real_change_chosen"] += 1
        if decision_type == "evidence_sufficiency":
            truth, pred = SUFFICIENCY_ORDER.get(s.get("ground_truth_value")), SUFFICIENCY_ORDER.get(s.get("predicted_value"))
            if truth is not None and pred is not None:
                counts["evidence__under_called" if pred < truth else "evidence__over_called"] += 1
    return dict(counts)


# ── primitive-specific detail ──────────────────────────────────────────────────────
def confidence_histogram(records: list) -> dict:
    edges = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.0001)]
    confs = [_conf(r) for r in records if _conf(r) is not None]
    return {f"{lo:.1f}-{min(hi, 1.0):.1f}": sum(1 for c in confs if lo <= c < hi) for lo, hi in edges}


def evidence_detail(records: list) -> dict:
    matrix = Counter((r["scoring"]["ground_truth_value"], r["scoring"]["predicted_value"]) for r in records if r["scoring"].get("predicted_value") is not None)
    truths = Counter(r["scoring"]["ground_truth_value"] for r in records)
    per_class = {}
    for label in SUFFICIENCY_ORDER:
        group = [r for r in records if r["scoring"]["ground_truth_value"] == label]
        k, n = _kn(group)
        per_class[label] = {"n": n, "recall": (k / n) if n else None}
    majority_label, majority_n = truths.most_common(1)[0]
    return {"confusion": {f"{t}->{p}": c for (t, p), c in sorted(matrix.items(), key=lambda kv: str(kv[0]))}, "truth_distribution": dict(truths), "per_class_accuracy": per_class,
            "majority_class": majority_label, "majority_baseline_accuracy": majority_n / len(records), "confidence_distribution": confidence_histogram(records)}


def incident_detail(records: list) -> dict:
    scored = [r for r in records if r["scoring"].get("predicted_value") is not None]
    pos = [r for r in scored if r["scoring"]["ground_truth_value"]]
    neg = [r for r in scored if not r["scoring"]["ground_truth_value"]]
    tp = sum(1 for r in pos if r["scoring"]["predicted_value"])
    fp = sum(1 for r in neg if r["scoring"]["predicted_value"])
    by_relationship = {}
    for label in sorted({r["scoring"].get("incident_relationship") for r in scored}):
        group = [r for r in scored if r["scoring"].get("incident_relationship") == label]
        k, n = _kn(group)
        wrong_pos = sum(1 for r in group if r["scoring"]["predicted_value"] and not r["scoring"]["ground_truth_value"])
        by_relationship[str(label)] = {"n": n, "accuracy": (k / n) if n else None, "predicted_related": sum(1 for r in group if r["scoring"]["predicted_value"]), "false_attributions": wrong_pos}
    pairs = [(r["scoring"]["raw_probability_for_true"], r["scoring"]["ground_truth_value"]) for r in scored if r["scoring"].get("raw_probability_for_true") is not None]
    from agent.jev_v2.compare_jev_llm import auc

    return {"eligible_decisions": len(records), "scored": len(scored), "true_related": len(pos), "not_related": len(neg),
            "true_positive_rate": (tp / len(pos)) if pos else None, "false_positive_rate": (fp / len(neg)) if neg else None,
            "false_attribution_count": fp, "missed_incident_count": len(pos) - tp, "tp": tp, "fp": fp, "auc_raw_probability": auc(pairs),
            "by_true_relationship": by_relationship, "majority_baseline_never_related": (len(neg) / len(scored)) if scored else None}


def primitive_block(records: list, decision_type: str) -> dict:
    """Everything reported per Jev primitive on validation."""
    block = build_report(records)[decision_type]
    out = {
        "n_decisions": len(records), "accuracy": _acc_block(records), "macro_f1": block.get("macro_f1"), "per_class": block.get("per_class", {}),
        "brier": block["brier_and_ece"]["brier_score"], "ece": block["brier_and_ece"]["ece"], "calibration_table": block["calibration_table"],
        "false_confident": _false_confident(records), "automation": automation(records), "trivial_baselines": block["trivial_baselines"],
        "contract": block["contract"], "efficiency": block["efficiency"],
        "slices_by_archetype": slices(records, "difficulty_archetype"), "failures": failures(records, decision_type),
        "confidence_histogram": confidence_histogram(records),
    }
    if decision_type != "incident_relationship":
        out["candidates"] = candidate_stats(records, decision_type)
        present = [r for r in records if r["scoring"].get("candidate_answer_present")]
        out["conditional_accuracy"] = _acc_block(present)
    if decision_type in ("issue_category", "root_cause", "causal_change", "owning_team"):
        out["slices_by_evidence_sufficiency"] = slices(records, "evidence_sufficiency")
    if decision_type in ("root_cause", "causal_change", "owning_team"):
        out["accuracy_by_candidate_set_size"] = size_bins(records)
    if decision_type == "owning_team":
        primary_present = [r for r in records if r["scoring"].get("primary_candidate_present")]
        acceptable_present = [r for r in records if r["scoring"].get("acceptable_candidate_present")]
        out["team"] = {"primary": _acc_block(records, "correct"), "acceptable": _acc_block(records, "acceptable_match"),
                       "conditional_primary": _acc_block(primary_present, "correct"), "conditional_acceptable": _acc_block(acceptable_present, "acceptable_match"),
                       "metrics": owning_team_metrics(records)}
    if decision_type == "causal_change":
        cats = causal_change_recency_categories(records)
        out["recency"] = cats
        out["recency_detail"] = _recency_detail(records)
        out["causal"] = {"false_positive_rate_no_change": cats["false_positive_rate_when_no_causal_change"], "distractor_selection_rate_when_offered": cats["distractor_selection_rate_when_a_distractor_was_offered"],
                         "no_change_accuracy": cats["no_causal_change_accuracy"]}
    if decision_type == "evidence_sufficiency":
        out["evidence"] = evidence_detail(records)
    if decision_type == "incident_relationship":
        out["incident"] = incident_detail(records)
    return out


def _recency_detail(records: list) -> dict:
    """Per group: n, accuracy, conditional accuracy, high-confidence errors, newest-change selection rate."""
    def group_of(r):
        s, meta = r["scoring"], r.get("candidate_meta") or {}
        starts = meta.get("change_started_ats") or {}
        truth = s.get("ground_truth_value")
        if truth == "none":
            return "C"
        if truth in starts:
            truth_ts = starts[truth] or ""
            return "B" if any((ts or "") > truth_ts for cid, ts in starts.items() if cid != truth) else "A"
        return "E"

    out = {}
    for name in ("A", "B", "C", "E"):
        group = [r for r in records if group_of(r) == name]
        offered = [r for r in group if r["scoring"].get("candidate_answer_present")]
        scored = [r for r in group if _conf(r) is not None and r["scoring"].get("correct") is not None]
        out[name] = {"n": len(group), "accuracy": _acc_block(group)["accuracy"], "conditional_accuracy": _acc_block(offered)["accuracy"],
                     "high_confidence_errors": sum(1 for r in scored if not r["scoring"]["correct"] and _conf(r) >= FALSE_CONFIDENT_THRESHOLD),
                     "newest_change_selection_rate": statistics.fmean([1.0 if r["scoring"].get("selected_is_newest_change") else 0.0 for r in group]) if group else None}
    multi = [r for r in records if (r.get("candidate_meta") or {}).get("num_real_change_candidates", 0) >= 2]
    scored = [r for r in multi if _conf(r) is not None and r["scoring"].get("correct") is not None]
    out["D"] = {"n": len(multi), "accuracy": _acc_block(multi)["accuracy"], "conditional_accuracy": _acc_block([r for r in multi if r["scoring"].get("candidate_answer_present")])["accuracy"],
                "high_confidence_errors": sum(1 for r in scored if not r["scoring"]["correct"] and _conf(r) >= FALSE_CONFIDENT_THRESHOLD),
                "newest_change_selection_rate": statistics.fmean([1.0 if r["scoring"].get("selected_is_newest_change") else 0.0 for r in multi]) if multi else None,
                "by_true_group": {name: sum(1 for r in multi if group_of(r) == name) for name in ("A", "B", "C", "E")}}
    return out


# ── generalization (dev vs validation) ─────────────────────────────────────────────
def _row(label: str, dev_kn: tuple, val_kn: tuple, extra: dict = None, lower_is_better: bool = False) -> dict:
    (kd, nd), (kv, nv) = dev_kn, val_kn
    delta = newcombe_diff(kd, nd, kv, nv)
    return {"metric": label, "dev": {"k": kd, "n": nd, "rate": (kd / nd) if nd else None}, "validation": {"k": kv, "n": nv, "rate": (kv / nv) if nv else None},
            "delta": delta, "ratio": ratio_ci(kd, nd, kv, nv), "label": delta_label(delta, nd, nv, lower_is_better), **(extra or {})}


def generalization(dev: dict, val: dict, primitives: list = None) -> list:
    primitives = primitives or PRIMITIVES
    rows = []
    for dt, field, label in (("issue_category", "correct", "Issue category accuracy"), ("root_cause", "correct", "Root cause accuracy"), ("causal_change", "correct", "Causal change accuracy"),
                             ("owning_team", "correct", "Owning team primary accuracy"), ("owning_team", "acceptable_match", "Owning team acceptable accuracy"),
                             ("evidence_sufficiency", "correct", "Evidence sufficiency accuracy"), ("incident_relationship", "correct", "Incident relationship accuracy")):
        if dt in primitives:
            rows.append(_row(label, _kn(dev[dt], field), _kn(val[dt], field)))
    # candidate recall (absent counts) and false-confident
    for dt, label in (("root_cause", "Root cause candidate recall"), ("causal_change", "Causal change candidate recall")):
        if dt not in primitives:
            continue
        dn, vn = len(dev[dt]), len(val[dt])
        rows.append(_row(label, (dn - sum(1 for r in dev[dt] if r["scoring"].get("candidate_answer_present") is False), dn), (vn - sum(1 for r in val[dt] if r["scoring"].get("candidate_answer_present") is False), vn)))
    for field, label in (("primary_candidate_present", "Owning team primary candidate recall"), ("acceptable_candidate_present", "Owning team acceptable candidate recall")):
        if "owning_team" not in primitives:
            continue
        dn, vn = len(dev["owning_team"]), len(val["owning_team"])
        rows.append(_row(label, (sum(1 for r in dev["owning_team"] if r["scoring"].get(field)), dn), (sum(1 for r in val["owning_team"] if r["scoring"].get(field)), vn)))
    for dt in primitives:
        fd, fv = _false_confident(dev[dt]), _false_confident(val[dt])
        rows.append(_row(f"{dt} false-confident rate (lower is better)", (fd["count"], fd["n"]), (fv["count"], fv["n"]), lower_is_better=True))
    return rows


# ── capability rubric (pre-registered) ─────────────────────────────────────────────
def classify(primitives: dict, gen_rows: list, val: dict, scope: list = None) -> dict:
    by_metric = {r["metric"]: r for r in gen_rows}
    headline = {"issue_category": "Issue category accuracy", "root_cause": "Root cause accuracy", "causal_change": "Causal change accuracy",
                "owning_team": "Owning team primary accuracy", "evidence_sufficiency": "Evidence sufficiency accuracy", "incident_relationship": "Incident relationship accuracy"}
    recall_metric = {"root_cause": "Root cause candidate recall", "causal_change": "Causal change candidate recall", "owning_team": "Owning team acceptable candidate recall"}
    out = {}
    for dt in (scope or PRIMITIVES):
        block = primitives[dt]
        acc = block["team"]["primary"] if dt == "owning_team" else block["accuracy"]
        tb = block["trivial_baselines"]
        baseline = max(tb.get("majority_class_accuracy") or 0.0, tb.get("newest_change_else_none_accuracy") or 0.0)
        if dt == "incident_relationship":
            baseline = block["incident"]["majority_baseline_never_related"] or 0.0
        n_ok = len(val[dt]) >= 100 and (dt != "incident_relationship" or block["incident"]["true_related"] >= 20)
        t1 = acc["ci_low"] is not None and acc["ci_low"] > baseline
        row = by_metric[headline[dt]]
        t2a = row["label"] != "material degradation"
        recall_ok = True
        if dt in recall_metric:
            recall_ok = (by_metric[recall_metric[dt]]["validation"]["rate"] or 0.0) >= 0.95
        t2 = t2a and recall_ok
        fc = block["false_confident"]["rate"]
        t3 = acc["accuracy"] is not None and acc["accuracy"] >= 0.85 and fc is not None and fc <= 0.05
        if not n_ok:
            cls = "insufficient sample"
        elif not t1:
            cls = "weak / deprioritize"
        elif t1 and t2 and t3:
            cls = "candidate for locked benchmark"
        else:
            cls = "supporting-only"
        out[dt] = {"class": cls, "T1_beats_baseline": t1, "T2_generalizes": t2, "T2_no_material_degradation": t2a, "T2_candidate_recall_ge_0.95": recall_ok,
                   "T3_strong": t3, "T4_adequate_sample": n_ok, "accuracy": acc["accuracy"], "accuracy_ci": [acc["ci_low"], acc["ci_high"]],
                   "baseline_accuracy": baseline, "false_confident_rate": fc, "dev_to_validation_label": row["label"]}
    return out


# ── Jev vs LLM ─────────────────────────────────────────────────────────────────────
def jev_vs_llm(jev_val: list, llm_val: list) -> dict:
    comparison = build_comparison(jev_val, llm_val)
    for dt, c in comparison.items():
        for side, recs in (("jev", [r for r in jev_val if r["decision_type"] == dt]), ("llm", [r for r in llm_val if r["decision_type"] == dt])):
            lat = [r["latency_ms"] for r in recs if r.get("latency_ms") is not None]
            c[side]["p90_latency_ms"] = _percentile(lat, 0.90)
            c[side]["first_attempt_failure_kinds"] = c[side]["contract"].get("first_attempt_failure_kinds")
            if side == "llm":
                confs = [_conf(r) for r in recs if _conf(r) is not None]
                c[side]["confidence_distinct_values"] = len({round(x, 3) for x in confs})
                c[side]["confidence_mean"] = statistics.fmean(confs) if confs else None
    return comparison


def ranking_generalization(dev_cmp: dict, val_cmp: dict, scope: list = None) -> list:
    rows = []
    for dt in (scope or PRIMITIVES):
        d, v = dev_cmp.get(dt), val_cmp.get(dt)
        if not d or not v:
            continue
        dd, vd = d["paired"]["jev_minus_llm_accuracy_ci"], v["paired"]["jev_minus_llm_accuracy_ci"]
        def sign(x):
            return "Jev ahead" if x["ci_low"] is not None and x["ci_low"] > 0 else "LLM ahead" if x["ci_high"] is not None and x["ci_high"] < 0 else "no clear difference"
        rows.append({"decision": dt, "dev_diff": dd, "dev_reading": sign(dd), "val_diff": vd, "val_reading": sign(vd), "same_reading": sign(dd) == sign(vd), "val_mcnemar_p": v["paired"]["mcnemar_exact_p"]})
    return rows


def build(val_jev: list, val_llm: list, dev_jev: list, dev_llm: list, dev_causal: dict, scope: list = None) -> dict:
    """`val_*` is the run being evaluated and `dev_*` the reference it is compared with (dev for Stage C; validation
    for the locked benchmark). `scope` restricts the primitives analysed (default: all six)."""
    scope = scope or PRIMITIVES
    val, dev = _by_type(val_jev), _by_type(dev_jev)
    primitives = {dt: primitive_block(val[dt], dt) for dt in scope}
    dev_primitives = {dt: primitive_block(dev[dt], dt) for dt in scope}
    gen = generalization(dev, val, scope)
    val_cmp = jev_vs_llm([r for r in val_jev if r["decision_type"] in scope], [r for r in val_llm if r["decision_type"] in scope])
    dev_cmp = jev_vs_llm([r for r in dev_jev if r["decision_type"] in scope], [r for r in dev_llm if r["decision_type"] in scope])
    causal_dev_runs = {label: {"k_n": _kn([r for r in recs if r["decision_type"] == "causal_change"]), } for label, recs in dev_causal.items()}
    return {"primitives": primitives, "dev_primitives": dev_primitives, "generalization": gen, "classification": classify(primitives, gen, val, scope),
            "jev_vs_llm": val_cmp, "dev_jev_vs_llm": dev_cmp, "ranking_generalization": ranking_generalization(dev_cmp, val_cmp, scope), "causal_dev_runs": causal_dev_runs,
            "llm_validation": {dt: primitive_block([r for r in val_llm if r["decision_type"] == dt], dt) for dt in scope}}


# ── rendering ────────────────────────────────────────────────────────────────────────
def _p(x, nd=1):
    return f"{x * 100:.{nd}f}%" if x is not None else "n/a"


def _pp(x):
    return f"{x * 100:+.1f}" if x is not None else "n/a"


DEFAULT_LABELS = {"title": "Stage C validation report (machine-generated tables)", "cur": "validation", "ref": "dev", "Cur": "Validation", "Ref": "Dev", "cur_s": "val", "Cur_s": "Val"}


def render(report: dict, meta: dict, labels: dict = None) -> str:
    """`labels` renames the two sides (Stage C: dev -> validation; locked benchmark: validation -> locked test)."""
    lb = labels or DEFAULT_LABELS
    cur, ref, Cur, Ref = lb["cur"], lb["ref"], lb["Cur"], lb["Ref"]
    cur_s, Cur_s = lb["cur_s"], lb["Cur_s"]
    scope = list(report["primitives"])
    L = [f"# {lb['title']}", "",
         f"- Jev {cur}: `{meta['jev_val']}`", f"- LLM {cur}: `{meta['llm_val']}`", f"- {ref} references: Jev `{meta['jev_dev']}`, LLM `{meta['llm_dev']}`",
         f"- {cur} cases: {meta['n_cases']}; protocol sha256 `{meta.get('protocol_sha256')}`", ""]
    # B. candidate generalization
    L += ["## Candidate generalization", "", f"| Decision | Recall {ref} | Recall {cur} | Avg cands {ref} / {cur_s} | Median / P90 {cur_s} | Absent ({cur_s}) |", "|---|---:|---:|---:|---:|---:|"]
    dev_p, val_p = report["dev_primitives"], report["primitives"]
    for dt in [x for x in ("issue_category", "root_cause", "causal_change", "owning_team") if x in scope]:
        d, v = dev_p[dt]["candidates"], val_p[dt]["candidates"]
        rd = d.get("acceptable_recall", d["recall"]); rv = v.get("acceptable_recall", v["recall"])
        absent = v.get("acceptable_absent", v.get("absent"))
        name = dt + (" (acceptable)" if dt == "owning_team" else "")
        L.append(f"| {name} | {_p(rd)} | {_p(rv)} | {d['avg_candidates']:.1f} / {v['avg_candidates']:.1f} | {v['median_candidates']} / {v['p90_candidates']} | {absent} of {v['n']} |")
    if "owning_team" in scope:
        t = val_p["owning_team"]["candidates"]
        L += ["", f"Owning team primary recall: {cur} {_p(t['primary_recall'])} ({t['primary_absent']} absent).", ""]
    # C. generalization table
    L += [f"## {Ref} versus {cur}", "", f"| Metric | {Ref} | {Cur} | Delta (pts) [95% CI] | {Cur_s}/{ref} ratio [95% CI] | Reading |", "|---|---:|---:|---:|---:|---|"]
    for r in report["generalization"]:
        d, v, dl, ra = r["dev"], r["validation"], r["delta"], r["ratio"]
        rr = f"{ra['ratio']:.2f} [{ra['ci_low']:.2f}, {ra['ci_high']:.2f}]" if ra.get("ci_low") is not None else (f"{ra['ratio']:.2f}" if ra.get("ratio") is not None else "n/a")
        L.append(f"| {r['metric']} | {_p(d['rate'])} ({d['k']}/{d['n']}) | {_p(v['rate'])} ({v['k']}/{v['n']}) | {_pp(dl['diff'])} [{_pp(dl['ci_low'])}, {_pp(dl['ci_high'])}] | {rr} | {r['label']} |")
    L.append("")
    # per primitive
    for dt in scope:
        b = val_p[dt]
        acc = b["accuracy"]
        L += [f"## {dt}", "", f"- n = {b['n_decisions']}; accuracy {_p(acc['accuracy'])} [{_p(acc['ci_low'])}, {_p(acc['ci_high'])}]; macro F1 {b['macro_f1'] if b['macro_f1'] is None else round(b['macro_f1'], 3)}",
              f"- trivial baselines: {b['trivial_baselines']}", f"- Brier {b['brier']:.3f}, ECE {b['ece']:.3f}; false-confident {b['false_confident']['count']}/{b['false_confident']['n']} ({_p(b['false_confident']['rate'])})" if b["brier"] is not None else "- calibration n/a",
              f"- contract: {b['contract']}", f"- failure categories: {b['failures']}"]
        if "conditional_accuracy" in b:
            ca = b["conditional_accuracy"]
            L.append(f"- conditional accuracy (true answer offered): {_p(ca['accuracy'])} [{_p(ca['ci_low'])}, {_p(ca['ci_high'])}] (n={ca['n']})")
        if dt == "owning_team":
            tm = b["team"]
            L.append("- " + "; ".join(f"{k} {_p(tm[k]['accuracy'])} [{_p(tm[k]['ci_low'])}, {_p(tm[k]['ci_high'])}] (n={tm[k]['n']})" for k in ("primary", "acceptable", "conditional_primary", "conditional_acceptable")))
        if dt == "evidence_sufficiency":
            e = b["evidence"]
            L += [f"- truth distribution {e['truth_distribution']}; majority baseline {_p(e['majority_baseline_accuracy'])} ({e['majority_class']})", f"- per-class accuracy {e['per_class_accuracy']}", f"- confusion {e['confusion']}", f"- confidence distribution {e['confidence_distribution']}"]
        if dt == "incident_relationship":
            i = b["incident"]
            L += [f"- eligible decisions {i['eligible_decisions']}; true-related {i['true_related']}, not related {i['not_related']}; TPR {_p(i['true_positive_rate'])}, FPR {_p(i['false_positive_rate'])}; false attributions {i['false_attribution_count']}, missed {i['missed_incident_count']}; AUC {i['auc_raw_probability']}",
                  f"- by true relationship: {i['by_true_relationship']}"]
        if dt == "causal_change":
            rd = b["recency_detail"]
            L += ["", "| Group | n | Accuracy | Conditional accuracy | High-conf errors | Newest-change selection |", "|---|---:|---:|---:|---:|---:|"]
            for name, label in (("A", "A true is newest"), ("B", "B true older than a newer distractor"), ("C", "C no causal change"), ("D", "D multiple recent changes"), ("E", "E true change not offered")):
                g = rd[name]
                L.append(f"| {label} | {g['n']} | {_p(g['accuracy'])} | {_p(g['conditional_accuracy'])} | {g['high_confidence_errors']} | {_p(g['newest_change_selection_rate'])} |")
            L += ["", f"- false-positive rate on no-change cases {_p(b['causal']['false_positive_rate_no_change'])}; distractor-selection rate when a distractor was offered {_p(b['causal']['distractor_selection_rate_when_offered'])}"]
        if "accuracy_by_candidate_set_size" in b:
            sb = b["accuracy_by_candidate_set_size"]
            L.append(f"- accuracy by candidate-set size: {sb['note'] or {k: (v['n'], _p(v['accuracy']), _p(v['conditional_accuracy'])) for k, v in sb['bins'].items()}}")
        L += ["", "Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):", ""]
        for name, s in b["slices_by_archetype"].items():
            L.append(f"- {name}: n={s['n']}{' (small)' if s['small'] else ''}, acc {_p(s['accuracy'])}, conf {_p(s['mean_confidence'])}, hc-err {_p(s['high_conf_error_rate'])}" + (" **FLAG: confidence does not track accuracy**" if s["flag_confidence_does_not_track_accuracy"] else ""))
        if "slices_by_evidence_sufficiency" in b:
            L += ["", "Evidence-quality slices:", ""]
            for name, s in b["slices_by_evidence_sufficiency"].items():
                L.append(f"- {name}: n={s['n']}{' (small)' if s['small'] else ''}, acc {_p(s['accuracy'])}, conf {_p(s['mean_confidence'])}, hc-err {_p(s['high_conf_error_rate'])}")
        au = b["automation"]
        L += ["", "| Threshold | Automated | Accuracy automated | Error | Deferred |", "|---|---:|---:|---:|---:|"]
        for row in au["thresholds"]:
            L.append(f"| >= {row['threshold']} | {_p(row['coverage'])} ({row['n_eligible']}) | {_p(row['accuracy_among_eligible'])} | {_p(row['error_rate'])} | {_p(row['deferred'])} |")
        L += ["", "| Target error | Max coverage | Decisions | Observed error | Upper 95% error |", "|---|---:|---:|---:|---:|"]
        for tgt, row in au["target_error"].items():
            L.append(f"| <= {float(tgt) * 100:.0f}% | {_p(row['max_coverage_at_or_below_target'])} | {row['n']} | {_p(row['observed_error'])} | {_p(row['error_upper_95'])} |")
        L.append("")
    # E. Jev vs LLM
    L += [f"## Jev vs LLM ({cur})", "", "| Decision | Jev acc | LLM acc | Jev minus LLM (paired CI) | McNemar p | Jev P50/P90/P95 ms | LLM P50/P90/P95 ms | $/1k Jev | $/1k LLM | LLM first-attempt valid |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for dt in scope:
        c = report["jev_vs_llm"].get(dt)
        if not c:
            continue
        j, l, ci = c["jev"], c["llm"], c["paired"]["jev_minus_llm_accuracy_ci"]
        L.append(f"| {dt} | {_p(j['as_scored_accuracy'])} | {_p(l['as_scored_accuracy'])} | {_pp(ci['diff'])} [{_pp(ci['ci_low'])}, {_pp(ci['ci_high'])}] | {c['paired']['mcnemar_exact_p']:.3f} | {j['p50_latency_ms']:.0f}/{j['p90_latency_ms']:.0f}/{j['p95_latency_ms']:.0f} | {l['p50_latency_ms']:.0f}/{l['p90_latency_ms']:.0f}/{l['p95_latency_ms']:.0f} | {j['cost_per_1000_decisions_usd']:.3f} | {l['cost_per_1000_decisions_usd']:.3f} | {l['contract']['first_attempt_valid']}/{l['contract']['n_decisions']} |")
    L += ["", "Does the ranking generalize?", "", f"| Decision | {Ref} Jev minus LLM | {Ref} reading | {Cur} Jev minus LLM | {Cur} reading | Same reading |", "|---|---:|---|---:|---|---|"]
    for r in report["ranking_generalization"]:
        d, v = r["dev_diff"], r["val_diff"]
        L.append(f"| {r['decision']} | {_pp(d['diff'])} [{_pp(d['ci_low'])}, {_pp(d['ci_high'])}] | {r['dev_reading']} | {_pp(v['diff'])} [{_pp(v['ci_low'])}, {_pp(v['ci_high'])}] | {r['val_reading']} | {r['same_reading']} |")
    L += ["", "## Capability classification (pre-registered rubric)", "", "| Primitive | Class | T1 beats baseline | T2 generalizes | T3 strong | T4 sample | Accuracy [CI] | Baseline | False-confident |", "|---|---|---|---|---|---|---:|---:|---:|"]
    for dt, c in report["classification"].items():
        L.append(f"| {dt} | **{c['class']}** | {c['T1_beats_baseline']} | {c['T2_generalizes']} | {c['T3_strong']} | {c['T4_adequate_sample']} | {_p(c['accuracy'])} [{_p(c['accuracy_ci'][0])}, {_p(c['accuracy_ci'][1])}] | {_p(c['baseline_accuracy'])} | {_p(c['false_confident_rate'])} |")
    return "\n".join(L) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jev-val", required=True)
    parser.add_argument("--llm-val", required=True)
    parser.add_argument("--jev-dev", required=True)
    parser.add_argument("--llm-dev", required=True)
    parser.add_argument("--causal-dev", action="append", default=[])
    parser.add_argument("--out-dir", help="Default: the Jev validation experiment's folder")
    args = parser.parse_args()

    jev_val_exp = load_experiment(args.jev_val)
    report = build(load_decisions(args.jev_val), load_decisions(args.llm_val), load_decisions(args.jev_dev), load_decisions(args.llm_dev), {e: load_decisions(e) for e in args.causal_dev})
    meta = {"jev_val": args.jev_val, "llm_val": args.llm_val, "jev_dev": args.jev_dev, "llm_dev": args.llm_dev, "n_cases": jev_val_exp["num_cases"],
            "protocol_sha256": (jev_val_exp["config"].get("pre_registered_protocol") or {}).get("sha256")}
    out_dir = Path(args.out_dir) if args.out_dir else Path("data/experiments") / args.jev_val
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage_c_report.json").write_text(json.dumps({"meta": meta, "report": report}, indent=2, default=str))
    (out_dir / "stage_c_report.md").write_text(render(report, meta))
    print(out_dir / "stage_c_report.md")
    for dt, c in report["classification"].items():
        print(f"  {dt}: {c['class']}")


if __name__ == "__main__":
    main()
