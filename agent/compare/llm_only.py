"""LLM Only: one direct model call on the support ticket. No Neo4j, no tools, no evidence retrieval, no Jev.

This module deliberately imports nothing but the LLM transport, the config and the standard library, so the boundary is structural (a test checks the import closure and that no
graph or Jev object can be reached from here). The model sees the ticket fields and the standing issue-category and root-cause vocabulary (the same option lists the graph agent
chooses from at finalization, read from the observable reference tables). It is not given graph relationships, similar cases, topology, hidden truth or any score.
"""
import csv
import json
import time
import uuid
from datetime import datetime, timezone

from agent.agent_v3.config import MODEL_NAME, PROJECT_ROOT, TEMPERATURE
from agent.compare.models import TOGETHER_USD_PER_M_TOKENS

PROMPT_VERSION = "llm_only_v1"
RUNS_DIR = PROJECT_ROOT / "data" / "comparison_runs"
STATUSES = ("DIAGNOSIS_PROPOSED", "INSUFFICIENT_EVIDENCE", "HUMAN_REVIEW_REQUIRED")
MAX_TOKENS = 700

SYSTEM = """You are a support-triage assistant. You are given one support ticket and nothing else: you have no tools, no logs, no telemetry, no knowledge base and no \
history. Diagnose as well as the ticket alone allows and reply with one JSON object that follows the supplied schema.
- issue_category and root_cause must be chosen from the lists in the request, or be null when the ticket does not justify a choice.
- affected_component and owning_team: name one only if the ticket itself supports it, otherwise null. causal_change: null unless the ticket itself names a recent change.
- Do not invent identifiers. Null is better than a guess. confidence (0-1) says how much the ticket alone supports your diagnosis.
- status: DIAGNOSIS_PROPOSED, INSUFFICIENT_EVIDENCE (the ticket is too thin to diagnose) or HUMAN_REVIEW_REQUIRED."""


def taxonomy() -> tuple:
    """(issue category names, root cause names): the standing vocabulary, from the observable reference tables."""
    def names(fn):
        with open(PROJECT_ROOT / "data" / "raw_v2" / fn, newline="", encoding="utf-8") as f:
            return [r["name"] for r in csv.DictReader(f)]
    return names("issue_categories.csv"), names("root_causes.csv")


def _nullable(inner):
    return {"anyOf": [inner, {"type": "null"}]}


def schema(categories: list, causes: list) -> dict:
    props = {
        "issue_category": _nullable({"type": "string", "enum": categories}),
        "root_cause": _nullable({"type": "string", "enum": causes}),
        "affected_component": _nullable({"type": "string", "maxLength": 80}),
        "causal_change": _nullable({"type": "string", "maxLength": 160}),
        "owning_team": _nullable({"type": "string", "maxLength": 60}),
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "status": {"type": "string", "enum": list(STATUSES)},
        "summary": {"type": "string", "maxLength": 500},
    }
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def validate(raw, categories: list, causes: list) -> tuple:
    """(object|None, errors). Deterministic; nothing is repaired."""
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError):
        return None, ["not_json"]
    if not isinstance(obj, dict):
        return None, ["not_json"]
    errors = [f"missing_field:{k}" for k in ("issue_category", "root_cause", "affected_component", "causal_change", "owning_team", "confidence", "status", "summary") if k not in obj]
    if errors:
        return None, errors
    errors += [f"unknown_field:{k}" for k in obj if k not in ("issue_category", "root_cause", "affected_component", "causal_change", "owning_team", "confidence", "status", "summary")]
    if obj["issue_category"] is not None and obj["issue_category"] not in categories:
        errors.append("issue_category_not_in_list")
    if obj["root_cause"] is not None and obj["root_cause"] not in causes:
        errors.append("root_cause_not_in_list")
    c = obj["confidence"]
    if isinstance(c, bool) or not isinstance(c, (int, float)) or not 0 <= c <= 1:
        errors.append("confidence_out_of_range")
    if obj["status"] not in STATUSES:
        errors.append("bad_status")
    for k in ("affected_component", "causal_change", "owning_team"):
        if obj[k] is not None and not isinstance(obj[k], str):
            errors.append(f"{k}_not_text")
    if not isinstance(obj["summary"], str) or not obj["summary"].strip():
        errors.append("empty_summary")
    return (None if errors else obj), errors


def _messages(ticket: dict, categories: list, causes: list, error_note: str = "") -> list:
    user = ("SUPPORT TICKET\n" + json.dumps(ticket, default=str, ensure_ascii=False) + "\n\nISSUE CATEGORIES (choose one or null)\n" + "\n".join(f"- {c}" for c in categories) +
            "\n\nROOT CAUSES (choose one or null)\n" + "\n".join(f"- {c}" for c in causes))
    if error_note:
        user += "\n\nYour previous reply was invalid (" + error_note + "). Reply again with a valid object."
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def run_llm_only(case_id: str, ticket: dict, llm) -> dict:
    """One model call (plus at most one repair). Returns the stored-run record. `tool_calls`, `evidence_count`, `graph_used` and `jev_used` are structural zeros/False."""
    categories, causes = taxonomy()
    sch, t0, usage, calls, errors_seen = schema(categories, causes), time.time(), {"prompt": 0, "completion": 0}, [], []
    parsed, error_note = None, ""
    for attempt in (0, 1):
        res = llm.complete(_messages(ticket, categories, causes, error_note), sch, "llm_only", MAX_TOKENS)
        usage["prompt"] += res.prompt_tokens
        usage["completion"] += res.completion_tokens
        calls.append({"attempt": attempt, "latency_ms": round(res.latency_ms, 1), "finish_reason": res.finish_reason, "raw_output": res.content})
        parsed, errors = validate(res.content, categories, causes)
        if not errors:
            break
        errors_seen.append(errors)
        error_note = ", ".join(errors)
    tokens = usage["prompt"] + usage["completion"]
    return {
        "run_id": f"llmonly_{case_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}", "case_id": case_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "prompt_version": PROMPT_VERSION, "model_name": MODEL_NAME, "temperature": TEMPERATURE,
        "ticket_shown_to_model": ticket, "n_categories_offered": len(categories), "n_root_causes_offered": len(causes),
        "parsed": parsed, "status": parsed["status"] if parsed else "CONTRACT_FAILURE", "validation_errors": errors_seen, "repair_used": len(calls) > 1,
        "llm_calls": calls, "tokens": {"prompt": usage["prompt"], "completion": usage["completion"], "total": tokens},
        "latency_ms": round(sum(c["latency_ms"] for c in calls), 1), "wall_ms": round((time.time() - t0) * 1000, 1),
        "cost_usd_estimate": round(tokens / 1e6 * TOGETHER_USD_PER_M_TOKENS, 6),
        "tool_calls": 0, "evidence_count": 0, "graph_used": False, "jev_used": False,
    }


def persist(record: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{record['run_id']}.json").write_text(json.dumps(record, indent=1, default=str))
    with open(RUNS_DIR / "index.jsonl", "a") as f:
        f.write(json.dumps({"run_id": record["run_id"], "case_id": record["case_id"], "created_at": record["created_at"], "status": record["status"]}) + "\n")
