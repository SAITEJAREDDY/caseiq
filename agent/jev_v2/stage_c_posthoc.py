"""Stage C post-hoc descriptive analysis (NOT pre-registered).

Everything here is computed from already-stored, already-scored decision
records: no Jev/LLM call, no graph access, no hidden-truth read beyond the
fields scoring.py wrote into each record. Nothing here feeds the pre-registered
capability classification; it exists to explain the pre-registered numbers and
to give issue-log entries reproducible evidence. Every table is labelled
post-hoc in the output.

Usage:
    python3 -m agent.jev_v2.stage_c_posthoc \
        --jev-val <exp id> --llm-val <exp id> --jev-dev <exp id> --llm-dev <exp id> [--out-dir DIR]
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

from agent.jev_v2.aggregate import _percentile, decision_cost_usd
from agent.jev_v2.registry import load_decisions
from agent.jev_v2.stage_c_report import wilson

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "experiments"


def _by(records, dt):
    return [r for r in records if r["decision_type"] == dt]


def _rate(k, n):
    return None if not n else k / n


def causal_split(records: list) -> dict:
    """Accuracy split by whether a true causal change exists, from the stored truth."""
    recs = _by(records, "causal_change")
    exists = [r for r in recs if r["scoring"]["ground_truth_value"] != "none"]
    absent = [r for r in recs if r["scoring"]["ground_truth_value"] == "none"]
    ok = lambda rs: sum(1 for r in rs if r["scoring"]["correct"])
    predicted_none = lambda rs: sum(1 for r in rs if r["scoring"]["predicted_value"] == "none")
    lo, hi = wilson(ok(exists), len(exists))
    return {
        "n": len(recs),
        "change_exists": {"n": len(exists), "correct": ok(exists), "accuracy": _rate(ok(exists), len(exists)), "wilson_ci": [lo, hi],
                          "answered_none": predicted_none(exists), "answered_none_rate": _rate(predicted_none(exists), len(exists)),
                          "wrong_real_change": sum(1 for r in exists if not r["scoring"]["correct"] and r["scoring"]["predicted_value"] != "none")},
        "no_change": {"n": len(absent), "correct": ok(absent), "accuracy": _rate(ok(absent), len(absent)),
                      "false_positive": len(absent) - ok(absent), "false_positive_rate": _rate(len(absent) - ok(absent), len(absent))},
    }


def group_b_detail(records: list) -> list:
    """Every case where the true change was visible and strictly older than another visible candidate."""
    out = []
    for r in _by(records, "causal_change"):
        s, truth = r["scoring"], r["scoring"]["ground_truth_value"]
        starts = s.get("change_started_ats") or {}
        if truth != "none" and truth in starts and any((ts or "") > (starts[truth] or "") for cid, ts in starts.items() if cid != truth):
            out.append({"case_id": r["case_id"], "true": truth, "predicted": s["predicted_value"], "confidence": s["predicted_confidence"],
                        "n_real_candidates": len(starts), "correct": bool(s["correct"])})
    return out


def id_artifact_check(records: list) -> dict:
    """JEV-025 evidence on this split: does the change-id number, or 'a deployment is offered', separate the true cause?
    Reads only the stored candidate metadata and the stored true id."""
    num = lambda cid: int(re.sub(r"\D", "", cid)) if re.sub(r"\D", "", cid) else None
    true_ids, other_ids = [], []
    dep_cases = dep_true = 0
    for r in _by(records, "causal_change"):
        truth = r["scoring"]["ground_truth_value"]
        meta = r.get("candidate_meta") or {}
        events = meta.get("candidate_events") or {}
        real = [c for c in (r.get("candidates") or {}) if c != "none"]
        if truth != "none" and truth in real:
            n = num(truth)
            if n is not None:
                true_ids.append(n)
        for c in real:
            if c != truth and num(c) is not None:
                other_ids.append(num(c))
        dep_ids = [c for c, e in events.items() if (e or {}).get("event_type") == "deployment" or (e or {}).get("deployment")]
        if dep_ids:
            dep_cases += 1
            dep_true += 1 if truth in dep_ids else 0
    span = lambda xs: [min(xs), max(xs)] if xs else None
    overlap = None
    if true_ids and other_ids:
        lo, hi = min(true_ids), max(true_ids)
        overlap = sum(1 for x in other_ids if lo <= x <= hi)
    return {"true_id_range": span(true_ids), "n_true": len(true_ids), "non_true_id_range": span(other_ids), "n_non_true": len(other_ids),
            "non_true_ids_inside_true_range": overlap,
            "cases_with_visible_deployment_candidate": dep_cases, "of_which_true_cause_is_that_deployment": dep_true}


def root_cause_detail(records: list) -> dict:
    recs = _by(records, "root_cause")
    out = {"n": len(recs)}
    quality = defaultdict(list)
    for r in recs:
        quality[(r.get("stratification") or {}).get("evidence_sufficiency")].append(r)
    out["by_evidence_quality"] = {}
    for q, rs in sorted(quality.items(), key=lambda kv: str(kv[0])):
        confs = [r["scoring"]["predicted_confidence"] for r in rs if r["scoring"]["predicted_confidence"] is not None]
        out["by_evidence_quality"][str(q)] = {
            "n": len(rs), "accuracy": _rate(sum(1 for r in rs if r["scoring"]["correct"]), len(rs)),
            "mean_confidence": sum(confs) / len(confs) if confs else None,
            "true_is_RC40": sum(1 for r in rs if r["scoring"]["ground_truth_value"] == "RC40"),
            "predicted_RC40": sum(1 for r in rs if r["scoring"]["predicted_value"] == "RC40"),
            "true_answer_offered": sum(1 for r in rs if r["scoring"]["candidate_answer_present"])}
    out["predicted_RC40"] = sum(1 for r in recs if r["scoring"]["predicted_value"] == "RC40")
    out["true_RC40"] = sum(1 for r in recs if r["scoring"]["ground_truth_value"] == "RC40")
    out["absent_true_answers"] = dict(Counter(r["scoring"]["ground_truth_value"] for r in recs if not r["scoring"]["candidate_answer_present"]))
    out["top_predicted"] = Counter(r["scoring"]["predicted_value"] for r in recs).most_common(5)
    out["top_true"] = Counter(r["scoring"]["ground_truth_value"] for r in recs).most_common(5)
    return out


def sufficiency_predictions(records: list) -> dict:
    recs = _by(records, "evidence_sufficiency")
    pred = Counter(r["scoring"]["predicted_value"] for r in recs)
    by_truth = defaultdict(Counter)
    for r in recs:
        by_truth[r["scoring"]["ground_truth_value"]][r["scoring"]["predicted_value"]] += 1
    return {"n": len(recs), "predicted_distribution": dict(pred), "by_truth": {k: dict(v) for k, v in by_truth.items()}}


def mcnemar_exact(only_a: int, only_b: int) -> float:
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def incident_detail(jev: list, llm: list) -> dict:
    j, l = _by(jev, "incident_relationship"), _by(llm, "incident_relationship")
    cases = Counter(r["case_id"] for r in j)
    related = [r for r in j if r["scoring"]["ground_truth_value"] is True]
    related_cases = {r["case_id"] for r in related}
    hc_wrong = [r for r in j if not r["scoring"]["correct"] and (r["scoring"]["predicted_confidence"] or 0) >= 0.90]
    lk = {(r["case_id"], r.get("incident_id")): r for r in l}
    only_j = only_l = 0
    for r in j:
        m = lk.get((r["case_id"], r.get("incident_id")))
        if m is None:
            continue
        a, b = bool(r["scoring"]["correct"]), bool(m["scoring"]["correct"])
        only_j += a and not b
        only_l += b and not a
    return {"n_decisions": len(j), "n_distinct_cases": len(cases), "decisions_per_case": dict(Counter(cases.values())),
            "true_related": len(related), "true_related_distinct_cases": len(related_cases),
            "jev_true_positives": sum(1 for r in related if r["scoring"]["predicted_value"] is True),
            "llm_true_positives": sum(1 for r in l if r["scoring"]["ground_truth_value"] is True and r["scoring"]["predicted_value"] is True),
            "jev_high_confidence_errors": len(hc_wrong),
            "jev_high_confidence_errors_that_are_missed_related": sum(1 for r in hc_wrong if r["scoring"]["ground_truth_value"] is True),
            "discordant_only_jev": only_j, "discordant_only_llm": only_l, "mcnemar_exact_p": mcnemar_exact(only_j, only_l)}


def confidence_vs_chosen_probability(records: list) -> dict:
    """How does Jev's `confidence` field relate to the probability of the option it chose? Descriptive only: the
    API does not document the field here and no definition is inferred."""
    n = equal = below = above = 0
    for r in records:
        a = r.get("answer") or {}
        probs, conf, choice = a.get("probabilities"), a.get("confidence"), a.get("choice")
        if a.get("type") != "choice" or not isinstance(probs, dict) or conf is None or choice not in probs:
            continue
        n += 1
        d = conf - probs[choice]
        if abs(d) <= 0.02:
            equal += 1
        elif d < 0:
            below += 1
        else:
            above += 1
    return {"n_choice_answers": n, "confidence_within_0.02_of_chosen_probability": equal, "confidence_lower": below, "confidence_higher": above}


def causal_nontrivial(records: list) -> dict:
    """Decisions where at least one real change was offered (`none` is not the only option), with two rule baselines."""
    recs = _by(records, "causal_change")
    real = lambda r: (r.get("candidate_meta") or {}).get("num_real_change_candidates", 0)
    non = [r for r in recs if real(r) >= 1]
    ok = sum(1 for r in non if r["scoring"]["correct"])
    lo, hi = wilson(ok, len(non))
    always_none = sum(1 for r in non if r["scoring"]["ground_truth_value"] == "none")
    newest = sum(1 for r in non if r["scoring"]["ground_truth_value"] == (r.get("candidate_meta") or {}).get("newest_change_id"))
    hc = [r for r in recs if (r["scoring"]["predicted_confidence"] or 0) >= 0.90]
    return {"n_all": len(recs), "n_only_none_offered": len(recs) - len(non), "n_nontrivial": len(non), "correct_nontrivial": ok,
            "accuracy_nontrivial": _rate(ok, len(non)), "wilson_ci": [lo, hi],
            "baseline_always_none_nontrivial": _rate(always_none, len(non)), "baseline_newest_change_nontrivial": _rate(newest, len(non)),
            "confidence_ge_0.90": {"n": len(hc), "chose_none": sum(1 for r in hc if r["scoring"]["predicted_value"] == "none"),
                                   "chose_real_change": sum(1 for r in hc if r["scoring"]["predicted_value"] != "none"),
                                   "wrong": sum(1 for r in hc if not r["scoring"]["correct"]),
                                   "only_none_offered": sum(1 for r in hc if real(r) == 0)}}


def root_cause_commitment(records: list) -> dict:
    """RC40 is the taxonomy's 'insufficient information' option. The true answer is never RC40 in the scored data,
    so every RC40 answer scores wrong; this separates abstention from committed wrong answers."""
    recs = _by(records, "root_cause")
    committed = [r for r in recs if r["scoring"]["predicted_value"] != "RC40"]
    ok = sum(1 for r in committed if r["scoring"]["correct"])
    lo, hi = wilson(ok, len(committed))
    return {"n": len(recs), "true_answer_is_RC40": sum(1 for r in recs if r["scoring"]["ground_truth_value"] == "RC40"),
            "answered_RC40": len(recs) - len(committed), "answered_RC40_share": _rate(len(recs) - len(committed), len(recs)),
            "committed_n": len(committed), "committed_accuracy": _rate(ok, len(committed)), "committed_wilson_ci": [lo, hi]}


def run_totals(jev: list, llm: list) -> dict:
    out = {}
    for name, recs in (("jev", jev), ("llm", llm)):
        costs = [decision_cost_usd(r) for r in recs]
        lat = [r["latency_ms"] for r in recs if r.get("latency_ms") is not None]
        out[name] = {"decisions": len(recs), "total_cost_usd": sum(c for c in costs if c is not None),
                     "latency_ms": {"p50": _percentile(lat, 0.50), "p90": _percentile(lat, 0.90), "p95": _percentile(lat, 0.95)}}
    return out


def build(jev_val, llm_val, jev_dev, llm_dev) -> dict:
    return {
        "label": "post-hoc, not pre-registered; never used for the capability classification",
        "causal_split": {"jev_validation": causal_split(jev_val), "llm_validation": causal_split(llm_val),
                         "jev_dev": causal_split(jev_dev), "llm_dev": causal_split(llm_dev)},
        "group_b_validation": {"jev": group_b_detail(jev_val), "llm": group_b_detail(llm_val)},
        "id_artifact_validation": id_artifact_check(jev_val),
        "id_artifact_dev": id_artifact_check(jev_dev),
        "root_cause_jev_validation": root_cause_detail(jev_val),
        "root_cause_llm_validation": root_cause_detail(llm_val),
        "root_cause_accuracy_dev_vs_validation": {
            name: {"dev": _rate(sum(1 for r in _by(d, "root_cause") if r["scoring"]["correct"]), len(_by(d, "root_cause"))),
                   "validation": _rate(sum(1 for r in _by(v, "root_cause") if r["scoring"]["correct"]), len(_by(v, "root_cause")))}
            for name, d, v in (("jev", jev_dev, jev_val), ("llm", llm_dev, llm_val))},
        "evidence_sufficiency_predictions": {"jev": sufficiency_predictions(jev_val), "llm": sufficiency_predictions(llm_val)},
        "incident_relationship": incident_detail(jev_val, llm_val),
        "jev_confidence_vs_chosen_probability": confidence_vs_chosen_probability(jev_val),
        "causal_nontrivial": {"jev_validation": causal_nontrivial(jev_val), "llm_validation": causal_nontrivial(llm_val),
                              "jev_dev": causal_nontrivial(jev_dev), "llm_dev": causal_nontrivial(llm_dev)},
        "root_cause_commitment": {"jev_validation": root_cause_commitment(jev_val), "llm_validation": root_cause_commitment(llm_val),
                                  "jev_dev": root_cause_commitment(jev_dev), "llm_dev": root_cause_commitment(llm_dev)},
        "run_totals_validation": run_totals(jev_val, llm_val),
    }


def to_markdown(r: dict) -> str:
    L = ["# Stage C post-hoc analysis", "", f"*{r['label']}.*", ""]
    cs = r["causal_split"]
    L += ["## Causal change split by whether a true change exists", "",
          "| System / split | True change exists: n | accuracy [Wilson 95%] | answered `none` | No change: n | accuracy | false positives |", "|---|---:|---:|---:|---:|---:|---:|"]
    for k, label in (("jev_validation", "Jev validation"), ("llm_validation", "LLM validation"), ("jev_dev", "Jev dev-100"), ("llm_dev", "LLM dev-100")):
        c = cs[k]
        e, nc = c["change_exists"], c["no_change"]
        L.append(f"| {label} | {e['n']} | {e['accuracy']:.1%} [{e['wilson_ci'][0]:.1%}, {e['wilson_ci'][1]:.1%}] | {e['answered_none']} ({e['answered_none_rate']:.1%}) | {nc['n']} | {nc['accuracy']:.1%} | {nc['false_positive']} |")
    L += ["", "## Group B cases on validation (true change older than a visible candidate)", ""]
    for who in ("jev", "llm"):
        L.append(f"- {who}: {json.dumps(r['group_b_validation'][who])}")
    L += ["", "## Change-id artifact (JEV-025) on validation versus dev", "",
          f"- validation: {json.dumps(r['id_artifact_validation'])}", f"- dev-100: {json.dumps(r['id_artifact_dev'])}", ""]
    L += ["## Root cause (Jev, validation)", "", f"```\n{json.dumps(r['root_cause_jev_validation'], indent=1)}\n```", "",
          f"Root cause accuracy dev vs validation: {json.dumps(r['root_cause_accuracy_dev_vs_validation'])}", ""]
    L += ["## Evidence sufficiency predicted classes", "", f"```\n{json.dumps(r['evidence_sufficiency_predictions'], indent=1)}\n```", ""]
    L += ["## Incident relationship structure", "", f"```\n{json.dumps(r['incident_relationship'], indent=1)}\n```", ""]
    L += ["## Causal change on non-trivial decisions (a real change was offered)", "", f"```\n{json.dumps(r['causal_nontrivial'], indent=1)}\n```", ""]
    L += ["## Root cause: abstention (RC40) versus committed answers", "", f"```\n{json.dumps(r['root_cause_commitment'], indent=1)}\n```", ""]
    L += ["## Jev `confidence` versus the chosen option's probability (descriptive)", "", f"{json.dumps(r['jev_confidence_vs_chosen_probability'])}", ""]
    L += ["## Run totals (validation)", "", f"```\n{json.dumps(r['run_totals_validation'], indent=1)}\n```", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    for a in ("--jev-val", "--llm-val", "--jev-dev", "--llm-dev"):
        ap.add_argument(a, required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    report = build(load_decisions(args.jev_val), load_decisions(args.llm_val), load_decisions(args.jev_dev), load_decisions(args.llm_dev))
    out_dir = Path(args.out_dir) if args.out_dir else EXPERIMENTS_DIR / args.jev_val
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stage_c_posthoc.json").write_text(json.dumps(report, indent=2, default=str))
    (out_dir / "stage_c_posthoc.md").write_text(to_markdown(report))
    print(out_dir / "stage_c_posthoc.md")


if __name__ == "__main__":
    main()
