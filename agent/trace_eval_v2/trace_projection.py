"""The model-facing projection of a completed trace (`trace_projection_v1`). Everything Jev and the LLM judge see comes from here.

Boundary. This module reads only what a reviewer could observe after the run: the agent's instructions, the case as reported, the agent's tool
calls and results, its structured hypotheses, its final structured answer, and the observable evidence that was available to it. It never imports
hidden truth (checked by validate_boundaries.py). It also never includes the agent's free-text `rationale`: the projection keeps structured
hypothesis state and drops free-text reasoning, so the evaluators are never asked to read or judge a chain of thought.

Identifier projection (`trace_alias_v1`). Phase 7 showed that model decisions can depend on identifier structure, so every internal id (signals,
changes, incidents, components, teams, cases, customers, taxonomy ids, composite telemetry keys) is replaced by an opaque alias derived from
sha256(scheme | salt | id). An alias carries the entity kind (SIG_, CHG_, ...; the kind is already visible from the tool that returned it) and nothing
else: it does not encode order, number, time, component or role. Event type, timestamps, component, text and every other observable field are
left as they are. The mapping is kept evaluator-side; Jev and the LLM judge get the identical projection.
"""
import hashlib
import json

from agent.trace_eval_v2.config import ALIAS_SCHEME, PROJECTION_VERSION
from agent.trace_eval_v2.models import ID_RE, Trace, id_kind

ALPHABET = "bcdfghjkmnpqrstvwxz23456789"  # no vowels: no accidental words
MAX_TEXT = 280
INVENTORY_ORDER = {"signal": 0, "change": 1, "deployment": 2, "incident": 3, "configuration_snapshot": 4}

_KIND_PREFIX = {"SIG": "SIG", "CHG": "CHG", "INC": "INC", "SHE": "SHE", "CFG": "CFG", "TEL": "TEL", "KB": "KB", "CASE": "CASE", "CMP": "CMP",
                "TEAM": "TEAM", "CAT": "CAT", "SUB": "SUB", "RCF": "RCF", "ENT": "ENT", "CUST": "CUST", "PROD": "PROD", "AGT": "AGT"}


class Aliaser:
    """Deterministic, injective id -> alias map for one packet. `salt` changes the whole mapping (used by perturbation P6)."""

    def __init__(self, salt: str):
        self.salt = salt
        self.forward, self.reverse = {}, {}

    def alias(self, canonical_id: str) -> str:
        if canonical_id in self.forward:
            return self.forward[canonical_id]
        kind = id_kind(canonical_id) or "ID"
        bump = 0
        while True:
            n = int.from_bytes(hashlib.sha256(f"{ALIAS_SCHEME}|{self.salt}|{canonical_id}|{bump}".encode()).digest()[:8], "big")
            chars = []
            for _ in range(5):
                n, r = divmod(n, len(ALPHABET))
                chars.append(ALPHABET[r])
            candidate = f"{_KIND_PREFIX.get(kind, kind)}_{''.join(chars)}"
            if candidate not in self.reverse:
                break
            bump += 1
        self.forward[canonical_id] = candidate
        self.reverse[candidate] = canonical_id
        return candidate

    def text(self, s: str) -> str:
        return ID_RE.sub(lambda m: self.alias(m.group(0)), s)

    def obj(self, x):
        """Alias every id inside strings, recursively. Dict keys are field names, never ids, and are left alone."""
        if isinstance(x, str):
            return self.text(x)
        if isinstance(x, dict):
            return {k: self.obj(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [self.obj(v) for v in x]
        return x


def _short(x):
    if isinstance(x, str):
        return x if len(x) <= MAX_TEXT else x[: MAX_TEXT - 1] + "…"
    if isinstance(x, dict):
        return {k: _short(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_short(v) for v in x[:8]]
    return x


def build_review_context(session, case_id: str, as_of: str) -> dict:
    """The observable material a reviewer sees next to the trace: the ticket as reported and the evidence that was available to the agent's tools
    at the end of its run. Read through the agent's own time-gated query functions, so nothing the agent could not have retrieved is included."""
    from agent.agent_v2.tools import q_active_incidents, q_case_context, q_configuration_history, q_deployment_history, q_recent_changes, q_technical_signals, q_telemetry

    ctx = q_case_context(session, case_id)
    ticket = {k: ctx.get(k) for k in ("title", "description", "environment", "region", "reported_business_impact", "reported_affected_users", "priority",
                                      "created_date", "customer_tier", "customer_industry", "customer_company_size", "reported_product_name", "reported_symptoms")}
    inventory = []
    for row in q_technical_signals(session, case_id, as_of).get("signals", []):
        inventory.append({"id": row["evidence_id"], "kind": "signal", "type": row["signal_type"], "component": row["component_id"], "time": row["timestamp"], "text": row["message"]})
    for row in q_recent_changes(session, case_id, as_of).get("recent_changes", []):
        inventory.append({"id": row["evidence_id"], "kind": "change", "type": row["change_type"], "component": row["component_id"], "time": row["started_at"],
                          "status": row["status"], "time_proximity_hours": row["time_proximity_hours"], "scope_match": row["scope_match"]})
    for row in q_deployment_history(session, case_id, as_of).get("deployments", []):
        inventory.append({"id": row["evidence_id"], "kind": "deployment", "type": "deployment", "component": row["component_id"], "time": row["started_at"],
                          "text": f"version {row['version_from']} to {row['version_to']}, {row['rollout_strategy']} rollout", "status": row["status"],
                          "time_proximity_hours": row["time_proximity_hours"]})
    for row in q_active_incidents(session, case_id, as_of).get("incidents", []):
        inventory.append({"id": row["evidence_id"], "kind": "incident", "type": "incident", "component": ",".join(row["affected_components"] or []), "time": row["started_at"],
                          "text": row["summary"], "severity": row["severity"], "status": row["status"], "region": row["region"]})
    for row in q_configuration_history(session, case_id, as_of).get("configuration_snapshots", []):
        inventory.append({"id": row["evidence_id"], "kind": "configuration_snapshot", "type": row["config_key"], "component": row["component_id"], "time": row["snapshot_at"],
                          "text": f"{row['config_key']} = {row['config_value']}" + (f" ({row['note']})" if row.get("note") else "")})
    categories = q_telemetry(session, case_id, as_of).get("available_metric_categories", [])
    return {"ticket": ticket, "inventory": inventory, "telemetry_categories_with_data": categories, "as_of": as_of}


def _compact_result(tool: str, result, al: Aliaser):
    if tool == "get_case_context":
        return "the case context (see case_as_reported)"
    if isinstance(result, dict) and "error" in result:
        return {"error": al.text(str(result["error"]).split("\n")[0][:240])}
    return al.obj(_short(result))


def project(trace: Trace, context: dict, alias_salt: str = "0") -> tuple:
    """Returns (state, aliaser). `state` is the exact JSON-able object sent to both judges; `aliaser.reverse` maps aliases back for the scorer only."""
    from agent.agent_v2.prompts import SYSTEM_PROMPT

    al = Aliaser(f"{trace.case_id}|{alias_salt}")
    retrieved = trace.retrieved_ids
    first_step = trace.first_retrieval_step()
    retrieved_set = set(retrieved)

    steps = []
    for s in trace.diagnostic_steps:
        entry = {"step": s.n, "clock": s.clock, "tool": s.tool, "arguments": al.obj(s.args), "outcome": s.status,
                 "result": _compact_result(s.tool, s.result, al), "returned_evidence": [al.alias(e) for e in s.evidence],
                 "hypotheses_stated": [{k: (al.text(v) if isinstance(v, str) else v) for k, v in h.items() if k in ("label", "confidence")} for h in s.hypotheses]}
        steps.append(entry)
    submit = trace.submit_step
    final = trace.final or {}
    hypotheses = [{"label": al.text(h.get("label", "")), "description": al.text(h.get("description", "")), "confidence": h.get("confidence"), "status": h.get("status"),
                   "supporting_evidence": [al.alias(e) for e in h.get("supporting_evidence") or []],
                   "contradicting_evidence": [al.alias(e) for e in h.get("contradicting_evidence") or []]} for h in final.get("hypotheses") or []]
    predicted = {k: (al.text(v) if isinstance(v, str) else v) for k, v in final.items() if k.startswith("predicted_") or k in ("recommended_team_id",)}
    confidences = {k: v for k, v in final.items() if k.endswith("_confidence") and k != "overall_confidence"}
    cited = {e for h in final.get("hypotheses") or [] for e in list(h.get("supporting_evidence") or []) + list(h.get("contradicting_evidence") or [])}
    if final.get("predicted_causal_change_id"):
        cited.add(final["predicted_causal_change_id"])
    final_output = {
        "hypotheses": hypotheses, "structured_predictions": predicted, "prediction_confidences": confidences,
        "evidence_sufficiency_claimed": final.get("evidence_sufficiency"), "overall_confidence": final.get("overall_confidence"),
        "human_review_required": final.get("human_review_required"), "human_review_reason": al.text(final.get("human_review_reason") or "") or None,
        "recommended_next_action": al.text(final.get("recommended_next_action") or ""), "evidence_summary": al.text(final.get("evidence_summary") or ""),
        "unresolved_uncertainties": [al.text(u) for u in final.get("unresolved_uncertainties") or []],
        "cited_evidence_never_retrieved": sorted(al.alias(e) for e in cited if e not in retrieved_set),
        "submitted_at_clock": submit.clock if submit else None,
    }
    invalid = [{"step": s.n, "tool": s.tool, "problem": s.error_kind} for s in trace.diagnostic_steps if s.status == "error"]
    inventory = []
    for item in context["inventory"]:
        entry = {k: (al.text(v) if isinstance(v, str) else v) for k, v in item.items() if k != "id"}
        entry["id"] = al.alias(item["id"])
        entry["retrieved_by_agent"] = item["id"] in retrieved_set
        entry["first_retrieved_at_step"] = first_step.get(item["id"])
        inventory.append(entry)
    inventory.sort(key=lambda e: (INVENTORY_ORDER.get(e["kind"], 9), e.get("time") or "", e["id"]))

    state = {
        "packet_version": PROJECTION_VERSION,
        "agent_instructions": SYSTEM_PROMPT,
        "available_tools": sorted({"get_case_context", "get_customer_deployment", "get_component_topology", "get_technical_signals", "get_telemetry", "get_recent_changes",
                                   "get_deployment_history", "get_configuration_history", "get_service_health", "get_active_incidents", "get_similar_cases",
                                   "search_knowledge_base", "get_team_capability", "get_agent_availability", "submit_diagnosis"}),
        "case_as_reported": al.obj(context["ticket"]),
        "investigation": {
            "tool_budget": 10, "stop_reason": trace.stop_reason, "diagnostic_tool_calls": len(trace.diagnostic_steps),
            "steps": steps, "invalid_tool_events": invalid, "redundant_calls": sum(1 for s in trace.diagnostic_steps if s.redundant),
            "repair_events": [{"step": e.get("step"), "kind": e.get("kind"), "detail": al.text(str(e.get("detail", ""))[:200])} for e in trace.repair_events],
        },
        "final_output": final_output,
        "available_evidence_inventory": {"as_of": context["as_of"], "items": inventory, "telemetry_categories_with_data": context["telemetry_categories_with_data"],
                                         "note": "Observable evidence that the agent's tools could return by the end of the run. 'retrieved_by_agent' says whether this trace retrieved it."},
    }
    return state, al


def state_json(state: dict) -> str:
    return json.dumps(state, default=str, ensure_ascii=False)


def approx_tokens(state: dict) -> int:
    """Rough size (characters / 4). The providers' own usage figures are what cost accounting uses."""
    return len(state_json(state)) // 4
