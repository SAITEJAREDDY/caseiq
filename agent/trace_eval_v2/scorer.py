"""Scoring: raw judge records (Jev or LLM) + reference labels -> scored rows, and the observable-only deterministic baselines.

Evaluator side. This is where hidden-truth-derived reference labels meet judge outputs, always after the judge has answered. Judges are scored against the reference labels only; neither
judge is ever scored by agreement with the other.

Binary targets (positive = the YES condition of the question):
  J1 support            positive = SUPPORTED; UNSUPPORTED is negative; PARTIALLY_SUPPORTED is the ambiguous middle band and is excluded from the binary headline (reported separately).
  J2 missed evidence    positive = accessible critical evidence was never retrieved.
  J3 distractor anchor  positive = the conclusion is tied to a known distractor more strongly than to critical evidence.
  J4 premature close    positive = committed while an evidence gap or unresolved competition remained.
  J5 final consistency  positive = consistent (no violation found).
  J6 human review       three tiers; the binary view is "problematic" = not AUTO_CLOSE, scored on 1 - P(AUTO_CLOSE) for Jev and on the hard choice for the LLM judge. `p_level` is the
                        expected review level scaled to [0, 1] ((P_HUMAN + 2 P_PRIORITY) / 2 for Jev, 0 / 0.5 / 1 for the LLM's hard choice); the metamorphic tests use it because P(AUTO_CLOSE) is near 0
                        for almost every trace, which leaves "review goes up" no headroom (Stage A finding).
"""
from agent.jev_v2.aggregate import decision_cost_usd
from agent.trace_eval_v2 import labels as L
from agent.trace_eval_v2.config import JUDGMENTS
from agent.trace_eval_v2.models import Trace

REVIEW_TIERS = ["AUTO_CLOSE", "HUMAN_REVIEW", "PRIORITY_REVIEW"]
EMPTY_TRUTH = {"phase2_ground_truth": {}, "phase3_ground_truth": {}}


def binary_target(judgment: str, labels: dict):
    lab = labels["labels"]
    if judgment == "support":
        return {"SUPPORTED": 1, "UNSUPPORTED": 0}.get(lab["support"]["label"])
    if judgment == "missed_evidence":
        return int(lab["missed_evidence"]["label"])
    if judgment == "distractor_anchor":
        return int(lab["distractor_anchor"]["label"])
    if judgment == "premature_close":
        return int(lab["premature_close"]["label"])
    if judgment == "final_consistency":
        return int(lab["final_consistency"]["label"])
    if judgment == "human_review":
        return int(lab["human_review"]["label"] != "AUTO_CLOSE")
    raise ValueError(judgment)


def yes_probability(raw: dict):
    a = raw.get("answer") or {}
    p = a.get("noul") if "noul" in a else a.get("noul_probability")
    return None if p is None else float(p)


def choice_view(raw: dict) -> dict:
    a = raw.get("answer") or {}
    probs = a.get("probabilities")
    return {"pred": a.get("choice"), "confidence": a.get("confidence"), "probs": probs if isinstance(probs, dict) else None}


def _contract(raw: dict) -> dict:
    if raw["judge"] != "llm":
        return {"status": raw.get("status")}
    return {"status": raw.get("status"), "first_attempt_valid": raw.get("first_attempt_valid"), "first_attempt_failure": raw.get("first_attempt_failure"),
            "repair_required": raw.get("repair_required"), "repair_succeeded": raw.get("repair_succeeded"), "unrecoverable": raw.get("unrecoverable_failure")}


def score_row(raw: dict, item: dict, labels: dict) -> dict:
    """`item` = {"trace_key", "run_id", "case_id", "variant"(perturbation id or None)}; `labels` = compute_labels output for that trace."""
    judgment = raw["judgment"]
    row = {"trace_key": item["trace_key"], "run_id": item["run_id"], "case_id": item["case_id"], "variant": item.get("variant"), "judge": raw["judge"], "judgment": judgment,
           "status": raw.get("status"), "valid": raw.get("status") == "ok" and raw.get("answer") is not None, "latency_ms": raw.get("latency_ms"), "cost_usd": decision_cost_usd(raw),
           "input_tokens": (raw.get("usage") or {}).get("input_tokens"), "contract": _contract(raw)}
    if judgment == "human_review":
        cv = choice_view(raw)
        ref = labels["labels"]["human_review"]["label"]
        pred = cv["pred"] if cv["pred"] in REVIEW_TIERS else None
        p_auto = (cv["probs"] or {}).get("AUTO_CLOSE") if cv["probs"] else None
        probs = cv["probs"] or {}
        level = ((probs.get("HUMAN_REVIEW", 0.0) + 2.0 * probs.get("PRIORITY_REVIEW", 0.0)) / 2.0) if cv["probs"] else (None if pred is None else REVIEW_TIERS.index(pred) / 2.0)
        row.update({"ref": ref, "pred": pred, "conf": cv["confidence"], "probs": cv["probs"], "p_auto": p_auto, "p_level": level,
                    "y": binary_target(judgment, labels), "p": (1.0 - p_auto) if p_auto is not None else (None if pred is None else (0.0 if pred == "AUTO_CLOSE" else 1.0)),
                    "ref_process_only": labels["labels"]["human_review_process_only"]["label"]})
    else:
        p = yes_probability(raw)
        row.update({"p": p, "y": binary_target(judgment, labels), "ref": labels["labels"][judgment]["label"] if judgment == "support" else None,
                    "conf": None if p is None else max(p, 1 - p)})
    return row


# ── observable-only deterministic baselines (no hidden truth) ─────────────────────────
def observable_baselines(trace: Trace, inventory: list) -> dict:
    """What a developer could write from the trace alone. Each returns 1 (yes) or 0 (no) for the same question a judge answers.
    Nothing here reads hidden truth; the critical and distractor sets are empty by construction."""
    inv_ids = {i["id"] for i in inventory}
    f = L.trace_facts(trace, inv_ids, EMPTY_TRUTH)
    retrieved = f["retrieved"]
    unretrieved_signal_or_change = [i for i in inventory if i["kind"] in ("signal", "change", "deployment") and i["id"] not in retrieved]
    support = L.label_support(f)["label"]
    consistency = L.label_consistency(trace, f)["label"]
    committed = f["committed"]
    tie = f["top_two_margin"] is not None and f["top_two_margin"] < L.TIE_MARGIN and not f["any_confirmed"]
    final = trace.final or {}
    problems = bool(f["n_errors"]) or bool(trace.repair_events) or bool(trace.citation_violations) or support != "SUPPORTED" or not consistency or bool(unretrieved_signal_or_change) or f["fallback"]
    return {
        "support": int(support == "SUPPORTED"),
        "missed_evidence": int(bool(unretrieved_signal_or_change)),
        "distractor_anchor": 0,  # no natural observable rule: the majority answer
        "premature_close": int(bool(committed and (unretrieved_signal_or_change or tie))),
        "final_consistency": int(consistency),
        # review: two natural rules. The agent's own flag; and any observable process defect.
        "human_review_agent_flag": int(bool(final.get("human_review_required"))),
        "human_review_defect_rule": int(problems),
    }


def baseline_row(judgment: str, item: dict, labels: dict, prediction: int, name: str) -> dict:
    """A baseline is scored exactly like a judge: as a probability of 0 or 1."""
    y = binary_target(judgment, labels)
    return {"trace_key": item["trace_key"], "run_id": item["run_id"], "case_id": item["case_id"], "variant": item.get("variant"), "judge": name, "judgment": judgment, "status": "ok", "valid": True,
            "p": float(prediction), "y": y, "ref": None, "conf": 1.0, "latency_ms": 0.0, "cost_usd": 0.0}
