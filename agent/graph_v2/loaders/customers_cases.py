"""Customer + Case nodes and the case's own t=0 observable facts.

Case node properties come EXCLUSIVELY from case_observable.csv -- cases.csv
(the wide file with gt_* columns) is never opened by this module or any
other loader. RAISED is created directly from case_observable.csv's own
customer_id column (customer_cases.csv is redundant with it and is not read
separately).

case_products.csv is filtered to relation == 'reported' only: the
relation == 'confirmed' rows restate gt_product_id and must never become a
graph edge (see dataset_classification.json / GRAPH_DATA_BOUNDARIES.md).
"""
from agent.graph_v2.config import DATA_PHASE2, DATA_PHASE3, DATA_RAW_V2
from agent.graph_v2.db import read_csv, run_batched


def load(session, case_ids=None):
    _load_customers(session)
    _load_cases(session, case_ids)
    _load_reported_products(session, case_ids)
    _load_symptoms(session, case_ids)
    _load_required_skills(session, case_ids)
    _load_phase2_observable_properties(session, case_ids)
    _load_phase3_outcome_properties(session, case_ids)


def _filter(rows, case_ids, col="case_id"):
    if case_ids is None:
        return rows
    return [r for r in rows if r[col] in case_ids]


def _load_customers(session):
    rows = read_csv(DATA_RAW_V2 / "customers.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:Customer {id: r.id})
        SET n.name = r.name, n.tier = r.tier, n.region = r.region,
            n.industry = r.industry, n.company_size = r.company_size,
            n.technical_maturity = r.technical_maturity,
            n.deployment_complexity = r.deployment_complexity,
            n.tenure_months = toInteger(r.tenure_months)
        """,
        "Customer",
    )


def _load_cases(session, case_ids):
    rows = _filter(read_csv(DATA_RAW_V2 / "case_observable.csv"), case_ids, "id")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:Case {id: r.id})
        SET n.title = r.title,
            n.description = r.description,
            n.environment = r.environment,
            n.region = r.region,
            n.reported_business_impact = r.reported_business_impact,
            n.reported_affected_users = toInteger(r.reported_affected_users),
            n.priority = r.priority,
            n.status = r.status,
            n.created_date = r.created_date
        WITH n, r
        MATCH (cust:Customer {id: r.customer_id})
        MERGE (cust)-[:RAISED]->(n)
        """,
        "Case",
    )


def _load_reported_products(session, case_ids):
    rows = [r for r in read_csv(DATA_RAW_V2 / "case_products.csv") if r["relation"] == "reported"]
    rows = _filter(rows, case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        MATCH (p:Product {id: r.product_id})
        MERGE (c)-[:REPORTED_PRODUCT]->(p)
        """,
        "Case-REPORTED_PRODUCT",
    )


def _load_symptoms(session, case_ids):
    rows = _filter(read_csv(DATA_RAW_V2 / "case_symptoms.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        MATCH (s:Symptom {id: r.symptom_id})
        MERGE (c)-[:REPORTS_SYMPTOM]->(s)
        """,
        "Case-REPORTS_SYMPTOM",
    )


def _load_required_skills(session, case_ids):
    rows = _filter(read_csv(DATA_RAW_V2 / "case_required_skills.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        MATCH (s:Skill {id: r.skill_id})
        MERGE (c)-[:REQUIRES_SKILL]->(s)
        """,
        "Case-REQUIRES_SKILL",
    )


def _load_phase2_observable_properties(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE2 / "phase2_observable.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        SET c.has_telemetry = (r.has_telemetry = 'true'),
            c.telemetry_reading_count = toInteger(r.telemetry_reading_count),
            c.signal_count = toInteger(r.signal_count),
            c.nearby_change_count = toInteger(r.nearby_change_count),
            c.config_snapshot_count = toInteger(r.config_snapshot_count),
            c.incident_window_overlap = (r.incident_window_overlap = 'true')
        """,
        "Case phase2_observable properties",
    )


def _load_phase3_outcome_properties(session, case_ids):
    rows = _filter(read_csv(DATA_PHASE3 / "case_outcomes_phase3.csv"), case_ids)
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Case {id: r.case_id})
        SET c.is_resolved = (r.is_resolved = 'true'),
            c.first_touch_resolution = (r.first_touch_resolution = 'true'),
            c.num_routing_transitions = toInteger(r.num_routing_transitions),
            c.num_agents_involved = toInteger(r.num_agents_involved),
            c.num_hypotheses = toInteger(r.num_hypotheses),
            c.num_evidence_queries = toInteger(r.num_evidence_queries),
            c.num_kb_interactions = toInteger(r.num_kb_interactions),
            c.num_similar_case_interactions = toInteger(r.num_similar_case_interactions),
            c.num_resolution_attempts = toInteger(r.num_resolution_attempts),
            c.num_failed_attempts = toInteger(r.num_failed_attempts),
            c.num_collaboration_events = toInteger(r.num_collaboration_events),
            c.escalated = (r.escalated = 'true'),
            c.num_escalations = toInteger(r.num_escalations),
            c.engineering_engaged = (r.engineering_engaged = 'true'),
            c.reopened = (r.reopened = 'true'),
            c.time_to_triage_minutes = toFloat(r.time_to_triage_minutes),
            c.time_to_diagnosis_hours = toFloat(r.time_to_diagnosis_hours),
            c.time_to_mitigation_hours = toFloat(r.time_to_mitigation_hours),
            c.time_to_resolution_hours = toFloat(r.time_to_resolution_hours),
            c.sla_outcome = r.sla_outcome
        """,
        "Case phase3_outcome properties",
    )
