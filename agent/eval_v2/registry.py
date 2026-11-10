"""The experiment registry (spec section 4): append-only, never overwritten.
Each experiment gets its own folder under data/experiments/<experiment_id>/
holding the full case-level and aggregate output; registry.jsonl is a thin
index for listing experiments without opening every folder.
"""
import csv
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.eval_v2.config import EVAL_HARNESS_VERSION, EXPERIMENTS_DIR, SPLIT_VERSION

REGISTRY_PATH = EXPERIMENTS_DIR / "registry.jsonl"


def new_experiment_id(name: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return f"exp_{safe_name}_{ts}_{uuid.uuid4().hex[:8]}"


def dataset_checksum_digest() -> str:
    """A fresh combined digest over Phase 1/2/3's own frozen-baseline
    manifests (agent.graph_v2.checksums, read-only, already used by Phase
    4/5) -- proves which exact frozen dataset an experiment was scored
    against, without needing every historical agent run to carry it."""
    from agent.graph_v2 import checksums

    problems = checksums.verify()
    if problems:
        raise RuntimeError(f"Refusing to create an experiment against drifted Phase 1-3 data: {problems}")
    combined = hashlib.sha256()
    for phase in sorted(checksums.PHASES):
        manifest_path = checksums.MANIFEST_DIR / f"{phase}_checksums.json"
        combined.update(manifest_path.read_bytes())
    return combined.hexdigest()[:16]


def create_experiment(
    name: str,
    kind: str,
    dataset_split: str,
    case_ids: list,
    agent_version_fields: dict,
    run_mode: str,
    run_ids: list,
    aggregate: dict,
) -> dict:
    experiment_id = new_experiment_id(name)
    record = {
        "experiment_id": experiment_id,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "dataset_split": dataset_split,
        "split_version": SPLIT_VERSION,
        "case_ids": case_ids,
        "num_cases": len(case_ids),
        "agent": agent_version_fields,
        "dataset_checksum_digest": dataset_checksum_digest(),
        "evaluator_version": EVAL_HARNESS_VERSION,
        "run_mode": run_mode,
        "run_ids": run_ids,
        "aggregate": aggregate,
    }
    return record


def persist_experiment(record: dict, case_records: list) -> Path:
    exp_dir = EXPERIMENTS_DIR / record["experiment_id"]
    exp_dir.mkdir(parents=True, exist_ok=True)

    with open(exp_dir / "experiment.json", "w") as f:
        json.dump(record, f, indent=2, default=str)

    with open(exp_dir / "case_metrics.jsonl", "w") as f:
        for rec in case_records:
            f.write(json.dumps(rec, default=str) + "\n")

    _write_case_metrics_csv(exp_dir / "case_metrics.csv", case_records)

    with open(exp_dir / "confusion_matrices.json", "w") as f:
        json.dump(record["aggregate"].get("confusion_matrices", {}), f, indent=2)

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    index_line = {
        "experiment_id": record["experiment_id"],
        "name": record["name"],
        "created_at": record["created_at"],
        "kind": record["kind"],
        "dataset_split": record["dataset_split"],
        "num_cases": record["num_cases"],
        "run_mode": record["run_mode"],
    }
    with open(REGISTRY_PATH, "a") as f:
        f.write(json.dumps(index_line, default=str) + "\n")

    return exp_dir


def _flatten(d: dict, prefix: str = "") -> dict:
    flat = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            flat.update(_flatten(v, key + "."))
        elif isinstance(v, list):
            flat[key] = ";".join(str(x) for x in v)
        else:
            flat[key] = v
    return flat


def _write_case_metrics_csv(path: Path, case_records: list):
    if not case_records:
        path.write_text("")
        return
    flat_rows = [_flatten(r) for r in case_records]
    fieldnames = sorted({k for row in flat_rows for k in row})
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_rows)


def list_experiments() -> list:
    if not REGISTRY_PATH.exists():
        return []
    with open(REGISTRY_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_experiment(experiment_id: str) -> dict:
    exp_dir = EXPERIMENTS_DIR / experiment_id
    with open(exp_dir / "experiment.json") as f:
        return json.load(f)


def load_case_metrics(experiment_id: str) -> list:
    exp_dir = EXPERIMENTS_DIR / experiment_id
    with open(exp_dir / "case_metrics.jsonl") as f:
        return [json.loads(line) for line in f if line.strip()]
