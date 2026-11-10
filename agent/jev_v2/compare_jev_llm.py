"""Paired Jev-vs-LLM primitive comparison (JEV-018).

Given the two experiments produced by `run_experiment --compare-llm`, pairs
every decision by (case_id, decision_type, incident_id) and reports, per
decision type, measured numbers only: accuracy in both the strict
(first-attempt) and as-scored forms, conditional accuracy, macro F1, high-
confidence errors, contract reliability, latency, tokens and cost, plus the
paired outcome table, an exact McNemar p-value and a paired bootstrap CI.

It also verifies input parity -- that Jev and the LLM received the same case,
snapshot, decision timestamp and candidate set -- by hashing the stored state
and candidates of each pair.

Confidence is NOT put on one scale. Jev's is a native probability from the
typed primitive; the LLM's is a self-reported number it was asked to write.
Both are shown, labelled, and no head-to-head calibration ranking is drawn.

Read-only over the stored experiments; no API or graph calls.
"""
import hashlib
import json
from pathlib import Path

from agent.jev_v2.aggregate import build_report
from agent.jev_v2.config import FALSE_CONFIDENT_THRESHOLD
from agent.jev_v2.paired_stats import mcnemar_exact_p, paired_bootstrap_diff


def _pct(x):
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _num(x, fmt="{:.3f}"):
    return fmt.format(x) if x is not None else "n/a"


def _key(r):
    return (r["case_id"], r["decision_type"], r.get("incident_id"))


def _input_hash(r) -> str:
    return hashlib.sha256(json.dumps({"state": r["state"], "candidates": r["candidates"], "as_of": r["as_of"]}, sort_keys=True, default=str).encode()).hexdigest()


def auc(pairs: list):
    """Rank AUC of a probability against a boolean truth (ties count half).
    None unless both classes are present."""
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if not pos or not neg:
        return None
    wins = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def _high_conf(records):
    scored = [r for r in records if r["scoring"].get("predicted_confidence") is not None and r["scoring"].get("correct") is not None]
    high = [r for r in scored if r["scoring"]["predicted_confidence"] >= FALSE_CONFIDENT_THRESHOLD]
    wrong = [r for r in high if not r["scoring"]["correct"]]
    return {"n_high_confidence": len(high), "n_high_confidence_wrong": len(wrong), "share_high_confidence": (len(high) / len(scored)) if scored else None}


def _system_metrics(records: list, block: dict, decision_type: str) -> dict:
    eff, contract = block["efficiency"], block["contract"]
    out = {
        "n": block["n_decisions"], "as_scored_accuracy": block["accuracy"], "strict_first_attempt_accuracy": block["strict_first_attempt_accuracy"],
        "accuracy_ci": block["bootstrap_ci_accuracy"], "macro_f1": block.get("macro_f1"),
        "false_confident": block["false_confident"], "high_confidence": _high_conf(records),
        "brier": block["brier_and_ece"]["brier_score"], "ece": block["brier_and_ece"]["ece"],
        "contract": contract, "p50_latency_ms": eff["p50_latency_ms"], "p95_latency_ms": eff["p95_latency_ms"],
        "mean_input_tokens": eff["mean_input_tokens"], "mean_output_tokens": eff["mean_output_tokens"],
        "cost_per_decision_usd": eff["cost_per_decision_usd"], "cost_per_1000_decisions_usd": eff["cost_per_1000_decisions_usd"],
        "total_cost_usd": eff["total_cost_usd"],
    }
    if "candidate_recall" in block:
        cr = block["candidate_recall"]
        out.update({"candidate_recall": cr["candidate_recall"], "conditional_accuracy": cr["conditional_accuracy_given_present"], "avg_candidates": cr["avg_candidate_count"]})
    if decision_type == "owning_team":
        tm = block["owning_team_metrics"]
        out.update({"primary_accuracy": tm["primary_accuracy"], "acceptable_accuracy": tm["acceptable_accuracy"], "primary_candidate_recall": tm["primary_candidate_recall"],
                    "acceptable_candidate_recall": tm["acceptable_candidate_recall"], "conditional_acceptable_accuracy": tm["conditional_acceptable_accuracy"]})
    if decision_type == "causal_change":
        rc = block["recency_categories"]
        out["recency"] = {k: {"n": rc[k]["n"], "accuracy": rc[k]["accuracy"]} for k in ("A", "B", "C", "D_multiple_recent_changes", "E")}
        out["distractor_selection_rate_when_offered"] = rc["distractor_selection_rate_when_a_distractor_was_offered"]
        out["no_causal_change_accuracy"] = rc["no_causal_change_accuracy"]
    if decision_type == "incident_relationship":
        pairs = [(r["scoring"]["raw_probability_for_true"], r["scoring"]["ground_truth_value"]) for r in records if r["scoring"].get("raw_probability_for_true") is not None]
        out["auc"] = auc(pairs)
        out["noul_metrics"] = block["noul_metrics"]
        out["raw_probability_brier"] = block["raw_probability_calibration"]["brier_score"]
    return out


def build_comparison(jev_records: list, llm_records: list) -> dict:
    jev_by, llm_by = {}, {}
    for r in jev_records:
        jev_by.setdefault(r["decision_type"], []).append(r)
    for r in llm_records:
        llm_by.setdefault(r["decision_type"], []).append(r)

    out = {}
    for dt in sorted(set(jev_by) & set(llm_by)):
        j_recs, l_recs = jev_by[dt], llm_by[dt]
        j_block, l_block = build_report(j_recs)[dt], build_report(l_recs)[dt]
        l_index = {_key(r): r for r in l_recs}
        pairs = [(r, l_index[_key(r)]) for r in j_recs if _key(r) in l_index]

        parity_ok = sum(1 for j, l in pairs if _input_hash(j) == _input_hash(l))
        both = only_jev = only_llm = neither = 0
        j_flags, l_flags, l_strict_flags = [], [], []
        for j, l in pairs:
            jc = bool(j["scoring"].get("correct"))
            lc = bool(l["scoring"].get("correct"))
            lc_strict = lc and bool(l.get("first_attempt_valid"))
            j_flags.append(1 if jc else 0)
            l_flags.append(1 if lc else 0)
            l_strict_flags.append(1 if lc_strict else 0)
            if jc and lc:
                both += 1
            elif jc:
                only_jev += 1
            elif lc:
                only_llm += 1
            else:
                neither += 1
        out[dt] = {
            "n_pairs": len(pairs), "input_parity": {"identical_state_candidates_asof": parity_ok, "n_pairs": len(pairs)},
            "jev": _system_metrics(j_recs, j_block, dt), "llm": _system_metrics(l_recs, l_block, dt),
            "trivial_baselines": j_block["trivial_baselines"],
            "paired": {
                "both_correct": both, "only_jev_correct": only_jev, "only_llm_correct": only_llm, "neither_correct": neither,
                "mcnemar_exact_p": mcnemar_exact_p(only_jev, only_llm),
                "jev_minus_llm_accuracy_ci": paired_bootstrap_diff(j_flags, l_flags),
                "jev_minus_llm_strict_accuracy_ci": paired_bootstrap_diff(j_flags, l_strict_flags),
            },
        }
    return out


def render(comparison: dict, jev_experiment: dict, llm_experiment: dict) -> str:
    lines = [
        "# Jev vs LLM primitive baseline (JEV-018)", "",
        f"- Jev: `{jev_experiment['experiment_id']}`  ({jev_experiment['config'].get('jev_model_requested')})",
        f"- LLM: `{llm_experiment['experiment_id']}`  ({llm_experiment['config'].get('llm_model')}, temperature {llm_experiment['config'].get('llm_temperature')}, one repair re-prompt allowed)",
        f"- cohort: {jev_experiment['num_cases']} `{jev_experiment['dataset_split']}` cases; candidate versions {jev_experiment['config'].get('candidate_generation_versions')}; root-cause context {jev_experiment['config'].get('context_version')}",
        f"- evaluator {jev_experiment['evaluator_version']}; pricing {jev_experiment['config'].get('pricing_version')} (token counts are provider-returned; prices are versioned assumptions)",
        "- Single run per system (LLM temperature 0.1, no seed): no run-to-run variance is measured for the LLM.",
        "- **Confidence is not comparable.** Jev's is a native probability from the typed primitive; the LLM's is a number it was asked to write. Shown side by side for transparency, never ranked against each other.", "",
    ]
    for dt, c in comparison.items():
        j, l, par, tb = c["jev"], c["llm"], c["paired"], c["trivial_baselines"]
        lines += [f"## {dt}", "",
                  f"- n = {c['n_pairs']} paired decisions; input parity (identical state, candidates, decision time): {c['input_parity']['identical_state_candidates_asof']}/{c['input_parity']['n_pairs']}",
                  f"- trivial baseline: always `{tb.get('majority_class')}` = {_pct(tb.get('majority_class_accuracy'))}" + (f"; newest-change-else-none = {_pct(tb['newest_change_else_none_accuracy'])}" if "newest_change_else_none_accuracy" in tb else ""), "",
                  "| Metric | Jev | LLM |", "|---|---:|---:|"]
        if "candidate_recall" in j:
            lines.append(f"| Candidate recall (same set for both) | {_pct(j['candidate_recall'])} | {_pct(l['candidate_recall'])} |")
            lines.append(f"| Avg candidates | {_num(j['avg_candidates'], '{:.1f}')} | {_num(l['avg_candidates'], '{:.1f}')} |")
        lines.append(f"| Accuracy (as scored) | {_pct(j['as_scored_accuracy'])} [{_pct(j['accuracy_ci'].get('ci_low'))}, {_pct(j['accuracy_ci'].get('ci_high'))}] | {_pct(l['as_scored_accuracy'])} [{_pct(l['accuracy_ci'].get('ci_low'))}, {_pct(l['accuracy_ci'].get('ci_high'))}] |")
        lines.append(f"| Accuracy, strict first attempt (contract failures = wrong) | {_pct(j['strict_first_attempt_accuracy'])} | {_pct(l['strict_first_attempt_accuracy'])} |")
        if "conditional_accuracy" in j:
            lines.append(f"| Conditional accuracy (true answer offered) | {_pct(j['conditional_accuracy'])} | {_pct(l['conditional_accuracy'])} |")
        if dt == "owning_team":
            lines.append(f"| Primary-team accuracy / acceptable-team accuracy | {_pct(j['primary_accuracy'])} / {_pct(j['acceptable_accuracy'])} | {_pct(l['primary_accuracy'])} / {_pct(l['acceptable_accuracy'])} |")
        if j.get("macro_f1") is not None or l.get("macro_f1") is not None:
            lines.append(f"| Macro F1 | {_num(j['macro_f1'])} | {_num(l['macro_f1'])} |")
        if dt == "incident_relationship":
            lines.append(f"| AUC of raw P(related) | {_num(j['auc'])} | {_num(l['auc'])} |")
            lines.append(f"| Brier of raw P(related) | {_num(j['raw_probability_brier'])} | {_num(l['raw_probability_brier'])} |")
            jn, ln = j["noul_metrics"], l["noul_metrics"]
            lines.append(f"| TP / FP / FN / TN at 0.5 | {jn['tp']}/{jn['fp']}/{jn['fn']}/{jn['tn']} | {ln['tp']}/{ln['fp']}/{ln['fn']}/{ln['tn']} |")
        lines.append(f"| High-confidence (>= {FALSE_CONFIDENT_THRESHOLD}) wrong / high-confidence predictions | {j['high_confidence']['n_high_confidence_wrong']} / {j['high_confidence']['n_high_confidence']} | {l['high_confidence']['n_high_confidence_wrong']} / {l['high_confidence']['n_high_confidence']} |")
        lines.append(f"| Brier / ECE on the answer's confidence (see confidence note) | {_num(j['brier'])} / {_num(j['ece'])} | {_num(l['brier'])} / {_num(l['ece'])} |")
        jc, lc = j["contract"], l["contract"]
        lines.append(f"| First-attempt valid output | {jc['first_attempt_valid']}/{jc['n_decisions']} (native typed) | {lc['first_attempt_valid']}/{lc['n_decisions']} |")
        lines.append(f"| Repair required / succeeded / unrecoverable | n/a | {lc['repair_required']} / {lc['repair_succeeded']} / {lc['unrecoverable_failures']} |")
        lines.append(f"| API/request errors | {jc['request_or_api_errors']} | {lc['request_or_api_errors']} |")
        lines.append(f"| Latency P50 / P95 (ms) | {_num(j['p50_latency_ms'], '{:.0f}')} / {_num(j['p95_latency_ms'], '{:.0f}')} | {_num(l['p50_latency_ms'], '{:.0f}')} / {_num(l['p95_latency_ms'], '{:.0f}')} |")
        lines.append(f"| Mean input / output tokens | {_num(j['mean_input_tokens'], '{:.0f}')} / {_num(j['mean_output_tokens'], '{:.0f}')} | {_num(l['mean_input_tokens'], '{:.0f}')} / {_num(l['mean_output_tokens'], '{:.0f}')} |")
        lines.append(f"| Cost per decision / per 1,000 decisions (USD) | {_num(j['cost_per_decision_usd'], '{:.6f}')} / {_num(j['cost_per_1000_decisions_usd'], '{:.4f}')} | {_num(l['cost_per_decision_usd'], '{:.6f}')} / {_num(l['cost_per_1000_decisions_usd'], '{:.4f}')} |")
        if dt == "causal_change":
            lines.append(f"| No-causal-change accuracy | {_pct(j['no_causal_change_accuracy'])} | {_pct(l['no_causal_change_accuracy'])} |")
            lines.append(f"| Distractor-selection rate (a distractor was offered) | {_pct(j['distractor_selection_rate_when_offered'])} | {_pct(l['distractor_selection_rate_when_offered'])} |")
            for key, label in (("A", "A true is newest"), ("B", "B true older than a distractor"), ("C", "C no causal change"), ("D_multiple_recent_changes", "D multiple recent changes"), ("E", "E true change not offered")):
                lines.append(f"| Recency {label} (n = {j['recency'][key]['n']}) | {_pct(j['recency'][key]['accuracy'])} | {_pct(l['recency'][key]['accuracy'])} |")
        ci, sci = par["jev_minus_llm_accuracy_ci"], par["jev_minus_llm_strict_accuracy_ci"]
        lines += ["",
                  f"Paired outcomes: both correct {par['both_correct']}, only Jev {par['only_jev_correct']}, only LLM {par['only_llm_correct']}, neither {par['neither_correct']}; exact McNemar p = {par['mcnemar_exact_p']:.3f}.",
                  f"Jev minus LLM accuracy (paired bootstrap 95% CI): {_num(ci['diff'], '{:+.3f}')} [{_num(ci['ci_low'], '{:+.3f}')}, {_num(ci['ci_high'], '{:+.3f}')}]; against the LLM's strict first-attempt outcomes: {_num(sci['diff'], '{:+.3f}')} [{_num(sci['ci_low'], '{:+.3f}')}, {_num(sci['ci_high'], '{:+.3f}')}].", ""]
    return "\n".join(lines)


def write_comparison(jev_experiment: dict, jev_records: list, llm_experiment: dict, llm_records: list, out_dir: Path) -> dict:
    comparison = build_comparison(jev_records, llm_records)
    md_path, json_path = Path(out_dir) / "comparison_jev_vs_llm.md", Path(out_dir) / "comparison_jev_vs_llm.json"
    md_path.write_text(render(comparison, jev_experiment, llm_experiment) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps({"jev_experiment_id": jev_experiment["experiment_id"], "llm_experiment_id": llm_experiment["experiment_id"], "comparison": comparison}, indent=2, default=str), encoding="utf-8")
    return {"markdown": md_path, "json": json_path}
