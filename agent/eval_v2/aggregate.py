"""Case-level CaseEvalRecords -> one experiment's aggregate report. Every
number here is a plain deterministic computation over the records already
produced by metrics.py -- no LLM calls, fixed-seed bootstrap only source of
"randomness" (and that is seeded, so it is reproducible too).
"""
import random
import statistics
from collections import Counter, defaultdict

from agent.eval_v2.config import AUTOMATION_THRESHOLDS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, CONFIDENCE_BUCKETS, FALSE_CONFIDENT_THRESHOLD
from agent.eval_v2.confusion import all_confusion_matrices

OUTCOME_FIELDS = {
    "product": lambda r: r["outcome"]["product"]["correct"],
    "component": lambda r: r["outcome"]["component"]["correct"],
    "issue_category": lambda r: r["outcome"]["category"]["correct"],
    "issue_subcategory": lambda r: r["outcome"]["subcategory"]["correct"],
    "root_cause_exact": lambda r: r["outcome"]["root_cause"]["exact_match"],
    "root_cause_containment": lambda r: r["outcome"]["root_cause"]["containment_match"],
    "causal_change": lambda r: r["outcome"]["causal_change"]["correct"],
    "severity_exact": lambda r: r["outcome"]["severity"]["exact"],
    "severity_within_one": lambda r: r["outcome"]["severity"]["within_one"],
    "team_primary": lambda r: r["outcome"]["team"]["primary_match"],
    "team_acceptable": lambda r: r["outcome"]["team"]["acceptable_match"],
    "evidence_sufficiency": lambda r: r["outcome"]["evidence_sufficiency"]["correct"],
    "human_review_agreement": lambda r: r["outcome"]["human_review"]["agrees_with_reference"],
}

STRATIFICATION_DIMENSIONS = [
    "difficulty_archetype", "issue_category_id", "evidence_sufficiency", "incident_relationship",
    "dependency_driven", "customer_misdiagnosis", "multi_component", "ambiguous", "low_evidence",
    "reopened", "escalated",
]

def _rate(records, get_value):
    vals = [get_value(r) for r in records]
    scored = [v for v in vals if v is not None]
    n_total = len(records)
    n_scored = len(scored)
    n_correct = sum(1 for v in scored if v)
    return {
        "accuracy": (n_correct / n_scored) if n_scored else None,
        "n_correct": n_correct,
        "n_scored": n_scored,
        "n_total": n_total,
        "prediction_rate": (n_scored / n_total) if n_total else None,
    }


def outcome_summary(records) -> dict:
    return {name: _rate(records, fn) for name, fn in OUTCOME_FIELDS.items()}


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def _percentile(vals, pct):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(vals) - 1)
    if f == c:
        return vals[f]
    return vals[f] + (vals[c] - vals[f]) * (k - f)


def slice_summary(records) -> dict:
    """Spec section 3/34/35/36: never report only overall averages."""
    slices = {}
    for dim in STRATIFICATION_DIMENSIONS:
        by_value = defaultdict(list)
        for r in records:
            by_value[r["stratification"].get(dim)].append(r)
        slices[dim] = {
            str(value): {
                "n_cases": len(group),
                "outcome": outcome_summary(group),
                "human_review_rate_agent": _mean([1.0 if g["predictions"].get("human_review_required") else 0.0 for g in group]),
                "mean_overall_confidence": _mean([g["overall_confidence"] for g in group]),
            }
            for value, group in sorted(by_value.items(), key=lambda kv: str(kv[0]))
        }
    return slices


def _confidence_bucket_label(lo, hi):
    return f"{lo:.2f}-{min(hi, 1.0):.2f}"


def calibration_table(records, confidence_fn, correct_fn) -> list:
    rows = []
    for lo, hi in CONFIDENCE_BUCKETS:
        bucket_records = []
        for r in records:
            conf = confidence_fn(r)
            correct = correct_fn(r)
            if conf is None or correct is None:
                continue
            if lo <= conf < hi:
                bucket_records.append((conf, correct))
        n = len(bucket_records)
        rows.append({
            "bucket": _confidence_bucket_label(lo, hi),
            "n_cases": n,
            "mean_predicted_confidence": _mean([c for c, _ in bucket_records]),
            "observed_accuracy": (sum(1 for _, correct in bucket_records if correct) / n) if n else None,
        })
    return rows


def brier_and_ece(records, confidence_fn, correct_fn) -> dict:
    """Binary (chosen-answer) Brier score / ECE -- NOT a full categorical-
    distribution calibration metric (spec section 17's own caution: the
    agent outputs one confidence for its chosen answer, not a full
    probability distribution over all possible answers)."""
    pairs = []
    for r in records:
        conf, correct = confidence_fn(r), correct_fn(r)
        if conf is not None and correct is not None:
            pairs.append((conf, 1.0 if correct else 0.0))
    if not pairs:
        return {"brier_score": None, "ece": None, "n_scored": 0}
    brier = _mean([(c - y) ** 2 for c, y in pairs])
    table = calibration_table(records, confidence_fn, correct_fn)
    n_total = sum(row["n_cases"] for row in table)
    ece = sum(
        (row["n_cases"] / n_total) * abs(row["mean_predicted_confidence"] - row["observed_accuracy"])
        for row in table
        if row["n_cases"] > 0
    ) if n_total else None
    return {"brier_score": brier, "ece": ece, "n_scored": len(pairs), "note": "binary chosen-answer Brier/ECE, not full multiclass calibration"}


def false_confident_rate(records, confidence_fn, correct_fn, threshold=FALSE_CONFIDENT_THRESHOLD) -> dict:
    denom, flagged = 0, 0
    for r in records:
        conf, correct = confidence_fn(r), correct_fn(r)
        if conf is None or correct is None:
            continue
        denom += 1
        if (not correct) and conf >= threshold:
            flagged += 1
    return {"rate": (flagged / denom) if denom else None, "count": flagged, "denominator": denom, "threshold": threshold}


_FIELD_ACCESSORS = {
    "product": (lambda r: r["outcome"]["product"]["confidence"], lambda r: r["outcome"]["product"]["correct"]),
    "component": (lambda r: r["outcome"]["component"]["confidence"], lambda r: r["outcome"]["component"]["correct"]),
    "root_cause": (lambda r: r["outcome"]["root_cause"]["confidence"], lambda r: r["outcome"]["root_cause"]["containment_match"]),
    "causal_change": (lambda r: r["outcome"]["causal_change"]["confidence"], lambda r: r["outcome"]["causal_change"]["correct"]),
    "team": (lambda r: r["outcome"]["team"]["confidence"], lambda r: r["outcome"]["team"]["acceptable_match"]),
    "severity": (lambda r: r["outcome"]["severity"]["confidence"], lambda r: r["outcome"]["severity"]["within_one"]),
    "overall": (lambda r: r["overall_confidence"], lambda r: r["outcome"]["root_cause"]["containment_match"]),
}


def confidence_and_calibration(records) -> dict:
    out = {}
    for field, (conf_fn, correct_fn) in _FIELD_ACCESSORS.items():
        out[field] = {
            "calibration_table": calibration_table(records, conf_fn, correct_fn),
            "brier_and_ece": brier_and_ece(records, conf_fn, correct_fn),
            "false_confident": false_confident_rate(records, conf_fn, correct_fn),
        }
    return out


def false_confident_by_scenario(records) -> dict:
    conf_fn, correct_fn = _FIELD_ACCESSORS["root_cause"]
    scenarios = {
        "insufficient_evidence": [r for r in records if r["stratification"]["low_evidence"]],
        "ambiguous": [r for r in records if r["stratification"]["ambiguous"]],
        "customer_misdiagnosis": [r for r in records if r["stratification"]["customer_misdiagnosis"]],
    }
    return {name: false_confident_rate(group, conf_fn, correct_fn) for name, group in scenarios.items()}


def automation_coverage_simulation(records) -> list:
    """Evaluation-only simulation (spec section 19) -- never changes agent
    behavior. Root-cause containment-match is used as the correctness proxy
    for 'would this automated action have been right.'"""
    total = len(records)
    rows = []
    for threshold in AUTOMATION_THRESHOLDS:
        eligible = [r for r in records if (r["overall_confidence"] or 0) >= threshold]
        below = [r for r in records if (r["overall_confidence"] or 0) < threshold]
        n_eligible = len(eligible)
        correct_among_eligible = sum(1 for r in eligible if r["outcome"]["root_cause"]["containment_match"] is True)
        rows.append({
            "threshold": threshold,
            "pct_eligible": (n_eligible / total) if total else None,
            "n_eligible": n_eligible,
            "accuracy_among_eligible": (correct_among_eligible / n_eligible) if n_eligible else None,
            "wrong_auto_action_rate": ((n_eligible - correct_among_eligible) / n_eligible) if n_eligible else None,
            "human_review_pct_below_threshold": _mean([1.0 if r["predictions"].get("human_review_required") else 0.0 for r in below]),
        })
    return rows


def failure_taxonomy_summary(records) -> dict:
    total = len(records)
    counter = Counter(tag for r in records for tag in r["failure_tags"])
    n_with_any = sum(1 for r in records if r["failure_tags"])
    return {
        "tag_counts": dict(counter.most_common()),
        "tag_rates": {tag: count / total for tag, count in counter.items()} if total else {},
        "pct_cases_with_any_failure_tag": (n_with_any / total) if total else None,
    }


def process_and_contract_summary(records) -> dict:
    total = len(records)
    known_repair = [r for r in records if r["process"]["repair"]["repair_status_known"]]
    clean = [r for r in known_repair if r["process"]["clean_run"]]
    repaired_not_clean = [r for r in known_repair if not r["process"]["clean_run"]]

    def acc(group, fn):
        return _rate(group, fn)

    correct_fn = lambda r: r["outcome"]["root_cause"]["containment_match"]
    return {
        "mean_tool_calls": _mean([r["efficiency"]["num_tool_calls"] for r in records]),
        "p95_tool_calls": _percentile([r["efficiency"]["num_tool_calls"] for r in records], 0.95),
        "redundant_call_rate": _mean([1.0 if r["process"]["tool"]["redundant_calls"] > 0 else 0.0 for r in records]),
        "tool_error_rate": _mean([1.0 if r["process"]["tool"]["tool_errors"] > 0 else 0.0 for r in records]),
        "unknown_tool_call_rate": _mean([1.0 if r["process"]["tool"]["unknown_tool_calls"] > 0 else 0.0 for r in records]),
        "unsupported_evidence_rate": _mean([1.0 if r["process"]["unsupported_evidence_count"] > 0 else 0.0 for r in records]),
        "budget_exhaustion_rate": _mean([1.0 if r["process"]["stop_reason"] == "tool_budget_exhausted" else 0.0 for r in records]),
        "clean_run_rate": (len(clean) / len(known_repair)) if known_repair else None,
        "n_repair_status_unknown": total - len(known_repair),
        "root_cause_accuracy_among_clean_runs": acc(clean, correct_fn),
        "root_cause_accuracy_among_repaired_runs": acc(repaired_not_clean, correct_fn),
        "hypothesis_recovery": {
            "recovered_from_wrong_initial_rate": _mean([
                1.0 if r["process"]["hypothesis_recovery"]["recovered_from_wrong_initial"] else 0.0
                for r in records if r["process"]["hypothesis_recovery"]["recovered_from_wrong_initial"] is not None
            ]),
            "abandoned_correct_hypothesis_rate": _mean([
                1.0 if r["process"]["hypothesis_recovery"]["abandoned_correct_hypothesis"] else 0.0
                for r in records if r["process"]["hypothesis_recovery"]["abandoned_correct_hypothesis"] is not None
            ]),
        },
    }


def efficiency_summary(records) -> dict:
    tokens = [r["efficiency"]["token_usage"].get("total_tokens") for r in records if r["efficiency"].get("token_usage")]
    costs = [r["efficiency"]["approx_cost_usd"] for r in records if r["efficiency"].get("approx_cost_usd") is not None]
    latencies = [r["efficiency"]["total_llm_latency_ms"] for r in records]
    correct_root_cause = [r for r in records if r["outcome"]["root_cause"]["containment_match"] is True]
    return {
        "mean_tokens": _mean(tokens),
        "mean_cost_usd": _mean(costs),
        "total_cost_usd": sum(costs) if costs else 0.0,
        "mean_llm_latency_ms": _mean(latencies),
        "p95_llm_latency_ms": _percentile(latencies, 0.95),
        "cost_per_correct_root_cause_diagnosis": (sum(costs) / len(correct_root_cause)) if costs and correct_root_cause else None,
    }


def _bootstrap_ci(records, correct_fn, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED) -> dict:
    scored = [correct_fn(r) for r in records]
    scored = [v for v in scored if v is not None]
    n = len(scored)
    if n < 5:
        return {"point_estimate": (sum(scored) / n) if n else None, "ci_low": None, "ci_high": None, "n_scored": n, "note": "too few scored cases for a meaningful bootstrap CI"}
    rng = random.Random(seed)
    point = sum(scored) / n
    resample_accs = []
    for _ in range(resamples):
        sample = rng.choices(scored, k=n)
        resample_accs.append(sum(sample) / n)
    resample_accs.sort()
    lo = resample_accs[int(0.025 * resamples)]
    hi = resample_accs[int(0.975 * resamples) - 1]
    return {"point_estimate": point, "ci_low": lo, "ci_high": hi, "n_scored": n, "resamples": resamples}


def bootstrap_confidence_intervals(records) -> dict:
    return {
        "root_cause_containment": _bootstrap_ci(records, lambda r: r["outcome"]["root_cause"]["containment_match"]),
        "component": _bootstrap_ci(records, lambda r: r["outcome"]["component"]["correct"]),
        "team_acceptable": _bootstrap_ci(records, lambda r: r["outcome"]["team"]["acceptable_match"]),
        "issue_category": _bootstrap_ci(records, lambda r: r["outcome"]["category"]["correct"]),
    }


def build_aggregate(records: list) -> dict:
    return {
        "n_cases": len(records),
        "outcome": outcome_summary(records),
        "slices": slice_summary(records),
        "confidence_and_calibration": confidence_and_calibration(records),
        "false_confident_by_scenario": false_confident_by_scenario(records),
        "automation_coverage_simulation": automation_coverage_simulation(records),
        "evidence": {
            "critical_all_retrieved_rate": _mean([
                1.0 if r["evidence"]["critical"]["all_critical_retrieved"] else 0.0
                for r in records if not r["evidence"]["critical"]["no_critical_evidence_exists"]
            ]),
            "critical_all_cited_rate": _mean([
                1.0 if r["evidence"]["critical"]["all_critical_cited"] else 0.0
                for r in records if not r["evidence"]["critical"]["no_critical_evidence_exists"]
            ]),
            "distractor_selected_as_causal_change_rate": _mean([
                1.0 if r["evidence"]["distractor"]["distractor_selected_as_causal_change"] else 0.0 for r in records
            ]),
        },
        "process_and_contract": process_and_contract_summary(records),
        "efficiency": efficiency_summary(records),
        "failure_taxonomy": failure_taxonomy_summary(records),
        "confusion_matrices": all_confusion_matrices(records),
        "bootstrap_confidence_intervals": bootstrap_confidence_intervals(records),
    }
