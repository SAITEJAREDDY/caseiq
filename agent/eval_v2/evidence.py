"""Evidence-retrieval/citation metrics (spec sections 20, 21, 45, 46, 47).
Operates only on a run's own persisted trace_steps/final_diagnosis/
evidence_ids_seen -- never re-derives "what was retrieved" by some other
means, so a run can only get credit for evidence it actually saw this run.
"""


def _split_ids(raw) -> set:
    if not raw:
        return set()
    return {x.strip() for x in str(raw).split(";") if x.strip()}


def _cited_evidence_ids(final_diagnosis: dict) -> set:
    cited = set()
    for hyp in final_diagnosis.get("hypotheses") or []:
        if isinstance(hyp, dict):
            cited.update(hyp.get("supporting_evidence") or [])
            cited.update(hyp.get("contradicting_evidence") or [])
    causal_change = final_diagnosis.get("predicted_causal_change_id")
    if causal_change:
        cited.add(causal_change)
    return cited


def critical_evidence_metrics(run: dict, phase3_gt: dict, phase2_gt: dict) -> dict:
    """Critical evidence = phase3_ground_truth.critical_evidence_ids, unioned
    with phase2_ground_truth's own causal_signal_ids/causal_change_id (the
    two sources describe overlapping but not identical concepts -- phase3's
    list is curated per spec, phase2's is the raw causal id set)."""
    critical = _split_ids((phase3_gt or {}).get("critical_evidence_ids"))
    causal_change_id = (phase2_gt or {}).get("causal_change_id") or ""
    critical |= _split_ids((phase2_gt or {}).get("causal_signal_ids"))
    if causal_change_id:
        critical.add(causal_change_id)

    seen = set(run.get("evidence_ids_seen") or [])
    cited = _cited_evidence_ids(run.get("final_diagnosis") or {})

    retrieved = critical & seen
    cited_and_critical = critical & cited
    return {
        "critical_total": len(critical),
        "critical_ids": sorted(critical),
        "critical_retrieved": len(retrieved),
        "critical_retrieved_ids": sorted(retrieved),
        "critical_cited": len(cited_and_critical),
        "critical_cited_ids": sorted(cited_and_critical),
        "all_critical_retrieved": bool(critical) and retrieved == critical,
        "all_critical_cited": bool(critical) and cited_and_critical == critical,
        "no_critical_evidence_exists": len(critical) == 0,
    }


def distractor_metrics(run: dict, phase2_gt: dict) -> dict:
    distractors = _split_ids((phase2_gt or {}).get("distractor_signal_ids"))
    distractors |= _split_ids((phase2_gt or {}).get("irrelevant_change_ids"))

    seen = set(run.get("evidence_ids_seen") or [])
    cited = _cited_evidence_ids(run.get("final_diagnosis") or {})

    retrieved = distractors & seen
    cited_distractors = distractors & cited

    causal_change_id = (phase2_gt or {}).get("causal_change_id") or ""
    predicted_causal = (run.get("final_diagnosis") or {}).get("predicted_causal_change_id")
    distractor_selected_as_causal = bool(
        predicted_causal and predicted_causal in distractors and predicted_causal != causal_change_id
    )

    return {
        "distractor_total": len(distractors),
        "distractor_ids": sorted(distractors),
        "distractor_retrieved": len(retrieved),
        "distractor_cited": len(cited_distractors),
        "distractor_cited_ids": sorted(cited_distractors),
        "distractor_selected_as_causal_change": distractor_selected_as_causal,
    }


def incident_metrics(run: dict, phase2_gt: dict) -> dict:
    incident_id = (phase2_gt or {}).get("incident_id") or ""
    relationship = (phase2_gt or {}).get("incident_relationship") or "none"
    if not incident_id:
        return {"incident_id": None, "incident_relationship": "none", "incident_retrieved": False, "incident_cited": False}

    seen = set(run.get("evidence_ids_seen") or [])
    retrieved = incident_id in seen

    text_fields = [
        (run.get("final_diagnosis") or {}).get("evidence_summary", ""),
        (run.get("final_diagnosis") or {}).get("rationale", ""),
        " ".join((run.get("final_diagnosis") or {}).get("unresolved_uncertainties") or []),
    ]
    cited = incident_id in _cited_evidence_ids(run.get("final_diagnosis") or {}) or any(
        incident_id in t for t in text_fields if t
    )

    return {
        "incident_id": incident_id,
        "incident_relationship": relationship,
        "incident_retrieved": retrieved,
        "incident_cited": cited,
    }


def unsupported_evidence_count(run: dict) -> int:
    """Reuses the run's own citation_violations -- computed once, at
    execution time, by loop.py -- never re-derived differently here."""
    return len(run.get("citation_violations") or [])
