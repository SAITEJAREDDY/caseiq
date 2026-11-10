"""Run persistence for the Phase 9A agent: one JSON per run under data/agent_runs_v3/ plus an append-only index. Phase 5's data/agent_runs is
never read for writing. The record keeps the Phase 5 run shape (so the unchanged Phase 6 evaluator scores it) and adds the contract fields."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.agent_v3 import config as C


def _code_digest() -> str:
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        if p.name.startswith("test_") or p.name in ("run_batch.py", "validate_boundaries.py", "evaluate.py", "cohorts.py", "dry_run.py"):
            continue  # runtime modules only: the digest identifies the agent, not its harness
        h.update(p.name.encode() + p.read_bytes())
    return h.hexdigest()


def versions() -> dict:
    return {
        "agent_version": C.AGENT_VERSION, "contract_version": C.CONTRACT_VERSION, "prompt_version": C.PROMPT_VERSION,
        "tool_catalog_version": C.TOOL_CATALOG_VERSION, "action_schema_version": C.ACTION_SCHEMA_VERSION, "final_schema_version": C.FINAL_SCHEMA_VERSION,
        "registry_version": C.REGISTRY_VERSION, "alias_scheme": C.ALIAS_SCHEME, "repair_policy_version": C.REPAIR_POLICY_VERSION,
        "decoding": C.DECODING, "code_digest": _code_digest(),
    }


def persist_run(run: dict, tag: str, runs_dir: Path = None) -> Path:
    runs_dir = Path(runs_dir or C.RUNS_DIR)
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"run_{run['case_id']}_{ts}_{uuid.uuid4().hex[:8]}"
    usage = run["token_usage"]
    record = {
        "run_id": run_id, "case_id": run["case_id"], "created_at": datetime.now(timezone.utc).isoformat(), "run_tag": tag,
        "model_provider": C.MODEL_PROVIDER, "model_name": C.MODEL_NAME, "temperature": C.TEMPERATURE, "graph_version": C.GRAPH_VERSION_TAG,
        "sim_clock_step_minutes": C.SIM_CLOCK_STEP_MINUTES, "max_tool_calls": C.MAX_TOOL_CALLS, "max_repeated_same_tool": C.MAX_REPEATED_SAME_TOOL,
        "max_tool_contract_repairs": C.MAX_TOOL_CONTRACT_REPAIRS, "max_final_contract_repairs": C.MAX_FINAL_CONTRACT_REPAIRS,
        **versions(),
        # Phase 5 field names the Phase 6 evaluator reads, mapped to this agent's versions
        "toolset_version": C.TOOL_CATALOG_VERSION, "output_schema_version": C.FINAL_SCHEMA_VERSION, "agent_loop_version": C.AGENT_VERSION,
        "repair_layer_version": C.REPAIR_POLICY_VERSION,
        "approx_cost_usd": round((usage["prompt_tokens"] + usage["completion_tokens"]) / 1000 * 0.0001, 6),
        **run,
    }
    path = runs_dir / f"{run_id}.json"
    path.write_text(json.dumps(record, indent=1, default=str))
    idx = {"run_id": run_id, "case_id": record["case_id"], "run_tag": tag, "created_at": record["created_at"], "stop_reason": record["stop_reason"],
           "final_status": record["final_status"], "first_pass_final": record["validation_result"]["first_pass_ok"],
           "tool_contract_errors": len(record["tool_contract_errors"]), "contract_failure": record["contract_failure"]}
    with open(runs_dir / "runs_index.jsonl", "a") as f:
        f.write(json.dumps(idx) + "\n")
    return path
