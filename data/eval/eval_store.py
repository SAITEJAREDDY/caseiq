"""The Phase 4 evaluation store: a read-only accessor over Phase 1/2/3's
HIDDEN ground-truth files, keyed by case_id.

This module is the ONLY sanctioned way to read evaluation_only data. It is
never imported by anything under agent/graph_v2/, and it never imports
anything from agent/graph_v2/ -- the separation is structural, not just a
comment, and is checked by agent/graph_v2/validate_graph.py's leakage scan
(which greps agent/graph_v2/ source for these filenames, not this file).

A future CaseIQ agent (Phase 5/6) must never be given access to this module;
only an evaluation harness should import it.
"""
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_V2 = PROJECT_ROOT / "data" / "raw_v2"
DATA_PHASE2 = PROJECT_ROOT / "data" / "phase2"
DATA_PHASE3 = PROJECT_ROOT / "data" / "phase3"

_cache = {}


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _indexed(path, key_col, cache_key):
    if cache_key not in _cache:
        _cache[cache_key] = {row[key_col]: row for row in _read_csv(path)}
    return _cache[cache_key]


def _grouped(path, key_col, cache_key):
    if cache_key not in _cache:
        grouped = {}
        for row in _read_csv(path):
            grouped.setdefault(row[key_col], []).append(row)
        _cache[cache_key] = grouped
    return _cache[cache_key]


def get_case_ground_truth(case_id):
    """Phase 1: true product/component/category/root cause/resolution/team/
    severity/escalated/reopened/csat/assigned agent/difficulty archetype."""
    return _indexed(DATA_RAW_V2 / "case_ground_truth.csv", "id", "case_ground_truth").get(case_id)


def get_phase2_ground_truth(case_id):
    """Phase 2: causal component/change/signals, incident relationship,
    evidence sufficiency, expected confidence band."""
    return _indexed(DATA_PHASE2 / "phase2_ground_truth.csv", "case_id", "phase2_ground_truth").get(case_id)


def get_phase3_ground_truth(case_id):
    """Phase 3: routing/diagnosis correctness, escalation warranted/occurred,
    investigation efficiency label, sla outcome, time to correct team."""
    return _indexed(DATA_PHASE3 / "phase3_ground_truth.csv", "case_id", "phase3_ground_truth").get(case_id)


def get_event_quality_labels(case_id):
    """Phase 3: per-event judgments (routing mistake type, hypothesis
    correctness, action appropriateness, escalation timing, KB/similar-case
    relevance) -- long/tidy, one row per (event_id, label_name)."""
    return _grouped(DATA_PHASE3 / "phase3_event_quality_labels.csv", "case_id", "phase3_event_quality_labels").get(case_id, [])


def get_ideal_investigation_requirements(case_id):
    """Phase 3: the investigation envelope -- required evidence types,
    correct routing team, correct hypothesis root cause, key decision
    points, appropriate remediation class."""
    return _indexed(
        DATA_PHASE3 / "ideal_investigation_requirements.csv", "case_id", "ideal_investigation_requirements"
    ).get(case_id)


def get_case_team_ownership(case_id):
    """Phase 1: the authoritative team-ownership set for a case (primary/
    secondary roles) -- richer than the two gt_*_team_id columns alone.
    Returns a list of {case_id, team_id, role} dict rows (possibly empty)."""
    return _grouped(DATA_RAW_V2 / "case_team_ownership.csv", "case_id", "case_team_ownership").get(case_id, [])


def get_incident_relationship(case_id):
    """Phase 2: which incident (if any) this case's time/region overlapped
    and how it actually relates (see phase2_ground_truth.incident_relationship
    for the same fact restated) -- returns a list of {incident_id, case_id,
    relationship} rows (a case could in principle overlap more than one)."""
    return _grouped(DATA_PHASE2 / "incident_cases.csv", "case_id", "incident_cases").get(case_id, [])


def get_full_answer_key(case_id):
    """Convenience: every hidden fact known about a case, merged. For
    building an eval harness's scoring step -- never for anything a runtime
    agent can reach."""
    return {
        "case_ground_truth": get_case_ground_truth(case_id),
        "phase2_ground_truth": get_phase2_ground_truth(case_id),
        "phase3_ground_truth": get_phase3_ground_truth(case_id),
        "event_quality_labels": get_event_quality_labels(case_id),
        "ideal_investigation_requirements": get_ideal_investigation_requirements(case_id),
    }


if __name__ == "__main__":
    import sys

    case_id = sys.argv[1] if len(sys.argv) > 1 else "CS00001"
    import json

    print(json.dumps(get_full_answer_key(case_id), indent=2))
