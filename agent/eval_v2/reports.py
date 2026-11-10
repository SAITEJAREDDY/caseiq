"""Aggregate dict -> human-readable Markdown report (spec section 41). Only
reports measured numbers -- no subjective verdicts ("the agent is good"),
and no single blended "CaseIQ score" (spec section 63): every dimension
stays a separate, independently-inspectable number.
"""


def _pct(x):
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _fmt_rate(rate: dict) -> str:
    acc = _pct(rate["accuracy"])
    return f"{acc} (n={rate['n_scored']}/{rate['n_total']}, prediction_rate={_pct(rate['prediction_rate'])})"


def render_report(experiment: dict) -> str:
    agg = experiment["aggregate"]
    lines = []
    lines.append(f"# Experiment: {experiment['name']}")
    lines.append("")
    lines.append(f"- experiment_id: `{experiment['experiment_id']}`")
    lines.append(f"- kind: {experiment['kind']}")
    lines.append(f"- created_at: {experiment['created_at']}")
    lines.append(f"- dataset_split: {experiment['dataset_split']} (split_version {experiment['split_version']})")
    lines.append(f"- num_cases: {experiment['num_cases']}")
    lines.append(f"- run_mode: {experiment['run_mode']}")
    lines.append(f"- evaluator_version: {experiment['evaluator_version']}")
    lines.append(f"- dataset_checksum_digest: `{experiment['dataset_checksum_digest']}`")
    lines.append(f"- agent: {experiment['agent']}")
    lines.append("")

    lines.append("## Outcome correctness")
    lines.append("")
    lines.append("| Field | Accuracy (scored/total, prediction_rate) |")
    lines.append("|---|---|")
    for name, rate in agg["outcome"].items():
        lines.append(f"| {name} | {_fmt_rate(rate)} |")
    lines.append("")

    lines.append("## Bootstrap 95% CIs (headline metrics)")
    lines.append("")
    lines.append("| Metric | Point estimate | CI low | CI high | n scored |")
    lines.append("|---|---|---|---|---|")
    for name, ci in agg["bootstrap_confidence_intervals"].items():
        lines.append(f"| {name} | {_pct(ci['point_estimate'])} | {_pct(ci['ci_low'])} | {_pct(ci['ci_high'])} | {ci['n_scored']} |")
    lines.append("")

    lines.append("## Confidence / calibration (chosen-answer, not full-distribution)")
    lines.append("")
    for field, block in agg["confidence_and_calibration"].items():
        be = block["brier_and_ece"]
        fc = block["false_confident"]
        lines.append(f"### {field}")
        lines.append(f"- Brier score: {be['brier_score']:.4f}" if be["brier_score"] is not None else "- Brier score: n/a")
        lines.append(f"- ECE: {be['ece']:.4f}" if be["ece"] is not None else "- ECE: n/a")
        lines.append(f"- False-confident rate (wrong AND conf>={fc['threshold']}): {_pct(fc['rate'])} (n={fc['denominator']})")
        lines.append("")
        lines.append("| Bucket | n | mean conf | observed accuracy |")
        lines.append("|---|---|---|---|")
        for row in block["calibration_table"]:
            lines.append(f"| {row['bucket']} | {row['n_cases']} | {_pct(row['mean_predicted_confidence'])} | {_pct(row['observed_accuracy'])} |")
        lines.append("")

    lines.append("## False-confident root-cause rate by scenario")
    lines.append("")
    for scenario, fc in agg["false_confident_by_scenario"].items():
        lines.append(f"- {scenario}: {_pct(fc['rate'])} (n={fc['denominator']})")
    lines.append("")

    lines.append("## Automation-coverage simulation (evaluation only)")
    lines.append("")
    lines.append("| Threshold | % eligible | accuracy among eligible | wrong-auto-action rate | human-review % below |")
    lines.append("|---|---|---|---|---|")
    for row in agg["automation_coverage_simulation"]:
        lines.append(
            f"| >= {row['threshold']} | {_pct(row['pct_eligible'])} | {_pct(row['accuracy_among_eligible'])} | "
            f"{_pct(row['wrong_auto_action_rate'])} | {_pct(row['human_review_pct_below_threshold'])} |"
        )
    lines.append("")

    lines.append("## Evidence")
    lines.append("")
    for k, v in agg["evidence"].items():
        lines.append(f"- {k}: {_pct(v)}")
    lines.append("")

    lines.append("## Process / contract compliance")
    lines.append("")
    pc = agg["process_and_contract"]
    for k in [
        "mean_tool_calls", "p95_tool_calls", "redundant_call_rate", "tool_error_rate",
        "unknown_tool_call_rate", "unsupported_evidence_rate", "budget_exhaustion_rate", "clean_run_rate",
        "n_repair_status_unknown",
    ]:
        v = pc[k]
        lines.append(f"- {k}: {_pct(v) if isinstance(v, float) and v <= 1 else v}")
    lines.append(f"- root_cause_accuracy_among_clean_runs: {_fmt_rate(pc['root_cause_accuracy_among_clean_runs'])}")
    lines.append(f"- root_cause_accuracy_among_repaired_runs: {_fmt_rate(pc['root_cause_accuracy_among_repaired_runs'])}")
    lines.append("")

    lines.append("## Efficiency")
    lines.append("")
    for k, v in agg["efficiency"].items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Failure taxonomy")
    lines.append("")
    ft = agg["failure_taxonomy"]
    lines.append(f"- % cases with at least one failure tag: {_pct(ft['pct_cases_with_any_failure_tag'])}")
    lines.append("")
    lines.append("| Tag | Count | Rate |")
    lines.append("|---|---|---|")
    for tag, count in ft["tag_counts"].items():
        lines.append(f"| {tag} | {count} | {_pct(ft['tag_rates'][tag])} |")
    lines.append("")

    lines.append("## Slices")
    lines.append("")
    for dim, values in agg["slices"].items():
        lines.append(f"### {dim}")
        lines.append("")
        lines.append("| value | n | root_cause_containment | component | team_acceptable | mean confidence |")
        lines.append("|---|---|---|---|---|---|")
        for value, block in values.items():
            o = block["outcome"]
            lines.append(
                f"| {value} | {block['n_cases']} | {_fmt_rate(o['root_cause_containment'])} | "
                f"{_fmt_rate(o['component'])} | {_fmt_rate(o['team_acceptable'])} | {_pct(block['mean_overall_confidence'])} |"
            )
        lines.append("")

    return "\n".join(lines)
