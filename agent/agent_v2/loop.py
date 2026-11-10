"""The Phase 5 baseline agent loop: one LLM call per investigation step,
hypothesis state carried on every tool call, deterministic sim-clock
time-gating, redundancy/budget enforcement, forced-submit on exhaustion.
"""
import json
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agent.agent_v2.config import KEEP_LAST_N_FULL_TOOL_RESULTS, MAX_REPEATED_SAME_TOOL, MAX_TOOL_CALLS
from agent.agent_v2.llm import get_llm, invoke_with_retry
from agent.agent_v2.prompts import SYSTEM_PROMPT
from agent.agent_v2.schemas import FinalDiagnosis
from agent.agent_v2.time_gate import SimClock
from agent.agent_v2.tools import make_tools, q_case_context


def _collect_evidence_ids(obj, out: set):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "evidence_id" and isinstance(v, str):
                out.add(v)
            else:
                _collect_evidence_ids(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_evidence_ids(item, out)


def _normalize_hypotheses(raw):
    """Some open-weight models occasionally double-encode array-typed tool
    arguments as a JSON string instead of a true array (observed with
    Llama-3.3-70B-Instruct-Turbo via Together AI). Recover gracefully rather
    than let a stray string get iterated character-by-character."""
    if isinstance(raw, list):
        return [str(h) for h in raw]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(h) for h in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return [raw] if raw else []
    return []


def _args_key(tool_name: str, args: dict) -> str:
    scoped = {k: v for k, v in args.items() if k not in ("hypotheses", "rationale")}
    return f"{tool_name}:{json.dumps(scoped, sort_keys=True, default=str)}"


def _usage_from_response(resp) -> dict:
    usage = (resp.response_metadata or {}).get("token_usage") or (resp.response_metadata or {}).get("usage") or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def _trimmed_for_llm(messages: list) -> list:
    """Full message history is kept for the trace; the model only sees the
    most recent KEEP_LAST_N_FULL_TOOL_RESULTS tool results in full -- older
    ones are collapsed to a short placeholder so a long investigation
    doesn't exhaust Groq's 8000 TPM budget by itself (empirically, a 10-step
    run's uncompacted history alone approached the entire per-request cap).
    """
    tool_indices = [i for i, m in enumerate(messages) if isinstance(m, ToolMessage)]
    to_collapse = set(tool_indices[:-KEEP_LAST_N_FULL_TOOL_RESULTS]) if KEEP_LAST_N_FULL_TOOL_RESULTS > 0 else set(tool_indices)
    trimmed = []
    for i, m in enumerate(messages):
        if i in to_collapse:
            trimmed.append(ToolMessage(content="[earlier tool result omitted to save context -- see run trace]", tool_call_id=m.tool_call_id))
        else:
            trimmed.append(m)
    return trimmed


def _repair_final_diagnosis_args(args: dict) -> dict:
    """Best-effort repair for the same class of schema-compliance slips
    observed from Llama-3.3-70B-Instruct-Turbo on the terminal call (a
    non-enum hypothesis status like "open", missing overall_confidence/
    evidence_summary) -- tried once, after a direct validation failure,
    before falling back to _fallback_diagnosis."""
    repaired = dict(args)
    raw_hyps = repaired.get("hypotheses", [])
    if isinstance(raw_hyps, str):
        try:
            raw_hyps = json.loads(raw_hyps)
        except (json.JSONDecodeError, TypeError):
            raw_hyps = []
    fixed_hyps = []
    for h in raw_hyps if isinstance(raw_hyps, list) else []:
        if not isinstance(h, dict):
            continue
        h = dict(h)
        if h.get("status") not in ("active", "rejected", "confirmed"):
            h["status"] = "active"
        h.setdefault("label", "unspecified_hypothesis")
        h.setdefault("confidence", 0.5)
        h.setdefault("description", "")
        h.setdefault("supporting_evidence", [])
        h.setdefault("contradicting_evidence", [])
        fixed_hyps.append(h)
    repaired["hypotheses"] = fixed_hyps

    if not isinstance(repaired.get("overall_confidence"), (int, float)):
        confs = [h["confidence"] for h in fixed_hyps if isinstance(h.get("confidence"), (int, float))]
        repaired["overall_confidence"] = max(confs) if confs else 0.3
    if not repaired.get("evidence_summary"):
        repaired["evidence_summary"] = repaired.get("rationale") or "No summary provided by the agent."
    if not repaired.get("recommended_next_action"):
        repaired["recommended_next_action"] = "request human review"
    repaired.setdefault("evidence_sufficiency", "partial")
    repaired.setdefault("human_review_required", True)
    repaired.setdefault("rationale", "")
    return repaired


def _fallback_diagnosis(reason: str) -> FinalDiagnosis:
    return FinalDiagnosis(
        hypotheses=[],
        rationale=f"Fallback: {reason}",
        evidence_sufficiency="insufficient",
        overall_confidence=0.0,
        recommended_next_action="escalate to engineering for manual investigation",
        human_review_required=True,
        human_review_reason=reason,
        evidence_summary="The agent could not complete a normal investigation loop.",
        unresolved_uncertainties=[reason],
    )


def run_case(case_id: str, session) -> dict:
    """Runs one full investigation. `session` is an open Neo4j session
    (caller owns the driver/session lifecycle). Returns a plain dict ready
    for trace.persist_run()."""
    ctx = q_case_context(session, case_id)
    if "error" in ctx:
        raise ValueError(ctx["error"])

    sim_clock = SimClock(ctx["created_date"])
    tools = make_tools(session, case_id, sim_clock)
    tools_by_name = {t.name: t for t in tools}
    submit_tool = tools_by_name["submit_diagnosis"]

    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Investigate case {case_id}. Begin your investigation now."),
    ]

    trace_steps = []
    seen_evidence_ids: set = set()
    call_counts: dict = {}
    repair_events: list = []
    step = 0
    llm_calls = 0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    final_diagnosis = None
    stop_reason = None

    while step < MAX_TOOL_CALLS:
        t0 = time.time()
        resp = invoke_with_retry(llm_with_tools, _trimmed_for_llm(messages))
        llm_calls += 1
        latency_ms = (time.time() - t0) * 1000
        u = _usage_from_response(resp)
        for k in usage_total:
            usage_total[k] += u[k]

        if not resp.tool_calls:
            messages.append(resp)
            messages.append(HumanMessage(content="You must call exactly one of the provided tools now. Try again."))
            t1 = time.time()
            resp = invoke_with_retry(llm_with_tools, _trimmed_for_llm(messages))
            llm_calls += 1
            latency_ms += (time.time() - t1) * 1000
            u2 = _usage_from_response(resp)
            for k in usage_total:
                usage_total[k] += u2[k]
            if not resp.tool_calls:
                stop_reason = "agent_failed_to_call_tool"
                final_diagnosis = _fallback_diagnosis(stop_reason)
                break

        messages.append(resp)
        submitted_this_turn = None

        for tool_call in resp.tool_calls:
            step += 1
            name = tool_call["name"]
            args = tool_call.get("args", {}) or {}
            as_of_at_call = sim_clock.as_of

            if name == "submit_diagnosis":
                hypotheses = args.get("hypotheses", [])
                rationale = args.get("rationale", "") or ""
                try:
                    diag = FinalDiagnosis(**args)
                except Exception as e1:
                    try:
                        diag = FinalDiagnosis(**_repair_final_diagnosis_args(args))
                        repair_events.append({
                            "step": step, "kind": "final_diagnosis_repair",
                            "detail": f"direct validation failed ({e1}); repaired args validated",
                        })
                    except Exception as e2:
                        diag = _fallback_diagnosis(f"submit_diagnosis args failed validation even after repair: {e2} (original: {e1})")
                        repair_events.append({
                            "step": step, "kind": "final_diagnosis_fallback",
                            "detail": f"direct validation failed ({e1}); repair also failed ({e2})",
                        })
                messages.append(ToolMessage(content="diagnosis submitted", tool_call_id=tool_call["id"]))
                trace_steps.append({
                    "step": step, "sim_clock": as_of_at_call, "tool_name": name, "args": args,
                    "hypotheses": hypotheses, "rationale": rationale,
                    "result_summary": "submitted", "latency_ms": round(latency_ms, 1),
                    "status": "ok", "redundant": False,
                })
                submitted_this_turn = diag
                continue

            raw_hypotheses = args.get("hypotheses")
            hypotheses = _normalize_hypotheses(raw_hypotheses)
            if not isinstance(raw_hypotheses, list):
                repair_events.append({
                    "step": step, "kind": "hypothesis_normalization",
                    "detail": f"tool={name}: hypotheses arg was {type(raw_hypotheses).__name__}, not a list; coerced",
                })
            rationale = args.get("rationale", "") or ""
            args["hypotheses"] = hypotheses
            args["rationale"] = rationale

            key = _args_key(name, args)
            call_counts[key] = call_counts.get(key, 0) + 1
            redundant = call_counts[key] > MAX_REPEATED_SAME_TOOL

            if redundant:
                result = {"note": "redundant query -- identical arguments already used this run, no new information returned"}
                status = "redundant"
            elif name not in tools_by_name:
                result = {"error": f"unknown tool '{name}'. Valid tools are: {sorted(tools_by_name.keys())}"}
                status = "error"
            else:
                try:
                    result = tools_by_name[name].invoke(args)
                    status = "ok"
                except Exception as e:
                    result = {"error": str(e)}
                    status = "error"

            _collect_evidence_ids(result, seen_evidence_ids)
            sim_clock.advance()

            messages.append(ToolMessage(content=json.dumps(result, default=str), tool_call_id=tool_call["id"]))
            trace_steps.append({
                "step": step, "sim_clock": as_of_at_call, "tool_name": name, "args": args,
                "hypotheses": hypotheses, "rationale": rationale,
                "result_summary": result, "latency_ms": round(latency_ms, 1),
                "status": status, "redundant": redundant,
            })

            if step >= MAX_TOOL_CALLS and submitted_this_turn is None:
                break

        if submitted_this_turn is not None:
            final_diagnosis = submitted_this_turn
            stop_reason = "model_submitted"
            break
    else:
        stop_reason = "tool_budget_exhausted"

    if final_diagnosis is None and stop_reason == "tool_budget_exhausted":
        forced_llm = llm.bind_tools([submit_tool])
        messages.append(HumanMessage(
            content="Investigation budget exhausted. Call submit_diagnosis now with your best assessment "
            "based on everything gathered so far."
        ))
        try:
            t0 = time.time()
            resp = invoke_with_retry(forced_llm, _trimmed_for_llm(messages))
            llm_calls += 1
            latency_ms = (time.time() - t0) * 1000
            u = _usage_from_response(resp)
            for k in usage_total:
                usage_total[k] += u[k]
            if resp.tool_calls:
                args = resp.tool_calls[0].get("args", {}) or {}
                try:
                    final_diagnosis = FinalDiagnosis(**args)
                except Exception as e1:
                    try:
                        final_diagnosis = FinalDiagnosis(**_repair_final_diagnosis_args(args))
                        repair_events.append({
                            "step": step + 1, "kind": "final_diagnosis_repair",
                            "detail": f"forced-submit direct validation failed ({e1}); repaired args validated",
                        })
                    except Exception as e2:
                        final_diagnosis = _fallback_diagnosis(f"forced submit args failed validation even after repair: {e2} (original: {e1})")
                        repair_events.append({
                            "step": step + 1, "kind": "final_diagnosis_fallback",
                            "detail": f"forced-submit direct validation failed ({e1}); repair also failed ({e2})",
                        })
                trace_steps.append({
                    "step": step + 1, "sim_clock": sim_clock.as_of, "tool_name": "submit_diagnosis",
                    "args": args, "hypotheses": args.get("hypotheses", []), "rationale": args.get("rationale", ""),
                    "result_summary": "submitted (forced)", "latency_ms": round(latency_ms, 1),
                    "status": "ok", "redundant": False,
                })
            else:
                final_diagnosis = _fallback_diagnosis("tool_budget_exhausted and forced submit produced no tool call")
        except Exception as e:
            final_diagnosis = _fallback_diagnosis(f"tool_budget_exhausted and forced submit failed: {e}")

    citation_violations = []
    for hyp in final_diagnosis.hypotheses:
        for ev_id in list(hyp.supporting_evidence) + list(hyp.contradicting_evidence):
            if ev_id not in seen_evidence_ids:
                citation_violations.append(ev_id)
    if final_diagnosis.predicted_causal_change_id and final_diagnosis.predicted_causal_change_id not in seen_evidence_ids:
        citation_violations.append(final_diagnosis.predicted_causal_change_id)

    return {
        "case_id": case_id,
        "stop_reason": stop_reason,
        "num_tool_calls": step,
        "num_llm_calls": llm_calls,
        "token_usage": usage_total,
        "trace_steps": trace_steps,
        "final_diagnosis": final_diagnosis.model_dump(),
        "citation_violations": citation_violations,
        "evidence_ids_seen": sorted(seen_evidence_ids),
        "repair_events": repair_events,
    }
