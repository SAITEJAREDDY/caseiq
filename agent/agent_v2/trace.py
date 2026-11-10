"""Agent run persistence: one JSON file per run under data/agent_runs/, plus
an append-only runs_index.jsonl for fast batch listing. Agent runs are
experimental artifacts -- never written into data/raw_v2|phase2|phase3, and
never read back by anything in agent/graph_v2/ (one-directional: this
package writes here, nothing reads it back into the runtime path).
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.agent_v2.config import (
    AGENT_LOOP_VERSION,
    AGENT_MODEL_NAME,
    AGENT_MODEL_PROVIDER,
    AGENT_RUNS_DIR,
    AGENT_TEMPERATURE,
    APPROX_USD_PER_1K_INPUT_TOKENS,
    APPROX_USD_PER_1K_OUTPUT_TOKENS,
    GRAPH_VERSION_TAG,
    MAX_REPEATED_SAME_TOOL,
    MAX_TOOL_CALLS,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_VERSION,
    REPAIR_LAYER_VERSION,
    SIM_CLOCK_STEP_MINUTES,
    TOOLSET_VERSION,
)


def new_run_id(case_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{case_id}_{ts}_{uuid.uuid4().hex[:8]}"


def _approx_cost_usd(usage: dict) -> float:
    return round(
        usage.get("prompt_tokens", 0) / 1000 * APPROX_USD_PER_1K_INPUT_TOKENS
        + usage.get("completion_tokens", 0) / 1000 * APPROX_USD_PER_1K_OUTPUT_TOKENS,
        6,
    )


def persist_run(run_result: dict) -> Path:
    AGENT_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = new_run_id(run_result["case_id"])
    record = {
        "run_id": run_id,
        "case_id": run_result["case_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_provider": AGENT_MODEL_PROVIDER,
        "model_name": AGENT_MODEL_NAME,
        "temperature": AGENT_TEMPERATURE,
        "prompt_version": PROMPT_VERSION,
        "toolset_version": TOOLSET_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "agent_loop_version": AGENT_LOOP_VERSION,
        "repair_layer_version": REPAIR_LAYER_VERSION,
        "graph_version": GRAPH_VERSION_TAG,
        "sim_clock_step_minutes": SIM_CLOCK_STEP_MINUTES,
        "max_tool_calls": MAX_TOOL_CALLS,
        "max_repeated_same_tool": MAX_REPEATED_SAME_TOOL,
        "stop_reason": run_result["stop_reason"],
        "num_tool_calls": run_result["num_tool_calls"],
        "num_llm_calls": run_result["num_llm_calls"],
        "token_usage": run_result["token_usage"],
        "approx_cost_usd": _approx_cost_usd(run_result["token_usage"]),
        "approx_cost_note": "Estimated from a configurable placeholder rate, not exact provider billing -- see config.py",
        "trace_steps": run_result["trace_steps"],
        "final_diagnosis": run_result["final_diagnosis"],
        "citation_violations": run_result["citation_violations"],
        "evidence_ids_seen": run_result["evidence_ids_seen"],
        "repair_events": run_result.get("repair_events", []),
    }

    out_path = AGENT_RUNS_DIR / f"{run_id}.json"
    with open(out_path, "w") as f:
        json.dump(record, f, indent=2, default=str)

    index_line = {
        "run_id": run_id,
        "case_id": record["case_id"],
        "created_at": record["created_at"],
        "stop_reason": record["stop_reason"],
        "overall_confidence": record["final_diagnosis"].get("overall_confidence"),
        "evidence_sufficiency": record["final_diagnosis"].get("evidence_sufficiency"),
        "human_review_required": record["final_diagnosis"].get("human_review_required"),
        "num_tool_calls": record["num_tool_calls"],
        "citation_violations": len(record["citation_violations"]),
        "repair_events": len(record["repair_events"]),
    }
    with open(AGENT_RUNS_DIR / "runs_index.jsonl", "a") as f:
        f.write(json.dumps(index_line, default=str) + "\n")

    return out_path
