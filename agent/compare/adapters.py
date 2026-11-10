"""Adapters: every architecture's stored or live record -> one `ComparisonResult`, so rendering has a single code path. Also the stored-run lookups for the three stores:
LLM Only (data/comparison_runs), LLM + Graph (data/agent_runs_v3, agent only) and LLM + Graph + Jev (data/runtime_verifier_runs)."""
import json
from collections import Counter
from typing import Optional

from agent.agent_v3.config import PROJECT_ROOT
from agent.agent_v3.registry import ALIAS_RE
from agent.compare import llm_only
from agent.compare.models import (JEV_USD_PER_M_INPUT_TOKENS, MODE_FULL, MODE_GRAPH, MODE_LLM, MODES, SELECTION_FIELDS, TOGETHER_USD_PER_M_TOKENS, ComparisonResult)

GRAPH_DIR = PROJECT_ROOT / "data" / "agent_runs_v3"
FULL_DIR = PROJECT_ROOT / "data" / "runtime_verifier_runs"
GRAPH_TAGS = ("ui", "verify100_final", "iter50_b")   # v3.1 agent runs; iter50_a (the pre-correction prompt) is only a fallback
_SEL_KIND = {"issue_category": "CATEGORY", "root_cause": "CAUSE", "affected_component": "COMPONENT", "causal_change": "CHANGE", "owning_team": "TEAM"}


def _read_index(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def graph_index() -> dict:
    best = {}
    for e in _read_index(GRAPH_DIR / "runs_index.jsonl"):
        if e["run_tag"] in GRAPH_TAGS or (e["run_tag"] == "iter50_a" and e["case_id"] not in best):
            best[e["case_id"]] = e["run_id"]
    return best


def full_index() -> dict:
    return {e["case_id"]: e["run_id"] for e in _read_index(FULL_DIR / "index.jsonl")}


def llm_index() -> dict:
    return {e["case_id"]: e["run_id"] for e in _read_index(llm_only.RUNS_DIR / "index.jsonl")}


_STORES = {MODE_LLM: (llm_index, llm_only.RUNS_DIR), MODE_GRAPH: (graph_index, GRAPH_DIR), MODE_FULL: (full_index, FULL_DIR)}


def available(case_id: str) -> dict:
    return {m: case_id in _STORES[m][0]() for m in MODES}


def load_stored(mode: str, case_id: str) -> Optional[ComparisonResult]:
    index, folder = _STORES[mode]
    run_id = index().get(case_id)
    if not run_id:
        return None
    record = json.loads((folder / f"{run_id}.json").read_text())
    return {MODE_LLM: from_llm_only, MODE_GRAPH: from_graph_run, MODE_FULL: from_verified}[mode](record, "stored")


# ── helpers over an agent run ─────────────────────────────────────────────────────────────

def _label(mp: dict, alias) -> Optional[str]:
    e = mp.get(alias) if alias else None
    return (e.get("display_name") or e.get("summary")) if e else None


def _labels(fa, mp) -> dict:
    return {f: (_label(mp, fa[f]) if fa else None) for f in SELECTION_FIELDS}


def model_tool_calls(run: dict) -> int:
    return sum(1 for s in run["trace_steps"] if s.get("proposed_by") == "model" and s["tool_name"] != "submit_diagnosis")


def entity_counts(run: dict) -> dict:
    mp = run["alias_mappings"]
    ev = [e for e in mp.values() if e["kind"] in ("EVIDENCE", "CHANGE", "INCIDENT")]
    by = Counter(e["type"] for e in ev)
    with_evidence = set()
    for e in ev:
        with_evidence |= {m.group(0) for m in ALIAS_RE.finditer(e["summary"]) if m.group(0).startswith("COMPONENT_")}
    queried = {v for s in run["trace_steps"] if s.get("proposed_by") == "model" for k, v in (s.get("args_alias") or {}).items() if k == "component"}
    return {"signals": by["signal"], "telemetry": by["telemetry"], "changes": by["change"] + by["deployment"], "incidents": by["incident"], "similar_cases": by["similar_case"],
            "config_snapshots": by["config_snapshot"], "health_events": by["health_event"], "kb_articles": by["kb_article"], "components_with_evidence": len(with_evidence),
            "components_queried": len(queried)}


def _ids(run: dict) -> dict:
    fd = run["final_diagnosis"]
    return {"issue_category": fd.get("predicted_category_id"), "root_cause": fd.get("predicted_root_cause_family"), "affected_component": fd.get("predicted_component_id"),
            "causal_change": fd.get("predicted_causal_change_id"), "owning_team": fd.get("recommended_team_id")}


def _model_seconds(run: dict) -> float:
    return sum(c["latency_ms"] for c in run["llm_calls"]) / 1000


# ── the three adapters ────────────────────────────────────────────────────────────────────

def from_llm_only(record: dict, source: str = "stored") -> ComparisonResult:
    p = record.get("parsed") or {}
    return ComparisonResult(
        mode=MODE_LLM, case_id=record["case_id"], status=record["status"], issue_category=p.get("issue_category"), root_cause=p.get("root_cause"),
        affected_component=p.get("affected_component"), causal_change=p.get("causal_change"), owning_team=p.get("owning_team"), confidence=p.get("confidence"),
        summary=p.get("summary") or "The model's answer was not valid after one repair; no diagnosis was produced.", tool_calls=0, evidence_count=0, graph_used=False, jev_used=False,
        latency_seconds=record["latency_ms"] / 1000, estimated_cost=record["cost_usd_estimate"], run_id=record["run_id"], source=source, raw=record)


def from_graph_run(run: dict, source: str = "stored") -> ComparisonResult:
    fa, fd, mp = run.get("final_alias_form"), run["final_diagnosis"], run["alias_mappings"]
    sel = _labels(fa, mp)
    return ComparisonResult(
        mode=MODE_GRAPH, case_id=run["case_id"], status=run["final_status"], confidence=fd["overall_confidence"], summary=fd["evidence_summary"], tool_calls=model_tool_calls(run),
        evidence_count=len(run["evidence_ids_seen"]), graph_used=True, jev_used=False, latency_seconds=_model_seconds(run),
        estimated_cost=run["token_usage"]["total_tokens"] / 1e6 * TOGETHER_USD_PER_M_TOKENS, hypotheses=len((fa or {}).get("hypotheses") or []), entities=entity_counts(run),
        selection_ids=_ids(run), run_id=run.get("run_id", ""), source=source, raw=run, **sel)


def _view_fields(view: Optional[dict]) -> Optional[dict]:
    """A runtime_verifier `diagnosis_view` -> plain display fields."""
    if not view:
        return None
    out = {f: ((view["selections"].get(f) or {}).get("name")) for f in SELECTION_FIELDS}
    out.update(status=view["status"], confidence=view["confidence"], summary=view["summary"])
    return out


def _triage_view(record: dict) -> Optional[dict]:
    """The early-triage panel data, or None for a run made before early triage existed (a late-verification-only run)."""
    t = record.get("early_triage")
    if not record.get("early_triage_used") or t is None:
        return None
    final, initial = record.get("triage_outcome") or {}, record.get("triage_outcome_initial") or {}
    return {"status": t["status"], "fallback": t["fallback"], "fallback_reason": t.get("fallback_reason"), "category": t.get("category_name"), "category_id": t.get("category_id"),
            "probability": t.get("probability"), "uncertainty": t.get("uncertainty"), "abstain_probability": t.get("abstain_probability"), "alternatives": t.get("alternatives") or [],
            "distribution_top": t.get("distribution_top") or [], "suggested_tools": t.get("suggested_tools") or [], "latency_ms": t.get("latency_ms", 0.0),
            "input_tokens": t.get("input_tokens", 0), "jev_model": t.get("jev_model"), "question_version": t.get("question_version"),
            "outcome": final.get("outcome"), "final_category": final.get("final_category"), "final_in_alternatives": final.get("final_in_alternatives"),
            "outcome_initial": initial.get("outcome"), "initial_category": initial.get("final_category")}


def from_verified(record: dict, source: str = "stored") -> ComparisonResult:
    run = record["agent_run"]
    fa, fd, mp = run.get("final_alias_form"), run["final_diagnosis"], run["alias_mappings"]
    passes = [{"round": r["round"], "checks": {k: v for k, v in r["deterministic_checks"].items() if k != "all_passed"}, "missed": r["jev_missed_evidence"],
               "distractor": r["jev_distractor_anchor"], "review": (r["jev_review"] or {}).get("label"), "review_probabilities": (r["jev_review"] or {}).get("probabilities"),
               "jev_available": r["jev_available"], "decision": r["policy_decision"], "reason": r["reason"], "triggers": r.get("triggers", []), "message": r.get("message_to_agent")}
              for r in record["verification_rounds"]]
    additional = record["additional_investigation_performed"]
    initial = _view_fields(record["agent_initial_result"])
    extra = (run["num_tool_calls"] - (run.get("initial_result") or {}).get("num_tool_calls", run["num_tool_calls"])) if additional else 0
    verifier_s = sum(r.get("verifier_latency_ms", 0) for r in run["verification_rounds"]) / 1000
    verification = {"first_decision": record["policy_decision"], "final_decision": record["final_policy_decision"], "reason": record["final_reason"], "additional_investigation": additional,
                    "passes": passes, "contract_failure": run.get("contract_failure")}
    jev_tokens = record.get("jev_input_tokens", 0)
    triage = _triage_view(record)
    return ComparisonResult(
        mode=MODE_FULL, case_id=record["case_id"], status=run["final_status"], confidence=fd["overall_confidence"], summary=fd["evidence_summary"], tool_calls=model_tool_calls(run),
        evidence_count=len(run["evidence_ids_seen"]), graph_used=True, jev_used=True, latency_seconds=_model_seconds(run) + verifier_s + ((triage or {}).get("latency_ms", 0.0) / 1000),
        estimated_cost=run["token_usage"]["total_tokens"] / 1e6 * TOGETHER_USD_PER_M_TOKENS + jev_tokens / 1e6 * JEV_USD_PER_M_INPUT_TOKENS, verification=verification,
        hypotheses=len((fa or {}).get("hypotheses") or []), entities=entity_counts(run), selection_ids=_ids(run), initial=initial, extra_tool_calls=extra, triage=triage,
        run_id=record.get("run_id", ""), source=source, raw=record, **_labels(fa, mp))
