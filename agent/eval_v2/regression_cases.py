"""A fixed, permanent regression suite (spec sections 58-59): a small,
stable case-ID list covering the acceptance-scenario types spec'd for
Phase 5, all drawn from the `dev` split so the locked `validation`/`test`
splits are never touched by routine regression checks.

Selection method (a one-time, dev-only lookup against hidden fields,
exactly the pattern already established by agent/agent_v2/run_batch.py's
own case-selection docs -- this file's own runtime use never touches those
fields again, it just hardcodes the resulting nine case IDs so the suite is
stable across code changes):

    dev_ids = case_ids_for_split("dev")
    first case in sorted(dev_ids) matching each criterion below.

| case_id | scenario represented |
|---|---|
| CS00191 | primary Phase 5 acceptance case: clear archetype, real policy change (CH030460) with a distractor config change (CH003378), no causal label exposed |
| CS00001 | clear, sufficient evidence |
| CS00085 | customer_misdiagnosis archetype |
| CS00166 | dependency_root_cause archetype |
| CS00014 | multi_component_symptoms archetype |
| CS00079 | incident_relationship == directly_caused |
| CS00034 | incident_relationship == coincidental_unrelated (must not be attributed) |
| CS00278 | evidence_sufficiency == insufficient |
| CS00012 | conflicting evidence: causal_signal_ids AND distractor_signal_ids AND irrelevant_change_ids all present |
"""

REGRESSION_CASES = {
    "CS00191": "primary_acceptance_case",
    "CS00001": "clear",
    "CS00085": "customer_misdiagnosis",
    "CS00166": "dependency_root_cause",
    "CS00014": "multi_component_symptoms",
    "CS00079": "incident_directly_caused",
    "CS00034": "incident_coincidental_unrelated",
    "CS00278": "insufficient_evidence",
    "CS00012": "conflicting_evidence",
}


def regression_case_ids() -> list:
    return list(REGRESSION_CASES.keys())
