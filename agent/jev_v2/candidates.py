"""Candidate-set generation for every Choice decision (spec sections 3, 9,
10, 40, 42). Every strategy here is observable-rule-based -- built from
reference/topology tables and the same raw tool functions state_builder.py
uses, never from the hidden true answer. Each function returns
`(candidates: dict[key, description_or_None], meta: dict)` where `meta`
records enough about the strategy to compute candidate-recall offline
(scoring.py) without re-deriving the candidate set from scratch.
"""
from collections import defaultdict

from agent.agent_v2.tools import q_active_incidents, q_deployment_history, q_recent_changes
from agent.jev_v2.config import CANDIDATE_GENERATION_VERSIONS, MAX_ROOT_CAUSE_CANDIDATES, MAX_TEAM_CANDIDATES
from agent.jev_v2.reference_data import (
    NO_ROOT_CAUSE_ID,
    all_issue_categories,
    all_root_causes,
    component_root_cause_links,
    component_team_links,
    components_for_product,
    product_team_links,
    subcategory_root_cause_links,
    subcategory_team_links,
    symptom_subcategory_links,
    team_name_lookup,
)

NO_CAUSAL_CHANGE_KEY = "none"


def issue_category_candidates() -> tuple:
    cats = all_issue_categories()
    return cats, {"strategy": "all_canonical_categories", "size": len(cats)}


def _rank(scores: dict) -> list:
    """Deterministic ordering: strongest observable support then stable id."""
    return [key for key, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def root_cause_candidates(state: dict) -> tuple:
    """Bounded v2 candidates from public topology plus case evidence.

    Product topology establishes broad plausibility (weight 1).  A signal on
    a component is more specific, so it contributes weight 4.  Reported
    symptoms contribute through the public symptom/subcategory taxonomy with
    the same weight 4.  None of these relationships contains a case-level
    causal marker; they are exactly the observable reference relations loaded
    into the runtime graph.
    """
    product_id = (state.get("reported_product") or {}).get("id")
    technical = state.get("technical_evidence") or {}
    ticket = state.get("ticket") or {}
    scores = defaultdict(float)
    component_roots = component_root_cause_links()
    symptom_subcats = symptom_subcategory_links()
    subcategory_roots = subcategory_root_cause_links()

    product_components = components_for_product(product_id)
    signal_components = [s.get("component_id") for s in technical.get("signals", []) if s.get("component_id")]
    for component_id in product_components:
        for root_cause_id, support in component_roots.get(component_id, []):
            scores[root_cause_id] += support
    for component_id in signal_components:
        for root_cause_id, support in component_roots.get(component_id, []):
            scores[root_cause_id] += 4.0 * support
    for symptom_name in ticket.get("reported_symptoms") or []:
        for subcategory_id, symptom_support in symptom_subcats.get(symptom_name, []):
            for root_cause_id, root_support in subcategory_roots.get(subcategory_id, []):
                scores[root_cause_id] += 4.0 * symptom_support * root_support

    # RC40 is the canonical taxonomy's explicit abstention / "insufficient
    # information" family, so it stays available independently of evidence.
    ranked = _rank(scores)
    root_limit = max(0, MAX_ROOT_CAUSE_CANDIDATES - 1)
    selected = ranked[:root_limit]
    names = all_root_causes()
    cands = {root_cause_id: names.get(root_cause_id, root_cause_id) for root_cause_id in selected}
    cands[NO_ROOT_CAUSE_ID] = names.get(NO_ROOT_CAUSE_ID, "insufficient information to determine root cause")
    return cands, {
        "strategy": "v2_weighted_product_signal_symptom_topology",
        "size": len(cands), "product_id": product_id,
        "root_cause_cutoff_excluding_rc40": root_limit,
        "source_component_counts": {"product": len(product_components), "signal": len(signal_components)},
        "source_symptom_count": len(ticket.get("reported_symptoms") or []),
        "ordered_candidate_ids": list(cands),
    }


NO_CAUSAL_CHANGE_DESCRIPTION = "No recent change is causally related to this incident"


def _causal_change_candidates_v2(session, case_id: str, as_of: str) -> tuple:
    """Stage B v1/v2 strategy, kept verbatim so those experiments stay
    reproducible. Known limitation (JEV-013): q_recent_changes filters out
    Deployment-type events, so a deployment that is the true cause is never
    offered as an option."""
    result = q_recent_changes(session, case_id, as_of)
    changes = result.get("recent_changes", [])
    cands = {
        c["evidence_id"]: f"{c.get('change_type', 'change')} on {c.get('component_id', 'unknown component')} "
        f"started {c.get('started_at', 'unknown time')}"
        for c in changes
    }
    cands[NO_CAUSAL_CHANGE_KEY] = NO_CAUSAL_CHANGE_DESCRIPTION
    newest_change_id = None
    if changes:
        newest_change_id = max(changes, key=lambda c: c.get("started_at") or "")["evidence_id"]
    return cands, {
        "strategy": "recent_changes_plus_none_option",
        "candidate_generation_version": "v2",
        "size": len(cands),
        "num_real_change_candidates": len(changes),
        "newest_change_id": newest_change_id,
        "change_started_ats": {c["evidence_id"]: c.get("started_at") for c in changes},
    }


def _normalize_causal_event(row: dict, source: str) -> dict:
    """One observable change/deployment row -> one normalized candidate.

    Both tools read the same `ChangeEvent` id space (a deployment is a
    `ChangeEvent:Deployment`), so `evidence_id` is the canonical source id.
    Deliberately NOT carried over: `status` (a completed/rolled-back state can
    post-date the decision time) and `time_proximity_hours`. `environment`
    and `region` are not returned by either Phase 5 projection, so they are
    not available here without a new graph query.
    """
    is_deployment = source == "deployment_history"
    event_type = "deployment" if is_deployment else (row.get("change_type") or "change")
    component = row.get("component_id") or "unknown component"
    started_at = row.get("started_at") or "unknown time"
    deployment_meta = None
    description = f"{event_type} on {component} started {started_at}"
    if is_deployment:
        deployment_meta = {
            "version_from": row.get("version_from"),
            "version_to": row.get("version_to"),
            "rollout_strategy": row.get("rollout_strategy"),
            "deploy_duration_minutes": row.get("deploy_duration_minutes"),
        }
        details = []
        if deployment_meta["version_from"] and deployment_meta["version_to"]:
            details.append(f"version {deployment_meta['version_from']} -> {deployment_meta['version_to']}")
        if deployment_meta["rollout_strategy"]:
            details.append(f"{deployment_meta['rollout_strategy']} rollout")
        if details:
            description += f" ({', '.join(details)})"
    return {
        "source_id": row["evidence_id"], "sources": [source], "event_type": event_type,
        "component_id": row.get("component_id"), "started_at": row.get("started_at"),
        "deployment": deployment_meta, "description": description,
    }


def _causal_change_candidates_v3(session, case_id: str, as_of: str, key_mode: str = "canonical") -> tuple:
    """candidate_generation_v3 (JEV-013): every observable change AND every
    observable deployment, deduplicated by canonical source id, plus the
    explicit "none" option.

    Observable-only: both inputs are Phase 5's own time-gated tool functions,
    and no hidden label or evaluation-only field is read. The rule is
    generic -- it never asks whether an event "should" appear.
    """
    changes = q_recent_changes(session, case_id, as_of).get("recent_changes", [])
    deployments = q_deployment_history(session, case_id, as_of).get("deployments", [])

    merged, duplicates_suppressed, future_dropped = {}, 0, 0
    for source, rows in (("recent_changes", changes), ("deployment_history", deployments)):
        for row in rows:
            # Defensive re-check of the same as_of gate the tools apply in Cypher.
            if row.get("started_at") and str(row["started_at"]) > str(as_of):
                future_dropped += 1
                continue
            event = _normalize_causal_event(row, source)
            existing = merged.get(event["source_id"])
            if existing is not None:
                # Same canonical id from both projections = the same real-world event.
                duplicates_suppressed += 1
                existing["sources"].append(source)
                if event["deployment"] and not existing["deployment"]:
                    existing["deployment"] = event["deployment"]
                continue
            merged[event["source_id"]] = event

    # Deterministic order: newest first, then id.
    ordered = sorted(merged.values(), key=lambda e: (-_ts_rank(e["started_at"]), e["source_id"]))
    cands = {e["source_id"]: e["description"] for e in ordered}
    cands[NO_CAUSAL_CHANGE_KEY] = NO_CAUSAL_CHANGE_DESCRIPTION
    newest_change_id = max(merged.values(), key=lambda e: (e["started_at"] or "", e["source_id"]))["source_id"] if merged else None

    meta = {
        "strategy": "changes_plus_deployments_plus_none_option",
        "candidate_generation_version": "v3",
        "size": len(cands),
        "num_real_change_candidates": len(ordered),
        "num_non_deployment_candidates": sum(1 for e in ordered if e["event_type"] != "deployment"),
        "num_deployment_candidates": sum(1 for e in ordered if e["event_type"] == "deployment"),
        "duplicates_suppressed": duplicates_suppressed,
        "future_events_dropped": future_dropped,
        "newest_change_id": newest_change_id,
        "change_started_ats": {e["source_id"]: e["started_at"] for e in ordered},
        "event_types": {e["source_id"]: e["event_type"] for e in ordered},
        "candidate_events": {e["source_id"]: {k: v for k, v in e.items() if k != "description"} for e in ordered},
        "ordered_candidate_ids": [e["source_id"] for e in ordered] + [NO_CAUSAL_CHANGE_KEY],
        "key_mode": key_mode,
    }
    if key_mode == "opaque":
        # Diagnostic control only: model-facing keys carry no id-number information.
        alias_to_id = {f"option_{i}": e["source_id"] for i, e in enumerate(ordered, start=1)}
        meta["alias_to_id"] = alias_to_id
    elif key_mode != "canonical":
        raise ValueError(f"unknown key_mode: {key_mode}")
    return cands, meta


def _ts_rank(started_at) -> float:
    """Sort helper: ISO-ish timestamps compare lexicographically, so map to a
    number that preserves order without importing datetime parsing rules."""
    if not started_at:
        return 0.0
    digits = "".join(ch for ch in str(started_at) if ch.isdigit())
    return float(digits or 0)


def causal_change_candidates(session, case_id: str, as_of: str, version: str = None, key_mode: str = "canonical") -> tuple:
    """Versioned dispatch. `version=None` uses the configured current version
    (candidate_generation_v3); pass "v2" to reproduce Stage B v1/v2 exactly."""
    version = version or CANDIDATE_GENERATION_VERSIONS["causal_change"]
    if version == "v2":
        if key_mode != "canonical":
            raise ValueError("opaque key mode is only defined for candidate_generation_v3")
        return _causal_change_candidates_v2(session, case_id, as_of)
    if version == "v3":
        return _causal_change_candidates_v3(session, case_id, as_of, key_mode)
    raise ValueError(f"unknown causal_change candidate version: {version}")


def model_facing_candidates(cands: dict, meta: dict) -> dict:
    """The option keys actually sent to Jev/the LLM. Identical to `cands`
    except in the opaque-key diagnostic control, where each real change is
    replaced by an id-free alias (the "none" option is unchanged)."""
    alias_to_id = (meta or {}).get("alias_to_id")
    if not alias_to_id:
        return cands
    out = {alias: cands[source_id] for alias, source_id in alias_to_id.items()}
    if NO_CAUSAL_CHANGE_KEY in cands:
        out[NO_CAUSAL_CHANGE_KEY] = cands[NO_CAUSAL_CHANGE_KEY]
    return out


def to_canonical_answer(answer: dict, meta: dict) -> dict:
    """Map an answer given in model-facing aliases back to canonical ids,
    keeping the original alias for audit. No-op unless aliasing was used."""
    alias_to_id = (meta or {}).get("alias_to_id")
    if not alias_to_id or not isinstance(answer, dict) or "choice" not in answer:
        return answer
    mapped = dict(answer)
    mapped["choice_alias"] = answer.get("choice")
    mapped["choice"] = alias_to_id.get(answer.get("choice"), answer.get("choice"))
    if isinstance(answer.get("probabilities"), dict):
        mapped["probabilities_alias"] = answer["probabilities"]
        mapped["probabilities"] = {alias_to_id.get(k, k): v for k, v in answer["probabilities"].items()}
    return mapped


def owning_team_candidates(state: dict) -> tuple:
    """Return top 12 teams by aggregated observable support.

    This removes v1's order-dependent first-eight deployed-component slice.
    Every deployed component contributes its public ownership weight; the
    product, observed signal components, and ticket symptoms add independent
    public support.  The output remains bounded and deterministically ranked.
    """
    scores = defaultdict(float)
    names = team_name_lookup()
    component_teams = component_team_links()
    product_teams = product_team_links()
    symptom_subcats = symptom_subcategory_links()
    subcategory_teams = subcategory_team_links()
    deployed_components = state.get("deployed_components") or []
    product_id = (state.get("reported_product") or {}).get("id")
    ticket = state.get("ticket") or {}
    evidence = state.get("evidence_summary") or {}
    signal_components = [s.get("component_id") for s in evidence.get("signals", []) if s.get("component_id")]

    for component_id in deployed_components:
        for team_id, support in component_teams.get(component_id, []):
            scores[team_id] += support
    for team_id, support in product_teams.get(product_id, []):
        scores[team_id] += 2.0 * support
    for component_id in signal_components:
        for team_id, support in component_teams.get(component_id, []):
            scores[team_id] += 3.0 * support
    for symptom_name in ticket.get("reported_symptoms") or []:
        for subcategory_id, symptom_support in symptom_subcats.get(symptom_name, []):
            for team_id, team_support in subcategory_teams.get(subcategory_id, []):
                scores[team_id] += 2.0 * symptom_support * team_support

    selected = _rank(scores)[:MAX_TEAM_CANDIDATES]
    if not selected:
        selected = sorted(names)[:MAX_TEAM_CANDIDATES]
        strategy = "v2_fallback_canonical_teams"
    else:
        strategy = "v2_weighted_deployment_product_signal_symptom_support"
    cands = {team_id: names.get(team_id, team_id) for team_id in selected}
    return cands, {
        "strategy": strategy, "size": len(cands), "team_cutoff": MAX_TEAM_CANDIDATES,
        "source_component_counts": {"deployed": len(deployed_components), "signal": len(signal_components)},
        "source_symptom_count": len(ticket.get("reported_symptoms") or []),
        "ordered_candidate_ids": selected,
    }


def evidence_sufficiency_candidates() -> tuple:
    cands = {
        "sufficient": "The available evidence is enough to reach a supported diagnosis without collecting materially more information",
        "partially_sufficient": "Some relevant evidence is available but important gaps remain",
        "insufficient": "The available evidence is too limited or inconclusive to support a diagnosis",
    }
    return cands, {"strategy": "fixed_three_way_evidence_sufficiency", "size": len(cands)}


def incident_candidates(session, case_id: str, as_of: str) -> tuple:
    """Not a Choice candidate set -- returns the list of candidate incidents
    to run one Noul question per (spec section 16)."""
    result = q_active_incidents(session, case_id, as_of)
    incidents = result.get("incidents", [])
    return incidents, {"strategy": "active_incidents_overlapping_case", "size": len(incidents)}
