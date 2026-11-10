"""Controlled trace perturbations (`perturbations_v1`), spec sections 26 to 33.

Each perturbation derives a synthetic variant from an existing trace, offline and deterministically. Originals are never modified. A variant carries `synthetic: True`,
its perturbation id, its base run id and its parameters, and it is stored and reported as synthetic evaluation data. Nothing is fabricated: every piece of evidence in a
variant was observable in the case, and no final answer is invented (P4 reuses an alternative that the trace itself contains).

Because a perturbation's effect on a judgment is known in advance, each variant carries the direction each judgment SHOULD move (`EXPECTED`). The metamorphic evaluation
scores whether a judge's probabilities move that way; it does not depend on the reference labels being right.

This module reads hidden truth only to choose *which* observable item to remove, move or reuse (for example, which retrieved evidence is critical). It is evaluator-side.
"""
import copy
import random
import re

from agent.trace_eval_v2.config import PERTURBATION_SEED, PERTURBATION_VERSION
from agent.trace_eval_v2.labels import tokens
from agent.trace_eval_v2.models import Step, Trace

CLOCK_STEP_MINUTES = 15

EXPECTED = {
    "P1": {"support": "down", "missed_evidence": "up", "human_review": "up"},
    "P2": {"distractor_anchor": "up"},
    "P3": {"premature_close": "up", "human_review": "up", "support": "down"},
    "P4": {"final_consistency": "down", "human_review": "up"},
    "P5": {j: "stable" for j in ("support", "missed_evidence", "distractor_anchor", "premature_close", "final_consistency", "human_review")},
    "P6": {j: "stable" for j in ("support", "missed_evidence", "distractor_anchor", "premature_close", "final_consistency", "human_review")},
}
DESCRIPTIONS = {
    "P1": "remove one critical evidence item from the trace's tool results",
    "P2": "move the step that returned a known distractor to just before the conclusion and repeat it once (no new evidence)",
    "P3": "truncate the trace before the first retrieval of critical evidence (the final answer is unchanged)",
    "P4": "replace the final top hypothesis with an alternative the trace already contains, without new supporting evidence",
    "P5": "remove one duplicate tool call (5 natural cases), else insert one exact repeat of an evidence-returning call; unique evidence unchanged",
    "P6": "re-alias every model-facing identifier with a different mapping (content unchanged)",
}


def _variant(base: Trace, perturbation: str, variant_id: str, params: dict, trace: Trace = None, alias_salt: str = "0") -> dict:
    t = trace or copy.deepcopy(base)
    t.variant = {"perturbation": perturbation, "variant_id": variant_id, "base_run_id": base.run_id, "synthetic": True, "params": params, "version": PERTURBATION_VERSION}
    return {"perturbation": perturbation, "variant_id": variant_id, "base_run_id": base.run_id, "trace": t, "alias_salt": alias_salt, "params": params,
            "expected": EXPECTED[perturbation], "synthetic": True}


def _drop_evidence(result, evidence_id: str):
    """Remove every list row whose evidence_id matches and keep the tool's own `count` field consistent."""
    if isinstance(result, dict):
        out = {}
        for k, v in result.items():
            out[k] = _drop_evidence(v, evidence_id)
        if isinstance(out.get("count"), int):
            lists = [v for v in out.values() if isinstance(v, list)]
            if lists:
                out["count"] = len(lists[0])
        return out
    if isinstance(result, list):
        return [_drop_evidence(r, evidence_id) for r in result if not (isinstance(r, dict) and r.get("evidence_id") == evidence_id)]
    return result


def _renumber(t: Trace) -> None:
    """Contiguous step numbers and a monotonic clock in the agent's own 15-minute steps, from the trace's original first clock."""
    from datetime import datetime, timedelta

    start = datetime.strptime(t.steps[0].clock, "%Y-%m-%d %H:%M:%S")
    for i, s in enumerate(t.steps, start=1):
        s.n = i
        s.clock = (start + timedelta(minutes=CLOCK_STEP_MINUTES * (i - 1))).strftime("%Y-%m-%d %H:%M:%S")


def _scoped_key(s: Step) -> str:
    return f"{s.tool}:{sorted((k, str(v)) for k, v in s.args.items())}"


# ── P1 ────────────────────────────────────────────────────────────────────────────────
def p1_remove_critical(base: Trace, facts: dict):
    retrieved_critical = sorted(facts["retrieved_critical"], key=lambda e: (base.first_retrieval_step().get(e, 99), e))
    if not retrieved_critical:
        return None
    target = retrieved_critical[0]
    t = copy.deepcopy(base)
    for s in t.diagnostic_steps:
        if target in s.evidence:
            s.result = _drop_evidence(s.result, target)
            s.evidence = [e for e in s.evidence if e != target]
    return _variant(base, "P1", "rm1", {"removed_evidence": target}, t)


# ── P2 ────────────────────────────────────────────────────────────────────────────────
def p2_distractor_prominence(base: Trace, facts: dict):
    diag = base.diagnostic_steps
    if len(diag) < 3 or not facts["retrieved_distractors"]:
        return None
    src = next((i for i, s in enumerate(diag) if set(s.evidence) & facts["retrieved_distractors"] and s.status == "ok"), None)
    if src is None or src >= len(diag) - 1:
        return None
    t = copy.deepcopy(base)
    d = t.diagnostic_steps
    payload = lambda s: (s.tool, s.args, s.status, s.redundant, s.result, s.evidence, s.error_kind)
    moved = payload(d[src])
    for i in range(src, len(d) - 1):  # every later payload shifts one slot earlier; slot-level hypotheses and clocks stay where they were
        d[i].tool, d[i].args, d[i].status, d[i].redundant, d[i].result, d[i].evidence, d[i].error_kind = payload(d[i + 1])
    d[-1].tool, d[-1].args, d[-1].status, d[-1].redundant, d[-1].result, d[-1].evidence, d[-1].error_kind = moved
    repeat = copy.deepcopy(d[-1])
    repeat.n = d[-1].n + 1
    submit = t.submit_step
    idx = t.steps.index(submit)
    t.steps.insert(idx, repeat)
    _renumber(t)
    return _variant(base, "P2", "prom1", {"moved_step_from": src + 1, "distractor_ids": sorted(set(base.diagnostic_steps[src].evidence) & facts["retrieved_distractors"])}, t)


# ── P3 ────────────────────────────────────────────────────────────────────────────────
def p3_truncate(base: Trace, facts: dict, labels: dict):
    """Eligible when the agent committed and had retrieved critical evidence after at least one earlier diagnostic step. Everything from the first critical retrieval onward is removed
    (the final answer is unchanged), so the variant reads as a conclusion reached before the key evidence was gathered. Only 5 baseline traces both committed and had retrieved every
    accessible critical item, so a base that already missed other critical evidence is allowed; bases whose own J4 reference is negative are taken first."""
    if not facts["committed"] or not facts["retrieved_critical"]:
        return None
    first = base.first_retrieval_step()
    k = min(first[e] for e in facts["retrieved_critical"])
    kept = [s for s in base.diagnostic_steps if s.n < k]
    if len(kept) < 1 or k >= base.submit_step.n:
        return None
    t = copy.deepcopy(base)
    t.steps = [s for s in t.steps if s.n < k] + [t.submit_step]
    t.stop_reason = "model_submitted"
    _renumber(t)
    return _variant(base, "P3", "trunc1", {"truncated_before_step": k, "kept_diagnostic_steps": len(kept), "base_already_premature": bool(labels["premature_close"]["label"])}, t)


# ── P4 ────────────────────────────────────────────────────────────────────────────────
def p4_inconsistent_final(base: Trace, facts: dict, labels: dict, inventory: list):
    """Replace the final top hypothesis with a plausible alternative taken from the case itself: the type of an available signal or change that the agent never retrieved (for example
    `IDP_UNREACHABLE` becomes `idp_unreachable_issue`). It shares nothing with what the trace retrieved and was never stated, so the final conclusion contradicts the trace. It becomes the
    top hypothesis at 0.85 confidence and nothing new is cited. Eligible only when the base final is currently consistent."""
    final = base.final or {}
    hyps = [h for h in final.get("hypotheses") or [] if isinstance(h, dict) and isinstance(h.get("confidence"), (int, float))]
    if not hyps or not labels["final_consistency"]["label"]:
        return None
    from agent.trace_eval_v2.labels import _item_texts

    retrieved = set(base.retrieved_ids)
    retrieved_words = set()
    for text in _item_texts(base).values():
        retrieved_words |= tokens(text)
    stated = {h.get("label") for s in base.diagnostic_steps for h in s.hypotheses if h.get("label")}
    options = sorted((i for i in inventory if i["id"] not in retrieved and i["kind"] in ("signal", "change") and i.get("type")), key=lambda i: (i.get("time") or "", i["id"]))
    alt = next((f"{i['type'].lower()}_issue" for i in options if f"{i['type'].lower()}_issue" not in stated and not (tokens(i["type"]) & retrieved_words)), None)
    if alt is None:
        return None
    t = copy.deepcopy(base)
    new_hyps = [dict(h) for h in t.final.get("hypotheses") or []]
    top_label = max(hyps, key=lambda h: h["confidence"])["label"]
    for h in new_hyps:
        if h.get("label") == top_label:
            h["confidence"] = min(h.get("confidence", 0.2), 0.2)
    new_hyps.append({"label": alt, "description": "", "confidence": 0.85, "supporting_evidence": [], "contradicting_evidence": [], "status": "confirmed"})
    t.final = dict(t.final)
    t.final["hypotheses"] = new_hyps
    t.final["overall_confidence"] = 0.85
    return _variant(base, "P4", "swap1", {"demoted_top": top_label, "alternative_from_unretrieved_evidence": alt}, t)


# ── P5 ────────────────────────────────────────────────────────────────────────────────
def p5_duplicate_call(base: Trace, facts: dict):
    """Robustness to irrelevant trace length. Where the trace contains a duplicate call (same tool, same arguments, identical result) the duplicate is removed. Only 5 of 300 baseline traces
    contain one, so for the rest the mirror-image change is used: one exact repeat of an evidence-returning call is inserted right after it (the agent's own redundancy pattern, no new
    information). Either way the unique evidence is unchanged and every judgment should stay put."""
    seen, drop = {}, None
    for s in base.diagnostic_steps:
        key = _scoped_key(s)
        if key in seen and (s.redundant or (s.status == "ok" and seen[key].status == "ok" and s.result == seen[key].result)):
            drop = s
            break
        seen.setdefault(key, s)
    t = copy.deepcopy(base)
    if drop is not None:
        t.steps = [s for s in t.steps if s.n != drop.n]
        _renumber(t)
        return _variant(base, "P5", "dup1", {"mode": "remove", "removed_step": drop.n, "tool": drop.tool}, t)
    candidates = [s for s in t.diagnostic_steps if s.status == "ok" and s.evidence]
    if not candidates:
        return None
    src = candidates[-1]
    repeat = copy.deepcopy(src)
    t.steps.insert(t.steps.index(src) + 1, repeat)
    _renumber(t)
    return _variant(base, "P5", "dup1", {"mode": "insert", "repeated_step": src.n, "tool": src.tool}, t)


# ── P6 ────────────────────────────────────────────────────────────────────────────────
def p6_realias(base: Trace):
    return _variant(base, "P6", "alias1", {"alias_salt": "p6"}, None, alias_salt="p6")


TARGETS = {"P1": 30, "P2": 25, "P3": 30, "P4": 30, "P5": 25, "P6": 25}


def build_variants(bases: list, seed: int = PERTURBATION_SEED, targets: dict = None) -> list:
    """`bases` = [(Trace, facts, labels, inventory)]. Deterministic: for each perturbation, eligible bases are ordered by run id, shuffled with a seeded RNG and taken up to the target."""
    targets = targets or TARGETS
    out = []
    for name in ("P1", "P2", "P3", "P4", "P5", "P6"):
        rng = random.Random(f"{seed}|{name}")
        pool = sorted(bases, key=lambda b: b[0].run_id)
        rng.shuffle(pool)
        if name == "P3":  # bases whose own reference is not already premature first; the shuffle order breaks ties
            pool.sort(key=lambda b: bool(b[2]["premature_close"]["label"]))
        made = []
        for trace, facts, labels, inventory in pool:
            if len(made) >= targets[name]:
                break
            v = {"P1": lambda: p1_remove_critical(trace, facts), "P2": lambda: p2_distractor_prominence(trace, facts), "P3": lambda: p3_truncate(trace, facts, labels),
                 "P4": lambda: p4_inconsistent_final(trace, facts, labels, inventory), "P5": lambda: p5_duplicate_call(trace, facts), "P6": lambda: p6_realias(trace)}[name]()
            if v is not None:
                made.append(v)
        out += made
    return out
