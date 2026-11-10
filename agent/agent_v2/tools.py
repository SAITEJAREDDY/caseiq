"""The Phase 5 agent tool layer: 14 read-only, time-gated, bounded tools over
the Phase 4 runtime graph. Every Cypher statement here is MATCH/RETURN only
(mechanically checked by validate_boundaries.py) -- this layer cannot write
to the graph. `as_of` is never an LLM-visible argument (see time_gate.py);
each tool closes over the harness-owned case_id/session/sim_clock.
"""
import os
import sys
from typing import Optional

from langchain_core.tools import StructuredTool

from agent.agent_v2.config import DEFAULT_RESULT_LIMIT
from agent.agent_v2.schemas import (
    AgentAvailabilityArgs,
    ComponentScopedArgs,
    FinalDiagnosis,
    KBSearchArgs,
    NoExtraArgs,
    OptionalComponentArgs,
    TeamCapabilityArgs,
    TelemetryArgs,
)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "generators_phase2"))
import evidence_taxonomy as _et  # noqa: E402  -- read-only reuse of the metric family catalog

METRICS_BY_FAMILY: dict[str, list[str]] = {}
for _m in _et.METRIC_CATALOG:
    METRICS_BY_FAMILY.setdefault(_m["family"], []).append(_m["code"])


# ── Raw (no-LangChain) query functions ──────────────────────────────────────
# Each takes (session, case_id, as_of, ...) and returns a small, bounded dict.

def q_case_context(session, case_id: str) -> dict:
    rec = session.run(
        """
        MATCH (c:Case {id: $case_id})
        OPTIONAL MATCH (cust:Customer)-[:RAISED]->(c)
        OPTIONAL MATCH (c)-[:REPORTED_PRODUCT]->(p:Product)
        OPTIONAL MATCH (c)-[:REPORTS_SYMPTOM]->(sym:Symptom)
        RETURN c.id AS case_id, c.title AS title, c.description AS description,
               c.environment AS environment, c.region AS region,
               c.reported_business_impact AS reported_business_impact,
               c.reported_affected_users AS reported_affected_users,
               c.priority AS priority, c.created_date AS created_date,
               c.status AS status,
               cust.id AS customer_id, cust.tier AS customer_tier,
               cust.industry AS customer_industry, cust.company_size AS customer_company_size,
               p.id AS reported_product_id, p.name AS reported_product_name,
               collect(DISTINCT sym.name) AS reported_symptoms
        """,
        case_id=case_id,
    ).single()
    return dict(rec) if rec else {"error": f"case {case_id} not found"}


def q_customer_deployment(session, case_id: str) -> dict:
    # Not as_of-gated: customer_deployments.csv is an ambient CMDB-style pool
    # generated independently across the full ~730-day window, not causally
    # sequenced relative to any one case (verified empirically -- a case's
    # own customer can have every recorded deployment timestamped after the
    # case's own created_date). Treated like topology/taxonomy: standing,
    # always-knowable "what does this customer run" context, same as Phase
    # 4's own case_context query already did.
    rows = [
        dict(r)
        for r in session.run(
            """
            MATCH (cust:Customer)-[:RAISED]->(:Case {id: $case_id})
            MATCH (cust)-[dep:DEPLOYED]->(v:ProductVersion)<-[:HAS_VERSION]-(p:Product)
            OPTIONAL MATCH (p)-[:HAS_COMPONENT]->(comp:Component)
            RETURN p.id AS product_id, p.name AS product_name, v.version AS version,
                   dep.environment AS environment, dep.region AS region, dep.status AS status,
                   dep.deployed_at AS deployed_at,
                   [x IN collect(DISTINCT comp.id) WHERE x IS NOT NULL][..%d] AS product_components
            ORDER BY dep.deployed_at DESC
            LIMIT %d
            """
            % (DEFAULT_RESULT_LIMIT, DEFAULT_RESULT_LIMIT),
            case_id=case_id,
        )
    ]
    return {"deployments": rows}


def q_component_topology(session, component_id: str) -> dict:
    rec = session.run(
        """
        MATCH (c:Component {id: $component_id})
        OPTIONAL MATCH (c)-[:DEPENDS_ON]->(up:Component)
        OPTIONAL MATCH (down:Component)-[:DEPENDS_ON]->(c)
        OPTIONAL MATCH (c)-[:DEPENDS_ON_EXTERNAL]->(ext:ExternalService)
        OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(t:Team)
        RETURN c.id AS component_id, c.name AS component_name,
               [x IN collect(DISTINCT {id: up.id, name: up.name}) WHERE x.id IS NOT NULL] AS upstream_dependencies,
               [x IN collect(DISTINCT {id: down.id, name: down.name}) WHERE x.id IS NOT NULL] AS downstream_dependents,
               [x IN collect(DISTINCT ext.name) WHERE x IS NOT NULL] AS external_dependencies,
               [x IN collect(DISTINCT {id: t.id, name: t.name}) WHERE x.id IS NOT NULL] AS owning_teams
        """,
        component_id=component_id,
    ).single()
    return dict(rec) if rec else {"error": f"component {component_id} not found"}


def q_technical_signals(session, case_id: str, as_of: str, component_id: Optional[str] = None) -> dict:
    cypher = """
    MATCH (c:Case {id: $case_id})-[:HAS_SIGNAL]->(s:CaseSignalObservation)-[:OF_TYPE]->(st:SignalType)
    MATCH (s)-[:ON_COMPONENT]->(comp:Component)
    WHERE s.timestamp <= $as_of
    %s
    RETURN s.id AS evidence_id, st.id AS signal_type, s.message AS message,
           s.timestamp AS timestamp, comp.id AS component_id
    ORDER BY s.timestamp
    LIMIT %d
    """ % ("AND comp.id = $component_id" if component_id else "", DEFAULT_RESULT_LIMIT)
    params = {"case_id": case_id, "as_of": as_of}
    if component_id:
        params["component_id"] = component_id
    rows = [dict(r) for r in session.run(cypher, **params)]
    return {"signals": rows, "count": len(rows)}


def q_telemetry(session, case_id: str, as_of: str, metric_category: Optional[str] = None, component_id: Optional[str] = None) -> dict:
    if not metric_category:
        rec_rows = session.run(
            """
            MATCH (c:Case {id: $case_id})-[:HAS_TELEMETRY_FINDING]->(t:TelemetryFinding)
            RETURN DISTINCT t.metric_code AS metric_code
            """,
            case_id=case_id,
        )
        available_codes = {r["metric_code"] for r in rec_rows}
        available_families = sorted({fam for fam, codes in METRICS_BY_FAMILY.items() if any(c in available_codes for c in codes)})
        return {
            "available_metric_categories": available_families,
            "note": "Call again with one of these metric_category values to see actual readings.",
        }

    codes = METRICS_BY_FAMILY.get(metric_category, [])
    if not codes:
        return {"error": f"unknown metric_category '{metric_category}'", "valid_categories": sorted(METRICS_BY_FAMILY.keys())}

    cypher = """
    MATCH (c:Case {id: $case_id})-[:HAS_TELEMETRY_FINDING]->(t:TelemetryFinding)-[:ON_COMPONENT]->(comp:Component)
    WHERE t.metric_code IN $codes AND t.window_start <= $as_of
    %s
    RETURN t.id AS evidence_id, t.metric_code AS metric_code, comp.id AS component_id,
           t.baseline AS baseline, t.observed_min AS observed_min, t.observed_max AS observed_max,
           t.status AS status, t.direction AS direction,
           t.anomaly_start AS anomaly_start, t.anomaly_end AS anomaly_end
    LIMIT %d
    """ % ("AND comp.id = $component_id" if component_id else "", DEFAULT_RESULT_LIMIT)
    params = {"case_id": case_id, "codes": codes, "as_of": as_of}
    if component_id:
        params["component_id"] = component_id
    rows = [dict(r) for r in session.run(cypher, **params)]
    return {"telemetry_findings": rows, "count": len(rows)}


def q_recent_changes(session, case_id: str, as_of: str, component_id: Optional[str] = None) -> dict:
    cypher = """
    MATCH (c:Case {id: $case_id})-[rel:NEARBY_CHANGE]->(ch:ChangeEvent)
    WHERE NOT ch:Deployment AND ch.started_at <= $as_of
    OPTIONAL MATCH (ch)-[:MODIFIED]->(comp:Component)
    WITH ch, rel, comp
    WHERE 1 = 1 %s
    RETURN ch.id AS evidence_id, ch.change_type AS change_type, comp.id AS component_id,
           ch.started_at AS started_at, ch.completed_at AS completed_at,
           ch.status AS status, ch.initiated_by AS initiated_by,
           rel.time_proximity_hours AS time_proximity_hours, rel.scope_match AS scope_match
    ORDER BY ch.started_at DESC
    LIMIT %d
    """ % ("AND comp.id = $component_id" if component_id else "", DEFAULT_RESULT_LIMIT)
    params = {"case_id": case_id, "as_of": as_of}
    if component_id:
        params["component_id"] = component_id
    rows = [dict(r) for r in session.run(cypher, **params)]
    return {"recent_changes": rows, "count": len(rows)}


def q_deployment_history(session, case_id: str, as_of: str, component_id: Optional[str] = None) -> dict:
    cypher = """
    MATCH (c:Case {id: $case_id})-[rel:NEARBY_CHANGE]->(ch:ChangeEvent:Deployment)
    WHERE ch.started_at <= $as_of
    OPTIONAL MATCH (ch)-[:MODIFIED]->(comp:Component)
    WITH ch, rel, comp
    WHERE 1 = 1 %s
    RETURN ch.id AS evidence_id, comp.id AS component_id,
           ch.version_from AS version_from, ch.version_to AS version_to,
           ch.rollout_strategy AS rollout_strategy, ch.deploy_duration_minutes AS deploy_duration_minutes,
           ch.description AS description, ch.started_at AS started_at, ch.status AS status,
           rel.time_proximity_hours AS time_proximity_hours
    ORDER BY ch.started_at DESC
    LIMIT %d
    """ % ("AND comp.id = $component_id" if component_id else "", DEFAULT_RESULT_LIMIT)
    params = {"case_id": case_id, "as_of": as_of}
    if component_id:
        params["component_id"] = component_id
    rows = [dict(r) for r in session.run(cypher, **params)]
    return {"deployments": rows, "count": len(rows)}


def q_configuration_history(session, case_id: str, as_of: str, component_id: Optional[str] = None) -> dict:
    cypher = """
    MATCH (c:Case {id: $case_id})-[:HAS_CONFIG_SNAPSHOT]->(cfg:ConfigurationSnapshot)-[:ON_COMPONENT]->(comp:Component)
    WHERE cfg.snapshot_at <= $as_of
    %s
    RETURN cfg.id AS evidence_id, comp.id AS component_id, cfg.config_key AS config_key,
           cfg.config_value AS config_value, cfg.snapshot_at AS snapshot_at, cfg.note AS note
    ORDER BY cfg.snapshot_at DESC
    LIMIT %d
    """ % ("AND comp.id = $component_id" if component_id else "", DEFAULT_RESULT_LIMIT)
    params = {"case_id": case_id, "as_of": as_of}
    if component_id:
        params["component_id"] = component_id
    rows = [dict(r) for r in session.run(cypher, **params)]
    return {"configuration_snapshots": rows, "count": len(rows)}


def q_service_health(session, component_id: str, as_of: str) -> dict:
    rows = [
        dict(r)
        for r in session.run(
            """
            MATCH (comp:Component {id: $component_id})-[:HAD_HEALTH_EVENT]->(e:ServiceHealthEvent)
            WHERE e.started_at <= $as_of
            RETURN e.id AS evidence_id, e.started_at AS started_at, e.ended_at AS ended_at,
                   e.severity AS severity, e.description AS description
            ORDER BY e.started_at DESC
            LIMIT $limit
            """,
            component_id=component_id, as_of=as_of, limit=DEFAULT_RESULT_LIMIT,
        )
    ]
    return {"health_events": rows, "count": len(rows)}


def q_active_incidents(session, case_id: str, as_of: str) -> dict:
    rows = [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:OVERLAPS_INCIDENT]->(i:Incident)
            WHERE i.started_at <= $as_of
            OPTIONAL MATCH (i)-[:AFFECTS_COMPONENT]->(comp:Component)
            RETURN i.id AS evidence_id, i.region AS region, i.started_at AS started_at,
                   i.ended_at AS ended_at, i.severity AS severity, i.status AS status,
                   i.summary AS summary, [x IN collect(DISTINCT comp.id) WHERE x IS NOT NULL] AS affected_components
            ORDER BY i.started_at DESC
            LIMIT $limit
            """,
            case_id=case_id, as_of=as_of, limit=DEFAULT_RESULT_LIMIT,
        )
    ]
    return {"incidents": rows, "count": len(rows)}


def q_similar_cases(session, case_id: str, as_of: str) -> dict:
    rows = [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[rel:SIMILAR_TO]-(sc:Case)
            WHERE sc.created_date <= $as_of AND sc.status = 'resolved'
            OPTIONAL MATCH (sc)-[:CONFIRMED_DIAGNOSIS]->(rcf:RootCauseFamily)
            OPTIONAL MATCH (sc)-[:HAS_EVENT]->(ra:ResolutionAttempt {is_permanent: true})
            RETURN sc.id AS evidence_id, rel.similarity_score AS similarity_score,
                   sc.title AS title, rcf.name AS historical_diagnosis,
                   [x IN collect(DISTINCT ra.action) WHERE x IS NOT NULL][..3] AS historical_actions
            ORDER BY rel.similarity_score DESC
            LIMIT $limit
            """,
            case_id=case_id, as_of=as_of, limit=DEFAULT_RESULT_LIMIT,
        )
    ]
    return {"similar_cases": rows, "count": len(rows)}


def q_search_kb(session, keyword: Optional[str] = None, component_id: Optional[str] = None, category_id: Optional[str] = None) -> dict:
    # Not as_of-gated, for the same reason as customer deployments: KB
    # article created_date is an independent ambient timestamp (spans the
    # full dataset window irrespective of any one case's own date), not a
    # per-case event -- the standing KB corpus is always searchable.
    clauses = ["1 = 1"]
    params = {"limit": DEFAULT_RESULT_LIMIT}
    match_extra = ""
    if component_id:
        match_extra += "\nMATCH (a)-[:COVERS_COMPONENT]->(:Component {id: $component_id})"
        params["component_id"] = component_id
    if category_id:
        match_extra += "\nMATCH (a)-[:COVERS_CATEGORY]->(:IssueCategory {id: $category_id})"
        params["category_id"] = category_id
    if keyword:
        clauses.append("(toLower(a.title) CONTAINS toLower($keyword) OR toLower(a.content_summary) CONTAINS toLower($keyword))")
        params["keyword"] = keyword
    cypher = f"""
    MATCH (a:KnowledgeArticle)
    {match_extra}
    WHERE {' AND '.join(clauses)}
    RETURN a.id AS evidence_id, a.title AS title, a.content_summary AS summary,
           a.resolution_rate AS resolution_rate, a.outdated AS outdated
    ORDER BY a.resolution_rate DESC
    LIMIT $limit
    """
    rows = [dict(r) for r in session.run(cypher, **params)]
    return {"articles": rows, "count": len(rows)}


def q_team_capability(session, component_id: Optional[str] = None, subcategory_id: Optional[str] = None) -> dict:
    teams, skills = [], []
    if subcategory_id:
        teams += [dict(r) for r in session.run(
            """
            MATCH (s:IssueSubcategory {id: $sid})-[rel:TYPICALLY_OWNED_BY]->(t:Team)
            RETURN t.id AS team_id, t.name AS team_name, rel.role AS role, rel.weight AS weight
            ORDER BY rel.weight DESC LIMIT $limit
            """,
            sid=subcategory_id, limit=DEFAULT_RESULT_LIMIT,
        )]
        skills += [dict(r) for r in session.run(
            """
            MATCH (s:IssueSubcategory {id: $sid})-[rel:TYPICALLY_REQUIRES_SKILL]->(sk:Skill)
            RETURN sk.id AS skill_id, sk.name AS skill_name, rel.weight AS weight
            ORDER BY rel.weight DESC LIMIT $limit
            """,
            sid=subcategory_id, limit=DEFAULT_RESULT_LIMIT,
        )]
    if component_id:
        teams += [dict(r) for r in session.run(
            """
            MATCH (c:Component {id: $cid})-[rel:SUPPORTED_BY]->(t:Team)
            RETURN t.id AS team_id, t.name AS team_name, rel.role AS role, rel.weight AS weight
            ORDER BY rel.weight DESC LIMIT $limit
            """,
            cid=component_id, limit=DEFAULT_RESULT_LIMIT,
        )]
    if not component_id and not subcategory_id:
        return {"error": "provide component_id and/or subcategory_id"}
    return {"teams": teams, "skills": skills}


def q_agent_availability(session, team_id: str) -> dict:
    rows = [
        dict(r)
        for r in session.run(
            """
            MATCH (a:Agent)-[:MEMBER_OF]->(t:Team {id: $team_id})
            OPTIONAL MATCH (a)-[hs:HAS_SKILL]->(sk:Skill)
            RETURN a.id AS agent_id, a.seniority AS seniority,
                   a.max_concurrent_cases AS max_concurrent_cases,
                   a.current_utilization_pct AS current_utilization_pct,
                   [x IN collect(DISTINCT sk.name) WHERE x IS NOT NULL][..5] AS skills
            ORDER BY a.current_utilization_pct ASC
            LIMIT $limit
            """,
            team_id=team_id, limit=DEFAULT_RESULT_LIMIT,
        )
    ]
    return {"agents": rows, "count": len(rows)}


# ── Tool factory ─────────────────────────────────────────────────────────────

def make_tools(session, case_id: str, sim_clock) -> list[StructuredTool]:
    """Returns the 14 diagnostic tools + submit_diagnosis, closing over the
    harness-owned session/case_id/sim_clock. `as_of` is read from
    sim_clock.as_of at call time -- never a model-supplied argument."""

    def _wrap(fn, **extra):
        def inner(**kwargs):
            kwargs.pop("hypotheses", None)
            kwargs.pop("rationale", None)
            kwargs.update(extra)
            return fn(**kwargs)
        return inner

    tools = [
        StructuredTool.from_function(
            func=_wrap(lambda: q_case_context(session, case_id)),
            name="get_case_context",
            description="Get the basic observable support-case context: title, description, customer info, "
            "reported product, environment, region, reported symptoms/impact. Always call this first.",
            args_schema=NoExtraArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda: q_customer_deployment(session, case_id)),
            name="get_customer_deployment",
            description="Inspect what the customer actually has deployed: products, versions, environments, "
            "regions, and the components those products include.",
            args_schema=NoExtraArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id: q_component_topology(session, component_id)),
            name="get_component_topology",
            description="Explore a component's dependency graph: what it depends on, what depends on it, "
            "external dependencies, and which teams typically own it.",
            args_schema=ComponentScopedArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id=None: q_technical_signals(session, case_id, sim_clock.as_of, component_id)),
            name="get_technical_signals",
            description="Retrieve discrete technical signals observed for this case (HTTP errors, auth/authz "
            "failures, TLS failures, DB errors, timeouts, etc.) as raw observable evidence -- some may be noise.",
            args_schema=OptionalComponentArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda metric_category=None, component_id=None: q_telemetry(session, case_id, sim_clock.as_of, metric_category, component_id)),
            name="get_telemetry",
            description="Inspect summarized telemetry for this case's components, grouped by metric category "
            "(Compute, Application, Networking, Database, Identity, Storage, Integration, Capacity, Security, "
            "Data). Call once with no category to see which categories have data, then call again with a "
            "specific category.",
            args_schema=TelemetryArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id=None: q_recent_changes(session, case_id, sim_clock.as_of, component_id)),
            name="get_recent_changes",
            description="Inspect non-deployment changes near this case's timeframe (policy, config, firewall, "
            "DNS, certificate, feature-flag, capacity changes). May include changes unrelated to this case.",
            args_schema=OptionalComponentArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id=None: q_deployment_history(session, case_id, sim_clock.as_of, component_id)),
            name="get_deployment_history",
            description="Inspect recent deployments (version changes) near this case's timeframe, separate from "
            "general changes.",
            args_schema=OptionalComponentArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id=None: q_configuration_history(session, case_id, sim_clock.as_of, component_id)),
            name="get_configuration_history",
            description="Inspect observable configuration snapshots captured during investigation of this case "
            "(feature flags, rate limits, TLS versions, pool sizes, etc.).",
            args_schema=OptionalComponentArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id: q_service_health(session, component_id, sim_clock.as_of)),
            name="get_service_health",
            description="Inspect platform service-health events for a specific component (status, region, "
            "time window, degradation description).",
            args_schema=ComponentScopedArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda: q_active_incidents(session, case_id, sim_clock.as_of)),
            name="get_active_incidents",
            description="Find incidents whose time/region window overlaps this case. Overlap does not imply "
            "relevance -- you must judge whether the incident actually explains this case.",
            args_schema=NoExtraArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda: q_similar_cases(session, case_id, sim_clock.as_of)),
            name="get_similar_cases",
            description="Find similar historical (already-resolved) cases and how they were diagnosed/resolved. "
            "A similar case's outcome is not proof of this case's answer -- symptoms can look alike with "
            "different causes.",
            args_schema=NoExtraArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda keyword=None, component_id=None, category_id=None: q_search_kb(session, keyword, component_id, category_id)),
            name="search_knowledge_base",
            description="Search knowledge-base articles by keyword and/or component/category. Not every "
            "returned article is relevant or accurate -- some are outdated or only partially applicable.",
            args_schema=KBSearchArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda component_id=None, subcategory_id=None: q_team_capability(session, component_id, subcategory_id)),
            name="get_team_capability",
            description="Look up which teams typically own a component or issue subcategory, and what skills "
            "are typically required.",
            args_schema=TeamCapabilityArgs,
        ),
        StructuredTool.from_function(
            func=_wrap(lambda team_id: q_agent_availability(session, team_id)),
            name="get_agent_availability",
            description="Check agent availability/capacity/skills within a team, to support a routing "
            "recommendation.",
            args_schema=AgentAvailabilityArgs,
        ),
    ]

    def _submit(**kwargs):
        return "diagnosis submitted"

    submit_tool = StructuredTool.from_function(
        func=_submit,
        name="submit_diagnosis",
        description="Submit your final structured diagnosis and end the investigation. Call this once you "
        "have sufficient evidence, OR to explicitly report insufficient evidence / a need for human review. "
        "Never invent an evidence ID that did not appear in an earlier tool result.",
        args_schema=FinalDiagnosis,
    )
    tools.append(submit_tool)
    return tools
