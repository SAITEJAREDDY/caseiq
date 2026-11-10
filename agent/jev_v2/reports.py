"""Aggregate report dict -> Markdown (mirrors agent/eval_v2/reports.py's
style: measured numbers only, no single blended score, spec section 59)."""


def _pct(x):
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def render_report(experiment: dict) -> str:
    lines = [f"# Experiment: {experiment['name']}", ""]
    lines += [
        f"- experiment_id: `{experiment['experiment_id']}`",
        f"- experiment_type: {experiment['experiment_type']}",
        f"- kind: {experiment['kind']}",
        f"- created_at: {experiment['created_at']}",
        f"- dataset_split: {experiment['dataset_split']}",
        f"- num_cases: {experiment['num_cases']}",
        f"- decision_types: {', '.join(experiment['decision_types'])}",
        f"- question_set_version: {experiment['question_set_version']}",
        f"- candidate_strategy_version: {experiment['candidate_strategy_version']}",
        f"- evaluator_version: {experiment['evaluator_version']}",
        f"- dataset_checksum_digest: `{experiment['dataset_checksum_digest']}`",
        f"- config: {experiment['config']}",
        "",
    ]

    for dt, block in experiment["report"].items():
        lines.append(f"## {dt} ({block['primitive_type']})")
        lines.append("")
        lines.append(f"- n_decisions: {block['n_decisions']}  (errors: {block['n_errors']}, contract failures: {block['n_contract_failures']})")
        lines.append(f"- accuracy: {_pct(block['accuracy'])}")
        lines.append(f"- acceptable_match_rate: {_pct(block['acceptable_match_rate'])}")
        ci = block["bootstrap_ci_accuracy"]
        lines.append(f"- accuracy 95% CI: {_pct(ci.get('point_estimate'))} [{_pct(ci.get('ci_low'))}, {_pct(ci.get('ci_high'))}] (n={ci.get('n_scored')})")
        be = block["brier_and_ece"]
        lines.append(f"- Brier: {be['brier_score']:.4f}" if be["brier_score"] is not None else "- Brier: n/a")
        lines.append(f"- ECE: {be['ece']:.4f}" if be["ece"] is not None else "- ECE: n/a")
        fc = block["false_confident"]
        lines.append(f"- false-confident rate (wrong AND conf>={fc['threshold']}): {_pct(fc['rate'])} (n={fc['denominator']})")

        if "macro_f1" in block:
            lines.append(f"- macro F1: {block['macro_f1']:.3f}" if block["macro_f1"] is not None else "- macro F1: n/a")
        if "candidate_recall" in block and block["candidate_recall"]:
            cr = block["candidate_recall"]
            lines.append(f"- candidate recall: {_pct(cr['candidate_recall'])} (avg candidates: {cr['avg_candidate_count']:.1f})" if cr["avg_candidate_count"] else f"- candidate recall: {_pct(cr['candidate_recall'])}")
            lines.append(f"- candidate count distribution: median={cr.get('median_candidate_count')}, P90={cr.get('p90_candidate_count')}")
            lines.append(f"- end-to-end accuracy: {_pct(cr['end_to_end_accuracy'])} | conditional accuracy given candidate present: {_pct(cr['conditional_accuracy_given_present'])}")
        if "failure_decomposition" in block:
            fd = block["failure_decomposition"]
            lines.append(f"- failure decomposition: missing={fd['candidate_missing']}, present/jev-wrong={fd['candidate_present_jev_wrong']}, present/jev-correct={fd['candidate_present_jev_correct']}, high-confidence-wrong={fd['jev_wrong_high_confidence']}")
        if "owning_team_metrics" in block:
            tm = block["owning_team_metrics"]
            lines.append(f"- team candidate recall: primary={_pct(tm['primary_candidate_recall'])}, acceptable={_pct(tm['acceptable_candidate_recall'])}")
            lines.append(f"- team accuracy: primary={_pct(tm['primary_accuracy'])}, acceptable={_pct(tm['acceptable_accuracy'])}; conditional primary={_pct(tm['conditional_primary_accuracy'])}, conditional acceptable={_pct(tm['conditional_acceptable_accuracy'])}")
        if "noul_metrics" in block:
            nm = block["noul_metrics"]
            lines.append(f"- Noul precision/recall/F1: {nm['precision']}/{nm['recall']}/{nm['f1']}, FPR={_pct(nm['false_positive_rate'])}, FNR={_pct(nm['false_negative_rate'])}")
        if "strict_first_attempt_accuracy" in block:
            lines.append(f"- strict first-attempt accuracy (contract failures count as wrong): {_pct(block['strict_first_attempt_accuracy'])}")
        if block.get("contract"):
            c = block["contract"]
            if c.get("native_typed_output"):
                lines.append(f"- contract: native typed output; transport/API errors={c['request_or_api_errors']}")
            else:
                lines.append(
                    f"- contract: first-attempt valid={c['first_attempt_valid']}/{c['n_decisions']} ({_pct(c['first_attempt_valid_rate'])}), repair required={c['repair_required']}, "
                    f"repair succeeded={c['repair_succeeded']}, unrecoverable={c['unrecoverable_failures']}, request errors={c['request_or_api_errors']}, first-attempt failure kinds={c['first_attempt_failure_kinds']}"
                )
        if block.get("trivial_baselines"):
            tb = block["trivial_baselines"]
            extra = f"; newest-change-else-none={_pct(tb['newest_change_else_none_accuracy'])}" if "newest_change_else_none_accuracy" in tb else ""
            lines.append(f"- trivial baselines: always-majority ({tb['majority_class']})={_pct(tb['majority_class_accuracy'])}{extra}")
        if "recency_categories" in block:
            rc = block["recency_categories"]
            for key in ("A", "B", "C", "E"):
                g = rc[key]
                lines.append(f"- recency {g['label']}: n={g['n']}, accuracy={_pct(g['accuracy'])}, selected-newest={_pct(g['selected_newest_rate'])}, selected-none={_pct(g['selected_none_rate'])}")
            d = rc["D_multiple_recent_changes"]
            lines.append(f"- recency D_multiple_recent_changes: n={d['n']}, accuracy={_pct(d['accuracy'])}")
            lines.append(
                f"- no-causal-change accuracy={_pct(rc['no_causal_change_accuracy'])}; distractor-selection rate={_pct(rc['distractor_selection_rate_all_decisions'])} of all decisions, "
                f"{_pct(rc['distractor_selection_rate_when_a_distractor_was_offered'])} when a distractor was offered (n={rc['n_decisions_with_a_distractor_offered']})"
            )
        if "recency_analysis" in block:
            ra = block["recency_analysis"]
            lines.append(f"- selected-is-newest-change rate: {_pct(ra['selected_is_newest_change_rate'])}")
            lines.append(f"- accuracy when true causal change IS newest: {_pct(ra['accuracy_when_true_causal_change_is_newest'])} (n={ra['n_newest_is_causal']})")
            lines.append(f"- accuracy when true causal change is OLDER than a distractor: {_pct(ra['accuracy_when_true_causal_change_is_older_than_distractor'])} (n={ra['n_older_is_causal']})")

        lines.append("")
        eff = block.get("efficiency") or {}
        if eff:
            lines.append(f"- efficiency: mean latency={eff.get('mean_latency_ms')} ms (P50={eff.get('p50_latency_ms')}, P95={eff.get('p95_latency_ms')}); mean input/output tokens={eff.get('mean_input_tokens')}/{eff.get('mean_output_tokens')}; total input/output tokens={eff.get('total_input_tokens')}/{eff.get('total_output_tokens')}")
            if eff.get("total_cost_usd") is not None:
                lines.append(f"- cost (pricing {eff.get('pricing_version')}): total ${eff['total_cost_usd']:.4f}; ${eff['cost_per_1000_decisions_usd']:.3f} per 1,000 decisions")
            lines.append("")
        lines.append("Automation coverage:")
        lines.append("")
        lines.append("| Threshold | Coverage | Accuracy among eligible | Error rate |")
        lines.append("|---|---|---|---|")
        for row in block["automation_coverage"]:
            lines.append(f"| >= {row['threshold']} | {_pct(row['coverage'])} | {_pct(row['accuracy_among_eligible'])} | {_pct(row['error_rate'])} |")
        lines.append("")

        lines.append("Target-error coverage:")
        lines.append("")
        lines.append("| Target error | Max coverage | n |")
        lines.append("|---|---|---|")
        for target, row in block["target_error_coverage"].items():
            lines.append(f"| <={float(target) * 100:.0f}% | {_pct(row['max_coverage_at_or_below_target'])} | {row['n']} |")
        lines.append("")

        lines.append("Slices:")
        lines.append("")
        for dim, values in block["slices"].items():
            lines.append(f"- {dim}:")
            for value, v in values.items():
                lines.append(f"  - {value}: n={v['n']}, accuracy={_pct(v['accuracy'])}, mean_confidence={_pct(v['mean_confidence'])}")
        lines.append("")

    return "\n".join(lines)


def render_comparison_table(jev_report: dict, llm_report: dict) -> str:
    lines = ["# Jev vs. LLM primitive baseline", ""]
    decision_types = sorted(set(jev_report.keys()) | set(llm_report.keys()))
    for dt in decision_types:
        j, l = jev_report.get(dt, {}), llm_report.get(dt, {})
        lines.append(f"## {dt}")
        lines.append("")
        lines.append("| Metric | Jev | LLM |")
        lines.append("|---|---|---|")
        lines.append(f"| Accuracy | {_pct(j.get('accuracy'))} | {_pct(l.get('accuracy'))} |")
        lines.append(f"| Macro F1 | {j.get('macro_f1')} | {l.get('macro_f1')} |")
        lines.append(f"| Brier | {j.get('brier_and_ece', {}).get('brier_score')} | {l.get('brier_and_ece', {}).get('brier_score')} |")
        lines.append(f"| ECE | {j.get('brier_and_ece', {}).get('ece')} | {l.get('brier_and_ece', {}).get('ece')} |")
        lines.append(f"| False-confident rate | {_pct(j.get('false_confident', {}).get('rate'))} | {_pct(l.get('false_confident', {}).get('rate'))} |")
        lines.append(f"| Contract failures | {j.get('n_contract_failures')} | {l.get('n_contract_failures')} |")
        lines.append("")
    return "\n".join(lines)
