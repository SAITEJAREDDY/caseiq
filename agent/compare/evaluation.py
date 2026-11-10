"""OFFLINE evaluation against dev ground truth. This is the only module in the comparison package that reads hidden truth, and it is imported only after every architecture has
finished (the page imports it lazily, behind an explicit checkbox; nothing in the runtime path imports it). Dev cases only.

Rules (Phase 6 conventions): a root cause is correct if it exact- or containment-matches the true root-cause name; category, and the component and team of the graph modes, must equal the true
name after normalization; LLM Only's free-text component/team may contain, or be contained in, the true name. A null prediction is reported as ABSTAIN, never as wrong."""
import json

from agent.agent_v3.config import PROJECT_ROOT
from agent.compare.models import MODE_LLM, ComparisonResult
from agent.eval_v2 import text_match
from agent.eval_v2.ground_truth import component_name, get_hidden_truth, issue_category_name, root_cause_name, team_name

FIELDS = ("root_cause", "issue_category", "affected_component", "owning_team")


def assert_dev(case_id: str) -> None:
    pool = json.loads((PROJECT_ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"]
    if case_id not in pool:
        raise ValueError(f"{case_id} is not a dev case; ground truth is only shown for dev cases")


def truth(case_id: str) -> dict:
    assert_dev(case_id)
    t = get_hidden_truth(case_id)
    cgt = t["case_ground_truth"] or {}
    teams = {team_name(r["team_id"]) for r in (t["case_team_ownership"] or [])}
    return {"root_cause": root_cause_name(cgt.get("gt_root_cause_id")), "issue_category": issue_category_name(cgt.get("gt_issue_category_id")),
            "affected_component": component_name(cgt.get("gt_component_id")), "owning_team": sorted(x for x in teams if x)}


def _verdict(field: str, pred, true, mode: str) -> str:
    if not pred:
        return "abstain"
    if field == "root_cause":
        return "correct" if text_match.exact_match(pred, true) or text_match.containment_match(pred, true) else "wrong"
    options = true if isinstance(true, list) else [true]
    if mode == MODE_LLM and field in ("affected_component", "owning_team"):
        return "correct" if any(text_match.containment_match(pred, t) for t in options if t) else "wrong"
    return "correct" if any(text_match.normalize(pred) == text_match.normalize(t) for t in options if t) else "wrong"


def score(case_id: str, result: ComparisonResult, truth_names: dict = None) -> dict:
    t = truth_names or truth(case_id)
    return {f: _verdict(f, getattr(result, f), t[f], result.mode) for f in FIELDS}


def score_all(case_id: str, results: dict) -> dict:
    t = truth(case_id)
    return {"truth": t, "scores": {m: score(case_id, r, t) for m, r in results.items() if r is not None}}
