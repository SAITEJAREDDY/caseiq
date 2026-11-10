"""Simple deterministic checks over the agent's own run state (Phase 8: support, premature close and final consistency are simple rules, so they are code, not Jev).

Inputs are runtime-observable only: the agent's alias-form final answer, its trace and its evidence ledger. Nothing here reads hidden truth, a Phase 6 score or a label.
D1 is computed from the run's alias mapping alone, independently of the agent loop's own validator.
"""
import re

from agent.agent_v3.final_contract import FINAL_FIELDS, MODEL_STATUSES, SELECTIONS, supported_hypotheses
from agent.runtime_verifier.models import VerifierConfig

CITABLE = ("EVIDENCE", "CHANGE", "INCIDENT")
_STOP = {"the", "and", "for", "with", "issue", "error", "problem", "caused", "due", "from", "that", "this", "service", "failure"}


def _res(cid: str, name: str, passed: bool, detail: str, applicable: bool = True) -> dict:
    return {"id": cid, "name": name, "passed": bool(passed), "applicable": applicable, "detail": detail}


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _STOP}


def d1_valid_contract(run: dict) -> dict:
    """Schema, required fields, confidence bounds, and that every cited item / selected entity was actually retrieved before the answer."""
    fa, mp = run.get("final_alias_form"), run.get("alias_mappings") or {}
    if run.get("contract_failure") or fa is None:
        return _res("D1", "valid_final_contract", False, f"no valid final answer: {run.get('contract_failure') or 'missing'}")
    problems = [f"missing field {k}" for k in FINAL_FIELDS if k not in fa]
    if problems:
        return _res("D1", "valid_final_contract", False, "; ".join(problems))
    if fa["status"] not in MODEL_STATUSES:
        problems.append(f"bad status {fa['status']}")
    for k in ["confidence"] + [c for _v, c, _k in SELECTIONS]:
        v = fa[k]
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1):
            problems.append(f"{k} outside 0-1")
    final_step = max((s["step"] for s in run["trace_steps"]), default=0)
    seen = set(run.get("evidence_ids_seen") or [])

    def observed(alias, kinds, field):
        e = mp.get(alias)
        if e is None:
            problems.append(f"{field}: {alias!r} is not in the registry")
        elif e["kind"] not in kinds:
            problems.append(f"{field}: {alias!r} is a {e['kind']}, expected {'/'.join(kinds)}")
        elif e["first_observed_step"] is None or e["first_observed_step"] >= final_step:
            problems.append(f"{field}: {alias!r} was not retrieved before the final answer")
        elif kinds == CITABLE and e["canonical_id"] not in seen:
            problems.append(f"{field}: {alias!r} is not in the retrieved-evidence set")

    cites = list(fa["evidence_ids"])
    if len(cites) != len(set(cites)):
        problems.append("evidence_ids contains a duplicate")
    for a in cites:
        observed(a, CITABLE, "evidence_ids")
    for h in fa["hypotheses"]:
        for a in list(h["supporting_evidence"]) + list(h["contradicting_evidence"]):
            observed(a, CITABLE, "hypothesis citation")
    for v, c, kinds in SELECTIONS:
        if fa[v] is not None:
            observed(fa[v], kinds, v)
            if fa[c] is None:
                problems.append(f"{v} is set without a confidence")
    return _res("D1", "valid_final_contract", not problems, "; ".join(problems[:6]) if problems else "schema, bounds and every reference are valid")


def d2_evidence_support(run: dict) -> dict:
    """A proposed diagnosis must cite retrieved evidence and rest on at least one non-rejected hypothesis that cites support. Basic support only, not causal correctness."""
    fa = run.get("final_alias_form")
    if not fa or fa["status"] != "DIAGNOSIS_PROPOSED":
        return _res("D2", "evidence_support", True, "no diagnosis was proposed, so there is nothing to support", applicable=False)
    n_cited, n_sup = len(fa["evidence_ids"]), len(supported_hypotheses(fa))
    ok = n_cited >= 1 and n_sup >= 1
    return _res("D2", "evidence_support", ok, f"{n_cited} cited evidence item(s), {n_sup} supported hypothesis(es)")


def _top(hyps: list):
    live = [h for h in hyps if h.get("status") != "rejected"]
    return max(live, key=lambda h: h["confidence"]) if live else None


def d3_final_consistency(run: dict) -> dict:
    """The final answer must not obviously contradict the last structured hypothesis state or its own stated confidence."""
    fa = run.get("final_alias_form")
    if not fa:
        return _res("D3", "final_consistency", True, "no final answer to compare", applicable=False)
    problems, top = [], _top(fa["hypotheses"])
    if top is not None and fa["confidence"] - top["confidence"] > 0.3:
        problems.append(f"overall confidence {fa['confidence']} is far above the top hypothesis' {top['confidence']}")
    if fa["confidence"] >= 0.8 and (fa["unresolved_uncertainties"] or fa["evidence_sufficiency"] == "insufficient"):
        problems.append("confidence >= 0.8 despite stated uncertainty or insufficient evidence")
    if fa["evidence_sufficiency"] == "insufficient" and not fa["human_review_required"] and fa["status"] != "INSUFFICIENT_EVIDENCE":
        problems.append("claims insufficient evidence without asking for review")
    if top is not None:  # a hypothesis revised after new evidence is fine; one that was never stated and matches no retrieved evidence is not
        stated = set().union(*[_words(h["label"]) for s in run["trace_steps"] for h in s.get("hypothesis_state") or [] if s["tool_name"] != "submit_diagnosis"], set())
        ledger = set().union(*[_words(e["summary"]) | _words(e["display_name"]) for e in (run.get("alias_mappings") or {}).values() if e["kind"] in CITABLE], set())
        if not (_words(top["label"]) & (stated | ledger)):
            problems.append("the final top hypothesis was never stated during the investigation and matches no retrieved evidence")
    return _res("D3", "final_consistency", not problems, "; ".join(problems) if problems else "consistent with the last stated hypotheses and its own confidence")


def d4_premature_finalization(run: dict, cfg: VerifierConfig) -> dict:
    """Very simple rule: finalizing with no evidence at all, or with no supported hypothesis while tool budget was still left, is premature."""
    fa = run.get("final_alias_form")
    if not fa:
        return _res("D4", "premature_finalization", False, "no final answer", applicable=False)
    n_evidence = len(run.get("evidence_ids_seen") or [])
    executed = max(0, run["num_tool_calls"] - 1)                 # the final submit is not an executed tool call
    left = max(0, run.get("tool_budget", 0) - executed)
    supported = bool(supported_hypotheses(fa))
    premature = n_evidence == 0 or (not supported and left >= cfg.premature_min_steps_left)
    reason = ("no evidence was retrieved" if n_evidence == 0 else
              f"no supported hypothesis and {left} tool call(s) were still available" if premature else
              "evidence was retrieved and either a hypothesis is supported or the tool budget is used up")
    # `passed` = NOT premature, so every check reads "True = fine"
    return _res("D4", "premature_finalization", not premature, reason)


def run_all(run: dict, cfg: VerifierConfig) -> dict:
    checks = {"D1": d1_valid_contract(run), "D2": d2_evidence_support(run), "D3": d3_final_consistency(run), "D4": d4_premature_finalization(run, cfg)}
    checks["all_passed"] = all(c["passed"] for c in checks.values())
    return checks
