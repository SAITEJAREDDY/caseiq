"""The runtime decision policy. Jev and the deterministic checks produce SIGNALS; this module (plain code, easy to configure) makes the decision.

Order (first match wins, after collecting every reason that calls for more investigation so the agent gets one clear message):
  invalid final answer / references                  -> HUMAN_REVIEW
  premature / unsupported proposal, Jev missed-evidence >= t, Jev distractor-anchor >= t
                                                     -> CONTINUE_INVESTIGATION on the first pass, HUMAN_REVIEW on the second
  Jev unreachable (and configured to require it)     -> HUMAN_REVIEW
  Jev review signal is PRIORITY_REVIEW               -> PRIORITY_REVIEW
  final answer inconsistent (D3)                     -> HUMAN_REVIEW
  the agent proposed no diagnosis or asked for review-> HUMAN_REVIEW
  agent confidence below the minimum                 -> HUMAN_REVIEW
  otherwise                                          -> ACCEPT
There are never more than two verification passes.
"""
from agent.agent_v3.catalog import TOOL_NAMES
from agent.runtime_verifier.models import ACCEPT, CONTINUE, HUMAN_REVIEW, PRIORITY_REVIEW, VerifierConfig


def continue_message(reasons: list, run: dict, cfg: VerifierConfig) -> str:
    used = {s["tool_name"] for s in run["trace_steps"]}
    unused = [t for t in TOOL_NAMES if t not in used and t != "submit_diagnosis"]
    lines = ["Verification result:", "More investigation required.", "Reasons:"] + [f"- {r}" for r in reasons]
    if unused:
        lines.append("Tools you have not used yet: " + ", ".join(unused) + ".")
    lines.append(f"Continue investigating using available tools. Do not repeat already completed tool calls unless necessary. You have up to {cfg.extra_steps} more tool "
                 "calls; then you will be asked for your final diagnosis again.")
    return "\n".join(lines)


def decide(run: dict, det: dict, jev: dict, round_no: int, cfg: VerifierConfig) -> dict:
    fa = run.get("final_alias_form")
    can_continue = round_no == 1
    out = lambda decision, reason, **kw: {"decision": decision, "reason": reason, "round": round_no, **kw}

    if not det["D1"]["passed"]:
        return out(HUMAN_REVIEW, f"invalid final answer or references: {det['D1']['detail']}", triggers=["D1"])

    more = []                                            # reasons that call for more investigation
    if not det["D4"]["passed"]:
        more.append(("D4", f"premature finalization: {det['D4']['detail']}"))
    if det["D2"]["applicable"] and not det["D2"]["passed"]:
        more.append(("D2", f"the proposed diagnosis is not supported by cited evidence ({det['D2']['detail']})"))
    have_jev = bool(jev and jev.get("available"))
    if have_jev and jev["missed_evidence_probability"] is not None and jev["missed_evidence_probability"] >= cfg.missed_evidence_threshold:
        more.append(("jev_missed_evidence", "possible missed evidence"))
    if have_jev and jev["distractor_anchor_probability"] is not None and jev["distractor_anchor_probability"] >= cfg.distractor_threshold:
        more.append(("jev_distractor_anchor", "possible anchoring on weak or distracting evidence while stronger competing evidence exists"))
    if more:
        triggers, reasons = [t for t, _ in more], [r for _, r in more]
        if can_continue:
            return out(CONTINUE, "; ".join(reasons), triggers=triggers, message=continue_message(reasons, run, cfg))
        return out(HUMAN_REVIEW, "still unresolved after the additional investigation round: " + "; ".join(reasons), triggers=triggers)

    if not have_jev and cfg.require_jev_to_accept:
        return out(HUMAN_REVIEW, "Jev signals were unavailable, so the result cannot be accepted automatically: " + "; ".join((jev or {}).get("errors") or ["no Jev result"]),
                   triggers=["jev_unavailable"])
    probs = (jev or {}).get("review_probabilities") or {}
    if have_jev and (jev.get("review") == "PRIORITY_REVIEW" or probs.get("PRIORITY_REVIEW", 0) >= cfg.priority_review_threshold):
        return out(PRIORITY_REVIEW, "Jev flags this investigation for priority review", triggers=["jev_priority_review"])
    if det["D3"]["applicable"] and not det["D3"]["passed"]:
        return out(HUMAN_REVIEW, f"the final answer is inconsistent: {det['D3']['detail']}", triggers=["D3"])
    if fa["status"] != "DIAGNOSIS_PROPOSED" or fa["human_review_required"]:
        why = fa.get("review_reason") or ("the agent could not propose a diagnosis" if fa["status"] != "DIAGNOSIS_PROPOSED" else "the agent asked for review")
        return out(HUMAN_REVIEW, f"the agent itself did not clear the result: {fa['status']}; {why}", triggers=["agent_requested_review"])
    if fa["confidence"] < cfg.min_confidence:
        return out(HUMAN_REVIEW, f"agent confidence {fa['confidence']} is below {cfg.min_confidence}", triggers=["low_confidence"])
    return out(ACCEPT, "deterministic checks passed and no Jev signal crossed a threshold", triggers=[])
