"""Evaluation-only reference labels for the six Phase 8 judgments (`reference_labels_v1`) and the human-review policy (`review_policy_v1`).

THIS MODULE READS HIDDEN TRUTH. It is imported only by evaluator-side code (scorer, perturbations, corpus selection, reports) and never by
anything that builds or sends a model input (trace_projection, questions, the two judges). validate_boundaries.py enforces the direction.

Every rule is explicit and deterministic, and every rule is documented in docs/TRACE_EVAL_REFERENCE_LABELS.md with its known limits. The rules were
written and frozen before the first Jev or LLM-judge call; they are not tuned to any judge's output. Jev is never the ground truth, and neither is the
LLM judge: both are scored against these labels.

Vocabulary. A trace's *retrieved* evidence is what its diagnostic tool calls returned. *Accessible* evidence is what the agent's own time-gated tools could
return by the end of its run (the inventory in the review packet). *Critical* evidence is the hidden causal set (Phase 3 critical evidence, plus Phase 2's
causal signals and causal change). *Distractors* are the hidden known-misleading signals and irrelevant changes.
"""
import re

from agent.eval_v2.ground_truth import get_hidden_truth
from agent.eval_v2.metrics import evaluate_run
from agent.trace_eval_v2.config import REFERENCE_LABEL_VERSION, REVIEW_POLICY_VERSION
from agent.trace_eval_v2.models import Trace

STOPWORDS = {"the", "and", "for", "with", "from", "into", "that", "this", "detected", "detection", "spike", "issue", "issues", "error", "errors", "problem", "failure",
             "failures", "failed", "service", "services", "unknown", "based", "not", "unspecified", "hypothesis", "none", "null"}
COMMIT_MIN_CONFIDENCE = 0.5
TIE_MARGIN = 0.2
MIN_CRITICAL_COVERAGE = 0.5
STRONG_LINK = 2
CITED_WEIGHT = 100


def tokens(text) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", str(text or "").lower()) if len(t) >= 3 and not t.isdigit() and t not in STOPWORDS}


def _split_ids(raw) -> set:
    return {x.strip() for x in str(raw or "").split(";") if x.strip()}


# ── facts ─────────────────────────────────────────────────────────────────────────────
def _item_texts(trace: Trace) -> dict:
    """evidence id -> the words of everything the tool returned about it (its own string fields, excluding ids and timestamps)."""
    out = {}

    def walk(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("evidence_id"), str):
                words = [str(v) for k, v in obj.items() if isinstance(v, str) and k not in ("evidence_id", "component_id", "started_at", "completed_at", "timestamp", "snapshot_at", "ended_at")]
                out[obj["evidence_id"]] = out.get(obj["evidence_id"], "") + " " + " ".join(words)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    for s in trace.diagnostic_steps:
        if s.status == "ok":
            walk(s.result)
    return out


def last_stated_tops(trace: Trace) -> set:
    """Labels tied for the highest confidence in the last diagnostic step that stated hypotheses (empty when the agent never stated any)."""
    stated = [s for s in trace.diagnostic_steps if any(isinstance(h.get("confidence"), (int, float)) for h in s.hypotheses)]
    if not stated:
        return set()
    hyps = [h for h in stated[-1].hypotheses if isinstance(h.get("confidence"), (int, float))]
    best = max(h["confidence"] for h in hyps)
    return {h["label"] for h in hyps if h["confidence"] == best}


def last_step_words(trace: Trace) -> set:
    """Content words of the evidence the last diagnostic step returned (what could justify a late change of mind)."""
    diag = trace.diagnostic_steps
    if not diag or not diag[-1].evidence:
        return set()
    texts = _item_texts(trace)
    words = set()
    for e in diag[-1].evidence:
        words |= tokens(texts.get(e, ""))
    return words


def top_hypothesis(final: dict) -> dict:
    hyps = [h for h in (final or {}).get("hypotheses") or [] if isinstance(h, dict)]
    if not hyps:
        return {}
    return max(hyps, key=lambda h: (h.get("confidence") if isinstance(h.get("confidence"), (int, float)) else -1.0))


def cited_ids(final: dict) -> set:
    cited = set()
    for h in (final or {}).get("hypotheses") or []:
        if isinstance(h, dict):
            cited.update(h.get("supporting_evidence") or [])
            cited.update(h.get("contradicting_evidence") or [])
    if (final or {}).get("predicted_causal_change_id"):
        cited.add(final["predicted_causal_change_id"])
    return cited


def trace_facts(trace: Trace, inventory_ids: set, truth: dict) -> dict:
    final = trace.final or {}
    p2, p3 = truth["phase2_ground_truth"] or {}, truth["phase3_ground_truth"] or {}
    critical = _split_ids(p3.get("critical_evidence_ids")) | _split_ids(p2.get("causal_signal_ids"))
    if p2.get("causal_change_id"):
        critical.add(p2["causal_change_id"])
    distractors = _split_ids(p2.get("distractor_signal_ids")) | _split_ids(p2.get("irrelevant_change_ids"))
    retrieved = set(trace.retrieved_ids)
    critical_acc = critical & inventory_ids
    cited = cited_ids(final)
    texts = _item_texts(trace)
    top = top_hypothesis(final)
    top_tokens = tokens((top.get("label") or "") + " " + (top.get("description") or ""))

    def weight(e):
        return CITED_WEIGHT if e in cited else len(top_tokens & tokens(texts.get(e, "")))

    hyps = [h for h in final.get("hypotheses") or [] if isinstance(h, dict) and isinstance(h.get("confidence"), (int, float))]
    confs = sorted((h["confidence"] for h in hyps), reverse=True)
    overall = final.get("overall_confidence")
    committed = (trace.stop_reason == "model_submitted" and not final.get("human_review_required") and final.get("evidence_sufficiency") != "insufficient"
                 and isinstance(overall, (int, float)) and overall >= COMMIT_MIN_CONFIDENCE)
    errors = [s for s in trace.diagnostic_steps if s.status == "error"]
    return {
        "retrieved": retrieved, "critical": critical, "critical_accessible": critical_acc, "distractors": distractors, "cited": cited,
        "cited_not_retrieved": cited - retrieved, "retrieved_critical": critical_acc & retrieved, "missed_critical": critical_acc - retrieved,
        "retrieved_distractors": distractors & retrieved, "top": top, "top_tokens": top_tokens, "weight": {e: weight(e) for e in retrieved},
        "has_hypotheses": bool(hyps), "top_two_margin": (confs[0] - confs[1]) if len(confs) >= 2 else None,
        "any_confirmed": any(h.get("status") == "confirmed" for h in hyps), "committed": committed,
        "n_errors": len(errors), "n_redundant": sum(1 for s in trace.diagnostic_steps if s.redundant),
        "n_diagnostic_calls": len(trace.diagnostic_steps), "fallback": not final.get("hypotheses") and trace.stop_reason != "model_submitted",
    }


# ── J1 conclusion support ─────────────────────────────────────────────────────────────
def label_support(f: dict) -> dict:
    """SUPPORTED / PARTIALLY_SUPPORTED / UNSUPPORTED. About support, not correctness: a wrong conclusion resting on misleading evidence can be supported.

    Support items are retrieved evidence the conclusion is tied to: cited by the final answer, or sharing words with the top hypothesis (`link` = number of shared
    content words). SUPPORTED needs a strong tie (cited, or link >= 2), every citation retrieved, some support item that is not a known distractor, and, when
    accessible critical evidence exists, at least half of it retrieved. No tie at all, or nothing hypothesised, is UNSUPPORTED. Anything between is PARTIALLY_SUPPORTED."""
    if not f["has_hypotheses"]:
        return {"label": "UNSUPPORTED", "reason": "no final hypotheses"}
    w = f["weight"]
    linked = {e for e, v in w.items() if v >= 1}
    strong = {e for e, v in w.items() if v >= STRONG_LINK}
    if not linked:
        return {"label": "UNSUPPORTED", "reason": "no retrieved evidence is cited or shares words with the final top hypothesis"}
    reasons = []
    if not strong:
        reasons.append("only a single-word tie to the top hypothesis")
    if f["cited_not_retrieved"]:
        reasons.append("cites evidence that was never retrieved")
    if linked <= f["distractors"]:
        reasons.append("the only supporting evidence is known-misleading")
    if f["critical_accessible"] and len(f["retrieved_critical"]) / len(f["critical_accessible"]) < MIN_CRITICAL_COVERAGE:
        reasons.append("less than half of the accessible critical evidence was retrieved")
    return {"label": "PARTIALLY_SUPPORTED" if reasons else "SUPPORTED", "reason": "; ".join(reasons) or "strong tie to retrieved, relevant evidence"}


# ── J2 missed critical evidence ───────────────────────────────────────────────────────
def label_missed(f: dict) -> dict:
    """Positive when critical evidence that was accessible through the agent's own tools by the end of its run was never retrieved. Evidence the agent could not
    have reached (not in the inventory) is never counted as missed."""
    missed = f["missed_critical"]
    return {"label": bool(missed), "n_missed": len(missed), "n_accessible_critical": len(f["critical_accessible"]),
            "reason": f"{len(missed)} of {len(f['critical_accessible'])} accessible critical items never retrieved" if f["critical_accessible"] else "no accessible critical evidence"}


# ── J3 distractor anchoring ───────────────────────────────────────────────────────────
def label_anchor(f: dict) -> dict:
    """Positive when the conclusion is tied to a retrieved known distractor more strongly than to any retrieved critical evidence (which may be absent). The tie is a citation
    or shared words with the top hypothesis, exactly as in J1."""
    w = f["weight"]
    d = max((w[e] for e in f["retrieved_distractors"]), default=0)
    c = max((w[e] for e in f["retrieved_critical"]), default=0)
    return {"label": d >= 1 and d > c, "distractor_tie": d, "critical_tie": c}


# ── J4 premature conclusion ───────────────────────────────────────────────────────────
def label_premature(f: dict) -> dict:
    """Positive when the agent committed (submitted by its own choice, without flagging review or insufficient evidence, at confidence >= 0.5) while either accessible
    critical evidence had not been retrieved or its own top two hypotheses were still within 0.2 of each other with none confirmed. Tool-call count is not used:
    a short investigation that retrieved what mattered is complete. A forced submit at the tool budget is not a choice to conclude, so it is not premature."""
    gap = bool(f["missed_critical"])
    tie = f["top_two_margin"] is not None and f["top_two_margin"] < TIE_MARGIN and not f["any_confirmed"]
    return {"label": bool(f["committed"] and (gap or tie)), "committed": f["committed"], "evidence_gap": gap, "unresolved_competition": tie}


# ── J5 final-answer consistency ───────────────────────────────────────────────────────
def label_consistency(trace: Trace, f: dict) -> dict:
    """Consistent (True) unless a violation is found. Largely deterministic by design: an intentionally easy control task.
    V1 cites evidence that was never retrieved. V2 the final top hypothesis is not among the last stated top hypotheses, was never stated at any step, and shares no content word with any
    retrieved evidence (a conclusion with no basis anywhere in the trace). V3 confidence contradicts the answer's own state (overall confidence far above the top hypothesis, high
    confidence with unresolved uncertainties or a claimed 'insufficient', no review flag with a claimed 'insufficient'). V4 a structured prediction is populated without its confidence."""
    final = trace.final or {}
    violations = []
    if f["cited_not_retrieved"]:
        violations.append("V1: cites evidence that was never retrieved")
    top = f["top"]
    tops = last_stated_tops(trace)
    ever_stated = {h.get("label") for st in trace.diagnostic_steps for h in st.hypotheses if h.get("label")}
    tied = max(f["weight"].values(), default=0) >= 1
    if ever_stated and top and top.get("label") and top["label"] not in tops and top["label"] not in ever_stated and not tied:
        violations.append("V2: the final top hypothesis was never stated during the investigation and is tied to no retrieved evidence")
    overall, top_conf = final.get("overall_confidence"), top.get("confidence") if top else None
    if isinstance(overall, (int, float)) and isinstance(top_conf, (int, float)) and overall - top_conf > 0.3:
        violations.append("V3: overall confidence is far above the top hypothesis' confidence")
    if isinstance(overall, (int, float)) and overall >= 0.8 and (final.get("unresolved_uncertainties") or final.get("evidence_sufficiency") == "insufficient"):
        violations.append("V3: high confidence despite stated uncertainty or insufficient evidence")
    if final.get("evidence_sufficiency") == "insufficient" and final.get("human_review_required") is False:
        violations.append("V3: claims insufficient evidence without requesting review")
    for field, conf in (("predicted_component_id", "component_confidence"), ("predicted_category_id", "category_confidence"), ("predicted_root_cause_family", "root_cause_confidence"),
                        ("predicted_causal_change_id", "causal_change_confidence"), ("recommended_team_id", "routing_confidence")):
        if final.get(field) and final.get(conf) is None:
            violations.append(f"V4: {field} is populated without {conf}")
    return {"label": not violations, "violations": violations}


# ── outcome (Phase 6 authority) and process ───────────────────────────────────────────
def outcome_label(p6: dict) -> dict:
    """CORRECT / WRONG / UNANSWERED from Phase 6's own deterministic scores (agent.eval_v2.metrics.evaluate_run). If any primary diagnostic field is populated, the
    outcome is CORRECT when at least one is correct and none is wrong; if none is populated, Phase 6's hypothesis recovery decides (a final hypothesis that
    containment-matches the true root cause). Phase 6's text matching under-counts true positives and never over-counts (its own documented limit)."""
    o = p6["outcome"]
    checks = {"root_cause": o["root_cause"]["containment_match"], "component": o["component"]["correct"], "category": o["category"]["correct"],
              "causal_change": (False if o["causal_change"]["false_positive"] else o["causal_change"]["correct"])}
    populated = {k: v for k, v in checks.items() if v is not None}
    hyp = p6["process"]["hypothesis_recovery"]["final_hypothesis_correct"]
    has_final = bool((p6["predictions"] or {}).get("hypotheses"))
    if populated:
        correct = any(populated.values()) and not any(v is False for v in populated.values())
        return {"label": "CORRECT" if correct else "WRONG", "basis": "populated fields", "fields": populated}
    if hyp:
        return {"label": "CORRECT", "basis": "final hypothesis matches the true root cause", "fields": {}}
    return {"label": "WRONG" if has_final else "UNANSWERED", "basis": "no populated field; hypothesis did not match" if has_final else "no answer", "fields": {}}


def process_label(labels: dict, f: dict) -> dict:
    """GOOD when the investigation shows none of the major process defects the judgments look for: an unsupported conclusion, missed critical evidence, distractor anchoring,
    a premature conclusion, an inconsistent final answer, a fallback diagnosis. A PARTIALLY_SUPPORTED conclusion (a single-word tie only) is a minor defect and is tolerated. Independent of
    whether the answer was right."""
    defects = []
    if labels["support"]["label"] == "UNSUPPORTED":
        defects.append("unsupported conclusion")
    if labels["missed_evidence"]["label"]:
        defects.append("missed critical evidence")
    if labels["distractor_anchor"]["label"]:
        defects.append("distractor anchoring")
    if labels["premature_close"]["label"]:
        defects.append("premature conclusion")
    if not labels["final_consistency"]["label"]:
        defects.append("inconsistent final answer")
    if f["fallback"]:
        defects.append("fallback diagnosis")
    return {"label": "GOOD" if not defects else "BAD", "defects": defects}


# ── J6 review policy ──────────────────────────────────────────────────────────────────
def review_policy(trace: Trace, f: dict, labels: dict, outcome: dict, truth: dict, include_hidden_outcome: bool = True) -> dict:
    """review_policy_v1. AUTO_CLOSE / HUMAN_REVIEW / PRIORITY_REVIEW.

    PRIORITY_REVIEW: a wrong or unanswered result that the agent stated with confidence >= 0.8 and no review flag (false-confident); or a failed run (fallback
    diagnosis); or a warranted escalation that the agent did not flag on a wrong or unanswered result.
    HUMAN_REVIEW: any of: wrong or unanswered result; unsupported conclusion; missed critical evidence; a tool error that coincided with an evidence gap; unresolved
    competition between hypotheses when committed; citation violations, a fallback diagnosis or an inconsistent answer; hidden low evidence availability; a warranted escalation the
    agent did not flag. Otherwise AUTO_CLOSE.

    Not a trigger: the final-diagnosis repair event. It is present in every baseline trace (the agent's submit call never matches the output schema), so it cannot tell one trace from
    another; it is reported as a corpus-level finding instead. Decided at label design, before any judge was called.

    `include_hidden_outcome=False` gives the process-only variant (no outcome, low-evidence or escalation triggers): what a reviewer could conclude from the trace's own
    defects. It is reported as a secondary analysis."""
    final = trace.final or {}
    p2, p3 = truth["phase2_ground_truth"] or {}, truth["phase3_ground_truth"] or {}
    not_correct = outcome["label"] != "CORRECT"
    overall = final.get("overall_confidence") if isinstance(final.get("overall_confidence"), (int, float)) else 0.0
    flagged = bool(final.get("human_review_required"))
    escalation_missed = str(p3.get("escalation_warranted", "")).lower() == "true" and not flagged
    triggers = []
    if include_hidden_outcome and not_correct:
        triggers.append("wrong_or_unanswered_result")
    if labels["support"]["label"] == "UNSUPPORTED":
        triggers.append("unsupported_conclusion")
    if labels["missed_evidence"]["label"]:
        triggers.append("missed_critical_evidence")
    if f["n_errors"] >= 1 and f["missed_critical"]:
        triggers.append("tool_error_with_evidence_gap")
    if labels["premature_close"]["unresolved_competition"] and f["committed"]:
        triggers.append("unresolved_competing_hypotheses")
    if trace.citation_violations or not labels["final_consistency"]["label"] or any(e.get("kind") == "final_diagnosis_fallback" for e in trace.repair_events):
        triggers.append("contract_or_consistency_problem")
    if include_hidden_outcome and p2.get("evidence_sufficiency") == "insufficient":
        triggers.append("low_evidence_availability")
    if include_hidden_outcome and escalation_missed:
        triggers.append("warranted_escalation_not_flagged")
    priority = []
    if include_hidden_outcome and not_correct and overall >= 0.8 and not flagged:
        priority.append("false_confident_result")
    if f["fallback"]:
        priority.append("failed_run")
    if include_hidden_outcome and escalation_missed and not_correct:
        priority.append("escalation_missed_on_bad_result")
    tier = "PRIORITY_REVIEW" if priority else ("HUMAN_REVIEW" if triggers else "AUTO_CLOSE")
    return {"label": tier, "triggers": triggers, "priority_triggers": priority}


# ── everything for one trace ──────────────────────────────────────────────────────────
def compute_labels(trace: Trace, inventory_ids: set, truth: dict = None) -> dict:
    truth = truth or get_hidden_truth(trace.case_id)
    p6 = evaluate_run(trace.to_run())
    f = trace_facts(trace, inventory_ids, truth)
    labels = {"support": label_support(f), "missed_evidence": label_missed(f), "distractor_anchor": label_anchor(f),
              "premature_close": label_premature(f), "final_consistency": label_consistency(trace, f)}
    outcome = outcome_label(p6)
    process = process_label(labels, f)
    labels["human_review"] = review_policy(trace, f, labels, outcome, truth)
    labels["human_review_process_only"] = review_policy(trace, f, labels, outcome, truth, include_hidden_outcome=False)
    strat = p6["stratification"]
    return {
        "reference_label_version": REFERENCE_LABEL_VERSION, "review_policy_version": REVIEW_POLICY_VERSION,
        "labels": labels, "outcome": outcome, "process": process,
        "quadrant": ("A" if outcome["label"] == "CORRECT" and process["label"] == "GOOD" else "B" if outcome["label"] == "CORRECT" else "C" if process["label"] == "GOOD" else "D"),
        "facts": {"n_retrieved": len(f["retrieved"]), "n_critical": len(f["critical"]), "n_critical_accessible": len(f["critical_accessible"]), "n_retrieved_critical": len(f["retrieved_critical"]),
                  "n_retrieved_distractors": len(f["retrieved_distractors"]), "n_errors": f["n_errors"], "n_redundant": f["n_redundant"], "n_diagnostic_calls": f["n_diagnostic_calls"],
                  "committed": f["committed"], "has_hypotheses": f["has_hypotheses"], "fallback": f["fallback"]},
        "stratification": strat, "phase6": {"clean_run": p6["process"]["clean_run"], "failure_tags": p6["failure_tags"],
                                            "false_confident": any([p6["outcome"]["root_cause"]["false_confident"], p6["outcome"]["component"]["false_confident"],
                                                                    p6["outcome"]["causal_change"]["false_confident"]]),
                                            "overall_confidence": p6["overall_confidence"], "hypothesis_revisions": p6["process"]["hypothesis_recovery"]["hypothesis_revisions"]},
    }
