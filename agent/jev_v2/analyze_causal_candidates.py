"""Offline (no Jev/LLM call) candidate-recall measurement for causal change:
candidate_generation_v2 vs candidate_generation_v3 on the exact Stage B v2
development cohort (JEV-013).

Truth is read only through scoring.py (the one module allowed to), after the
candidate sets are built from observable data. Also records two structural
properties of the candidate sets that affect how the result should be read:
whether the numeric change-id range or "a deployment is visible" separates the
true cause from the distractors (a synthetic-data artifact, not a hidden-field
leak -- see docs/JEV_EVALUATION.md).

Usage:
    python3 -m agent.jev_v2.analyze_causal_candidates \
        --baseline-experiment-id exp_stage_b_dev_100_v2_20260923T083737Z_8eabb9a5
"""
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from agent.eval_v2.splits import case_ids_for_split
from agent.graph_v2.db import get_driver
from agent.jev_v2 import candidates as candidates_mod
from agent.jev_v2.aggregate import _percentile
from agent.jev_v2.registry import load_decisions, load_experiment
from agent.jev_v2.scoring import score_decision
from agent.jev_v2.state_builder import get_case_context

OUT_DIR = Path("data/eval/jev/analysis")


def _summarize(rows: list) -> dict:
    n = len(rows)
    counts = [r["n_candidates"] for r in rows]
    real = [r["n_real"] for r in rows]
    misses = [r["case_id"] for r in rows if not r["candidate_answer_present"]]
    return {
        "n": n,
        "candidate_recall": (n - len(misses)) / n,
        "n_missing_true_candidate": len(misses),
        "cases_missing_true_candidate": misses,
        "avg_candidate_count_incl_none": statistics.fmean(counts),
        "median_candidate_count_incl_none": statistics.median(counts),
        "p90_candidate_count_incl_none": _percentile(counts, 0.90),
        "avg_real_candidates": statistics.fmean(real),
        "cases_with_zero_real_candidates": sum(1 for x in real if x == 0),
        "cases_with_deployment_candidate": sum(1 for r in rows if r["n_deployment"] > 0),
        "share_with_deployment_candidate": sum(1 for r in rows if r["n_deployment"] > 0) / n,
        "cases_with_duplicate_suppression": sum(1 for r in rows if r["duplicates_suppressed"] > 0),
        "duplicates_suppressed_total": sum(r["duplicates_suppressed"] for r in rows),
        "future_events_dropped_total": sum(r["future_events_dropped"] for r in rows),
    }


def _id_number(candidate_id: str) -> int:
    return int("".join(ch for ch in candidate_id if ch.isdigit()) or 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-experiment-id", required=True, help="Stage B v2 experiment whose exact case ids and stored v2 candidates are the baseline")
    args = parser.parse_args()

    baseline = load_experiment(args.baseline_experiment_id)
    case_ids = baseline["case_ids"]
    if case_ids != case_ids_for_split("dev")[: len(case_ids)]:
        raise SystemExit("baseline cohort is not the leading slice of the dev split -- refusing to analyse")
    stored = {r["case_id"]: r for r in load_decisions(args.baseline_experiment_id) if r["decision_type"] == "causal_change"}

    per_version = {"v2": [], "v3": []}
    reproduces_stored_v2 = 0
    id_rows = []
    driver = get_driver()
    try:
        with driver.session() as session:
            for case_id in case_ids:
                as_of = get_case_context(session, case_id)["created_date"]
                for version in ("v2", "v3"):
                    cands, meta = candidates_mod.causal_change_candidates(session, case_id, as_of, version=version)
                    scored = score_decision({
                        "status": "ok", "case_id": case_id, "decision_type": "causal_change", "primitive_type": "choice",
                        "candidates": cands, "candidate_meta": meta, "answer": {},
                    })["scoring"]
                    per_version[version].append({
                        "case_id": case_id, "candidate_answer_present": bool(scored["candidate_answer_present"]),
                        "n_candidates": len(cands), "n_real": meta["num_real_change_candidates"],
                        "n_deployment": meta.get("num_deployment_candidates", 0),
                        "duplicates_suppressed": meta.get("duplicates_suppressed", 0),
                        "future_events_dropped": meta.get("future_events_dropped", 0),
                        "truth": scored["ground_truth_value"],
                    })
                    if version == "v2" and list(cands) == list(stored[case_id]["candidates"]):
                        reproduces_stored_v2 += 1
                    if version == "v3":
                        id_rows.append({"truth": scored["ground_truth_value"], "candidate_ids": [k for k in cands if k != "none"], "event_types": meta["event_types"]})
    finally:
        driver.close()

    v2, v3 = _summarize(per_version["v2"]), _summarize(per_version["v3"])
    still_missing = v3["cases_missing_true_candidate"]

    true_ids = [_id_number(r["truth"]) for r in id_rows if r["truth"] != "none"]
    other_ids = [_id_number(cid) for r in id_rows for cid in r["candidate_ids"] if cid != r["truth"]]
    boundary = min(true_ids) if true_ids else None
    dep_cases = [r for r in id_rows if any(t == "deployment" for t in r["event_types"].values())]
    dep_truth_cases = [r for r in dep_cases if r["event_types"].get(r["truth"]) == "deployment"]
    result = {
        "cohort": {"baseline_experiment_id": args.baseline_experiment_id, "n_cases": len(case_ids), "split": "dev"},
        "v2_reproduces_stored_stage_b_v2_candidate_keys": f"{reproduces_stored_v2}/{len(case_ids)}",
        "candidate_generation_v2": v2,
        "candidate_generation_v3": v3,
        "remaining_ceiling_v3": {
            "cases_still_missing_true_candidate": still_missing,
            "note": "empty means every true causal change is observably represented at T0" if not still_missing else "these cases have no observable representation of the true event under v3",
        },
        "structural_artifacts_v3": {
            "true_causal_change_id_number_range": [min(true_ids), max(true_ids)] if true_ids else None,
            "non_true_candidate_id_number_range": [min(other_ids), max(other_ids)] if other_ids else None,
            "id_number_separates_true_from_non_true_perfectly": bool(true_ids and other_ids and boundary > max(other_ids)),
            "cases_with_visible_deployment": len(dep_cases),
            "of_which_deployment_is_the_true_cause": len(dep_truth_cases),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = OUT_DIR / "causal_change_candidates_v2_vs_v3_dev100"
    stem.with_suffix(".json").write_text(json.dumps(result, indent=2))

    def pct(x):
        return f"{x * 100:.1f}%"

    lines = [
        "# Causal-change candidate generation: v2 vs v3 (dev-100, no Jev call)", "",
        f"- cohort: `{args.baseline_experiment_id}` ({len(case_ids)} dev cases, same ordered ids)",
        f"- v2 reproduces the stored Stage B v2 candidate keys for {reproduces_stored_v2}/{len(case_ids)} cases", "",
        "| Metric | v2 | v3 |", "|---|---:|---:|",
        f"| Candidate recall | {pct(v2['candidate_recall'])} | {pct(v3['candidate_recall'])} |",
        f"| Cases with no true candidate | {v2['n_missing_true_candidate']} | {v3['n_missing_true_candidate']} |",
        f"| Avg candidates (incl. `none`) | {v2['avg_candidate_count_incl_none']:.2f} | {v3['avg_candidate_count_incl_none']:.2f} |",
        f"| Median candidates | {v2['median_candidate_count_incl_none']} | {v3['median_candidate_count_incl_none']} |",
        f"| P90 candidates | {v2['p90_candidate_count_incl_none']} | {v3['p90_candidate_count_incl_none']} |",
        f"| Avg real (non-`none`) candidates | {v2['avg_real_candidates']:.2f} | {v3['avg_real_candidates']:.2f} |",
        f"| Cases with zero real candidates | {v2['cases_with_zero_real_candidates']} | {v3['cases_with_zero_real_candidates']} |",
        f"| Cases with a deployment-type candidate | {v2['cases_with_deployment_candidate']} ({pct(v2['share_with_deployment_candidate'])}) | {v3['cases_with_deployment_candidate']} ({pct(v3['share_with_deployment_candidate'])}) |",
        f"| Cases with duplicate suppression | n/a | {v3['cases_with_duplicate_suppression']} (total suppressed {v3['duplicates_suppressed_total']}) |",
        f"| Future events dropped by the defensive gate | n/a | {v3['future_events_dropped_total']} |", "",
        f"v2 misses: {', '.join(v2['cases_missing_true_candidate']) or 'none'}", "",
        f"v3 misses: {', '.join(v3['cases_missing_true_candidate']) or 'none'}", "",
        "## Structural properties of the v3 candidate sets (read before interpreting Jev's accuracy)", "",
        f"- true causal-change id numbers span {result['structural_artifacts_v3']['true_causal_change_id_number_range']}; every other visible candidate spans {result['structural_artifacts_v3']['non_true_candidate_id_number_range']}. "
        f"The id number alone separates them perfectly: {result['structural_artifacts_v3']['id_number_separates_true_from_non_true_perfectly']}.",
        f"- {len(dep_cases)} cases have a visible deployment; in {len(dep_truth_cases)} of them that deployment is the true cause.", "",
        "These are properties of how the synthetic data was generated, observable in the candidate ids, not hidden fields. "
        "They mean a system could in principle exploit the id number; the opaque-key control run measures whether Jev/the LLM do.", "",
    ]
    stem.with_suffix(".md").write_text("\n".join(lines))
    print(json.dumps({"v2": {k: v for k, v in v2.items() if k != 'cases_missing_true_candidate'}, "v3": {k: v for k, v in v3.items() if k != 'cases_missing_true_candidate'}, "v3_missing": still_missing, "v2_missing": v2["cases_missing_true_candidate"], "reproduces_v2": result["v2_reproduces_stored_stage_b_v2_candidate_keys"], "artifacts": result["structural_artifacts_v3"]}, indent=1))
    print("wrote", stem.with_suffix(".md"))


if __name__ == "__main__":
    main()
