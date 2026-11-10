"""Post-hoc, read-only comparison of two stored causal-change experiments on
the same ordered dev cases (JEV-013: candidate_generation v2 vs v3; also used
for the canonical-vs-opaque-key diagnostic control).

Re-aggregates both sides in memory with the CURRENT evaluator so they are
measured identically; never writes to either source experiment and makes no
API or graph calls. The rendered comparison is written next to side B.
"""
import argparse
import json
from pathlib import Path

from agent.jev_v2.aggregate import build_report
from agent.jev_v2.paired_stats import mcnemar_exact_p, paired_bootstrap_diff
from agent.jev_v2.registry import load_decisions, load_experiment


def _pct(x):
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _num(x, fmt="{:.2f}"):
    return fmt.format(x) if x is not None else "n/a"


def _causal(records):
    return [r for r in records if r["decision_type"] == "causal_change"]


def compare(exp_a: dict, recs_a: list, exp_b: dict, recs_b: list, label_a: str, label_b: str) -> tuple:
    recs_a, recs_b = _causal(recs_a), _causal(recs_b)
    a, b = build_report(recs_a)["causal_change"], build_report(recs_b)["causal_change"]
    by_case_a, by_case_b = {r["case_id"]: r for r in recs_a}, {r["case_id"]: r for r in recs_b}
    cases = [c for c in exp_a["case_ids"] if c in by_case_a and c in by_case_b]

    def rate_fc(block):
        return (block["false_confident"] or {}).get("rate")

    rows = [
        ("Candidate recall", _pct(a["candidate_recall"]["candidate_recall"]), _pct(b["candidate_recall"]["candidate_recall"])),
        ("Cases with no true candidate", a["failure_decomposition"]["candidate_missing"], b["failure_decomposition"]["candidate_missing"]),
        ("Avg candidates (incl. `none`)", _num(a["candidate_recall"]["avg_candidate_count"]), _num(b["candidate_recall"]["avg_candidate_count"])),
        ("Median / P90 candidates", f"{a['candidate_recall']['median_candidate_count']} / {a['candidate_recall']['p90_candidate_count']}", f"{b['candidate_recall']['median_candidate_count']} / {b['candidate_recall']['p90_candidate_count']}"),
        ("End-to-end accuracy", _pct(a["accuracy"]), _pct(b["accuracy"])),
        ("Conditional accuracy (true change offered)", _pct(a["candidate_recall"]["conditional_accuracy_given_present"]), _pct(b["candidate_recall"]["conditional_accuracy_given_present"])),
        ("Macro F1", _num(a.get("macro_f1"), "{:.3f}"), _num(b.get("macro_f1"), "{:.3f}")),
        ("False-confident rate (wrong at conf >= 0.90)", f"{_pct(rate_fc(a))} ({a['false_confident']['count']})", f"{_pct(rate_fc(b))} ({b['false_confident']['count']})"),
        ("No-causal-change accuracy", _pct(a["recency_categories"]["no_causal_change_accuracy"]), _pct(b["recency_categories"]["no_causal_change_accuracy"])),
        ("Distractor-selection rate (all decisions)", _pct(a["recency_categories"]["distractor_selection_rate_all_decisions"]), _pct(b["recency_categories"]["distractor_selection_rate_all_decisions"])),
        ("Distractor-selection rate (a distractor was offered)", f"{_pct(a['recency_categories']['distractor_selection_rate_when_a_distractor_was_offered'])} (n={a['recency_categories']['n_decisions_with_a_distractor_offered']})", f"{_pct(b['recency_categories']['distractor_selection_rate_when_a_distractor_was_offered'])} (n={b['recency_categories']['n_decisions_with_a_distractor_offered']})"),
        ("Latency P50 / P95 (ms)", f"{_num(a['efficiency']['p50_latency_ms'], '{:.0f}')} / {_num(a['efficiency']['p95_latency_ms'], '{:.0f}')}", f"{_num(b['efficiency']['p50_latency_ms'], '{:.0f}')} / {_num(b['efficiency']['p95_latency_ms'], '{:.0f}')}"),
        ("Mean input tokens", _num(a["efficiency"]["mean_input_tokens"], "{:.0f}"), _num(b["efficiency"]["mean_input_tokens"], "{:.0f}")),
        ("Cost per 1,000 decisions (USD)", _num(a["efficiency"]["cost_per_1000_decisions_usd"], "{:.4f}"), _num(b["efficiency"]["cost_per_1000_decisions_usd"], "{:.4f}")),
    ]
    tb = b["trivial_baselines"]
    lines = [
        f"# Causal change: {label_a} vs {label_b}", "",
        f"- {label_a}: `{exp_a['experiment_id']}`", f"- {label_b}: `{exp_b['experiment_id']}`",
        f"- {len(cases)} identical ordered dev cases; both sides re-aggregated with evaluator {exp_b['evaluator_version']} (stored files untouched).",
        f"- trivial baselines on these cases: always `none` = {_pct(tb['majority_class_accuracy'])}; newest-change-else-none = {_pct(tb['newest_change_else_none_accuracy'])}", "",
        f"| Metric | {label_a} | {label_b} |", "|---|---:|---:|",
    ] + [f"| {m} | {x} | {y} |" for m, x, y in rows] + ["", "## Recency and distractor groups", "",
        "A = true change is the newest candidate; B = true change is older than at least one distractor; C = no causal change; "
        "D = two or more real change candidates were offered (overlaps A/B/C); E = the true change was not offered at all.", "",
        f"| Group | {label_a} n | {label_a} accuracy | {label_b} n | {label_b} accuracy |", "|---|---:|---:|---:|---:|"]
    for key in ("A", "B", "C", "D_multiple_recent_changes", "E"):
        ga, gb = a["recency_categories"][key], b["recency_categories"][key]
        lines.append(f"| {ga['label']} | {ga['n']} | {_pct(ga['accuracy'])} | {gb['n']} | {_pct(gb['accuracy'])} |")
    lines.append("")
    if b["recency_categories"]["B"]["n"] == 0:
        lines += ["**Group B is empty**: no case in this cohort has a visible true cause older than a visible distractor, so this run cannot test recency-vs-causality.", ""]

    # paired flips
    flips_fixed, flips_broken, same_inputs, same_answer, diff_answer_same_inputs = [], [], 0, 0, []
    a_flags, b_flags = [], []
    for c in cases:
        ra, rb = by_case_a[c], by_case_b[c]
        ca, cb = ra["scoring"].get("correct"), rb["scoring"].get("correct")
        a_flags.append(1 if ca else 0)
        b_flags.append(1 if cb else 0)
        if ca is False and cb is True:
            flips_fixed.append(c)
        if ca is True and cb is False:
            flips_broken.append(c)
        if ra["candidates"] == rb["candidates"] and ra["state"] == rb["state"]:
            same_inputs += 1
            if ra["scoring"]["predicted_value"] == rb["scoring"]["predicted_value"]:
                same_answer += 1
            else:
                diff_answer_same_inputs.append(c)
    lines += ["## Paired outcome changes", "",
              f"- wrong under {label_a}, right under {label_b}: {len(flips_fixed)} ({', '.join(flips_fixed) or 'none'})",
              f"- right under {label_a}, wrong under {label_b}: {len(flips_broken)} ({', '.join(flips_broken) or 'none'})",
              f"- exact McNemar p on those discordant pairs: {mcnemar_exact_p(len(flips_broken), len(flips_fixed)):.3f}",
              f"- paired accuracy difference ({label_b} minus {label_a}): {json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in paired_bootstrap_diff(b_flags, a_flags).items()})}", "",
              "## Same inputs, same model: how repeatable is Jev?", "",
              f"- {same_inputs} of {len(cases)} cases had byte-identical state and candidate sets on both sides; Jev gave the same answer on {same_answer} of them"
              + (f" (differed on {', '.join(diff_answer_same_inputs)})." if diff_answer_same_inputs else "."),
              "- Differences on those cases are Jev run-to-run variability, not a candidate-set effect.", ""]

    # cases whose candidate sets changed
    changed = [c for c in cases if by_case_a[c]["candidates"] != by_case_b[c]["candidates"]]
    lines += [f"## The {len(changed)} cases whose candidate set differs", "", f"| case | truth | {label_a} predicted | {label_b} predicted | {label_b} confidence | {label_b} correct |", "|---|---|---|---|---:|---|"]
    for c in changed:
        sa, sb = by_case_a[c]["scoring"], by_case_b[c]["scoring"]
        lines.append(f"| {c} | {sb['ground_truth_value']} | {sa['predicted_value']} | {sb['predicted_value']} | {_num(sb['predicted_confidence'])} | {sb['correct']} |")
    lines.append("")
    payload = {"label_a": label_a, "label_b": label_b, "a": a, "b": b, "fixed": flips_fixed, "broken": flips_broken,
               "same_inputs": same_inputs, "same_answer_on_same_inputs": same_answer, "changed_candidate_cases": changed}
    return "\n".join(lines), payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True, help="baseline experiment id")
    parser.add_argument("--b", required=True, help="comparison experiment id (report is written into its folder)")
    parser.add_argument("--label-a", default="v2")
    parser.add_argument("--label-b", default="v3")
    args = parser.parse_args()
    exp_a, exp_b = load_experiment(args.a), load_experiment(args.b)
    if exp_a["case_ids"] != exp_b["case_ids"]:
        parser.error("experiments must contain exactly the same ordered case IDs")
    md, payload = compare(exp_a, load_decisions(args.a), exp_b, load_decisions(args.b), args.label_a, args.label_b)
    out = Path("data/experiments") / args.b
    (out / f"comparison_vs_{args.a}.md").write_text(md + "\n", encoding="utf-8")
    (out / f"comparison_vs_{args.a}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
