"""Orchestrates state + candidates + question -> one Jev system_one() call
-> one raw decision record. This module (like state_builder/candidates/
questions/client) never imports hidden truth -- it only ever sees what a
real support engineer could observe at `as_of`. Scoring against hidden
truth happens later, offline, in scoring.py.
"""
import uuid
from datetime import datetime, timezone
import time

from agent.jev_v2 import candidates as candidates_mod
from agent.jev_v2 import questions
from agent.jev_v2 import state_builder
from agent.jev_v2.config import CANDIDATE_GENERATION_VERSIONS, CANDIDATE_STRATEGY_VERSION, DEFAULT_CONTEXT_VERSION

DECISION_TYPES = ["issue_category", "root_cause", "causal_change", "owning_team", "evidence_sufficiency", "incident_relationship"]


def _new_decision_id(case_id: str, decision_type: str) -> str:
    return f"{case_id}__{decision_type}__{uuid.uuid4().hex[:8]}"


def _record(decision_id, case_id, decision_type, context_version, candidate_meta, candidates, state, as_of, **extra):
    return {
        "decision_id": decision_id,
        "case_id": case_id,
        "decision_type": decision_type,
        "question_id": decision_type,
        "question_version": questions.question_version(decision_type),
        "primitive_type": questions.primitive_type(decision_type),
        "context_version": context_version,
        "candidate_strategy_version": CANDIDATE_STRATEGY_VERSION,
        "candidate_generation_version": (candidate_meta or {}).get("candidate_generation_version") or CANDIDATE_GENERATION_VERSIONS.get(decision_type),
        "candidate_meta": candidate_meta,
        "candidates": candidates,
        "state": state,
        "as_of": as_of,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


def _call_one(client, case_id, decision_type, state, question, candidates, candidate_meta, as_of, context_version):
    decision_id = _new_decision_id(case_id, decision_type)
    key = decision_type
    t0 = time.time()
    try:
        resp = client.system_one(state=state, questions={key: question})
        latency_ms = (time.time() - t0) * 1000
        # In the opaque-key diagnostic control the option keys are aliases;
        # scoring always sees canonical ids (original alias kept for audit).
        answer = candidates_mod.to_canonical_answer(resp["answers"][key], candidate_meta)
        return _record(
            decision_id, case_id, decision_type, context_version, candidate_meta, candidates, state, as_of,
            jev_model=resp.get("model"), answer=answer, usage=resp.get("usage"),
            latency_ms=round(latency_ms, 1), status="ok",
        )
    except Exception as e:
        return _record(
            decision_id, case_id, decision_type, context_version, candidate_meta, candidates, state, as_of,
            status="error", error=str(e),
        )


def build_inputs(session, case_id: str, decision_type: str, as_of: str, context_version: str = DEFAULT_CONTEXT_VERSION, candidate_versions: dict = None, causal_key_mode: str = "canonical"):
    """Pure, side-effect-free construction of (state, candidates, meta) for
    every decision type EXCEPT incident_relationship (variable cardinality
    -- see build_incident_inputs). Shared by both the Jev call path
    (run_decision) and the LLM-baseline path (run_experiment.py's
    --compare-llm), so both see byte-identical inputs for a fair
    comparison, without duplicating the branching logic in two places.

    `candidate_versions` optionally overrides the configured per-decision
    candidate-generation versions (config.CANDIDATE_GENERATION_VERSIONS); only
    causal_change has more than one selectable version today. `causal_key_mode`
    is the opaque-key diagnostic control (candidate_generation_v3 only)."""
    if decision_type == "issue_category":
        state = state_builder.issue_category_state(session, case_id, as_of)
        cands, cmeta = candidates_mod.issue_category_candidates()
        return state, cands, cmeta
    if decision_type == "root_cause":
        state = state_builder.root_cause_state(session, case_id, as_of, context_version)
        candidate_state = state_builder.root_cause_candidate_state(session, case_id, as_of)
        cands, cmeta = candidates_mod.root_cause_candidates(candidate_state)
        return state, cands, cmeta
    if decision_type == "causal_change":
        state = state_builder.causal_change_state(session, case_id, as_of)
        version = (candidate_versions or {}).get("causal_change")
        cands, cmeta = candidates_mod.causal_change_candidates(session, case_id, as_of, version=version, key_mode=causal_key_mode)
        return state, cands, cmeta
    if decision_type == "owning_team":
        state = state_builder.owning_team_state(session, case_id, as_of)
        cands, cmeta = candidates_mod.owning_team_candidates(state)
        return state, cands, cmeta
    if decision_type == "evidence_sufficiency":
        state = state_builder.evidence_sufficiency_state(session, case_id, as_of)
        cands, cmeta = candidates_mod.evidence_sufficiency_candidates()
        return state, cands, cmeta
    raise ValueError(f"build_inputs does not support {decision_type} -- use build_incident_inputs")


def build_incident_inputs(session, case_id: str, as_of: str) -> list:
    """Returns a list of (state, incident_id, meta) tuples, one per
    candidate incident (0 if none overlap this case)."""
    incidents, cmeta = candidates_mod.incident_candidates(session, case_id, as_of)
    out = []
    for incident in incidents:
        state = state_builder.incident_relationship_state(session, case_id, as_of, incident)
        meta = {**cmeta, "incident_id": incident.get("evidence_id")}
        out.append((state, incident.get("evidence_id"), meta))
    return out


def run_decision(client, session, case_id: str, decision_type: str, as_of: str, context_version: str = DEFAULT_CONTEXT_VERSION, candidate_versions: dict = None, causal_key_mode: str = "canonical") -> list:
    """Runs one decision type for one case against Jev. Returns a list of
    raw decision records -- length 1 for every decision type except
    incident_relationship, which returns one record per candidate incident
    (0 if none overlap)."""
    if decision_type == "incident_relationship":
        records = []
        for state, incident_id, meta in build_incident_inputs(session, case_id, as_of):
            q = questions.build_question(decision_type, None)
            rec = _call_one(client, case_id, decision_type, state, q, None, meta, as_of, context_version)
            rec["incident_id"] = incident_id
            records.append(rec)
        return records

    state, cands, cmeta = build_inputs(session, case_id, decision_type, as_of, context_version, candidate_versions, causal_key_mode)
    q = questions.build_question(decision_type, candidates_mod.model_facing_candidates(cands, cmeta))
    return [_call_one(client, case_id, decision_type, state, q, cands, cmeta, as_of, context_version)]


def run_decisions_batched(client, session, case_id: str, decision_types: list, as_of: str, context_version: str = DEFAULT_CONTEXT_VERSION) -> list:
    """Spec section 47's parallel-question experiment: multiple decision
    types' questions batched into ONE system_one call (namespaced state),
    instead of one call per decision type. Excludes incident_relationship
    (variable-cardinality, not a clean 1:1 fit for this comparison)."""
    decision_types = [d for d in decision_types if d != "incident_relationship"]
    per_type_state, per_type_candidates, per_type_meta, per_type_question = {}, {}, {}, {}

    for dt in decision_types:
        if dt == "issue_category":
            per_type_state[dt] = state_builder.issue_category_state(session, case_id, as_of)
            per_type_candidates[dt], per_type_meta[dt] = candidates_mod.issue_category_candidates()
        elif dt == "root_cause":
            per_type_state[dt] = state_builder.root_cause_state(session, case_id, as_of, context_version)
            candidate_state = state_builder.root_cause_candidate_state(session, case_id, as_of)
            per_type_candidates[dt], per_type_meta[dt] = candidates_mod.root_cause_candidates(candidate_state)
        elif dt == "causal_change":
            per_type_state[dt] = state_builder.causal_change_state(session, case_id, as_of)
            per_type_candidates[dt], per_type_meta[dt] = candidates_mod.causal_change_candidates(session, case_id, as_of)
        elif dt == "owning_team":
            per_type_state[dt] = state_builder.owning_team_state(session, case_id, as_of)
            per_type_candidates[dt], per_type_meta[dt] = candidates_mod.owning_team_candidates(per_type_state[dt])
        elif dt == "evidence_sufficiency":
            per_type_state[dt] = state_builder.evidence_sufficiency_state(session, case_id, as_of)
            per_type_candidates[dt], per_type_meta[dt] = candidates_mod.evidence_sufficiency_candidates()
        else:
            raise ValueError(f"unsupported for batching: {dt}")
        per_type_question[dt] = questions.build_question(dt, per_type_candidates[dt])

    merged_state = {dt: per_type_state[dt] for dt in decision_types}
    t0 = time.time()
    try:
        resp = client.system_one(state=merged_state, questions=per_type_question)
        latency_ms = (time.time() - t0) * 1000
        records = []
        for dt in decision_types:
            answer = resp["answers"].get(dt)
            records.append(_record(
                _new_decision_id(case_id, dt), case_id, dt, context_version, per_type_meta[dt],
                per_type_candidates[dt], per_type_state[dt], as_of,
                jev_model=resp.get("model"), answer=answer, usage=resp.get("usage"),
                latency_ms=round(latency_ms, 1), status="ok", batched=True,
            ))
        return records
    except Exception as e:
        return [
            _record(
                _new_decision_id(case_id, dt), case_id, dt, context_version, per_type_meta[dt],
                per_type_candidates[dt], per_type_state[dt], as_of, status="error", error=str(e), batched=True,
            )
            for dt in decision_types
        ]
