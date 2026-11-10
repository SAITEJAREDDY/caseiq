"""Loads a persisted Phase 5 run into the canonical Trace. Nothing is repaired or filled in: a final diagnosis with empty ID fields
stays empty (Phase 8 treats missing contract fields as observable trace behaviour, not something to fix)."""
import json
import re
from pathlib import Path

from agent.eval_v2 import contract
from agent.trace_eval_v2.config import AGENT_RUNS_DIR
from agent.trace_eval_v2.models import EVIDENCE_KINDS, Step, Trace, id_kind


def _walk_evidence_ids(obj, out: list) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "evidence_id" and isinstance(v, str):
                out.append(v)
            else:
                _walk_evidence_ids(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_evidence_ids(item, out)


def _parse_hypotheses(raw) -> list:
    """Compact 'label:confidence' strings (regular steps) or the agent's raw hypothesis dicts (the submit step) -> [{"label", "confidence", ...}]."""
    out = []
    for h in raw or []:
        if isinstance(h, dict):
            out.append({k: h.get(k) for k in ("label", "confidence", "status", "description") if h.get(k) is not None})
        elif isinstance(h, str):
            label, sep, conf = h.rpartition(":")
            try:
                out.append({"label": label.strip() if sep else h, "confidence": float(conf)} if sep else {"label": h})
            except ValueError:
                out.append({"label": h})
    return out


def _step_from_dict(s: dict) -> Step:
    result = s.get("result_summary")
    evidence = []
    if s.get("tool_name") != "submit_diagnosis" and s.get("status") != "redundant":
        _walk_evidence_ids(result, evidence)
        evidence = list(dict.fromkeys(e for e in evidence if id_kind(e) in EVIDENCE_KINDS))
    error_kind = None
    if s.get("status") == "error" and isinstance(result, dict):
        error_kind = contract.classify_tool_error(result.get("error", ""))
    args = {k: v for k, v in (s.get("args") or {}).items() if k not in ("hypotheses", "rationale")}
    if s.get("tool_name") == "submit_diagnosis":
        args = {}  # the submit arguments are the final answer; they are presented as final_output, not as tool arguments
    return Step(n=s["step"], clock=s["sim_clock"], tool=s["tool_name"], args=args, hypotheses=_parse_hypotheses(s.get("hypotheses")),
                status=s.get("status", "ok"), redundant=bool(s.get("redundant")), result=result, evidence=evidence, error_kind=error_kind)


def load_trace(run: dict) -> Trace:
    steps = [_step_from_dict(s) for s in run["trace_steps"]]
    return Trace(run_id=run["run_id"], case_id=run["case_id"], stop_reason=run["stop_reason"], steps=steps, final=run["final_diagnosis"],
                 repair_events=list(run.get("repair_events") or []), citation_violations=list(run.get("citation_violations") or []),
                 token_usage=run.get("token_usage") or {}, model_name=run.get("model_name") or "")


def load_run(run_id: str) -> dict:
    return json.loads((Path(AGENT_RUNS_DIR) / f"{run_id}.json").read_text())


def load_trace_by_id(run_id: str) -> Trace:
    return load_trace(load_run(run_id))
