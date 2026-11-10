"""Decision-specific observable-state projections (spec section 23). Reuses
agent/agent_v2/tools.py's RAW query functions directly (not the LangChain
StructuredTool wrappers) plus agent/agent_v2/time_gate.py::SimClock -- the
exact same time-gated, bounded, read-only data path Phase 5's agent uses,
so Phase 7's boundary is Phase 5's boundary, not a new one to re-prove.

Never imports agent.eval_v2 or data.eval.eval_store (checked by
validate_boundaries.py) -- everything here is built from what a real
support engineer or the Phase 5 agent could observe at `as_of`.
"""
from agent.agent_v2.tools import (
    q_active_incidents,
    q_case_context,
    q_component_topology,
    q_configuration_history,
    q_customer_deployment,
    q_deployment_history,
    q_recent_changes,
    q_similar_cases,
    q_technical_signals,
    q_telemetry,
)


def _ticket_block(ctx: dict) -> dict:
    return {
        "title": ctx.get("title"),
        "description": ctx.get("description"),
        "reported_symptoms": ctx.get("reported_symptoms"),
        "environment": ctx.get("environment"),
        "region": ctx.get("region"),
        "reported_business_impact": ctx.get("reported_business_impact"),
        "reported_affected_users": ctx.get("reported_affected_users"),
        "priority": ctx.get("priority"),
    }


def _customer_block(ctx: dict) -> dict:
    return {"tier": ctx.get("customer_tier"), "industry": ctx.get("customer_industry"), "company_size": ctx.get("customer_company_size")}


def _product_block(ctx: dict) -> dict:
    return {"id": ctx.get("reported_product_id"), "name": ctx.get("reported_product_name")}


def _deployed_components(session, case_id: str, as_of: str) -> list:
    dep = q_customer_deployment(session, case_id)
    comps = set()
    for d in dep.get("deployments", []):
        comps.update(d.get("product_components") or [])
    return sorted(comps)


def get_case_context(session, case_id: str) -> dict:
    """Thin re-export so callers only need agent.jev_v2.state_builder, not
    agent.agent_v2.tools directly."""
    return q_case_context(session, case_id)


def issue_category_state(session, case_id: str, as_of: str) -> dict:
    ctx = q_case_context(session, case_id)
    signals = q_technical_signals(session, case_id, as_of)
    return {
        "ticket": _ticket_block(ctx),
        "customer": _customer_block(ctx),
        "reported_product": _product_block(ctx),
        "signal_count": signals.get("count", 0),
        "signal_types": sorted({s.get("signal_type") for s in signals.get("signals", [])}),
    }


def _technical_block(session, case_id: str, as_of: str) -> dict:
    signals = q_technical_signals(session, case_id, as_of)
    telemetry = q_telemetry(session, case_id, as_of)
    return {
        "signals": [{"signal_type": s.get("signal_type"), "message": s.get("message"), "component_id": s.get("component_id"), "timestamp": s.get("timestamp")} for s in signals.get("signals", [])],
        "telemetry_categories_with_data": telemetry.get("available_metric_categories", []),
    }


def _evidence_sufficiency_technical_block(session, case_id: str, as_of: str) -> dict:
    """Observable evidence projection for the v2 sufficiency question.

    The v1 projection exposed only telemetry *categories*.  Phase 2's label
    is partly driven by whether clear telemetry anomalies exist, so that
    omitted the observable fact most directly relevant to the question.
    This projection uses the existing time-gated raw tool to summarize
    findings; it never exposes Phase 2's causal-signal/change labels.
    """
    base = _technical_block(session, case_id, as_of)
    telemetry_findings = []
    for category in base["telemetry_categories_with_data"]:
        telemetry_findings.extend(q_telemetry(session, case_id, as_of, metric_category=category).get("telemetry_findings", []))
    abnormal = [f for f in telemetry_findings if f.get("status") == "abnormal"]
    return {
        **base,
        "telemetry_summary": {
            "finding_count": len(telemetry_findings),
            "abnormal_finding_count": len(abnormal),
            "abnormal_findings": [
                {"metric_code": f.get("metric_code"), "component_id": f.get("component_id"), "direction": f.get("direction")}
                for f in abnormal
            ],
        },
    }


def _operational_block(session, case_id: str, as_of: str) -> dict:
    changes = q_recent_changes(session, case_id, as_of)
    deployments = q_deployment_history(session, case_id, as_of)
    incidents = q_active_incidents(session, case_id, as_of)
    return {
        "recent_changes": [{"change_id": c["evidence_id"], "change_type": c.get("change_type"), "component_id": c.get("component_id"), "started_at": c.get("started_at"), "time_proximity_hours": c.get("time_proximity_hours")} for c in changes.get("recent_changes", [])],
        "recent_deployments": [{"deployment_id": d["evidence_id"], "component_id": d.get("component_id"), "started_at": d.get("started_at")} for d in deployments.get("deployments", [])],
        "active_incidents_summary": [{"region": i.get("region"), "severity": i.get("severity"), "status": i.get("status")} for i in incidents.get("incidents", [])],
    }


def _graph_block(session, case_id: str, as_of: str, component_ids: list) -> dict:
    topology = []
    for cid in component_ids[:5]:
        t = q_component_topology(session, cid)
        if "error" not in t:
            topology.append({
                "component_id": t["component_id"], "component_name": t.get("component_name"),
                "upstream_dependencies": [u["name"] for u in t.get("upstream_dependencies", [])],
            })
    similar = q_similar_cases(session, case_id, as_of)
    return {"component_topology": topology, "similar_case_count": similar.get("count", len(similar.get("similar_cases", [])) if isinstance(similar.get("similar_cases"), list) else 0)}


def root_cause_state(session, case_id: str, as_of: str, context_version: str) -> dict:
    """The 5 context-ablation levels (spec section 24). Each level's state
    is a superset of the previous one's fields, so accuracy differences are
    attributable to what was ADDED, not to an unrelated rewording."""
    ctx = q_case_context(session, case_id)
    state = {"ticket": {"title": ctx.get("title"), "description": ctx.get("description")}}
    if context_version == "v1_narrative":
        return state

    state["ticket"] = _ticket_block(ctx)
    state["reported_product"] = _product_block(ctx)
    state["deployed_components"] = _deployed_components(session, case_id, as_of)
    if context_version == "v2_domain":
        return state

    state["technical_evidence"] = _technical_block(session, case_id, as_of)
    if context_version == "v3_technical":
        return state

    state["operational_events"] = _operational_block(session, case_id, as_of)
    if context_version == "v4_operational":
        return state

    state["graph_context"] = _graph_block(session, case_id, as_of, state["deployed_components"])
    return state  # v5_graph


def root_cause_candidate_state(session, case_id: str, as_of: str) -> dict:
    """Stable observable input for v2 root-cause candidate generation.

    This intentionally does not vary with the model-context ablation level.
    Candidate recall must be held fixed while v1--v5 test what Jev sees in
    its question state; product, reported symptoms, and visible signals are
    valid observable sources for the candidate generator in every arm.
    """
    ctx = q_case_context(session, case_id)
    return {
        "ticket": {"reported_symptoms": ctx.get("reported_symptoms") or []},
        "reported_product": _product_block(ctx),
        "technical_evidence": {"signals": q_technical_signals(session, case_id, as_of).get("signals", [])},
    }


def causal_change_state(session, case_id: str, as_of: str) -> dict:
    ctx = q_case_context(session, case_id)
    return {
        "ticket": _ticket_block(ctx),
        "reported_product": _product_block(ctx),
        "deployed_components": _deployed_components(session, case_id, as_of),
        "technical_evidence": _technical_block(session, case_id, as_of),
    }


def owning_team_state(session, case_id: str, as_of: str) -> dict:
    ctx = q_case_context(session, case_id)
    return {
        "ticket": _ticket_block(ctx),
        "reported_product": _product_block(ctx),
        "deployed_components": _deployed_components(session, case_id, as_of),
        "evidence_summary": _technical_block(session, case_id, as_of),
    }


def evidence_sufficiency_state(session, case_id: str, as_of: str) -> dict:
    ctx = q_case_context(session, case_id)
    config_hist = q_configuration_history(session, case_id, as_of)
    state = {
        "ticket": _ticket_block(ctx),
        "reported_product": _product_block(ctx),
        "technical_evidence": _evidence_sufficiency_technical_block(session, case_id, as_of),
        "operational_events": _operational_block(session, case_id, as_of),
        "configuration_snapshot_count": config_hist.get("count", 0),
    }
    return state


def incident_relationship_state(session, case_id: str, as_of: str, incident: dict) -> dict:
    ctx = q_case_context(session, case_id)
    signals = q_technical_signals(session, case_id, as_of)
    return {
        "ticket": _ticket_block(ctx),
        "reported_product": _product_block(ctx),
        "case_signal_count": signals.get("count", 0),
        "candidate_incident": {
            "region": incident.get("region"),
            "started_at": incident.get("started_at"),
            "ended_at": incident.get("ended_at"),
            "severity": incident.get("severity"),
            "status": incident.get("status"),
            "summary": incident.get("summary"),
            "affected_components": incident.get("affected_components"),
        },
    }
