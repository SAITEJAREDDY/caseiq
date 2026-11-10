"""Phase 3 investigation ontology: evidence-query taxonomy, resolution-action
taxonomy, routing-mistake vocabulary, and the small allowlists that decide
when engineering gets engaged or an action counts as risky.

Static, hand-authored reference data only — no LLM, no randomness. Reuses
Phase 2's 18 issue-category keys (via generators_phase2/evidence_taxonomy.py)
as the join key for "what does an investigator typically check for this kind
of problem," so Phase 3's query behavior is keyed off the same ontology Phase
2's evidence was generated from, rather than a second, independently-invented
taxonomy that would need to be kept in sync by hand.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generators_phase2"))
import evidence_taxonomy as et  # noqa: E402

ISSUE_CATEGORY_KEYS = et.ISSUE_CATEGORY_KEYS
category_key_by_name = et.category_key_by_name


# ── Evidence-query taxonomy ────────────────────────────────────────────────
# Each query type reads from a specific Phase 1/2 table; result rows are only
# ever what already exists there for that case/component — an investigator
# never sees more than what generate_evidence.py / generate_changes.py /
# generate_incidents.py actually generated.

QUERY_TYPES = [
    "get_customer_deployment", "query_telemetry", "query_signals", "query_configuration",
    "query_recent_changes", "query_dependency_graph", "search_similar_cases",
    "search_kb", "check_active_incidents",
]

# category_key -> ordered list of query types a competent investigator would
# try first when that category is the leading hypothesis. Order matters: the
# simulator works down this list, stopping once enough signal is gathered.
CATEGORY_QUERY_PROFILE = {
    "IDENTITY_AUTH": ["query_telemetry", "query_signals", "query_recent_changes", "query_configuration"],
    "AUTHZ": ["query_signals", "query_recent_changes", "query_configuration"],
    "NETWORKING": ["query_telemetry", "check_active_incidents", "query_recent_changes"],
    "PERFORMANCE": ["query_telemetry", "query_dependency_graph", "query_recent_changes"],
    "RELIABILITY": ["query_telemetry", "check_active_incidents", "query_recent_changes"],
    "DEPLOYMENT": ["query_recent_changes", "query_telemetry", "query_signals"],
    "CONFIGURATION": ["query_configuration", "query_recent_changes"],
    "DATA_CORRUPTION": ["query_signals", "query_dependency_graph", "query_configuration"],
    "INTEGRATION_API": ["query_signals", "query_dependency_graph", "query_recent_changes"],
    "PROVISIONING": ["get_customer_deployment", "query_configuration"],
    "SECURITY": ["query_telemetry", "query_signals", "query_recent_changes"],
    "COMPLIANCE": ["query_configuration", "query_signals"],
    "BILLING": ["query_signals", "query_recent_changes"],
    "UX_DEFECT": ["query_telemetry", "query_recent_changes"],
    "STORAGE_DB": ["query_telemetry", "query_signals", "query_dependency_graph"],
    "CAPACITY": ["query_telemetry", "query_recent_changes"],
    "THIRD_PARTY": ["query_signals", "check_active_incidents", "query_dependency_graph"],
    "UNKNOWN": ["query_telemetry", "query_signals"],
}

# Evidence-type vocabulary used in hypothesis_evidence.csv's evidence_type column.
EVIDENCE_TYPES = [
    "telemetry", "signal", "change_event", "incident", "config_snapshot",
    "kb_article", "similar_case", "customer_info", "dependency_graph",
]

QUERY_TYPE_TO_EVIDENCE_TYPE = {
    "get_customer_deployment": "customer_info",
    "query_telemetry": "telemetry",
    "query_signals": "signal",
    "query_configuration": "config_snapshot",
    "query_recent_changes": "change_event",
    "query_dependency_graph": "dependency_graph",
    "search_similar_cases": "similar_case",
    "search_kb": "kb_article",
    "check_active_incidents": "incident",
}


# ── Resolution-action taxonomy ─────────────────────────────────────────────
# resolution_type_id (Phase 1, RT01..RT42) -> action code. Used both for the
# final successful resolution_attempts row (action must match gt_resolution_
# type_id's flavor) and for earlier attempts sampled from the same root
# cause's weighted-but-not-chosen resolution types (plausible failed
# attempts, never arbitrary).

RESOLUTION_TYPE_TO_ACTION = {
    "RT01": "modify_configuration", "RT02": "correct_policy", "RT03": "update_permissions",
    "RT04": "restart_service", "RT05": "renew_certificate", "RT06": "rollback_deployment",
    "RT07": "apply_patch", "RT08": "upgrade_version", "RT09": "remediate_dependency",
    "RT10": "update_dns", "RT11": "increase_capacity", "RT12": "optimize_database",
    "RT13": "clear_cache", "RT14": "disable_feature_flag", "RT15": "apply_workaround",
    "RT16": "educate_customer", "RT17": "correct_documentation", "RT18": "escalate_to_engineering",
    "RT19": "apply_known_issue_workaround", "RT20": "update_firewall_rule",
    "RT21": "reconfigure_load_balancer", "RT22": "rotate_credentials", "RT23": "reset_token_session",
    "RT24": "run_data_repair_script", "RT25": "resync_data", "RT26": "rebuild_index",
    "RT27": "restore_backup", "RT28": "execute_failover", "RT29": "add_monitoring_alert",
    "RT30": "complete_access_review", "RT31": "fix_api_contract", "RT32": "run_schema_migration",
    "RT33": "reprocess_queue", "RT34": "manual_reconciliation", "RT35": "issue_refund",
    "RT36": "correct_billing", "RT37": "engage_vendor", "RT38": "confirm_as_designed",
    "RT39": "close_as_duplicate", "RT40": "confirm_customer_side_fix",
    "RT41": "replace_infrastructure", "RT42": "adjust_rate_limit",
}

# Resolution types that read as an interim/temporary fix rather than a
# structural permanent one — drives mitigations.csv vs a direct permanent
# resolution_attempts row.
MITIGATION_FLAVORED_RESOLUTION_TYPES = {"RT04", "RT13", "RT14", "RT15", "RT19", "RT28"}

# Resolution types risky/production-impacting enough that a human-review
# boundary would realistically apply (spec §41) — flagged, not blocked.
RISKY_RESOLUTION_TYPES = {"RT06", "RT41", "RT28", "RT32", "RT22", "RT20", "RT03"}

# Root causes (Phase 1 root_causes.csv names) rare enough, and structural
# enough, to plausibly need engineering (not just support) involvement.
ENGINEERING_ENGAGEMENT_ROOT_CAUSES = {
    "product defect", "race condition", "incomplete migration", "data migration defect",
    "breaking API contract change", "schema mismatch", "incomplete rollback",
    "idempotency/duplicate-processing failure",
}
ENGINEERING_ACTIVITY_TYPES = [
    "bug_investigation", "log_review", "repro_attempt", "code_level_investigation",
    "product_defect_confirmation", "workaround_creation", "hotfix_development",
    "permanent_fix_planning",
]


# ── Routing / reassignment vocabulary ──────────────────────────────────────

ROUTING_REASON_CODES = [
    "initial_classification", "hypothesis_pivot", "expertise_mismatch",
    "capacity_reassignment", "customer_info_correction", "escalation_driven",
]
# Hidden per-transition judgment vocabulary (phase3_event_quality_labels.csv,
# label_name="routing_mistake_type").
ROUTING_MISTAKE_TYPES = [
    "correct", "understandable_but_incorrect", "avoidable_error",
    "misleading_customer_information", "insufficient_evidence",
    "incorrect_interpretation", "capacity_availability",
]

ASSIGNMENT_REASON_CODES = [
    "initial_assignment", "reassignment_expertise", "reassignment_capacity",
    "reassignment_team_change", "escalation_reassignment",
]


# ── Escalation / collaboration / customer-interaction vocabularies ────────

ESCALATION_TYPES = [
    "severity_escalation", "technical_escalation", "engineering_escalation",
    "management_escalation", "incident_escalation", "customer_escalation",
]
ESCALATION_TRIGGER_CODES = [
    "sla_risk", "repeated_failed_attempts", "severity_critical",
    "customer_pressure", "evidence_insufficient", "incident_correlation",
]

COLLABORATION_TYPES = [
    "sme_review", "peer_review", "engineering_consultation",
    "incident_commander_consultation", "product_team_consultation",
]

CUSTOMER_INTERACTION_TYPES = [
    "request_logs", "request_reproduction_steps", "request_configuration_details",
    "request_affected_user_scope", "communicate_workaround", "provide_status_update",
    "request_validation", "obtain_closure_confirmation",
]

KB_INTERACTION_TYPES = ["searched", "viewed", "applied", "ignored"]

VERIFICATION_TYPES = [
    "telemetry_normalized", "error_rate_baseline_restored", "synthetic_test_passed",
    "customer_confirmed", "affected_users_recovered", "dependency_health_restored",
    "no_recurrence_window",
]

REOPEN_REASONS = [
    "workaround_failed", "symptoms_returned", "incomplete_resolution",
    "regression", "new_affected_workflow_discovered", "misdiagnosed_root_cause",
]

# Initial-triage category/subcategory accuracy target by Phase 1 difficulty
# archetype. Measured directly: the symptom-weighted candidate pool derived
# from case_symptoms.csv/issue_subcategory_symptoms.csv turns out to carry
# essentially the *same* ambiguity (~62% argmax accuracy, ~22% average true-
# candidate weight share) across every archetype — Phase 1's archetype label
# evidently drives other things (case_components.csv count, product_reported_
# id vs gt_product_id, narrative vagueness) rather than symptom-pool
# statistics. Spec §3 explicitly requires triage error rates to vary by
# archetype, so accuracy is set explicitly here; the *wrong* guess, when one
# is drawn, still comes from the real weighted candidate pool (never
# arbitrary) — only the correct/incorrect coin flip itself is archetype-set.
TRIAGE_ACCURACY_BY_ARCHETYPE = {
    "clear": 0.90, "customer_misdiagnosis": 0.30, "vague": 0.40,
    "wrong_product_mentioned": 0.55, "multi_component_symptoms": 0.55,
    "dependency_root_cause": 0.65,
}

# priority (Phase 1 observable: low/medium/high) -> plausible initial severity
# guesses with weights. gt_severity (Sev1-4, hidden) is the truth this is
# compared against to produce over-/under-severity triage errors.
PRIORITY_TO_SEVERITY_GUESS = {
    "high": [("Sev1", 4), ("Sev2", 4), ("Sev3", 1)],
    "medium": [("Sev2", 3), ("Sev3", 4), ("Sev1", 1), ("Sev4", 1)],
    "low": [("Sev3", 4), ("Sev4", 4), ("Sev2", 1)],
}
