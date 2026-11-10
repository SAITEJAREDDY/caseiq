"""Phase 2 observable evidence: changes/deployments, incidents, service
health, discrete signals, configuration snapshots, and summarized telemetry.

No causal/distractor label from phase2_ground_truth.csv ever enters this
module. incident_cases.csv's `relationship` column (directly_caused /
partially_influenced / coincidental_unrelated / customer_assumed_incorrectly)
is deliberately NOT copied onto the OVERLAPS_INCIDENT edge -- it is exactly
the causal-relevance judgment a future agent must infer itself (only the
observable fact that the case's time/region window overlapped the incident
is loaded).
"""
from agent.graph_v2.config import DATA_PHASE2
from agent.graph_v2.db import read_csv, run_batched
from agent.graph_v2.telemetry_summarize import summarize as summarize_telemetry


def load(session, case_ids=None):
    _load_change_events_and_deployments(session)
    _load_incidents(session)
    _load_service_health_events(session)
    _load_signals(session, case_ids)
    _load_configuration_snapshots(session, case_ids)
    _load_case_change_links(session, case_ids)
    _load_incident_case_overlap(session, case_ids)
    _load_telemetry_findings(session, case_ids)


def _filter(rows, case_ids, col="case_id"):
    if case_ids is None:
        return rows
    return [r for r in rows if r[col] in case_ids]


def _load_change_events_and_deployments(session):
    # ChangeEvent nodes, always loaded in full -- ambient platform activity,
    # not case-specific, forms the shared "world" every case's
    # NEARBY_CHANGE edges resolve against.
    rows = read_csv(DATA_PHASE2 / "change_events.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:ChangeEvent {id: r.id})
        SET n.change_type = r.change_type,
            n.environment = r.environment,
            n.region = r.region,
            n.started_at = r.started_at,
            n.completed_at = r.completed_at,
            n.status = r.status,
            n.initiated_by = r.initiated_by
        WITH n, r
        MATCH (c:Component {id: r.component_id})
        MERGE (n)-[:MODIFIED]->(c)
        """,
        "ChangeEvent",
    )
    # optional product/customer scope, when present
    scoped = [r for r in rows if r.get("product_id")]
    run_batched(
        session, scoped,
        """
        UNWIND $rows AS r
        MATCH (n:ChangeEvent {id: r.id})
        MATCH (p:Product {id: r.product_id})
        MERGE (n)-[:AFFECTS_PRODUCT]->(p)
        """,
        "ChangeEvent-AFFECTS_PRODUCT",
        quiet=True,
    )

    deployments = read_csv(DATA_PHASE2 / "deployments.csv")
    run_batched(
        session, deployments,
        """
        UNWIND $rows AS r
        MATCH (n:ChangeEvent {id: r.change_event_id})
        SET n:Deployment,
            n.version_from = r.version_from,
            n.version_to = r.version_to,
            n.rollout_strategy = r.rollout_strategy,
            n.deploy_duration_minutes = toInteger(r.deploy_duration_minutes),
            n.description = r.description
        """,
        "Deployment (extra label on ChangeEvent)",
    )
    # (Deployment)-[:DEPLOYED_VERSION]->(ProductVersion) where version_to resolves
    dep_with_product = [r for r in deployments if r.get("product_id")]
    run_batched(
        session, dep_with_product,
        """
        UNWIND $rows AS r
        MATCH (n:ChangeEvent {id: r.change_event_id})
        MATCH (v:ProductVersion {product_id: r.product_id, version: r.version_to})
        MERGE (n)-[:DEPLOYED_VERSION]->(v)
        """,
        "Deployment-DEPLOYED_VERSION",
        quiet=True,
    )


def _load_incidents(session):
    rows = read_csv(DATA_PHASE2 / "incidents.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:Incident {id: r.id})
        SET n.region = r.region,
            n.started_at = r.started_at,
            n.ended_at = r.ended_at,
            n.severity = r.severity,
            n.status = r.status,
            n.summary = r.summary
        WITH n, r
        MATCH (c:Component {id: r.component_id})
        MERGE (n)-[:AFFECTS_COMPONENT]->(c)
        """,
        "Incident",
    )


def _load_service_health_events(session):
    rows = read_csv(DATA_PHASE2 / "service_health_events.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:ServiceHealthEvent {id: r.id})
        SET n.started_at = r.started_at,
            n.ended_at = r.ended_at,
            n.severity = r.severity,
            n.description = r.description
        WITH n, r
        MATCH (c:Component {id: r.component_id})
        MERGE (c)-[:HAD_HEALTH_EVENT]->(n)
        """,
        "ServiceHealthEvent",
    )


def _load_signals(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE2 / "case_signals.csv"), case_ids)
    signal_codes = sorted({r["signal_code"] for r in rows})
    run_batched(
        session, [{"id": code} for code in signal_codes],
        "UNWIND $rows AS r MERGE (n:SignalType {id: r.id})",
        "SignalType",
    )
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:CaseSignalObservation {id: r.id})
        SET n.case_id = r.case_id, n.timestamp = r.timestamp, n.message = r.message
        WITH n, r
        MATCH (c:Case {id: r.case_id})
        MATCH (comp:Component {id: r.component_id})
        MATCH (st:SignalType {id: r.signal_code})
        MERGE (c)-[:HAS_SIGNAL]->(n)
        MERGE (n)-[:ON_COMPONENT]->(comp)
        MERGE (n)-[:OF_TYPE]->(st)
        """,
        "CaseSignalObservation",
    )


def _load_configuration_snapshots(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE2 / "configuration_snapshots.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:ConfigurationSnapshot {id: r.id})
        SET n.case_id = r.case_id,
            n.snapshot_at = r.snapshot_at,
            n.config_key = r.config_key,
            n.config_value = r.config_value,
            n.note = r.note
        WITH n, r
        MATCH (c:Case {id: r.case_id})
        MATCH (comp:Component {id: r.component_id})
        MERGE (c)-[:HAS_CONFIG_SNAPSHOT]->(n)
        MERGE (n)-[:ON_COMPONENT]->(comp)
        """,
        "ConfigurationSnapshot",
    )


def _load_case_change_links(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE2 / "case_change_links.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        MATCH (ch:ChangeEvent {id: r.change_event_id})
        MERGE (c)-[rel:NEARBY_CHANGE]->(ch)
        SET rel.time_proximity_hours = toFloat(r.time_proximity_hours),
            rel.scope_match = r.scope_match
        """,
        "Case-NEARBY_CHANGE",
    )


def _load_incident_case_overlap(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE2 / "incident_cases.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        MATCH (i:Incident {id: r.incident_id})
        MERGE (c)-[:OVERLAPS_INCIDENT]->(i)
        """,
        "Case-OVERLAPS_INCIDENT",
    )


def _load_telemetry_findings(session, case_ids):
    findings = summarize_telemetry(DATA_PHASE2 / "case_telemetry.csv")
    findings = _filter(findings, case_ids)
    run_batched(
        session, findings,
        """
        UNWIND $rows AS r
        MERGE (n:TelemetryFinding {id: r.id})
        SET n.case_id = r.case_id,
            n.metric_code = r.metric_code,
            n.reading_count = r.reading_count,
            n.window_start = r.window_start,
            n.window_end = r.window_end,
            n.baseline = r.baseline,
            n.observed_min = r.observed_min,
            n.observed_max = r.observed_max,
            n.status = r.status,
            n.direction = r.direction,
            n.anomaly_start = r.anomaly_start,
            n.anomaly_end = r.anomaly_end
        WITH n, r
        MATCH (c:Case {id: r.case_id})
        MATCH (comp:Component {id: r.component_id})
        MERGE (c)-[:HAS_TELEMETRY_FINDING]->(n)
        MERGE (n)-[:ON_COMPONENT]->(comp)
        """,
        "TelemetryFinding",
    )
