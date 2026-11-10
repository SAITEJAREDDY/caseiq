"""THE ONLY module in agent/jev_v2/ allowed to import hidden truth (spec
section 64/30: ground truth reaches the deterministic evaluator, never Jev/
the LLM baseline, and Jev never judges its own answer). Pure function: a raw
decision record (already returned by Jev/the LLM, containing no truth) +
hidden truth -> a `scoring` block. Re-running this on the same stored record
must be byte-identical (checked by validate_boundaries.py), matching Phase
6's own determinism guarantee.
"""
from agent.eval_v2.ground_truth import get_hidden_truth
from agent.eval_v2.stratify import stratify_case

NO_CAUSAL_CHANGE_KEY = "none"


def _bool(s):
    return str(s).strip().lower() == "true"


def _choice_prediction(record: dict):
    answer = record.get("answer") or {}
    return answer.get("choice"), answer.get("confidence"), answer.get("probabilities")


def _noul_prediction(record: dict):
    answer = record.get("answer") or {}
    prob = answer.get("noul") if "noul" in answer else answer.get("noul_probability")
    if prob is None:
        return None, None
    predicted_bool = prob >= 0.5
    confidence_in_direction = prob if predicted_bool else (1.0 - prob)
    return predicted_bool, confidence_in_direction, prob


def score_issue_category(record: dict, cgt: dict) -> dict:
    predicted, confidence, probs = _choice_prediction(record)
    truth = cgt.get("gt_issue_category_id")
    candidates = record.get("candidates") or {}
    present = truth in candidates if candidates else None
    correct = (predicted == truth) if predicted is not None else None
    return {
        "ground_truth_value": truth, "predicted_value": predicted, "predicted_confidence": confidence,
        "probabilities": probs, "correct": correct, "acceptable_match": correct,
        "candidate_answer_present": present, "correct_given_present": (correct if present else None),
    }


def score_root_cause(record: dict, cgt: dict) -> dict:
    predicted, confidence, probs = _choice_prediction(record)
    truth = cgt.get("gt_root_cause_id")
    candidates = record.get("candidates") or {}
    present = truth in candidates if candidates else None
    correct = (predicted == truth) if predicted is not None else None
    return {
        "ground_truth_value": truth, "predicted_value": predicted, "predicted_confidence": confidence,
        "probabilities": probs, "correct": correct, "acceptable_match": correct,
        "candidate_answer_present": present, "correct_given_present": (correct if present else None),
    }


def score_causal_change(record: dict, p2gt: dict) -> dict:
    predicted, confidence, probs = _choice_prediction(record)
    truth_id = p2gt.get("causal_change_id") or ""
    truth_key = truth_id if truth_id else NO_CAUSAL_CHANGE_KEY
    candidates = record.get("candidates") or {}
    present = truth_key in candidates if candidates else None
    correct = (predicted == truth_key) if predicted is not None else None

    meta = record.get("candidate_meta") or {}
    newest_id = meta.get("newest_change_id")
    started_ats = meta.get("change_started_ats") or {}
    return {
        "ground_truth_value": truth_key, "predicted_value": predicted, "predicted_confidence": confidence,
        "probabilities": probs, "correct": correct, "acceptable_match": correct,
        "candidate_answer_present": present, "correct_given_present": (correct if present else None),
        "false_positive": bool(predicted and predicted != NO_CAUSAL_CHANGE_KEY and not truth_id),
        "missed": bool(truth_id and predicted == NO_CAUSAL_CHANGE_KEY),
        "distractor_selected": bool(predicted and truth_id and predicted != truth_id and predicted != NO_CAUSAL_CHANGE_KEY),
        "selected_is_newest_change": bool(predicted and newest_id and predicted == newest_id),
        "true_causal_change_is_newest": bool(truth_id and newest_id and truth_id == newest_id),
        "num_candidate_changes": meta.get("num_real_change_candidates"),
        "change_started_ats": started_ats,
    }


def score_owning_team(record: dict, team_ownership: list) -> dict:
    predicted, confidence, probs = _choice_prediction(record)
    primary = {r["team_id"] for r in team_ownership if r.get("role") == "primary"}
    acceptable = {r["team_id"] for r in team_ownership}
    candidates = record.get("candidates") or {}
    primary_present = bool(primary & set(candidates.keys())) if candidates else None
    acceptable_present = bool(acceptable & set(candidates.keys())) if candidates else None
    primary_match = (predicted in primary) if predicted is not None else None
    acceptable_match = (predicted in acceptable) if predicted is not None else None
    # ground_truth_value is a single scalar (the primary team id, or the sole
    # acceptable team if no row is marked primary) -- confusion_and_f1 needs a
    # hashable scalar per record, consistent with every other decision type;
    # the full acceptable set is preserved separately in acceptable_teams.
    truth_scalar = sorted(primary)[0] if primary else (sorted(acceptable)[0] if acceptable else None)
    return {
        "ground_truth_value": truth_scalar, "acceptable_teams": sorted(acceptable),
        "predicted_value": predicted, "predicted_confidence": confidence, "probabilities": probs,
        "correct": primary_match, "acceptable_match": acceptable_match,
        # Keep these generic fields aligned with the historical v1 meaning
        # (any acceptable team offered) for shared Choice metrics.
        "candidate_answer_present": acceptable_present,
        "correct_given_present": (acceptable_match if acceptable_present else None),
        # v2 reports additionally decompose primary and acceptable routing.
        "primary_candidate_present": primary_present,
        "acceptable_candidate_present": acceptable_present,
        "primary_correct_given_present": (primary_match if primary_present else None),
        "acceptable_correct_given_present": (acceptable_match if acceptable_present else None),
    }


def score_evidence_sufficiency(record: dict, p2gt: dict) -> dict:
    predicted, confidence, probs = _choice_prediction(record)
    truth = p2gt.get("evidence_sufficiency")  # already sufficient/partially_sufficient/insufficient -- same label
    # set our candidate keys use, so no relabeling is needed (spec section 17: don't destroy the 3-way label).
    correct = (predicted == truth) if predicted is not None else None
    return {
        "ground_truth_value": truth, "predicted_value": predicted, "predicted_confidence": confidence,
        "probabilities": probs, "correct": correct, "acceptable_match": correct,
        "candidate_answer_present": True, "correct_given_present": correct,
    }


def score_incident_relationship(record: dict, p2gt: dict) -> dict:
    predicted_bool, confidence, raw_prob = _noul_prediction(record)
    incident_id = record.get("incident_id")
    truth_incident_id = p2gt.get("incident_id") or ""
    relationship = p2gt.get("incident_relationship") or "none"
    is_true_incident = bool(incident_id) and incident_id == truth_incident_id
    truth_bool = is_true_incident and relationship in ("directly_caused", "partially_influenced")
    correct = (predicted_bool == truth_bool) if predicted_bool is not None else None
    return {
        "ground_truth_value": truth_bool, "predicted_value": predicted_bool, "predicted_confidence": confidence,
        "raw_probability_for_true": raw_prob, "correct": correct, "acceptable_match": correct,
        "candidate_answer_present": True, "correct_given_present": correct,
        "is_true_incident_candidate": is_true_incident, "incident_relationship": relationship,
    }


_SCORERS = {
    "issue_category": lambda rec, truth: score_issue_category(rec, truth["case_ground_truth"] or {}),
    "root_cause": lambda rec, truth: score_root_cause(rec, truth["case_ground_truth"] or {}),
    "causal_change": lambda rec, truth: score_causal_change(rec, truth["phase2_ground_truth"] or {}),
    "owning_team": lambda rec, truth: score_owning_team(rec, truth["case_team_ownership"] or []),
    "evidence_sufficiency": lambda rec, truth: score_evidence_sufficiency(rec, truth["phase2_ground_truth"] or {}),
    "incident_relationship": lambda rec, truth: score_incident_relationship(rec, truth["phase2_ground_truth"] or {}),
}


def score_decision(record: dict) -> dict:
    """Returns a NEW dict (record + 'scoring' + 'stratification'); never
    mutates the input, so re-scoring a stored record is trivially safe to
    repeat (spec section 60's determinism requirement)."""
    if record.get("status") != "ok":
        return {**record, "scoring": {"correct": None, "note": "decision record status was not ok; not scored"}, "stratification": stratify_case(record["case_id"])}

    truth = get_hidden_truth(record["case_id"])
    decision_type = record["decision_type"]
    scorer = _SCORERS.get(decision_type)
    if scorer is None:
        raise ValueError(f"no scorer registered for decision_type={decision_type}")

    scoring = scorer(record, truth)
    scoring["contract_failure"] = record.get("contract_failure")
    if record.get("contract_failure"):
        scoring["correct"] = None
        scoring["acceptable_match"] = None

    return {**record, "scoring": scoring, "stratification": stratify_case(record["case_id"])}
