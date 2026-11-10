"""Offline evaluation of a Phase 9A run set (EVALUATOR SIDE: reads hidden truth through the unchanged Phase 6 evaluator, only after the runs exist).

Protocol reliability and diagnostic quality are reported separately and never combined (spec section 38). Protocol metrics are computed from the
persisted run records alone; references are recounted independently of the validator (each alias re-checked against the run's own registry and the
step it was first observed), so the validator is not marking its own homework. Outcome metrics are observational and are never a tuning signal.

    python3 -m agent.agent_v3.evaluate --tag iter50_a --cohort iter50
"""
import argparse
import json
import math
from collections import Counter, defaultdict

from agent.agent_v3 import cohorts
from agent.agent_v3.catalog import ARG_FIELDS
from agent.agent_v3.config import COHORT_DIR, RUNS_DIR
from agent.agent_v3.final_contract import SELECTIONS
from agent.agent_v3.registry import CITABLE_KINDS, ID_RE

TARGETS = {  # engineering targets from the Phase 9A spec (section 36); not diagnostic targets
    "valid_registered_tool_name_rate": (">=", 0.98), "tool_argument_validity_rate": (">=", 0.98), "first_pass_final_valid_rate": (">=", 0.95),
    "final_valid_after_one_repair_rate": (">=", 0.99), "invented_canonical_ids": ("==", 0), "invalid_evidence_references": ("==", 0),
    "entity_aliases_outside_registry": ("==", 0), "unrecoverable_contract_failure_rate": ("<=", 0.02),
}


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "wilson95": wilson(k, n)}


def latest_runs(tag: str) -> dict:
    idx, latest = RUNS_DIR / "runs_index.jsonl", {}
    for line in idx.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            if e["run_tag"] == tag:
                latest[e["case_id"]] = e["run_id"]
    return {c: json.loads((RUNS_DIR / f"{r}.json").read_text()) for c, r in latest.items()}


# ── protocol metrics (run records only) ──────────────────────────────────────────────────────────────

def _parse(raw):
    try:
        o = json.loads(raw)
        return o if isinstance(o, dict) else None
    except (TypeError, ValueError):
        return None


def recount_references(run: dict) -> Counter:
    """Every reference in every model output of this run, re-checked against the run's own alias mapping: the alias must exist, be of the allowed
    kind, and have been observed BEFORE the call that used it. `entity` refs are selections and tool arguments; `evidence` refs are citations."""
    mp, c = run["alias_mappings"], Counter()

    def check(value, kinds, call_step, klass):
        c[f"{klass}_total"] += 1
        if not isinstance(value, str):
            c[f"{klass}_invalid"] += 1
            return
        if ID_RE.search(value):
            c["invented_canonical_ids"] += 1
            c[f"{klass}_invalid"] += 1
            return
        ent = mp.get(value)
        if ent is None or ent["kind"] == "REF":
            c["aliases_outside_registry"] += 1
            c[f"{klass}_invalid"] += 1
        elif ent["kind"] not in kinds:
            c["wrong_kind"] += 1
            c[f"{klass}_invalid"] += 1
        elif ent["first_observed_step"] is None or ent["first_observed_step"] >= call_step:
            c["cited_before_observed"] += 1
            c[f"{klass}_invalid"] += 1

    for call in run["llm_calls"]:
        o = _parse(call["raw_output"])
        if o is None:
            c["unparseable_outputs"] += 1
            continue
        step = call["step"]
        for h in o.get("hypotheses") or []:
            for k in ("supporting_evidence", "contradicting_evidence"):
                for a in (h.get(k) or []) if isinstance(h, dict) else []:
                    check(a, CITABLE_KINDS, step, "evidence")
        if call["phase"] == "action":
            for a, kind in (("component", "COMPONENT"), ("team", "TEAM")):
                if o.get(a) is not None:
                    check(o[a], (kind,), step, "entity")
        else:
            for value, _conf, kinds in SELECTIONS:
                if o.get(value) is not None:
                    check(o[value], kinds, step, "entity")
            for a in o.get("evidence_ids") or []:
                check(a, CITABLE_KINDS, step, "evidence")
    return c


def protocol_metrics(runs: dict) -> dict:
    R = list(runs.values())
    n = len(R)
    props = sum(r["tool_proposals"] for r in R)
    tool_errs = [e for r in R for te in r["tool_contract_errors"] for e in te["errors"]]
    rejected = sum(len(r["tool_contract_errors"]) for r in R)
    by_code = Counter(e["code"] for e in tool_errs)
    arg_rejects = sum(1 for r in R for te in r["tool_contract_errors"] if any(e["field"] in ARG_FIELDS for e in te["errors"]))
    hyp_rejects = sum(1 for r in R for te in r["tool_contract_errors"] if any(e["field"].startswith("hypotheses") for e in te["errors"]))
    name_rejects = sum(1 for r in R for te in r["tool_contract_errors"] if any(e["code"] == "unknown_tool" for e in te["errors"]))
    reached = [r for r in R if r["validation_result"]["first_pass_ok"] is not None]
    first_ok = sum(1 for r in reached if r["validation_result"]["first_pass_ok"])
    repaired = [r for r in reached if r["validation_result"]["repair_used"]]
    final_ok = sum(1 for r in reached if r["validation_result"]["final_ok"])
    fail_tool = sum(1 for r in R if r["stop_reason"] == "tool_contract_repair_budget_exhausted")
    fail_final = sum(1 for r in R if r["stop_reason"] == "final_contract_failure")
    refs = Counter()
    for r in R:
        refs.update(recount_references(r))
    first_final_errs = Counter(e["code"] for r in reached for e in r["validation_result"]["errors_first"])
    missing_field_runs = sum(1 for r in reached if any(e["code"] == "missing_field" for e in r["validation_result"]["errors_first"]))
    statuses = Counter(r["final_status"] for r in R)
    sel_null = {v: sum(1 for r in reached if r["final_alias_form"] and r["final_alias_form"][v] is None) for v, _c, _k in SELECTIONS}
    proposed = [r for r in R if r["final_status"] == "DIAGNOSIS_PROPOSED"]
    no_sel = sum(1 for r in R if r["final_alias_form"] and all(r["final_alias_form"][v] is None for v, _c, _k in SELECTIONS))
    return {
        "n_runs": n,
        "tool_contract": {
            "model_tool_proposals": props, "rejected_proposals": rejected,
            "valid_tool_call_rate": rate(props - rejected, props),
            "valid_registered_tool_name_rate": rate(props - name_rejects, props),
            "hallucinated_tool_name_rate": rate(name_rejects, props),
            "tool_argument_validity_rate": rate(props - arg_rejects, props),
            "invalid_argument_rate": rate(arg_rejects, props),
            "hypothesis_state_rejection_rate": rate(hyp_rejects, props),
            "tool_contract_repairs_total": sum(len(r["tool_contract_repairs"]) for r in R),
            "traces_with_a_rejected_proposal": rate(sum(1 for r in R if r["tool_contract_errors"]), n),
            "rejection_codes": dict(by_code),
        },
        "final_contract": {
            "runs_reaching_finalization": len(reached),
            "first_pass_final_valid_rate": rate(first_ok, len(reached)),
            "first_pass_contract_success_run_level": rate(sum(1 for r in reached if r["validation_result"]["first_pass_ok"] and not r["tool_contract_errors"]), n),
            "final_repairs_used": len(repaired), "repaired_valid": rate(sum(1 for r in repaired if r["validation_result"]["final_ok"]), len(repaired)),
            "final_valid_after_one_repair_rate": rate(final_ok, len(reached)),
            "final_contract_success_after_repair_run_level": rate(sum(1 for r in R if not r["contract_failure"]), n),
            "unrecoverable_contract_failure_rate": rate(fail_tool + fail_final, n),
            "unrecoverable_by_kind": {"tool_contract_repair_budget_exhausted": fail_tool, "final_contract_failure": fail_final},
            "first_pass_error_codes": dict(first_final_errs),
        },
        "grounding": {
            "references_recounted_independently": {k: v for k, v in sorted(refs.items())},
            "valid_entity_reference_rate": rate(refs["entity_total"] - refs["entity_invalid"], refs["entity_total"]),
            "valid_evidence_reference_rate": rate(refs["evidence_total"] - refs["evidence_invalid"], refs["evidence_total"]),
            "invented_canonical_ids": refs["invented_canonical_ids"],
            "invalid_evidence_references": refs["evidence_invalid"],
            "entity_aliases_outside_registry": refs["aliases_outside_registry"],
        },
        "completion": {
            "final_status_counts": dict(statuses),
            "missing_required_field_rate": rate(missing_field_runs, len(reached)),
            "runs_with_every_selection_null": rate(no_sel, len(reached)),
            "null_selection_rate_by_field": {v: rate(k, len(reached)) for v, k in sel_null.items()},
            "diagnosis_proposed_with_a_selection": rate(sum(1 for r in proposed if any(r["final_alias_form"][v] is not None for v, _c, _k in SELECTIONS)), len(proposed)),
        },
        "efficiency": {"mean_llm_calls": round(sum(r["num_llm_calls"] for r in R) / n, 2), "mean_total_tokens": round(sum(r["token_usage"]["total_tokens"] for r in R) / n),
                       "mean_executed_steps": round(sum(r["num_tool_calls"] for r in R) / n, 2)},
    }


def targets_check(pm: dict) -> dict:
    t, f, g = pm["tool_contract"], pm["final_contract"], pm["grounding"]
    measured = {
        "valid_registered_tool_name_rate": t["valid_registered_tool_name_rate"]["rate"], "tool_argument_validity_rate": t["tool_argument_validity_rate"]["rate"],
        "first_pass_final_valid_rate": f["first_pass_final_valid_rate"]["rate"], "final_valid_after_one_repair_rate": f["final_valid_after_one_repair_rate"]["rate"],
        "invented_canonical_ids": g["invented_canonical_ids"], "invalid_evidence_references": g["invalid_evidence_references"],
        "entity_aliases_outside_registry": g["entity_aliases_outside_registry"], "unrecoverable_contract_failure_rate": f["unrecoverable_contract_failure_rate"]["rate"],
    }
    out = {}
    for k, (op, target) in TARGETS.items():
        v = measured[k]
        met = None if v is None else {">=": v >= target, "==": v == target, "<=": v <= target}[op]
        out[k] = {"target": f"{op} {target}", "measured": v, "met": met}
    return out


# ── historical Phase 5 baseline on the same cases, same definitions ────────────────────────────────────────────────

def baseline_protocol(base: dict) -> dict:
    from agent.eval_v2 import contract

    R, n = list(base.values()), len(base)
    def invalid_tool(r):
        return any(s.get("status") == "error" and contract.classify_tool_error((s.get("result_summary") or {}).get("error", "") if isinstance(s.get("result_summary"), dict) else "")
                   in ("unknown_tool", "validation_error") for s in r["trace_steps"])
    def final_repaired(r):
        return any(e.get("kind") in ("final_diagnosis_repair", "final_diagnosis_fallback") for e in r.get("repair_events") or [])
    def id_fields(r):
        fd = r["final_diagnosis"]
        return any(fd.get(k) for k in ("predicted_component_id", "predicted_category_id", "predicted_subcategory_id", "predicted_product_id",
                                        "predicted_causal_change_id", "recommended_team_id"))
    steps = [s for r in R for s in r["trace_steps"] if s["tool_name"] != "submit_diagnosis"]
    unknown = sum(1 for s in steps if s.get("status") == "error" and "unknown tool" in json.dumps(s.get("result_summary")))
    invalid = sum(1 for s in steps if s.get("status") == "error")
    return {
        "n_runs": n,
        "invalid_tool_call_traces": rate(sum(invalid_tool(r) for r in R), n),
        "final_repair_required": rate(sum(final_repaired(r) for r in R), n),
        "structured_id_completion": rate(sum(id_fields(r) for r in R), n),
        "traces_with_a_citation_violation": rate(sum(1 for r in R if r.get("citation_violations")), n),
        "first_pass_valid_final": rate(sum(1 for r in R if not final_repaired(r)), n),
        "contract_failure_visible": rate(sum(1 for r in R if any(e.get("kind") == "final_diagnosis_fallback" for e in r.get("repair_events") or [])), n),
        "valid_registered_tool_name_rate": rate(len(steps) - unknown, len(steps)),
        "tool_argument_validity_rate": rate(len(steps) - (invalid - unknown), len(steps)),
        "model_tool_proposals": len(steps),
    }


def hardened_for_table(pm: dict, runs: dict) -> dict:
    R, n = list(runs.values()), len(runs)
    def id_fields(r):
        fd = r["final_diagnosis"]
        return any(fd.get(k) for k in ("predicted_component_id", "predicted_category_id", "predicted_subcategory_id", "predicted_product_id",
                                        "predicted_causal_change_id", "recommended_team_id"))
    reached = [r for r in R if r["validation_result"]["first_pass_ok"] is not None]
    return {
        "invalid_tool_call_traces": pm["tool_contract"]["traces_with_a_rejected_proposal"],
        "final_repair_required": rate(sum(1 for r in reached if r["validation_result"]["repair_used"]), n),
        "structured_id_completion": rate(sum(id_fields(r) for r in R), n),
        "traces_with_a_citation_violation": rate(sum(1 for r in R if r["citation_violations"]), n),
        "first_pass_valid_final": rate(sum(1 for r in reached if r["validation_result"]["first_pass_ok"]), n),
        "contract_failure_visible": rate(sum(1 for r in R if r["contract_failure"]), n),
        "valid_registered_tool_name_rate": pm["tool_contract"]["valid_registered_tool_name_rate"],
        "tool_argument_validity_rate": pm["tool_contract"]["tool_argument_validity_rate"],
        "model_tool_proposals": pm["tool_contract"]["model_tool_proposals"],
    }


# ── observational diagnostic outcomes (Phase 6 authority; never a tuning signal) ─────────────────────────────────────────

def outcomes(runs: dict, stratum: dict) -> dict:
    from agent.eval_v2.metrics import evaluate_run
    from agent.trace_eval_v2.labels import outcome_label

    recs = {c: evaluate_run(r) for c, r in runs.items()}
    lab = {c: outcome_label(p)["label"] for c, p in recs.items()}
    def field(sel, correct):
        vals = [correct(p) for p in recs.values()]
        ans = [v for v in vals if v is not None]
        return {"answered": rate(len(ans), len(vals)), "correct_given_answered": rate(sum(1 for v in ans if v), len(ans))}
    o = lambda p: p["outcome"]
    by_stratum = defaultdict(Counter)
    for c, l in lab.items():
        by_stratum[stratum.get(c, "?")][l] += 1
    low = [c for c, p in recs.items() if p["stratification"]["low_evidence"]]
    suff = [c for c, p in recs.items() if p["stratification"]["evidence_sufficiency"] == "sufficient"]
    def status_of(r):  # Phase 5 runs have no status field: derive the equivalent from the fields they do have
        if r.get("final_status"):
            return r["final_status"]
        fd = r["final_diagnosis"]
        return "HUMAN_REVIEW_REQUIRED" if fd.get("human_review_required") else "INSUFFICIENT_EVIDENCE" if fd.get("evidence_sufficiency") == "insufficient" else "DIAGNOSIS_PROPOSED"
    abstained = lambda r: status_of(r) in ("INSUFFICIENT_EVIDENCE", "HUMAN_REVIEW_REQUIRED", "CONTRACT_FAILURE")
    return {
        "note": "Observational only. Phase 6 text matching under-counts correct root causes; a contract-valid wrong diagnosis is still wrong, and a correct answer with invalid references is still contract-invalid.",
        "final_outcome_counts": dict(Counter(lab.values())),
        "final_outcome_correct": rate(sum(1 for v in lab.values() if v == "CORRECT"), len(lab)),
        "issue_category": field("category", lambda p: o(p)["category"]["correct"]),
        "root_cause_containment": field("root_cause", lambda p: o(p)["root_cause"]["containment_match"]),
        "component": field("component", lambda p: o(p)["component"]["correct"]),
        "causal_change": field("causal_change", lambda p: (False if o(p)["causal_change"]["false_positive"] else o(p)["causal_change"]["correct"])),
        "owning_team_acceptable": field("team", lambda p: o(p)["team"]["acceptable_match"]),
        "outcome_by_stratum": {k: dict(v) for k, v in sorted(by_stratum.items())},
        "abstention_on_insufficient_evidence_cases": rate(sum(1 for c in low if abstained(runs[c])), len(low)),
        "over_abstention_on_sufficient_evidence_cases": rate(sum(1 for c in suff if status_of(runs[c]) == "INSUFFICIENT_EVIDENCE"), len(suff)),
        "false_confident_root_cause": sum(1 for p in recs.values() if o(p)["root_cause"]["false_confident"]),
    }, recs


def build_report(tag: str, cohort_name: str) -> dict:
    from agent.trace_eval_v2.corpus import reusable_runs

    cohort = cohorts.load(cohort_name)
    runs = {c: r for c, r in latest_runs(tag).items() if c in set(cohort["case_ids"])}
    missing = sorted(set(cohort["case_ids"]) - set(runs))
    pm = protocol_metrics(runs)
    base = reusable_runs(list(runs))
    out, recs = outcomes(runs, cohort["stratum"])
    base_out, _ = outcomes({c: base[c] for c in runs if c in base}, cohort["stratum"]) if base else ({}, None)
    return {
        "tag": tag, "cohort": cohort_name, "cohort_sha256": cohort["case_ids_sha256"], "n_expected": cohort["n_cases"], "n_runs": len(runs), "missing_cases": missing,
        "protocol": pm, "targets": targets_check(pm) if runs else {},
        "before_after": {"phase5_historical": baseline_protocol({c: base[c] for c in runs if c in base}), "phase9a": hardened_for_table(pm, runs)} if base else {},
        "diagnostic_outcomes_observational": {"phase9a": out, "phase5_historical_same_cases": base_out},
        "contract_stratum_counts": dict(Counter(cohort["stratum"][c] for c in runs)),
    }


def render_markdown(rep: dict) -> str:
    pm, t = rep["protocol"], rep["targets"]
    fmt = lambda d: "n/a" if d is None or d.get("rate") is None else f"{d['rate']*100:.1f}% ({d['k']}/{d['n']})"
    L = [f"# Phase 9A report: {rep['tag']} on {rep['cohort']}", "", f"Runs: {rep['n_runs']} of {rep['n_expected']} cases (missing {len(rep['missing_cases'])}). Cohort sha256 `{rep['cohort_sha256'][:16]}`.", "",
         "## Engineering targets (spec section 36)", "", "| Target | Required | Measured | Met |", "|---|---|---|---|"]
    for k, v in t.items():
        L.append(f"| {k} | {v['target']} | {v['measured']} | {v['met']} |")
    ba = rep.get("before_after")
    if ba:
        L += ["", "## Before / after (same cases)", "", "| Metric | Phase 5 historical | Phase 9A |", "|---|---:|---:|"]
        for k in ("invalid_tool_call_traces", "final_repair_required", "structured_id_completion", "traces_with_a_citation_violation", "first_pass_valid_final", "contract_failure_visible",
                  "valid_registered_tool_name_rate", "tool_argument_validity_rate"):
            L.append(f"| {k} | {fmt(ba['phase5_historical'][k])} | {fmt(ba['phase9a'][k])} |")
    L += ["", "## Protocol detail", "", "```json", json.dumps({k: pm[k] for k in ("tool_contract", "final_contract", "grounding", "completion", "efficiency")}, indent=1), "```"]
    o = rep["diagnostic_outcomes_observational"]
    L += ["", "## Diagnostic outcomes (observational; not optimised)", "", "```json", json.dumps(o, indent=1), "```"]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--cohort", required=True, choices=list(cohorts.QUOTAS))
    a = ap.parse_args()
    rep = build_report(a.tag, a.cohort)
    d = COHORT_DIR / "reports"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"report_{a.tag}.json").write_text(json.dumps(rep, indent=1))
    (d / f"report_{a.tag}.md").write_text(render_markdown(rep))
    print(render_markdown(rep)[:6000])
