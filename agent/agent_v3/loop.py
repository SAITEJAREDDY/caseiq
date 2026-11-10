"""The Phase 9A contract-hardened investigation loop (`agent_v3`).

One constrained JSON action per turn; every action and the final answer are validated deterministically before anything happens; nothing is
silently rewritten. Repair budgets: at most 2 tool-contract repairs per run and 1 final-contract repair. Exceeding either ends the run as
CONTRACT_FAILURE with human review required, and no diagnosis is pretended.

Runtime-observable state only: this module never imports an evaluation store, a Phase 6 module or a hidden-truth reader, and it never imports Jev. `backend`,
`llm`, the optional `verifier` (late answer verification) and the optional `triage` callback (early category guidance) are injected, so the loop is fully testable with a
scripted model.
"""
import json
import time

from agent.agent_v2.time_gate import SimClock
from agent.agent_v3 import prompts, triage_hint
from agent.agent_v3.catalog import SUBMIT, action_schema, alias_args, available_tools, canonical_args, validate_action
from agent.agent_v3.config import (
    FINAL_MAX_TOKENS,
    MAX_FINAL_CONTRACT_REPAIRS,
    MAX_REPEATED_SAME_TOOL,
    MAX_TOOL_CALLS,
    MAX_TOOL_CONTRACT_REPAIRS,
    STEP_MAX_TOKENS,
)
from agent.agent_v3.final_contract import contract_failure_final, final_schema, to_phase5_final, validate_final
from agent.agent_v3.registry import CITABLE_KINDS, ObservedEntityRegistry, expose_result, leaked_ids


def _hyp_strings(hyps: list) -> list:
    return [f"{h['label']}:{h['confidence']}" for h in hyps]


def _history_line(step: int, tool: str, args: dict, status: str, n_evidence: int) -> str:
    shown = ", ".join(f"{k}={v}" for k, v in args.items()) or "no arguments"
    return f"{step}. {tool}({shown}) -> {status}" + (f", {n_evidence} evidence item(s)" if n_evidence else "")


def run_case(case_id: str, backend, llm, verifier=None, extra_steps: int = 4, triage=None) -> dict:
    """Runs one investigation. Returns a plain dict for `trace.persist_run` (Phase 5-compatible run shape plus the Phase 9A contract fields).

    `triage(ctx) -> record | None` is an optional EARLY-guidance callback, called once right after the case report is loaded and before any investigation tool runs. It sees the
    case context only. A usable record becomes a provisional category hint in every prompt (never a confirmed category, never evidence); any other record, or None, is a
    fallback and the run is exactly the unchanged workflow. The record and what the agent did with it (`triage_outcome`) are stored with the run. It is a different role from
    `verifier`, which judges the finished answer.

    `verifier(snapshot, round_no) -> {"decision": ..., "message": ...}` is an optional runtime-verifier callback (Phase 9). When it answers
    CONTINUE_INVESTIGATION after round 1, the same session resumes with the verifier's message and `extra_steps` more tool calls, then finalizes and
    is verified once more. There are never more than two rounds. Without a verifier this is the unchanged Phase 9A loop."""
    ctx = backend.case_context()
    if "error" in ctx:
        raise ValueError(ctx["error"])
    clock = SimClock(ctx["created_date"])
    reg = ObservedEntityRegistry(case_id)
    t_start = clock.as_of

    cats, causes = backend.taxonomy()
    for cid, name in cats:
        reg.add("CATEGORY", cid, type="issue_category", display_name=name, source_tool="taxonomy", step=0, clock=t_start)
    for cid, name in causes:
        reg.add("CAUSE", cid, type="root_cause", display_name=name, source_tool="taxonomy", step=0, clock=t_start)

    state = {
        "trace_steps": [], "history": [], "hyps": [], "latest": None, "call_counts": {}, "llm_calls": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "tool_contract_errors": [], "tool_contract_repairs": [], "final_contract_errors": [], "final_contract_repair": None,
        "registry_snapshots": [], "proposals": 0,
    }

    def call_llm(messages, schema, phase, step, attempt, max_tokens):
        res = llm.complete(messages, schema, phase, max_tokens)
        u = state["usage"]
        u["prompt_tokens"] += res.prompt_tokens
        u["completion_tokens"] += res.completion_tokens
        u["total_tokens"] += res.prompt_tokens + res.completion_tokens
        state["llm_calls"].append({"phase": phase, "step": step, "attempt": attempt, "prompt_tokens": res.prompt_tokens,
                                   "completion_tokens": res.completion_tokens, "latency_ms": round(res.latency_ms, 1),
                                   "finish_reason": res.finish_reason, "http_retries": res.http_retries, "raw_output": res.content})
        return res

    # ── step 1: the case report, executed by the harness (it was the first call in 300/300 baseline traces) ─────────────────
    step = 1
    case_report = expose_result(reg, "get_case_context", ctx, step=1, clock=clock.as_of)
    state["trace_steps"].append({
        "step": 1, "sim_clock": clock.as_of, "tool_name": "get_case_context", "args": {}, "args_alias": {}, "hypotheses": [], "hypothesis_state": [],
        "rationale": "", "result_summary": ctx, "latency_ms": 0.0, "status": "ok", "redundant": False, "proposed_by": "harness"})
    state["history"].append(_history_line(1, "get_case_context", {}, "ok (harness)", 0))
    clock.advance()
    state["registry_snapshots"].append(reg.snapshot(1))

    # ── early triage: the ONLY insertion point. After the case report, before the first model-chosen tool; a fallback leaves the hint text empty ─────────────────────
    early_record, hint_text = triage_hint.prepare(triage(ctx) if triage is not None else None, reg)
    cat_names = {e.canonical_id: e.display_name for e in reg.by_kind("CATEGORY")}

    # ── investigation + finalization; repeated once if the verifier asks for more investigation ─────────────────────────────
    budget = MAX_TOOL_CALLS
    tool_repairs_used, error_note, last_repair_idx, feedback = 0, "", None, ""
    verification_rounds, initial_result, additional = [], None, False
    final_alias, final_diag, validation, stop_reason, failure_reason, fstep = None, None, {}, None, None, step

    def seen_ids() -> list:
        return sorted({e.canonical_id for e in reg.by_kind(*CITABLE_KINDS)})

    def build_record() -> dict:
        seen = seen_ids()
        violations = [c for h in final_diag["hypotheses"] for c in h["supporting_evidence"] + h["contradicting_evidence"] if c not in seen]
        if final_diag.get("predicted_causal_change_id") and final_diag["predicted_causal_change_id"] not in seen:
            violations.append(final_diag["predicted_causal_change_id"])
        repair_events = [{"step": r["step"], "kind": "tool_contract_repair", "detail": ",".join(r["error_codes"]) + f" -> {r['outcome']}"} for r in state["tool_contract_repairs"]]
        if state["final_contract_repair"]:
            r = state["final_contract_repair"]
            repair_events.append({"step": r["step"], "kind": "final_contract_repair", "detail": ",".join(r["error_codes"]) + f" -> {r['outcome']}"})
        record = {
            "case_id": case_id, "stop_reason": stop_reason, "num_tool_calls": step, "num_llm_calls": len(state["llm_calls"]), "token_usage": state["usage"],
            "trace_steps": state["trace_steps"], "final_diagnosis": final_diag, "final_status": final_diag["status"], "final_alias_form": final_alias,
            "citation_violations": violations, "evidence_ids_seen": seen, "repair_events": repair_events,
            "tool_proposals": state["proposals"], "tool_contract_errors": state["tool_contract_errors"], "tool_contract_repairs": state["tool_contract_repairs"],
            "final_contract_errors": state["final_contract_errors"], "final_contract_repair": state["final_contract_repair"],
            "registry_snapshots": state["registry_snapshots"], "alias_mappings": reg.mapping(), "validation_result": validation,
            "contract_failure": failure_reason, "llm_calls": state["llm_calls"], "sim_clock_end": clock.as_of, "tool_budget": budget,
            "verification_rounds": verification_rounds, "initial_result": initial_result, "additional_investigation_performed": additional,
        }
        if triage is not None:      # keys exist only when the callback was supplied, so a baseline record keeps its exact shape
            record.update(early_triage=early_record, triage_hint_text=hint_text or None, triage_prompt_version=triage_hint.TRIAGE_PROMPT_VERSION,
                          triage_outcome=triage_hint.outcome(early_record, final_diag, cat_names))
        return record

    for round_no in range(1, (2 if verifier is not None else 1) + 1):
        stop_reason, failure_reason = None, None
        while step < budget:
            case_report = expose_result(reg, "get_case_context", ctx, step=1, clock=t_start)  # re-render: a prose reference upgrades once its entity is observed
            msgs = prompts.step_messages(case_report, reg, state["history"], state["hyps"], state["latest"], step + 1, error_note, feedback, budget, triage_hint=hint_text)
            res = call_llm(msgs, action_schema(reg), "action", step + 1, tool_repairs_used, STEP_MAX_TOKENS)
            state["proposals"] += 1
            action, errors = validate_action(res.content, reg)
            if last_repair_idx is not None:
                state["tool_contract_repairs"][last_repair_idx]["outcome"] = "accepted" if not errors else "rejected_again"
                last_repair_idx = None
            if errors:
                state["tool_contract_errors"].append({"step": step + 1, "errors": errors, "raw_output": res.content[:1500], "finish_reason": res.finish_reason})
                if tool_repairs_used >= MAX_TOOL_CONTRACT_REPAIRS:
                    stop_reason, failure_reason = "tool_contract_repair_budget_exhausted", "tool contract repair budget exhausted"
                    break
                tool_repairs_used += 1
                state["tool_contract_repairs"].append({"step": step + 1, "repair_number": tool_repairs_used, "error_codes": [e["code"] for e in errors], "outcome": "pending"})
                last_repair_idx = len(state["tool_contract_repairs"]) - 1
                error_note = prompts.tool_error_note(errors, available_tools(reg))
                continue
            error_note = ""
            state["hyps"] = action["hypotheses"]
            tool = action["tool"]
            if tool == SUBMIT:
                stop_reason = "model_submitted"
                break

            step += 1
            as_of = clock.as_of
            cargs, aargs = canonical_args(action, reg), alias_args(action)
            key = f"{tool}:{json.dumps(aargs, sort_keys=True)}"
            state["call_counts"][key] = state["call_counts"].get(key, 0) + 1
            redundant = state["call_counts"][key] > MAX_REPEATED_SAME_TOOL
            t0 = time.time()
            if redundant:
                canonical_result, status = {"note": "redundant query -- identical arguments already used this run, no new information returned"}, "redundant"
            else:
                try:
                    canonical_result = backend.execute(tool, cargs, as_of)
                    status = "error" if isinstance(canonical_result, dict) and "error" in canonical_result else "ok"
                except Exception as e:  # a backend fault is an execution error, not a contract violation
                    canonical_result, status = {"error": str(e)}, "error"
            before = len(reg.by_kind(*CITABLE_KINDS))
            exposed = canonical_result if redundant else expose_result(reg, tool, canonical_result, step=step, clock=as_of, name_lookup=backend.component_names)
            leaks = leaked_ids(exposed)
            if leaks:
                raise RuntimeError(f"canonical ids reached the model-facing result of {tool}: {leaks[:3]}")
            added = len(reg.by_kind(*CITABLE_KINDS)) - before
            clock.advance()
            state["latest"] = {"step": step, "tool": tool, "result": exposed}
            state["history"].append(_history_line(step, tool, aargs, status, added))
            state["registry_snapshots"].append(reg.snapshot(step))
            state["trace_steps"].append({
                "step": step, "sim_clock": as_of, "tool_name": tool, "args": cargs, "args_alias": aargs, "hypotheses": _hyp_strings(action["hypotheses"]),
                "hypothesis_state": action["hypotheses"], "rationale": "", "result_summary": canonical_result,
                "latency_ms": round(res.latency_ms + (time.time() - t0) * 1000, 1), "status": status, "redundant": redundant, "proposed_by": "model"})
        else:
            stop_reason = "tool_budget_exhausted"

        # ── finalization ────────────────────────────────────────────────────────────────────────────────────────────────────
        final_alias, final_diag = None, None
        validation = {"first_pass_ok": None, "errors_first": [], "repair_used": False, "final_ok": None, "errors_final": []}
        if failure_reason is None:
            forced = stop_reason == "tool_budget_exhausted"
            fstep = step + 1
            schema = final_schema(reg)
            case_report = expose_result(reg, "get_case_context", ctx, step=1, clock=t_start)
            msgs = prompts.final_messages(case_report, reg, state["history"], state["hyps"], forced=forced, feedback=feedback, triage_hint=hint_text)
            res = call_llm(msgs, schema, "final", fstep, 0, FINAL_MAX_TOKENS)
            final_alias, errors = validate_final(res.content, reg)
            validation.update(first_pass_ok=not errors, errors_first=errors)
            if errors:
                state["final_contract_errors"].append({"step": fstep, "attempt": 1, "errors": errors, "raw_output": res.content[:3000], "finish_reason": res.finish_reason})
                if MAX_FINAL_CONTRACT_REPAIRS >= 1:
                    res2 = call_llm(prompts.final_messages(case_report, reg, state["history"], state["hyps"], forced=forced, feedback=feedback,
                                                           error_note=prompts.final_error_note(errors), triage_hint=hint_text), schema, "final", fstep, 1, FINAL_MAX_TOKENS)
                    final_alias, errors2 = validate_final(res2.content, reg)
                    validation.update(repair_used=True, errors_final=errors2)
                    state["final_contract_repair"] = {"step": fstep, "error_codes": [e["code"] for e in errors], "outcome": "accepted" if not errors2 else "rejected"}
                    if errors2:
                        state["final_contract_errors"].append({"step": fstep, "attempt": 2, "errors": errors2, "raw_output": res2.content[:3000], "finish_reason": res2.finish_reason})
                        failure_reason, stop_reason = "final answer failed validation after the one allowed repair", "final_contract_failure"
                else:
                    failure_reason, stop_reason = "final answer failed validation", "final_contract_failure"
            validation["final_ok"] = failure_reason is None
            if failure_reason is None:
                final_diag = to_phase5_final(final_alias, reg)
                state["trace_steps"].append({
                    "step": fstep, "sim_clock": clock.as_of, "tool_name": SUBMIT, "args": {}, "args_alias": {}, "hypotheses": _hyp_strings(final_alias["hypotheses"]),
                    "hypothesis_state": final_alias["hypotheses"], "rationale": "", "result_summary": "submitted (forced)" if forced else "submitted",
                    "latency_ms": round(res.latency_ms, 1), "status": "ok", "redundant": False, "proposed_by": "model"})
                step = fstep
        if failure_reason is not None:
            final_alias = None
            final_diag = contract_failure_final(failure_reason)
            validation["final_ok"] = False
            break
        if verifier is None:
            break

        # ── runtime verification (Phase 9) ──────────────────────────────────────────────────────────────────────────────────
        verdict = verifier(build_record(), round_no)
        verification_rounds.append({"round": round_no, **verdict})
        if round_no == 1:
            initial_result = {"final_status": final_diag["status"], "final_alias_form": final_alias, "final_diagnosis": final_diag,
                              "validation_result": dict(validation), "num_tool_calls": step, "evidence_ids_seen": seen_ids()}
            if triage is not None:
                initial_result["triage_outcome"] = triage_hint.outcome(early_record, final_diag, cat_names)
        if verdict.get("decision") == "CONTINUE_INVESTIGATION" and round_no == 1:
            additional, feedback = True, verdict["message"]
            state["trace_steps"].pop()          # the round-1 submit step: the initial answer is kept in `initial_result`
            step = fstep - 1
            budget = step + extra_steps
            continue
        break

    return build_record()
