"""Per-case deterministic scoring (spec sections 5-18, 25-27, 33). Pure
function over one persisted agent run + hidden ground truth -- no LLM calls,
no randomness, so scoring the same run twice yields byte-identical output
(verified by validate_boundaries.py).
"""
import re

from agent.eval_v2 import contract, evidence, text_match
from agent.eval_v2.config import CONFIDENCE_BUCKETS, FALSE_CONFIDENT_THRESHOLD, SEVERITY_ORDER
from agent.eval_v2.ground_truth import get_hidden_truth, root_cause_name

_MODEL_NAME_TO_PROVIDER = {
    "openai/gpt-oss-120b": "groq",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": "together",
}

_SEVERITY_ALIASES = {
    "sev1": 1, "p1": 1, "critical": 1, "urgent": 1, "1": 1,
    "sev2": 2, "p2": 2, "high": 2, "2": 2,
    "sev3": 3, "p3": 3, "medium": 3, "moderate": 3, "3": 3,
    "sev4": 4, "p4": 4, "low": 4, "minor": 4, "4": 4,
}


def _bool(s) -> bool:
    return str(s).strip().lower() == "true"


def normalize_severity(raw) -> "int | None":
    """Deterministic alias table -- the agent's predicted_severity is free
    text (schema has no enum constraint), ground truth is always exactly
    'Sev1'..'Sev4'. Returns None (excluded from severity accuracy, not
    scored as wrong) when unmapped, matching the "don't force a guess"
    handling used for every other nullable prediction field."""
    if not raw:
        return None
    key = re.sub(r"[^a-z0-9]", "", str(raw).lower())
    return _SEVERITY_ALIASES.get(key)


def effective_model_provider(run: dict) -> str:
    return _MODEL_NAME_TO_PROVIDER.get(run.get("model_name"), run.get("model_provider", "unknown"))


def _confidence_bucket(conf) -> "str | None":
    if conf is None:
        return None
    for lo, hi in CONFIDENCE_BUCKETS:
        if lo <= conf < hi:
            return f"{lo:.2f}-{min(hi, 1.0):.2f}"
    return None


def _field_outcome(predicted, truth_id, confidence) -> dict:
    predicted_present = predicted is not None and predicted != ""
    truth_present = truth_id is not None and truth_id != ""
    correct = predicted_present and truth_present and predicted == truth_id
    return {
        "predicted": predicted,
        "truth": truth_id,
        "predicted_present": predicted_present,
        "correct": correct if predicted_present else None,  # None = no prediction made, excluded from accuracy
        "confidence": confidence,
        "confidence_bucket": _confidence_bucket(confidence),
        "false_confident": bool(
            predicted_present and not correct and confidence is not None and confidence >= FALSE_CONFIDENT_THRESHOLD
        ),
    }


def _hypothesis_labels(hyp_list) -> list:
    out = []
    for h in hyp_list or []:
        if isinstance(h, dict) and h.get("label"):
            out.append(h["label"])
        elif isinstance(h, str) and ":" in h:
            out.append(h.rsplit(":", 1)[0])
        elif isinstance(h, str):
            out.append(h)
    return out


def _hypothesis_recovery(trace_steps: list, root_cause_truth_name: str) -> dict:
    """Uses ONLY structured hypothesis-state strings already on every trace
    step (spec section 25's explicit instruction: never private reasoning).
    A step's hypothesis 'matches' truth via text_match's containment tier
    (deterministic, documented limitation same as the root-cause metric)."""
    diagnostic_steps = [s for s in trace_steps if s.get("tool_name") != "submit_diagnosis" and s.get("hypotheses")]
    if not diagnostic_steps or not root_cause_truth_name:
        return {
            "initial_hypothesis_correct": None, "final_hypothesis_correct": None,
            "hypothesis_revisions": 0, "recovered_from_wrong_initial": None,
            "abandoned_correct_hypothesis": None,
        }

    def any_correct(step_hyps):
        return any(text_match.containment_match(label, root_cause_truth_name) for label in _hypothesis_labels(step_hyps))

    per_step_correct = [any_correct(s["hypotheses"]) for s in diagnostic_steps]
    initial_correct = per_step_correct[0]
    final_correct = per_step_correct[-1]

    revisions = 0
    prev = _hypothesis_labels(diagnostic_steps[0]["hypotheses"])
    for s in diagnostic_steps[1:]:
        cur = _hypothesis_labels(s["hypotheses"])
        if set(cur) != set(prev):
            revisions += 1
        prev = cur

    return {
        "initial_hypothesis_correct": initial_correct,
        "final_hypothesis_correct": final_correct,
        "hypothesis_revisions": revisions,
        "recovered_from_wrong_initial": (not initial_correct) and final_correct,
        "abandoned_correct_hypothesis": initial_correct and not final_correct,
    }


def _failure_tags(outcome: dict, ev: dict, process: dict, fd: dict, strat: dict) -> list:
    tags = []
    if outcome["product"]["correct"] is False:
        tags.append("wrong_product")
    if outcome["component"]["correct"] is False:
        tags.append("wrong_component")
    if outcome["category"]["correct"] is False:
        tags.append("wrong_issue_category")
    if outcome["root_cause"]["exact_match"] is False and outcome["root_cause"]["containment_match"] is False:
        tags.append("wrong_root_cause")
    if outcome["causal_change"]["false_positive"] or outcome["causal_change"]["missed"]:
        tags.append("wrong_causal_change")
    if outcome["team"]["acceptable_match"] is False:
        tags.append("wrong_team")
    if outcome["severity"]["exact"] is False and outcome["severity"]["within_one"] is False:
        tags.append("severity_error")
    if ev["incident"]["incident_relationship"] in ("directly_caused", "partially_influenced") and not ev["incident"]["incident_retrieved"]:
        tags.append("missed_incident")
    if ev["incident"]["incident_relationship"] in ("coincidental_unrelated", "customer_assumed_incorrectly") and ev["incident"]["incident_cited"]:
        tags.append("false_incident_attribution")
    if strat.get("low_evidence") and (fd.get("overall_confidence") or 0) >= FALSE_CONFIDENT_THRESHOLD:
        tags.append("insufficient_evidence_overconfident")
    if not ev["critical"]["all_critical_retrieved"] and not ev["critical"]["no_critical_evidence_exists"]:
        tags.append("critical_evidence_missed")
    if ev["distractor"]["distractor_selected_as_causal_change"]:
        tags.append("distractor_selected")
    if process["tool"]["redundant_calls"] > 0:
        tags.append("tool_loop_redundancy")
    if (process["repair"].get("repair_event_count") or 0) > 0 or process["unsupported_evidence_count"] > 0:
        tags.append("contract_schema_problem")
    if process["stop_reason"] == "tool_budget_exhausted":
        tags.append("budget_exhaustion")
    if process["tool"]["tool_errors"] > process["tool"]["unknown_tool_calls"]:
        tags.append("tool_failure")
    if process["stop_reason"] == "model_submitted" and process["tool"]["diagnostic_tool_calls"] <= 2 and fd.get("evidence_sufficiency") != "sufficient":
        tags.append("agent_stopped_too_early")
    return tags


def evaluate_run(run: dict) -> dict:
    case_id = run["case_id"]
    fd = run.get("final_diagnosis") or {}
    truth = get_hidden_truth(case_id)
    cgt = truth["case_ground_truth"] or {}
    p2gt = truth["phase2_ground_truth"] or {}
    p3gt = truth["phase3_ground_truth"] or {}
    team_ownership = truth["case_team_ownership"] or []

    from agent.eval_v2.stratify import stratify_case
    strat = stratify_case(case_id)

    # ── Outcome ──────────────────────────────────────────────────────────
    product = _field_outcome(fd.get("predicted_product_id"), cgt.get("gt_product_id"), fd.get("product_confidence"))
    component = _field_outcome(fd.get("predicted_component_id"), cgt.get("gt_component_id"), fd.get("component_confidence"))
    category = _field_outcome(fd.get("predicted_category_id"), cgt.get("gt_issue_category_id"), fd.get("category_confidence"))
    subcategory = _field_outcome(fd.get("predicted_subcategory_id"), cgt.get("gt_issue_subcategory_id"), None)

    rc_predicted = fd.get("predicted_root_cause_family")
    rc_truth_name = root_cause_name(cgt.get("gt_root_cause_id")) or ""
    rc_truth_name_p3 = p3gt.get("actual_root_cause_name") or ""
    root_cause = {
        "predicted": rc_predicted,
        "truth_root_cause_name": rc_truth_name,
        "truth_actual_root_cause_name": rc_truth_name_p3,
        "predicted_present": bool(rc_predicted),
        "exact_match": (text_match.exact_match(rc_predicted, rc_truth_name) or text_match.exact_match(rc_predicted, rc_truth_name_p3)) if rc_predicted else None,
        "containment_match": (text_match.containment_match(rc_predicted, rc_truth_name) or text_match.containment_match(rc_predicted, rc_truth_name_p3)) if rc_predicted else None,
        "confidence": fd.get("root_cause_confidence"),
        "confidence_bucket": _confidence_bucket(fd.get("root_cause_confidence")),
    }
    root_cause["false_confident"] = bool(
        rc_predicted and not root_cause["containment_match"] and (fd.get("root_cause_confidence") or 0) >= FALSE_CONFIDENT_THRESHOLD
    )

    causal_change_truth = p2gt.get("causal_change_id") or ""
    causal_change_pred = fd.get("predicted_causal_change_id")
    if not causal_change_truth or not causal_change_pred:
        # No prediction, or no true causal change to score against: neither is
        # "wrong" (that would conflate "didn't answer" with "answered incorrectly"
        # -- see the null-handling rule in docs/EVALUATION_METRICS.md). 'missed'
        # and 'false_positive' below capture these two cases separately instead.
        causal_change_correct = None
    else:
        causal_change_correct = causal_change_pred == causal_change_truth
    causal_change = {
        "predicted": causal_change_pred,
        "truth": causal_change_truth or None,
        "correct": causal_change_correct,
        "false_positive": bool(causal_change_pred) and not causal_change_truth,
        "missed": bool(causal_change_truth) and not causal_change_pred,
        "confidence": fd.get("causal_change_confidence"),
        "false_confident": bool(
            causal_change_pred and causal_change_pred != causal_change_truth
            and (fd.get("causal_change_confidence") or 0) >= FALSE_CONFIDENT_THRESHOLD
        ),
    }

    sev_pred_raw = fd.get("predicted_severity")
    sev_pred = normalize_severity(sev_pred_raw)
    sev_truth = SEVERITY_ORDER.get(cgt.get("gt_severity"))
    severity = {
        "predicted_raw": sev_pred_raw,
        "predicted_normalized": sev_pred,
        "truth": cgt.get("gt_severity"),
        "exact": (sev_pred == sev_truth) if (sev_pred is not None and sev_truth is not None) else None,
        "within_one": (abs(sev_pred - sev_truth) <= 1) if (sev_pred is not None and sev_truth is not None) else None,
        "over_severity": (sev_pred is not None and sev_truth is not None and sev_pred < sev_truth),  # predicted MORE severe
        "under_severity": (sev_pred is not None and sev_truth is not None and sev_pred > sev_truth),  # predicted LESS severe
        "confidence": fd.get("severity_confidence"),
    }

    acceptable_teams = {row["team_id"] for row in team_ownership}
    primary_teams = {row["team_id"] for row in team_ownership if row.get("role") == "primary"}
    team_pred = fd.get("recommended_team_id")
    team = {
        "predicted": team_pred,
        "acceptable_teams": sorted(acceptable_teams),
        "primary_teams": sorted(primary_teams),
        "primary_match": (team_pred in primary_teams) if team_pred else None,
        "acceptable_match": (team_pred in acceptable_teams) if team_pred else None,
        "confidence": fd.get("routing_confidence"),
    }

    ref_human_review = (
        p2gt.get("evidence_sufficiency") == "insufficient"
        or _bool(p3gt.get("escalation_warranted", "false"))
        or p2gt.get("expected_confidence_band") == "low"
    )
    human_review = {
        "agent_flagged": fd.get("human_review_required"),
        "reference_derived": ref_human_review,
        "agrees_with_reference": fd.get("human_review_required") == ref_human_review,
        "note": "reference_derived is a documented proxy (evidence_sufficiency==insufficient OR "
                "escalation_warranted OR expected_confidence_band==low), not a direct ground-truth field",
    }

    evidence_sufficiency_map = {"sufficient": "sufficient", "partially_sufficient": "partial", "insufficient": "insufficient"}
    evidence_sufficiency = {
        "predicted": fd.get("evidence_sufficiency"),
        "truth": p2gt.get("evidence_sufficiency"),
        "truth_mapped_to_agent_labels": evidence_sufficiency_map.get(p2gt.get("evidence_sufficiency")),
        "correct": fd.get("evidence_sufficiency") == evidence_sufficiency_map.get(p2gt.get("evidence_sufficiency")),
    }

    outcome = {
        "product": product, "component": component, "category": category, "subcategory": subcategory,
        "root_cause": root_cause, "causal_change": causal_change, "severity": severity, "team": team,
        "human_review": human_review, "evidence_sufficiency": evidence_sufficiency,
    }

    # ── Evidence ─────────────────────────────────────────────────────────
    ev = {
        "critical": evidence.critical_evidence_metrics(run, p3gt, p2gt),
        "distractor": evidence.distractor_metrics(run, p2gt),
        "incident": evidence.incident_metrics(run, p2gt),
    }

    # ── Process ──────────────────────────────────────────────────────────
    tool_metrics = contract.tool_use_metrics(run.get("trace_steps") or [])
    repair = contract.repair_summary(run)
    hyp_recovery = _hypothesis_recovery(run.get("trace_steps") or [], rc_truth_name or rc_truth_name_p3)
    process = {
        "stop_reason": run.get("stop_reason"),
        "tool": tool_metrics,
        "repair": repair,
        "clean_run": contract.is_clean_run(run, tool_metrics, repair),
        "unsupported_evidence_count": evidence.unsupported_evidence_count(run),
        "hypothesis_recovery": hyp_recovery,
    }

    # ── Efficiency ───────────────────────────────────────────────────────
    total_llm_latency_ms = sum((s.get("latency_ms") or 0) for s in (run.get("trace_steps") or []))
    efficiency = {
        "num_tool_calls": run.get("num_tool_calls"),
        "num_llm_calls": run.get("num_llm_calls"),
        "token_usage": run.get("token_usage"),
        "approx_cost_usd": run.get("approx_cost_usd"),
        "total_llm_latency_ms": round(total_llm_latency_ms, 1),
    }

    record = {
        "run_id": run.get("run_id"),
        "case_id": case_id,
        "model_provider_recorded": run.get("model_provider"),
        "effective_model_provider": effective_model_provider(run),
        "model_name": run.get("model_name"),
        "versions": {
            "prompt_version": run.get("prompt_version"),
            "toolset_version": run.get("toolset_version"),
            "output_schema_version": run.get("output_schema_version"),
            "agent_loop_version": run.get("agent_loop_version"),
            "repair_layer_version": run.get("repair_layer_version"),
            "graph_version": run.get("graph_version"),
        },
        "stratification": strat,
        "predictions": fd,
        "outcome": outcome,
        "evidence": ev,
        "process": process,
        "efficiency": efficiency,
        "overall_confidence": fd.get("overall_confidence"),
        "overall_confidence_bucket": _confidence_bucket(fd.get("overall_confidence")),
    }
    record["failure_tags"] = _failure_tags(outcome, ev, process, fd, strat)
    return record
