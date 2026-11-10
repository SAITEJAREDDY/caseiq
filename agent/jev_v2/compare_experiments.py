"""Immutable, post-hoc comparison of two stored Jev primitive experiments.

The comparison re-aggregates stored records in memory only.  It never writes
to either source experiment and does not make any API or graph calls.
"""
import argparse
from pathlib import Path

from agent.jev_v2.aggregate import build_report
from agent.jev_v2.registry import load_decisions, load_experiment


def _pct(value):
    return f"{value * 100:.1f}%" if value is not None else "n/a"


def _choice_values(block):
    candidate = block.get("candidate_recall") or {}
    return {
        "candidate recall": _pct(candidate.get("candidate_recall")),
        "avg candidates": f"{candidate.get('avg_candidate_count'):.1f}" if candidate.get("avg_candidate_count") is not None else "n/a",
        "median / P90 candidates": f"{candidate.get('median_candidate_count')} / {candidate.get('p90_candidate_count')}",
        "conditional accuracy": _pct(candidate.get("conditional_accuracy_given_present")),
        "end-to-end accuracy": _pct(candidate.get("end_to_end_accuracy")),
        "macro F1": f"{block.get('macro_f1'):.3f}" if block.get("macro_f1") is not None else "n/a",
        "false-confident rate": _pct((block.get("false_confident") or {}).get("rate")),
    }


def _table(lines, title, left, right):
    lines.extend([f"## {title}", "", "| Metric | v1 | v2 |", "|---|---:|---:|"])
    for key in left:
        lines.append(f"| {key} | {left[key]} | {right.get(key, 'n/a')} |")
    lines.append("")


def render_comparison(v1_experiment: dict, v1_records: list, v2_experiment: dict, v2_records: list) -> str:
    v1 = build_report(v1_records)
    v2 = build_report(v2_records)
    lines = ["# Stage B v1 vs v2", "", f"- v1: `{v1_experiment['experiment_id']}`", f"- v2: `{v2_experiment['experiment_id']}`", "- Both experiments use the same ordered development case IDs; v1 source records remain unchanged.", ""]

    for decision_type in ("root_cause", "owning_team"):
        _table(lines, decision_type, _choice_values(v1[decision_type]), _choice_values(v2[decision_type]))
        fd1, fd2 = v1[decision_type]["failure_decomposition"], v2[decision_type]["failure_decomposition"]
        lines.extend([
            "Failure-source decomposition:", "",
            "| Source | v1 | v2 |", "|---|---:|---:|",
            f"| Candidate missing | {fd1['candidate_missing']} | {fd2['candidate_missing']} |",
            f"| Candidate present / Jev wrong | {fd1['candidate_present_jev_wrong']} | {fd2['candidate_present_jev_wrong']} |",
            f"| Candidate present / Jev correct | {fd1['candidate_present_jev_correct']} | {fd2['candidate_present_jev_correct']} |",
            f"| Jev wrong with high confidence | {fd1['jev_wrong_high_confidence']} | {fd2['jev_wrong_high_confidence']} |", "",
        ])
        if decision_type == "owning_team":
            t1, t2 = v1[decision_type]["owning_team_metrics"], v2[decision_type]["owning_team_metrics"]
            _table(lines, "owning-team primary and acceptable routing", {
                "primary candidate recall": _pct(t1["primary_candidate_recall"]), "acceptable candidate recall": _pct(t1["acceptable_candidate_recall"]),
                "primary accuracy": _pct(t1["primary_accuracy"]), "acceptable accuracy": _pct(t1["acceptable_accuracy"]),
                "conditional primary accuracy": _pct(t1["conditional_primary_accuracy"]), "conditional acceptable accuracy": _pct(t1["conditional_acceptable_accuracy"]),
            }, {
                "primary candidate recall": _pct(t2["primary_candidate_recall"]), "acceptable candidate recall": _pct(t2["acceptable_candidate_recall"]),
                "primary accuracy": _pct(t2["primary_accuracy"]), "acceptable accuracy": _pct(t2["acceptable_accuracy"]),
                "conditional primary accuracy": _pct(t2["conditional_primary_accuracy"]), "conditional acceptable accuracy": _pct(t2["conditional_acceptable_accuracy"]),
            })

    lines.extend(["## Evidence sufficiency", "", "| Metric | v1 | v2 |", "|---|---:|---:|", f"| Accuracy | {_pct(v1['evidence_sufficiency']['accuracy'])} | {_pct(v2['evidence_sufficiency']['accuracy'])} |", f"| Question version | evidence_sufficiency_v1 | evidence_sufficiency_v2 |", "", "v2 uses a time-gated observable telemetry summary and a versioned operational definition; the v1 2% score is retained as a measurement of its earlier, semantically incomplete state projection.", ""])

    lines.extend(["## Unchanged primitives", "", "| Decision | v1 accuracy | v2 accuracy |", "|---|---:|---:|"])
    for decision_type in ("issue_category", "causal_change", "incident_relationship"):
        lines.append(f"| {decision_type} | {_pct(v1[decision_type]['accuracy'])} | {_pct(v2[decision_type]['accuracy'])} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v1", required=True)
    parser.add_argument("--v2", required=True)
    args = parser.parse_args()
    v1_exp, v2_exp = load_experiment(args.v1), load_experiment(args.v2)
    if v1_exp.get("case_ids") != v2_exp.get("case_ids"):
        parser.error("experiments must contain exactly the same ordered case IDs")
    output = render_comparison(v1_exp, load_decisions(args.v1), v2_exp, load_decisions(args.v2))
    output_path = Path("data/experiments") / args.v2 / f"comparison_vs_{args.v1}.md"
    output_path.write_text(output + "\n", encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
