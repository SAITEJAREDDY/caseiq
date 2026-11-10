"""The Phase 4 canonical query catalog (spec sections 23/34): plain
parameterized Cypher wrapped in Python functions, returning dicts/lists.
Not an LLM-facing tool API -- that's Phase 5's job. Every function here only
traverses the runtime graph; none can reach the evaluation store.
"""


def case_context(session, case_id):
    """A. Given a case: customer, reported product, customer's deployed
    versions of that product, environment, and reported symptoms."""
    rec = session.run(
        """
        MATCH (c:Case {id: $case_id})
        OPTIONAL MATCH (cust:Customer)-[:RAISED]->(c)
        OPTIONAL MATCH (c)-[:REPORTED_PRODUCT]->(p:Product)
        OPTIONAL MATCH (cust)-[:DEPLOYED]->(v:ProductVersion)<-[:HAS_VERSION]-(p)
        OPTIONAL MATCH (c)-[:REPORTS_SYMPTOM]->(sym:Symptom)
        RETURN c {.*} AS case,
               cust {.*} AS customer,
               p {.*} AS reported_product,
               collect(DISTINCT v {.*}) AS customer_versions_of_reported_product,
               collect(DISTINCT sym.name) AS symptoms
        """,
        case_id=case_id,
    ).single()
    return dict(rec) if rec else None


def component_topology(session, component_id):
    """B. Given a component: upstream dependencies, downstream dependents,
    external dependencies."""
    rec = session.run(
        """
        MATCH (c:Component {id: $component_id})
        OPTIONAL MATCH (c)-[:DEPENDS_ON]->(up:Component)
        OPTIONAL MATCH (down:Component)-[:DEPENDS_ON]->(c)
        OPTIONAL MATCH (c)-[:DEPENDS_ON_EXTERNAL]->(ext:ExternalService)
        RETURN c {.*} AS component,
               collect(DISTINCT up {.*}) AS upstream_dependencies,
               collect(DISTINCT down {.*}) AS downstream_dependents,
               collect(DISTINCT ext {.*}) AS external_dependencies
        """,
        component_id=component_id,
    ).single()
    return dict(rec) if rec else None


def recent_changes_for_case(session, case_id):
    """C. Given a case: nearby changes/deployments (the real observable
    candidate pool -- no causal label)."""
    return [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[rel:NEARBY_CHANGE]->(ch:ChangeEvent)
            RETURN ch {.*} AS change_event,
                   'Deployment' IN labels(ch) AS is_deployment,
                   rel.time_proximity_hours AS time_proximity_hours,
                   rel.scope_match AS scope_match
            ORDER BY ch.started_at
            """,
            case_id=case_id,
        )
    ]


def signals_and_telemetry_for_case(session, case_id):
    """D. Given a case: observed discrete signals and telemetry findings
    (both normal and abnormal -- normal findings eliminate hypotheses)."""
    signals = [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:HAS_SIGNAL]->(s:CaseSignalObservation)-[:OF_TYPE]->(st:SignalType)
            MATCH (s)-[:ON_COMPONENT]->(comp:Component)
            RETURN s {.*} AS signal, st.id AS signal_type, comp.id AS component_id
            ORDER BY s.timestamp
            """,
            case_id=case_id,
        )
    ]
    telemetry = [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:HAS_TELEMETRY_FINDING]->(t:TelemetryFinding)-[:ON_COMPONENT]->(comp:Component)
            RETURN t {.*} AS finding, comp.id AS component_id
            ORDER BY t.metric_code
            """,
            case_id=case_id,
        )
    ]
    return {"signals": signals, "telemetry_findings": telemetry}


def overlapping_incidents(session, case_id):
    """E. Given a case: incidents whose window the case's own time/region
    overlapped (fact only -- no relevance/causal judgment)."""
    return [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:OVERLAPS_INCIDENT]->(i:Incident)
            OPTIONAL MATCH (i)-[:AFFECTS_COMPONENT]->(comp:Component)
            WITH i, collect(DISTINCT comp.id) AS affected_components
            RETURN i {.*} AS incident, affected_components
            ORDER BY i.started_at
            """,
            case_id=case_id,
        )
    ]


def similar_historical_cases(session, case_id):
    """F. Given a case: similar historical cases and (for the resolved ones)
    their confirmed diagnosis, permanent resolution, and KBs consulted."""
    return [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[rel:SIMILAR_TO]-(sc:Case)
            OPTIONAL MATCH (sc)-[:CONFIRMED_DIAGNOSIS]->(rcf:RootCauseFamily)
            OPTIONAL MATCH (sc)-[:HAS_EVENT]->(ra:ResolutionAttempt {is_permanent: true})
            OPTIONAL MATCH (sc)-[:CONSULTED]->(kb:KnowledgeArticle)
            RETURN sc.id AS similar_case_id, sc.status AS status,
                   rel.similarity_score AS similarity_score,
                   rcf.name AS confirmed_root_cause,
                   collect(DISTINCT ra.action) AS permanent_actions_taken,
                   collect(DISTINCT kb.id) AS kb_articles_consulted
            ORDER BY similarity_score DESC
            """,
            case_id=case_id,
        )
    ]


def decision_snapshot(session, case_id, asof):
    """G. Given a case and a timestamp: the investigation state as known at
    that point in time -- events already happened, hypotheses already
    introduced (and whether already resolved), evidence already gathered.
    Never reveals an event/hypothesis-disposition timestamped after asof."""
    events = [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:HAS_EVENT]->(ie:InvestigationEvent)
            WHERE ie.timestamp <= $asof
            RETURN ie {.*} AS event, labels(ie) AS labels
            ORDER BY ie.seq
            """,
            case_id=case_id, asof=asof,
        )
    ]
    hypotheses = [
        dict(r)
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:HAS_EVENT]->(ie:InvestigationEvent)-[:INTRODUCES]->(h:Hypothesis)
            WHERE ie.timestamp <= $asof
            OPTIONAL MATCH (de:InvestigationEvent)-[:RESOLVES]->(h)
            WITH h, de,
                 (de IS NOT NULL AND de.timestamp <= $asof) AS disposition_known
            RETURN h.native_id AS hypothesis_id,
                   h.suspected_root_cause_name AS suspected_root_cause_name,
                   CASE WHEN disposition_known THEN h.disposition ELSE 'pending' END AS disposition_as_of,
                   CASE WHEN disposition_known THEN h.confidence_current ELSE h.confidence_initial END AS confidence_as_of
            """,
            case_id=case_id, asof=asof,
        )
    ]
    return {"case_id": case_id, "asof": asof, "events": events, "hypotheses_known_as_of": hypotheses}


def teams_and_skills_for_issue(session, subcategory_id=None, component_id=None):
    """H. Given an issue subcategory and/or a component: associated teams
    and required skills (population-level roster facts)."""
    result = {"teams": [], "skills": []}
    if subcategory_id:
        result["teams"] += [
            dict(r)
            for r in session.run(
                """
                MATCH (s:IssueSubcategory {id: $sid})-[rel:TYPICALLY_OWNED_BY]->(t:Team)
                RETURN t.id AS team_id, t.name AS team_name, rel.role AS role, rel.weight AS weight
                ORDER BY rel.weight DESC
                """,
                sid=subcategory_id,
            )
        ]
        result["skills"] += [
            dict(r)
            for r in session.run(
                """
                MATCH (s:IssueSubcategory {id: $sid})-[rel:TYPICALLY_REQUIRES_SKILL]->(sk:Skill)
                RETURN sk.id AS skill_id, sk.name AS skill_name, rel.weight AS weight
                ORDER BY rel.weight DESC
                """,
                sid=subcategory_id,
            )
        ]
    if component_id:
        result["teams"] += [
            dict(r)
            for r in session.run(
                """
                MATCH (c:Component {id: $cid})-[rel:SUPPORTED_BY]->(t:Team)
                RETURN t.id AS team_id, t.name AS team_name, rel.role AS role, rel.weight AS weight
                ORDER BY rel.weight DESC
                """,
                cid=component_id,
            )
        ]
    return result
