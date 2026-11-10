"""The Phase 3 investigation timeline -- the highest-leakage-risk loader.

Governing principle (see docs/GRAPH_DATA_BOUNDARIES.md): any edge connecting
a Case to a diagnosis-shaped entity (component/category/root-cause
family/team/agent) is created ONLY here, from Phase 3's own observable
investigation record -- never from case_ground_truth.csv, case_components.csv,
case_products.csv (confirmed rows), case_team_ownership.csv, or agent_cases.csv
(none of which this module, or any other loader module, ever opens).

Model: one InvestigationEvent node per case_lifecycle_events.csv row
(id = event_id) is the generic ordered-timeline layer. Thirteen of the
seventeen observable detail tables map 1:1 to a single event_id and are
merged onto that SAME node via an extra label (multi-label merge -- no
duplicate node). diagnostic_hypotheses.csv is the one exception: a hypothesis
can have a *creation* event and a later *disposition* event, so it gets its
own distinct Hypothesis node (keyed by its native id) linked from both
events via INTRODUCES / RESOLVES.
"""
from agent.graph_v2.config import DATA_PHASE3
from agent.graph_v2.db import read_csv, run_batched


def load(session, case_ids=None):
    _load_lifecycle_events(session, case_ids)
    _load_triage(session, case_ids)
    _load_routing(session, case_ids)
    _load_assignment(session, case_ids)
    _load_hypotheses(session, case_ids)
    _load_hypothesis_evidence(session, case_ids)
    _load_evidence_queries(session, case_ids)
    _load_resolution_attempts(session, case_ids)
    _load_mitigations(session, case_ids)
    _load_resolution_verification(session, case_ids)
    _load_case_reopens(session, case_ids)
    _load_kb_interactions(session, case_ids)
    _load_similar_case_interactions(session, case_ids)
    _load_escalations(session, case_ids)
    _load_engineering_engagements(session, case_ids)
    _load_customer_interactions(session, case_ids)
    _load_collaboration_events(session, case_ids)


def _filter(rows, case_ids):
    if case_ids is None:
        return rows
    return [r for r in rows if r["case_id"] in case_ids]


def _load_lifecycle_events(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "case_lifecycle_events.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (ie:InvestigationEvent {id: r.event_id})
        SET ie.case_id = r.case_id,
            ie.seq = toInteger(r.seq),
            ie.event_type = r.event_type,
            ie.timestamp = r.timestamp,
            ie.actor_type = r.actor_type,
            ie.actor_id = r.actor_id,
            ie.note = r.note
        WITH ie, r
        MATCH (c:Case {id: r.case_id})
        MERGE (c)-[:HAS_EVENT]->(ie)
        """,
        "InvestigationEvent",
    )


def _load_triage(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "triage_history.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:TriageDecision,
            ie.predicted_severity = r.predicted_severity,
            ie.confidence = toFloat(r.confidence),
            ie.required_human_confirmation = (r.required_human_confirmation = 'true')
        WITH ie, r
        OPTIONAL MATCH (p:Product {id: r.predicted_product_id})
        FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:PREDICTS_PRODUCT]->(p))
        WITH ie, r
        OPTIONAL MATCH (comp:Component {id: r.predicted_component_id})
        FOREACH (_ IN CASE WHEN comp IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:PREDICTS_COMPONENT]->(comp))
        WITH ie, r
        OPTIONAL MATCH (subcat:IssueSubcategory {id: r.predicted_subcategory_id})
        FOREACH (_ IN CASE WHEN subcat IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:PREDICTS_SUBCATEGORY]->(subcat))
        WITH ie, r
        OPTIONAL MATCH (cat:IssueCategory {id: r.predicted_category_id})
        FOREACH (_ IN CASE WHEN cat IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:PREDICTS_CATEGORY]->(cat))
        WITH ie, r
        OPTIONAL MATCH (t:Team {id: r.predicted_team_id})
        FOREACH (_ IN CASE WHEN t IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:PREDICTS_TEAM]->(t))
        """,
        "TriageDecision",
    )


def _load_routing(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "routing_history.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:RoutingTransition,
            ie.reason_code = r.reason_code,
            ie.alternative_teams_considered = r.alternative_teams_considered
        WITH ie, r
        OPTIONAL MATCH (ft:Team {id: r.from_team_id})
        FOREACH (_ IN CASE WHEN ft IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:FROM_TEAM]->(ft))
        WITH ie, r
        MATCH (tt:Team {id: r.to_team_id})
        MERGE (ie)-[:TO_TEAM]->(tt)
        """,
        "RoutingTransition",
    )


def _load_assignment(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "assignment_history.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:AssignmentDecision,
            ie.reason_code = r.reason_code,
            ie.skill_match_score = toFloat(r.skill_match_score),
            ie.accepted = (r.accepted = 'true')
        WITH ie, r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (t:Team {id: r.team_id})
        MERGE (ie)-[:ASSIGNED_AGENT]->(a)
        MERGE (ie)-[:FOR_TEAM]->(t)
        """,
        "AssignmentDecision",
    )


def _load_hypotheses(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "diagnostic_hypotheses.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (h:Hypothesis {native_id: r.id})
        SET h.case_id = r.case_id,
            h.suspected_root_cause_name = r.suspected_root_cause_name,
            h.confidence_initial = toFloat(r.confidence_initial),
            h.confidence_current = toFloat(r.confidence_current),
            h.disposition = r.disposition,
            h.created_at = r.created_at,
            h.disposition_at = r.disposition_at
        WITH h, r
        OPTIONAL MATCH (comp:Component {id: r.suspected_component_id})
        FOREACH (_ IN CASE WHEN comp IS NULL THEN [] ELSE [1] END | MERGE (h)-[:CONSIDERS_COMPONENT]->(comp))
        WITH h, r
        OPTIONAL MATCH (cat:IssueCategory {id: r.suspected_category_id})
        FOREACH (_ IN CASE WHEN cat IS NULL THEN [] ELSE [1] END | MERGE (h)-[:CONSIDERS_CATEGORY]->(cat))
        WITH h, r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        MERGE (ie)-[:INTRODUCES]->(h)
        WITH h, r
        OPTIONAL MATCH (de:InvestigationEvent {id: r.disposition_event_id})
        FOREACH (_ IN CASE WHEN de IS NULL THEN [] ELSE [1] END | MERGE (de)-[:RESOLVES]->(h))
        """,
        "Hypothesis",
    )

    # The ONE sanctioned path for Case -> diagnosis-shaped entity: only from
    # a disposition == "confirmed" hypothesis, sourced from Phase 3's own
    # observable record (not case_ground_truth.csv), matching by name/id
    # coincidentally because Phase 3 forces convergence on resolved cases.
    #
    # disposition_at is stored ON the edge so a decision-snapshot query at an
    # earlier timestamp T (spec's time-aware retrieval requirement) can
    # filter it out with `WHERE rel.disposition_at <= $asof` -- without this,
    # the edge would leak the final answer to any query regardless of T,
    # including for cases still open (which also reach a confirmed
    # hypothesis in this dataset, per Phase 3's own design -- confirmed
    # verified empirically: all cases, resolved or open, get exactly one
    # confirmed hypothesis; only resolution_attempts are absent for open ones).
    confirmed = [r for r in rows if r["disposition"] == "confirmed"]
    run_batched(
        session, confirmed,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        MATCH (rcf:RootCauseFamily {name: r.suspected_root_cause_name})
        MERGE (c)-[rel:CONFIRMED_DIAGNOSIS]->(rcf)
        SET rel.disposition_at = r.disposition_at
        WITH c, r
        OPTIONAL MATCH (comp:Component {id: r.suspected_component_id})
        FOREACH (_ IN CASE WHEN comp IS NULL THEN [] ELSE [1] END |
            MERGE (c)-[rel2:CONFIRMED_DIAGNOSIS_COMPONENT]->(comp)
            SET rel2.disposition_at = r.disposition_at)
        """,
        "Case-CONFIRMED_DIAGNOSIS (confirmed hypotheses only)",
    )


def _flatten_evidence_targets(rows):
    """One hypothesis_evidence row can reference 0, 1, or several targets
    (semicolon-joined ids). Returns per-evidence-type lists of flattened
    single-target edges, resolved against the exact ref formats verified in
    the real data (signal->SG..., config_snapshot->CFG..., change_event->CH...,
    incident->INC..., dependency_graph->component ids, telemetry->"metric@HH:MM"
    tokens joined on case_id+metric_code). "none" and unresolvable types
    (customer_info) create no target edge -- the fact itself is still fully
    captured by the EvidenceLink label on the row's own InvestigationEvent.
    """
    out = {"signal": [], "config_snapshot": [], "change_event": [], "incident": [], "dependency_graph": [], "telemetry": []}
    for r in rows:
        ref = r["evidence_ref_id"]
        if not ref or ref == "none":
            continue
        etype = r["evidence_type"]
        base = {
            "hypothesis_native_id": r["hypothesis_id"],
            "support_type": r["support_type"],
            "confidence_after": r["confidence_after"],
            "timestamp": r["timestamp"],
        }
        tokens = [t for t in ref.split(";") if t]
        if etype == "telemetry":
            seen = set()
            for tok in tokens:
                metric_code = tok.split("@")[0]
                if metric_code in seen:
                    continue
                seen.add(metric_code)
                out["telemetry"].append({**base, "case_id": r["case_id"], "metric_code": metric_code})
        elif etype in out:
            for tok in tokens:
                out[etype].append({**base, "target_id": tok})
    return out


def _load_evidence_edge_group(session, edges, cypher_supports, cypher_contradicts, label):
    supports = [e for e in edges if e["support_type"] == "supports"]
    contradicts = [e for e in edges if e["support_type"] == "contradicts"]
    run_batched(session, supports, cypher_supports, f"Hypothesis-SUPPORTED_BY ({label})", quiet=True)
    run_batched(session, contradicts, cypher_contradicts, f"Hypothesis-CONTRADICTED_BY ({label})", quiet=True)


def _load_hypothesis_evidence(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "hypothesis_evidence.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:EvidenceLink,
            ie.evidence_type = r.evidence_type,
            ie.support_type = r.support_type,
            ie.confidence_after = toFloat(r.confidence_after)
        WITH ie, r
        MATCH (h:Hypothesis {native_id: r.hypothesis_id})
        MERGE (ie)-[:UPDATES]->(h)
        """,
        "EvidenceLink",
    )

    targets = _flatten_evidence_targets(rows)

    def simple_cypher(target_label, rel_type):
        return f"""
        UNWIND $rows AS r
        MATCH (h:Hypothesis {{native_id: r.hypothesis_native_id}})
        MATCH (t:{target_label} {{id: r.target_id}})
        MERGE (h)-[rel:{rel_type} {{confidence_after: toFloat(r.confidence_after), timestamp: r.timestamp}}]->(t)
        """

    _load_evidence_edge_group(
        session, targets["signal"],
        simple_cypher("CaseSignalObservation", "SUPPORTED_BY"),
        simple_cypher("CaseSignalObservation", "CONTRADICTED_BY"),
        "signal",
    )
    _load_evidence_edge_group(
        session, targets["config_snapshot"],
        simple_cypher("ConfigurationSnapshot", "SUPPORTED_BY"),
        simple_cypher("ConfigurationSnapshot", "CONTRADICTED_BY"),
        "config_snapshot",
    )
    _load_evidence_edge_group(
        session, targets["change_event"],
        simple_cypher("ChangeEvent", "SUPPORTED_BY"),
        simple_cypher("ChangeEvent", "CONTRADICTED_BY"),
        "change_event",
    )
    _load_evidence_edge_group(
        session, targets["incident"],
        simple_cypher("Incident", "SUPPORTED_BY"),
        simple_cypher("Incident", "CONTRADICTED_BY"),
        "incident",
    )
    _load_evidence_edge_group(
        session, targets["dependency_graph"],
        simple_cypher("Component", "CONSIDERS_DEPENDENCY_PATH"),
        simple_cypher("Component", "CONSIDERS_DEPENDENCY_PATH"),
        "dependency_graph",
    )

    telemetry_cypher = """
    UNWIND $rows AS r
    MATCH (h:Hypothesis {native_id: r.hypothesis_native_id})
    MATCH (t:TelemetryFinding {case_id: r.case_id, metric_code: r.metric_code})
    MERGE (h)-[rel:%s {confidence_after: toFloat(r.confidence_after), timestamp: r.timestamp}]->(t)
    """
    _load_evidence_edge_group(
        session, targets["telemetry"],
        telemetry_cypher % "SUPPORTED_BY",
        telemetry_cypher % "CONTRADICTED_BY",
        "telemetry",
    )


def _load_evidence_queries(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "evidence_queries.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:EvidenceQuery,
            ie.query_type = r.query_type,
            ie.target_ref = r.target_ref,
            ie.result_count = toInteger(r.result_count)
        """,
        "EvidenceQuery",
    )


def _load_resolution_attempts(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "resolution_attempts.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:ResolutionAttempt,
            ie.native_id = r.id,
            ie.action = r.action,
            ie.result = r.result,
            ie.is_temporary = (r.is_temporary = 'true'),
            ie.is_permanent = (r.is_permanent = 'true'),
            ie.human_approval_flagged = (r.human_approval_flagged = 'true'),
            ie.alternatives_considered = r.alternatives_considered
        WITH ie, r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (t:Team {id: r.team_id})
        MERGE (ie)-[:PERFORMED_BY]->(a)
        MERGE (ie)-[:FOR_TEAM]->(t)
        WITH ie, r
        OPTIONAL MATCH (rt:ResolutionType {id: r.resolution_type_id})
        FOREACH (_ IN CASE WHEN rt IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:USES_RESOLUTION_TYPE]->(rt))
        WITH ie, r
        OPTIONAL MATCH (h:Hypothesis {native_id: r.targeted_hypothesis_id})
        FOREACH (_ IN CASE WHEN h IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:TARGETS_HYPOTHESIS]->(h))
        """,
        "ResolutionAttempt",
    )


def _load_mitigations(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "mitigations.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:Mitigation, ie.description = r.description
        WITH ie, r
        MATCH (ra:ResolutionAttempt {native_id: r.resolution_attempt_id})
        MERGE (ie)-[:FOR_ATTEMPT]->(ra)
        """,
        "Mitigation",
    )


def _load_resolution_verification(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "resolution_verification.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:VerificationCheck, ie.verification_type = r.verification_type, ie.result = r.result
        """,
        "VerificationCheck",
    )


def _load_case_reopens(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "case_reopens.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:Reopen, ie.reason_code = r.reason_code
        WITH ie, r
        OPTIONAL MATCH (prior:InvestigationEvent {id: r.prior_resolution_event_id})
        FOREACH (_ IN CASE WHEN prior IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:REOPENED_AFTER]->(prior))
        """,
        "Reopen",
    )


def _load_kb_interactions(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "kb_interactions.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:KBInteraction, ie.interaction_type = r.interaction_type
        WITH ie, r
        MATCH (c:Case {id: r.case_id})
        MATCH (a:KnowledgeArticle {id: r.article_id})
        MERGE (ie)-[:ABOUT_ARTICLE]->(a)
        MERGE (c)-[:CONSULTED]->(a)
        """,
        "KBInteraction",
    )


def _load_similar_case_interactions(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "similar_case_interactions.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:SimilarCaseInteraction,
            ie.similarity_score = toFloat(r.similarity_score),
            ie.opened = (r.opened = 'true')
        WITH ie, r
        MATCH (sc:Case {id: r.similar_case_id})
        MERGE (ie)-[:ABOUT_SIMILAR_CASE]->(sc)
        """,
        "SimilarCaseInteraction",
    )


def _load_escalations(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "escalations.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:Escalation,
            ie.escalation_type = r.escalation_type,
            ie.trigger_code = r.trigger_code,
            ie.summary = r.summary
        WITH ie, r
        OPTIONAL MATCH (ft:Team {id: r.from_team_id})
        FOREACH (_ IN CASE WHEN ft IS NULL THEN [] ELSE [1] END | MERGE (ie)-[:FROM_TEAM]->(ft))
        WITH ie, r
        MATCH (tt:Team {id: r.to_team_id})
        MERGE (ie)-[:TO_TEAM]->(tt)
        """,
        "Escalation",
    )


def _load_engineering_engagements(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "engineering_engagements.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:EngineeringEngagement, ie.activity_type = r.activity_type, ie.finding_summary = r.finding_summary
        """,
        "EngineeringEngagement",
    )


def _load_customer_interactions(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "customer_interactions.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:CustomerInteraction,
            ie.interaction_type = r.interaction_type,
            ie.requested_info = r.requested_info,
            ie.response_delay_hours = toFloat(r.response_delay_hours)
        """,
        "CustomerInteraction",
    )


def _load_collaboration_events(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "collaboration_events.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (ie:InvestigationEvent {id: r.event_id})
        SET ie:CollaborationEvent, ie.collaboration_type = r.collaboration_type
        WITH ie, r
        MATCH (t:Team {id: r.collaborator_team_id})
        MERGE (ie)-[:WITH_TEAM]->(t)
        """,
        "CollaborationEvent",
    )
