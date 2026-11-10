"""Stratification metadata (spec section 3): a deterministic case_id -> dict
of slicing dimensions, computed purely from hidden ground truth. Used both
by splits.py (to build stratified dev/validation/test partitions) and by
aggregate.py (to slice metrics by difficulty/category/evidence-sufficiency/
scenario-type without ever reporting only overall averages).
"""
from agent.eval_v2.ground_truth import get_hidden_truth


def _bool(s):
    return str(s).strip().lower() == "true"


def stratify_case(case_id: str) -> dict:
    truth = get_hidden_truth(case_id)
    cgt = truth["case_ground_truth"] or {}
    p2gt = truth["phase2_ground_truth"] or {}

    archetype = cgt.get("gt_difficulty_archetype", "")
    evidence_sufficiency = p2gt.get("evidence_sufficiency", "")
    incident_relationship = p2gt.get("incident_relationship") or "none"

    return {
        "case_id": case_id,
        "difficulty_archetype": archetype,
        "issue_category_id": cgt.get("gt_issue_category_id", ""),
        "issue_subcategory_id": cgt.get("gt_issue_subcategory_id", ""),
        "root_cause_id": cgt.get("gt_root_cause_id", ""),
        "product_id": cgt.get("gt_product_id", ""),
        "component_id": cgt.get("gt_component_id", ""),
        "severity": cgt.get("gt_severity", ""),
        "evidence_sufficiency": evidence_sufficiency,
        "incident_relationship": incident_relationship,
        "incident_involved": incident_relationship != "none",
        "dependency_driven": _bool(p2gt.get("external_dependency_causal", "false")),
        "customer_misdiagnosis": archetype == "customer_misdiagnosis",
        "multi_component": archetype == "multi_component_symptoms",
        "ambiguous": archetype in ("vague", "wrong_product_mentioned"),
        "low_evidence": evidence_sufficiency == "insufficient",
        "reopened": _bool(cgt.get("gt_reopened", "false")),
        "escalated": _bool(cgt.get("gt_escalated", "false")),
        # (archetype, evidence_sufficiency) is the stratification key splits.py partitions on
        "stratum_key": f"{archetype}|{evidence_sufficiency}",
    }
