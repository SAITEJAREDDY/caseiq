"""OFFLINE evaluation of the early-triage workflow against dev ground truth. This is the only module in the package that reads hidden truth; nothing at runtime imports it, and it
runs only after every case has finished. Dev cases only (the fixed list in `run_dev`); the locked test split is never read.

Compared on the same cases:
  baseline      the stored LLM + Graph run (no triage, no verification)                          tag `verify100_final`
  early triage  the LLM + Graph + Jev run's FIRST answer: early Jev triage + the agent, before the late verifier can change anything. This isolates the effect of the early hint.
  full          the same run's FINAL answer and disposition after late verification (and the optional extra round).
Metrics: issue-category accuracy (exact id), critical-evidence retrieval (the frozen Phase 6 definition), investigation cost and latency, and final disposition. All descriptive: one run
per case per arm, so run-to-run model noise is not separated from the effect, and no improvement is claimed from a sample this size.

    python3 -m agent.early_triage.evaluation
"""
import json
import math
import statistics
from collections import Counter

from agent.agent_v3 import evaluate as AE
from agent.agent_v3.config import PROJECT_ROOT
from agent.compare import adapters
from agent.early_triage import run_dev
from agent.eval_v2 import evidence
from agent.eval_v2.ground_truth import get_hidden_truth

REPORT_JSON, REPORT_MD = run_dev.OUT / "report_v1.json", run_dev.OUT / "report_v1.md"
TOGETHER_USD_PER_M = 0.88


def verdict(pred, truth) -> str:
    return "abstain" if not pred else "correct" if pred == truth else "wrong"


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar (binomial) p-value on the discordant pairs."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def _initial_tool_calls(run: dict) -> int:
    cut = (run.get("initial_result") or {}).get("num_tool_calls") or run["num_tool_calls"]
    return sum(1 for s in run["trace_steps"] if s.get("proposed_by") == "model" and s["tool_name"] != "submit_diagnosis" and s["step"] < cut)


def _evidence(run_like: dict, p2: dict, p3: dict) -> dict:
    m = evidence.critical_evidence_metrics(run_like, p3, p2)
    return {"total": m["critical_total"], "retrieved": m["critical_retrieved"], "all": m["all_critical_retrieved"], "seen": len(run_like.get("evidence_ids_seen") or [])}


def case_row(cid: str, base: dict, rec: dict) -> dict:
    t = get_hidden_truth(cid)
    gt = (t["case_ground_truth"] or {})["gt_issue_category_id"]
    p2, p3 = t["phase2_ground_truth"] or {}, t["phase3_ground_truth"] or {}
    run = rec["agent_run"]
    init = run["initial_result"]
    tri = rec["early_triage"] or {}
    hint = tri.get("category_id") if tri.get("status") == "hint" else None
    top = (tri.get("distribution_top") or [{}])[0].get("category_id")
    init_fd, fin_fd = init["final_diagnosis"], run["final_diagnosis"]
    base_fd = base["final_diagnosis"]
    init_like = {"evidence_ids_seen": init.get("evidence_ids_seen") or [], "final_diagnosis": init_fd}
    verifier_s = sum(r.get("verifier_latency_ms", 0) for r in run["verification_rounds"]) / 1000
    return {
        "case_id": cid, "truth": gt,
        "jev_status": tri.get("status"), "jev_hint": hint, "jev_top": top, "jev_p": tri.get("probability"), "jev_hint_verdict": verdict(hint, gt) if hint else None,
        "jev_top_verdict": verdict(top, gt) if top else None, "jev_latency_s": (tri.get("latency_ms") or 0) / 1000, "jev_tokens": tri.get("input_tokens") or 0,
        "outcome": (rec.get("triage_outcome_initial") or {}).get("outcome"),
        "base_cat": base_fd.get("predicted_category_id"), "base": verdict(base_fd.get("predicted_category_id"), gt),
        "init_cat": init_fd.get("predicted_category_id"), "init": verdict(init_fd.get("predicted_category_id"), gt),
        "final_cat": fin_fd.get("predicted_category_id"), "final": verdict(fin_fd.get("predicted_category_id"), gt),
        "ev_base": _evidence(base, p2, p3), "ev_init": _evidence(init_like, p2, p3), "ev_final": _evidence(run, p2, p3),
        "tools_base": adapters.model_tool_calls(base), "tools_init": _initial_tool_calls(run), "tools_final": adapters.model_tool_calls(run),
        "tokens_base": base["token_usage"]["total_tokens"], "tokens_new": run["token_usage"]["total_tokens"], "jev_input_tokens_total": rec.get("jev_input_tokens", 0),
        "model_s_base": sum(c["latency_ms"] for c in base["llm_calls"]) / 1000, "model_s_new": sum(c["latency_ms"] for c in run["llm_calls"]) / 1000, "verifier_s": verifier_s,
        "cost_base": base["token_usage"]["total_tokens"] / 1e6 * TOGETHER_USD_PER_M, "cost_new": rec["cost_usd_estimate"],
        "extra_round": bool(rec["additional_investigation_performed"]), "first_decision": rec["policy_decision"], "final_decision": rec["final_policy_decision"],
        "base_status": base["final_status"], "base_review_flag": bool(base_fd.get("human_review_required")), "new_status": run["final_status"], "contract_failure": bool(run.get("contract_failure")),
    }


def _acc(rows, key) -> dict:
    n = len(rows)
    c = Counter(r[key] for r in rows)
    return {"n": n, "correct": c["correct"], "wrong": c["wrong"], "abstain": c["abstain"], "rate": round(c["correct"] / n, 4) if n else None, "wilson95": AE.wilson(c["correct"], n)}


def _mean(xs):
    xs = list(xs)
    return round(statistics.mean(xs), 4) if xs else None


def _pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 3) if xs else None


def aggregate(rows: list) -> dict:
    n = len(rows)
    out = {"n": n}
    out["category_accuracy"] = {k: _acc(rows, k) for k in ("base", "init", "final")}
    only_new = sum(1 for r in rows if r["init"] == "correct" and r["base"] != "correct")
    only_base = sum(1 for r in rows if r["base"] == "correct" and r["init"] != "correct")
    out["paired_baseline_vs_early"] = {"both_correct": sum(1 for r in rows if r["init"] == r["base"] == "correct"), "only_early_correct": only_new, "only_baseline_correct": only_base,
                                       "neither": n - only_new - only_base - sum(1 for r in rows if r["init"] == r["base"] == "correct"), "mcnemar_exact_p": round(mcnemar_exact(only_new, only_base), 4)}
    only_new_f = sum(1 for r in rows if r["final"] == "correct" and r["base"] != "correct")
    only_base_f = sum(1 for r in rows if r["base"] == "correct" and r["final"] != "correct")
    out["paired_baseline_vs_full"] = {"only_full_correct": only_new_f, "only_baseline_correct": only_base_f, "mcnemar_exact_p": round(mcnemar_exact(only_new_f, only_base_f), 4)}

    hinted = [r for r in rows if r["jev_hint"]]
    forced = [r for r in rows if r["jev_top"]]
    out["jev_early"] = {"status": dict(Counter(r["jev_status"] for r in rows)), "hint_coverage": {"k": len(hinted), "n": n}, "accuracy_when_hint_given": _acc(hinted, "jev_hint_verdict") if hinted else None,
                        "forced_top1_all_cases": _acc(forced, "jev_top_verdict") if forced else None,
                        "latency_s": {"mean": _mean(r["jev_latency_s"] for r in rows), "p95": _pct([r["jev_latency_s"] for r in rows], 0.95)},
                        "by_probability": {label: _acc([r for r in hinted if lo <= r["jev_p"] < hi], "jev_hint_verdict") for label, lo, hi in (("0.30-0.40", .3, .4), ("0.40-0.70", .4, .7), ("0.70-1.00", .7, 1.01))
                                           if any(lo <= r["jev_p"] < hi for r in hinted)}}
    right = [r for r in hinted if r["jev_hint_verdict"] == "correct"]
    wrong = [r for r in hinted if r["jev_hint_verdict"] == "wrong"]
    out["what_the_agent_did_with_the_hint"] = {
        "hint_correct": {"n": len(right), "confirmed": sum(1 for r in right if r["outcome"] == "confirmed"), "changed_away": sum(1 for r in right if r["outcome"] == "changed"),
                         "dropped": sum(1 for r in right if r["outcome"] == "dropped"), "baseline_correct_on_same_cases": sum(1 for r in right if r["base"] == "correct")},
        "hint_wrong": {"n": len(wrong), "adopted_the_wrong_hint": sum(1 for r in wrong if r["init_cat"] == r["jev_hint"]), "changed_to_the_true_category": sum(1 for r in wrong if r["init"] == "correct"),
                       "changed_to_another_wrong_category": sum(1 for r in wrong if r["init"] == "wrong" and r["init_cat"] != r["jev_hint"]), "dropped": sum(1 for r in wrong if r["outcome"] == "dropped"),
                       "baseline_correct_on_same_cases": sum(1 for r in wrong if r["base"] == "correct"), "baseline_also_chose_that_wrong_category": sum(1 for r in wrong if r["base_cat"] == r["jev_hint"])}}

    def ev(key):
        have = [r for r in rows if r[key]["total"] > 0]
        return {"cases_with_critical_evidence": len(have), "mean_critical_recall": _mean(r[key]["retrieved"] / r[key]["total"] for r in have),
                "all_critical_retrieved": sum(1 for r in have if r[key]["all"]), "mean_evidence_items_seen": _mean(r[key]["seen"] for r in rows)}
    out["evidence_retrieval"] = {"baseline": ev("ev_base"), "early_triage_first_answer": ev("ev_init"), "full_final": ev("ev_final")}

    calm = [r for r in rows if not r["extra_round"]]
    out["cost_latency"] = {
        "tool_calls_mean": {"baseline": _mean(r["tools_base"] for r in rows), "early_triage_first_answer": _mean(r["tools_init"] for r in rows), "full_final": _mean(r["tools_final"] for r in rows)},
        "agent_tokens_mean": {"baseline": _mean(r["tokens_base"] for r in rows), "full": _mean(r["tokens_new"] for r in rows)},
        "agent_tokens_mean_cases_without_extra_round": {"n": len(calm), "baseline": _mean(r["tokens_base"] for r in calm), "full": _mean(r["tokens_new"] for r in calm)},
        "model_seconds_mean": {"baseline": _mean(r["model_s_base"] for r in rows), "full": _mean(r["model_s_new"] for r in rows)},
        "added_jev_seconds_mean": {"early_triage": _mean(r["jev_latency_s"] for r in rows), "late_verifier": _mean(r["verifier_s"] for r in rows)},
        "est_cost_usd_mean": {"baseline": _mean(r["cost_base"] for r in rows), "full": _mean(r["cost_new"] for r in rows)},
        "runs_with_extra_investigation_round": sum(1 for r in rows if r["extra_round"])}
    accepted = [r for r in rows if r["final_decision"] == "ACCEPT"]
    base_auto = [r for r in rows if r["base_status"] == "DIAGNOSIS_PROPOSED" and not r["base_review_flag"]]
    out["disposition"] = {
        "baseline_agent_status": dict(Counter(r["base_status"] for r in rows)),
        "baseline_answered_without_review_flag": {"n": len(base_auto), **{k: sum(1 for r in base_auto if r["base"] == k) for k in ("correct", "wrong", "abstain")}},
        "full_first_policy_decision": dict(Counter(r["first_decision"] for r in rows)), "full_final_policy_decision": dict(Counter(r["final_decision"] for r in rows)),
        "full_accepted": {"n": len(accepted), **{k: sum(1 for r in accepted if r["final"] == k) for k in ("correct", "wrong", "abstain")}},
        "full_sent_to_review": {"n": n - len(accepted), "category_was_correct": sum(1 for r in rows if r["final_decision"] != "ACCEPT" and r["final"] == "correct")},
        "full_agent_status": dict(Counter(r["new_status"] for r in rows)), "contract_failures": sum(1 for r in rows if r["contract_failure"])}
    return out


def build() -> dict:
    spec = run_dev.frozen_cases()
    wanted = run_dev.evaluation_cases(spec)
    base_runs = AE.latest_runs(run_dev.BASELINE_TAG)
    rows, missing = [], []
    for cid in wanted:
        p = run_dev.RUNS / f"{cid}.json"
        if not p.exists() or cid not in base_runs:
            missing.append(cid)
            continue
        rows.append(case_row(cid, base_runs[cid], json.loads(p.read_text())))
    return {"spec": {**{k: spec[k] for k in ("version", "cohort", "baseline_tag", "case_ids_sha256", "rule")}, "n_cases": len(wanted), "n_in_frozen_list": spec["n_cases"]}, "missing_cases": missing, "aggregate": aggregate(rows), "rows": rows}


def _p(x, d=0):
    return "—" if x is None else f"{x * 100:.{d}f}%"


def render(rep: dict) -> str:
    a, n = rep["aggregate"], rep["aggregate"]["n"]
    ca = a["category_accuracy"]
    line = lambda name, d: f"| {name} | {d['correct']}/{d['n']} ({_p(d['rate'])}) | {_p(d['wilson95'][0])}–{_p(d['wilson95'][1])} | {d['wrong']} | {d['abstain']} |"
    j, h, pb = a["jev_early"], a["what_the_agent_did_with_the_hint"], a["paired_baseline_vs_early"]
    L = [f"# Early triage: dev comparison ({n} of {rep['spec']['n_cases']} cases)", "",
         f"Cases: the first {rep['spec']['n_cases']} of the {rep['spec']['n_in_frozen_list']}-case frozen list ({rep['spec']['rule']}). Missing: {rep['missing_cases'] or 'none'}. One run per case per arm; dev only.", "",
         "## Issue-category accuracy (exact id)", "", "| Arm | Correct | 95% CI (Wilson) | Wrong | No category |", "|---|---|---|---|---|",
         line("LLM + Graph baseline (stored)", ca["base"]), line("Early triage + agent, first answer", ca["init"]), line("LLM + Graph + Jev, final (after late verification)", ca["final"]), "",
         f"Paired baseline vs early-triage first answer: both correct {pb['both_correct']}, only early {pb['only_early_correct']}, only baseline {pb['only_baseline_correct']}, neither {pb['neither']}; "
         f"exact McNemar p = {pb['mcnemar_exact_p']}.", "",
         "## Early Jev alone", "", f"Statuses: {j['status']}. A hint was given on {j['hint_coverage']['k']}/{j['hint_coverage']['n']} cases."]
    if j["accuracy_when_hint_given"]:
        d = j["accuracy_when_hint_given"]
        L.append(f"Accuracy when a hint was given: {d['correct']}/{d['n']} ({_p(d['rate'])}, CI {_p(d['wilson95'][0])}–{_p(d['wilson95'][1])}).")
    if j["forced_top1_all_cases"]:
        d = j["forced_top1_all_cases"]
        L.append(f"Top-1 if it were always forced: {d['correct']}/{d['n']} ({_p(d['rate'])}).")
    L.append("By probability: " + "; ".join(f"{k}: {v['correct']}/{v['n']}" for k, v in j["by_probability"].items()) + f". Latency mean {j['latency_s']['mean']}s, p95 {j['latency_s']['p95']}s.")
    hr, hw = h["hint_correct"], h["hint_wrong"]
    L += ["", "## What the agent did with the hint", "",
          f"Hint correct (n={hr['n']}): confirmed {hr['confirmed']}, changed away {hr['changed_away']}, dropped {hr['dropped']}; the baseline was correct on {hr['baseline_correct_on_same_cases']} of these.",
          f"Hint wrong (n={hw['n']}): adopted the wrong hint {hw['adopted_the_wrong_hint']}, reached the true category {hw['changed_to_the_true_category']}, another wrong category "
          f"{hw['changed_to_another_wrong_category']}, dropped {hw['dropped']}; the baseline was correct on {hw['baseline_correct_on_same_cases']} and chose that same wrong category on "
          f"{hw['baseline_also_chose_that_wrong_category']}.", "", "## Evidence retrieval (critical evidence, Phase 6 definition)", "",
          "| Arm | Cases with critical evidence | Mean critical recall | All critical retrieved | Mean evidence items seen |", "|---|---|---|---|---|"]
    for name, k in (("Baseline", "baseline"), ("Early triage, first answer", "early_triage_first_answer"), ("Full, final", "full_final")):
        e = a["evidence_retrieval"][k]
        L.append(f"| {name} | {e['cases_with_critical_evidence']} | {_p(e['mean_critical_recall'])} | {e['all_critical_retrieved']} | {e['mean_evidence_items_seen']} |")
    c = a["cost_latency"]
    L += ["", "## Cost and latency (means)", "",
          f"Model tool calls: baseline {c['tool_calls_mean']['baseline']}, early-triage first answer {c['tool_calls_mean']['early_triage_first_answer']}, full {c['tool_calls_mean']['full_final']}.",
          f"Agent tokens: baseline {c['agent_tokens_mean']['baseline']}, full {c['agent_tokens_mean']['full']} (cases with no extra round, n={c['agent_tokens_mean_cases_without_extra_round']['n']}: "
          f"{c['agent_tokens_mean_cases_without_extra_round']['baseline']} vs {c['agent_tokens_mean_cases_without_extra_round']['full']}).",
          f"Model seconds: baseline {c['model_seconds_mean']['baseline']}, full {c['model_seconds_mean']['full']}; added Jev seconds: early triage {c['added_jev_seconds_mean']['early_triage']}, "
          f"late verifier {c['added_jev_seconds_mean']['late_verifier']}. Est. cost per case: baseline ${c['est_cost_usd_mean']['baseline']}, full ${c['est_cost_usd_mean']['full']}. "
          f"Runs with an extra investigation round: {c['runs_with_extra_investigation_round']}.", "", "## Final disposition", ""]
    d = a["disposition"]
    L += [f"Baseline agent status: {d['baseline_agent_status']}; answered without a review flag: {d['baseline_answered_without_review_flag']}.",
          f"LLM + Graph + Jev: first policy decision {d['full_first_policy_decision']}; final {d['full_final_policy_decision']}; agent status {d['full_agent_status']}; contract failures {d['contract_failures']}.",
          f"Accepted: {d['full_accepted']}. Sent to review: {d['full_sent_to_review']['n']}, of which the category was correct in {d['full_sent_to_review']['category_was_correct']}.", "",
          "## Limitations", "",
          "- One run per case per arm at temperature 0.1: run-to-run model noise is not separated from any effect. The baseline runs were made earlier with the same agent code and no triage.",
          f"- N = {n} dev cases; the intervals above are wide. Nothing here supports a claim of improvement or of no effect.",
          "- Early Jev sees ticket text only (no signals) and has an abstain option, so its accuracy is not comparable to the Phase 7 issue-category figure.",
          "- The hint wording, the 0.30 minimum probability, the uncertainty bands and the advisory tool map are hand-set and unvalidated; nothing was tuned on these results.",
          "- Category is one of five diagnostic fields and the only one Jev is asked about early; root cause, component and team were not evaluated here."]
    return "\n".join(L)


def main() -> None:
    rep = build()
    REPORT_JSON.write_text(json.dumps(rep, indent=1, default=str))
    REPORT_MD.write_text(render(rep))
    print(render(rep))


if __name__ == "__main__":
    main()
