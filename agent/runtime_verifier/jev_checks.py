"""The three Jev signals (Phase 8: Jev is a useful supporting signal for missed evidence, distractor anchoring and review risk; it is never asked which root cause is right).

Reuses, unchanged, the Phase 8 review packet (`trace_projection_v1`: every id an opaque alias, no free-text rationale), the versioned questions (`missed_evidence_v1`,
`distractor_anchor_v1`, `human_review_v1`) and the direct-HTTP Jev client with its leakage guard. Jev returns typed probabilities only; policy.py decides what to do.
"""
import time

from agent.agent_v3.config import MODEL_NAME
from agent.runtime_verifier.models import REVIEW_LABELS


def build_packet(session, run: dict, case_id: str) -> dict:
    """Runtime-observable material only: the ticket, the agent's trace and answer, and the evidence its own tools could return by the end of its run."""
    from agent.trace_eval_v2.trace_loader import load_trace
    from agent.trace_eval_v2.trace_projection import build_review_context, project

    trace = load_trace({**run, "run_id": f"runtime_{case_id}", "model_name": MODEL_NAME})
    context = build_review_context(session, case_id, run["sim_clock_end"])
    state, _aliaser = project(trace, context, alias_salt="runtime")
    return state


def signals(packet: dict, client=None) -> dict:
    """Three typed calls on the same packet. A failed call is recorded as None, never guessed."""
    from agent.trace_eval_v2 import jev_evaluator

    t0, out, cost_tokens, errors = time.time(), {}, 0, []
    for judgment, key in (("missed_evidence", "missed_evidence_probability"), ("distractor_anchor", "distractor_anchor_probability")):
        raw = jev_evaluator.ask(judgment, packet, client)
        ok = raw["status"] == "ok" and isinstance(raw["answer"].get("noul"), (int, float))
        out[key] = round(float(raw["answer"]["noul"]), 4) if ok else None
        cost_tokens += (raw.get("usage") or {}).get("input_tokens") or 0
        if not ok:
            errors.append(f"{judgment}: {raw.get('error', 'no typed answer')}")
    raw = jev_evaluator.ask("human_review", packet, client)
    probs = raw["answer"].get("probabilities") if raw["status"] == "ok" else None
    if isinstance(probs, dict):
        out["review_probabilities"] = {REVIEW_LABELS.get(k, k): round(float(v), 4) for k, v in probs.items()}
        out["review"] = REVIEW_LABELS.get(raw["answer"].get("choice"), raw["answer"].get("choice"))
    else:
        out["review_probabilities"], out["review"] = None, None
        errors.append(f"human_review: {raw.get('error', 'no typed answer')}")
    cost_tokens += (raw.get("usage") or {}).get("input_tokens") or 0
    out.update(available=not errors, errors=errors, jev_model=raw.get("jev_model"), input_tokens=cost_tokens, latency_ms=round((time.time() - t0) * 1000, 1),
               question_versions={"missed_evidence": "missed_evidence_v1", "distractor_anchor": "distractor_anchor_v1", "review": "human_review_v1"})
    return out
