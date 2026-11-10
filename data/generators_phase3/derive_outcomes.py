"""
Computes every Phase 3 CASE-LEVEL derived/hidden table purely by reading the
already-generated OBSERVABLE tables (generate_investigation.py's output) and
comparing them to Phase 1/2 ground truth. Nothing here influences the
observable timeline — this stage runs strictly after it, mirroring how Phase
2 kept `phase2_ground_truth.csv` a pure function of already-generated evidence
rather than something baked into generation.

Produces:
  - case_outcomes_phase3.csv   (observable: counts/timings derived from the
    case's OWN timeline; no comparison to hidden truth)
  - phase3_ground_truth.csv    (hidden: case-level correctness/efficiency
    judgments that require Phase 1/2 truth to compute)
  - phase3_event_quality_labels.csv  (hidden: long/tidy per-event judgments)
  - ideal_investigation_requirements.csv  (hidden: the investigation envelope)
"""
from datetime import datetime

FMT = "%Y-%m-%d %H:%M:%S"


def _parse(s):
    return datetime.strptime(s, FMT)


def _index_by_case(rows):
    out = {}
    for r in rows:
        out.setdefault(r["case_id"], []).append(r)
    return out


def _efficiency_label(n_hyp, n_routing, n_failed, archetype):
    baseline = {"clear": 1, "customer_misdiagnosis": 2, "vague": 2, "wrong_product_mentioned": 2,
                "multi_component_symptoms": 2, "dependency_root_cause": 2}.get(archetype, 2)
    score = (n_hyp - 1) + (n_routing - 1) + n_failed
    if score <= baseline - 1:
        return "efficient"
    if score <= baseline + 1:
        return "moderate"
    return "inefficient"


def _routing_mistake_type(row, case, p2gt):
    if row["to_team_id"] == case["gt_primary_team_id"]:
        return "correct"
    if row["reason_code"] == "capacity_reassignment":
        return "capacity_availability"
    if row["to_team_id"] == case["gt_secondary_team_id"]:
        return "understandable_but_incorrect"
    if case["gt_difficulty_archetype"] in ("customer_misdiagnosis", "wrong_product_mentioned"):
        return "misleading_customer_information"
    if p2gt["evidence_sufficiency"] == "insufficient":
        return "insufficient_evidence"
    return "understandable_but_incorrect" if row["seq"] == "1" else "avoidable_error"


def _escalation_warranted(case, p2gt):
    if case["gt_severity"] in ("Sev1", "Sev2"):
        return True
    if p2gt["evidence_sufficiency"] == "insufficient":
        return True
    if p2gt["incident_relationship"] in ("directly_caused", "partially_influenced"):
        return True
    return False


def _escalation_timing(esc_ts, t_start, t_end, warranted):
    span = (t_end - t_start).total_seconds() or 1.0
    frac = (esc_ts - t_start).total_seconds() / span
    if not warranted:
        return "premature" if frac < 0.5 else "unnecessary"
    if frac < 0.2:
        return "appropriately_early"
    if frac < 0.65:
        return "appropriately_delayed"
    return "late"


def derive(d, tables):
    cases = d["cases"]
    case_by_id = d["case_by_id"]

    routing_by_case = _index_by_case(tables["routing_history"])
    assignment_by_case = _index_by_case(tables["assignment_history"])
    hyp_by_case = _index_by_case(tables["diagnostic_hypotheses"])
    eq_by_case = _index_by_case(tables["evidence_queries"])
    ra_by_case = _index_by_case(tables["resolution_attempts"])
    kb_by_case = _index_by_case(tables["kb_interactions"])
    sim_by_case = _index_by_case(tables["similar_case_interactions"])
    esc_by_case = _index_by_case(tables["escalations"])
    eng_by_case = _index_by_case(tables["engineering_engagements"])
    collab_by_case = _index_by_case(tables["collaboration_events"])
    reopen_by_case = _index_by_case(tables["case_reopens"])
    events_by_case = _index_by_case(tables["case_lifecycle_events"])

    case_outcomes, ground_truth, event_labels, ideal_requirements = [], [], [], []

    for case in cases:
        cid = case["id"]
        p2gt = d["p2gt_by_case"][cid]
        events = sorted(events_by_case.get(cid, []), key=lambda r: int(r["seq"]))
        t_start = _parse(events[0]["timestamp"]) if events else None
        t_end = _parse(events[-1]["timestamp"]) if events else t_start

        routing = sorted(routing_by_case.get(cid, []), key=lambda r: int(r["seq"]))
        assignments = assignment_by_case.get(cid, [])
        hyps = sorted(hyp_by_case.get(cid, []), key=lambda r: int(r["seq"]))
        queries = eq_by_case.get(cid, [])
        attempts = ra_by_case.get(cid, [])
        escalations = esc_by_case.get(cid, [])
        reopens = reopen_by_case.get(cid, [])

        n_failed = sum(1 for a in attempts if a["result"] != "success")
        confirmed_hyps = [h for h in hyps if h["disposition"] == "confirmed"]

        # ── case_outcomes_phase3.csv (observable) ───────────────────────────
        first_touch = len(routing) <= 1 and n_failed == 0
        time_to_triage_min = None
        triage_events = [e for e in events if e["event_type"] == "triage_completed"]
        if triage_events and t_start:
            time_to_triage_min = round((_parse(triage_events[0]["timestamp"]) - t_start).total_seconds() / 60, 1)

        # Which team is "correct" is Phase 1 ground truth, not something a
        # runtime system knows — this timing lives in phase3_ground_truth.csv,
        # not the observable case_outcomes_phase3.csv.
        correct_team_row = next((r for r in routing if r["to_team_id"] == case["gt_primary_team_id"]), None)
        time_to_correct_team_h = round((_parse(correct_team_row["timestamp"]) - t_start).total_seconds() / 3600, 2) \
            if correct_team_row and t_start else None

        diag_events = [e for e in events if e["event_type"] == "hypothesis_confirmed"]
        time_to_diagnosis_h = round((_parse(diag_events[0]["timestamp"]) - t_start).total_seconds() / 3600, 2) \
            if diag_events and t_start else None

        time_to_first_attempt_h = round((_parse(attempts[0]["timestamp"]) - t_start).total_seconds() / 3600, 2) \
            if attempts and t_start else None
        time_to_resolution_h = None
        if not case["is_open"] and attempts and t_start:
            time_to_resolution_h = round((_parse(attempts[-1]["timestamp"]) - t_start).total_seconds() / 3600, 2)

        sla_target = d["sla_target_hours"](case["customer_id"], case["gt_severity"])
        if case["is_open"]:
            sla_outcome = "in_progress"
        elif sla_target is None or time_to_resolution_h is None:
            sla_outcome = "unknown"
        else:
            sla_outcome = "met" if time_to_resolution_h <= sla_target else "missed"

        case_outcomes.append({
            "case_id": cid, "is_resolved": str(not case["is_open"]).lower(),
            "first_touch_resolution": str(first_touch).lower(),
            "num_routing_transitions": max(len(routing) - 1, 0),
            "num_agents_involved": len({a["agent_id"] for a in assignments}),
            "num_hypotheses": len(hyps), "num_evidence_queries": len(queries),
            "num_kb_interactions": len(kb_by_case.get(cid, [])),
            "num_similar_case_interactions": len(sim_by_case.get(cid, [])),
            "num_resolution_attempts": len(attempts), "num_failed_attempts": n_failed,
            "num_collaboration_events": len(collab_by_case.get(cid, [])),
            "escalated": str(bool(escalations)).lower(), "num_escalations": len(escalations),
            "engineering_engaged": str(bool(eng_by_case.get(cid, []))).lower(),
            "reopened": str(bool(reopens)).lower(),
            "time_to_triage_minutes": time_to_triage_min if time_to_triage_min is not None else "",
            "time_to_diagnosis_hours": time_to_diagnosis_h if time_to_diagnosis_h is not None else "",
            "time_to_mitigation_hours": time_to_first_attempt_h if time_to_first_attempt_h is not None else "",
            "time_to_resolution_hours": time_to_resolution_h if time_to_resolution_h is not None else "",
            "sla_outcome": sla_outcome,
        })

        # ── phase3_ground_truth.csv (hidden) ────────────────────────────────
        initial_correct = bool(routing) and routing[0]["to_team_id"] == case["gt_primary_team_id"]
        eventual_correct = bool(routing) and routing[-1]["to_team_id"] in (
            case["gt_primary_team_id"], case["gt_secondary_team_id"])
        diagnosis_ok = bool(confirmed_hyps) and confirmed_hyps[-1]["suspected_root_cause_name"] == \
            d["root_cause_id_to_name"][case["gt_root_cause_id"]]

        causal_change_id = p2gt["causal_change_id"]
        causal_signal_ids = {s for s in p2gt["causal_signal_ids"].split(";") if s}
        all_result_ids = set()
        for q in queries:
            all_result_ids.update(q["result_ref_ids"].split(";"))
        causal_change_identified = bool(causal_change_id) and causal_change_id in all_result_ids
        causal_signal_identified = bool(causal_signal_ids & all_result_ids)
        evidence_available = p2gt["evidence_sufficiency"] == "sufficient"
        critical_evidence_missed = evidence_available and not (causal_change_identified or causal_signal_identified)

        warranted = _escalation_warranted(case, p2gt)
        n_hyp, n_routing_rows = len(hyps), len(routing)
        efficiency = _efficiency_label(n_hyp, n_routing_rows, n_failed, case["gt_difficulty_archetype"])

        ground_truth.append({
            "case_id": cid, "initial_routing_correct": str(initial_correct).lower(),
            "eventual_routing_correct": str(eventual_correct).lower(),
            "diagnosis_matches_truth": str(diagnosis_ok).lower(),
            "causal_change_identified": str(causal_change_identified).lower(),
            "causal_signal_identified": str(causal_signal_identified).lower(),
            "critical_evidence_ids": ";".join(filter(None, [causal_change_id] + sorted(causal_signal_ids))),
            "critical_evidence_missed": str(critical_evidence_missed).lower(),
            "escalation_warranted": str(warranted).lower(),
            "escalation_occurred": str(bool(escalations)).lower(),
            "investigation_efficiency_label": efficiency,
            "sla_outcome": case_outcomes[-1]["sla_outcome"],
            "expected_confidence_band": p2gt["expected_confidence_band"],
            "actual_root_cause_name": d["root_cause_id_to_name"][case["gt_root_cause_id"]],
            "time_to_correct_team_hours": time_to_correct_team_h if time_to_correct_team_h is not None else "",
        })

        # ── phase3_event_quality_labels.csv (hidden, long format) ───────────
        for r in routing:
            event_labels.append({"event_id": r["event_id"], "case_id": cid, "label_name": "routing_mistake_type",
                                  "label_value": _routing_mistake_type(r, case, p2gt)})
        true_rc_name = d["root_cause_id_to_name"][case["gt_root_cause_id"]]
        for h in hyps:
            correct = (h["suspected_category_id"] == case["gt_issue_category_id"] and
                       h["suspected_component_id"] in (case["gt_component_id"], p2gt["causal_component_id"]))
            event_labels.append({"event_id": h["event_id"], "case_id": cid, "label_name": "hypothesis_correct",
                                  "label_value": str(correct).lower()})
            event_labels.append({"event_id": h["event_id"], "case_id": cid, "label_name": "targets_true_root_cause",
                                  "label_value": str(h["suspected_root_cause_name"] == true_rc_name).lower()})
        for a in attempts:
            if a["result"] == "success" and a["resolution_type_id"] == case["gt_resolution_type_id"]:
                appropriateness = "appropriate"
            elif a["human_approval_flagged"] == "true" and a["result"] != "success":
                appropriateness = "risky"
            elif a["result"] in ("no_effect", "inconclusive"):
                appropriateness = "ineffective"
            else:
                appropriateness = "useful_but_unnecessary"
            event_labels.append({"event_id": a["event_id"], "case_id": cid, "label_name": "action_appropriateness",
                                  "label_value": appropriateness})
        for e in escalations:
            esc_ts = _parse(e["timestamp"])
            timing = _escalation_timing(esc_ts, t_start, t_end, warranted) if t_start and t_end else "unknown"
            event_labels.append({"event_id": e["event_id"], "case_id": cid, "label_name": "escalation_warranted",
                                  "label_value": str(warranted).lower()})
            event_labels.append({"event_id": e["event_id"], "case_id": cid, "label_name": "escalation_timing",
                                  "label_value": timing})
        for k in kb_by_case.get(cid, []):
            relevant = k["article_id"] in d["articles_by_root_cause"].get(case["gt_root_cause_id"], [])
            event_labels.append({"event_id": k["event_id"], "case_id": cid, "label_name": "kb_relevant",
                                  "label_value": str(relevant).lower()})
        for s in sim_by_case.get(cid, []):
            other = case_by_id.get(s["similar_case_id"])
            relevant = bool(other) and other["gt_root_cause_id"] == case["gt_root_cause_id"]
            event_labels.append({"event_id": s["event_id"], "case_id": cid, "label_name": "similar_case_relevant",
                                  "label_value": str(relevant).lower()})
            if s["opened"] == "true" and not relevant:
                event_labels.append({"event_id": s["event_id"], "case_id": cid,
                                      "label_name": "similar_case_misleading", "label_value": "true"})

        # ── ideal_investigation_requirements.csv (hidden envelope) ──────────
        rc_name = d["root_cause_id_to_name"][case["gt_root_cause_id"]]
        pattern = et_pattern_lookup(rc_name)
        required_evidence = []
        if pattern:
            if pattern.get("anomalous_metrics"):
                required_evidence.append("telemetry")
            if pattern.get("signal_pool"):
                required_evidence.append("signal")
            if pattern.get("change_type"):
                required_evidence.append("change_event")
            if pattern.get("dependency_flavored"):
                required_evidence.append("dependency_graph")
        if not required_evidence:
            required_evidence.append("customer_info")
        ideal_requirements.append({
            "case_id": cid, "required_evidence_types": ";".join(required_evidence),
            "correct_routing_team_id": case["gt_primary_team_id"],
            "correct_hypothesis_root_cause": rc_name,
            "key_decision_points": "evidence_queried;hypothesis_confirmed;resolution_attempt_succeeded",
            "appropriate_remediation_class": d["resolution_type_id_to_name"].get(case["gt_resolution_type_id"], ""),
        })

    return case_outcomes, ground_truth, event_labels, ideal_requirements


_ET_CACHE = {}


def et_pattern_lookup(root_cause_name):
    if not _ET_CACHE:
        import evidence_taxonomy as et
        _ET_CACHE.update(et.ROOT_CAUSE_EVIDENCE_PATTERNS)
    return _ET_CACHE.get(root_cause_name)
