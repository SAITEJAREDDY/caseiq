"""Writes Phase 7 experiments into the SAME data/experiments/ directory and
registry.jsonl Phase 6 already uses (spec section 52: "same general
experiment ecosystem," "do not overwrite Phase 6 agent experiments") --
reuses agent.eval_v2.registry's generic id/digest helpers directly rather
than reimplementing them; only the per-experiment file layout differs
(decisions.jsonl instead of case_metrics.jsonl, since a Phase 7 experiment
is a set of decisions, not a set of case runs).
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from agent.eval_v2.config import EXPERIMENTS_DIR
from agent.eval_v2.registry import REGISTRY_PATH, dataset_checksum_digest, new_experiment_id
from agent.jev_v2.config import CANDIDATE_STRATEGY_VERSION, EVALUATOR_VERSION, QUESTION_SET_VERSION


def create_experiment(name, kind, experiment_type, decision_types, case_ids, split_label, config_extra, report):
    experiment_id = new_experiment_id(name)
    return {
        "experiment_id": experiment_id,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "experiment_type": experiment_type,  # "jev_primitive" | "llm_primitive_baseline"
        "decision_types": decision_types,
        "dataset_split": split_label,
        "case_ids": case_ids,
        "num_cases": len(case_ids),
        "question_set_version": QUESTION_SET_VERSION,
        "candidate_strategy_version": CANDIDATE_STRATEGY_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "dataset_checksum_digest": dataset_checksum_digest(),
        "config": config_extra,
        "report": report,
    }


def _flatten(d, prefix=""):
    flat = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            flat.update(_flatten(v, key + "."))
        elif isinstance(v, list):
            flat[key] = json.dumps(v, default=str)
        else:
            flat[key] = v
    return flat


def persist_experiment(experiment: dict, decision_records: list) -> Path:
    exp_dir = EXPERIMENTS_DIR / experiment["experiment_id"]
    exp_dir.mkdir(parents=True, exist_ok=True)

    with open(exp_dir / "experiment.json", "w") as f:
        json.dump(experiment, f, indent=2, default=str)

    with open(exp_dir / "decisions.jsonl", "w") as f:
        for rec in decision_records:
            f.write(json.dumps(rec, default=str) + "\n")

    flat_rows = [_flatten(r) for r in decision_records]
    if flat_rows:
        fieldnames = sorted({k for row in flat_rows for k in row})
        with open(exp_dir / "decisions.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    index_line = {
        "experiment_id": experiment["experiment_id"], "name": experiment["name"],
        "created_at": experiment["created_at"], "kind": experiment["kind"],
        "experiment_type": experiment["experiment_type"], "dataset_split": experiment["dataset_split"],
        "num_cases": experiment["num_cases"],
    }
    with open(REGISTRY_PATH, "a") as f:
        f.write(json.dumps(index_line, default=str) + "\n")

    return exp_dir


def load_experiment(experiment_id: str) -> dict:
    with open(EXPERIMENTS_DIR / experiment_id / "experiment.json") as f:
        return json.load(f)


def load_decisions(experiment_id: str) -> list:
    with open(EXPERIMENTS_DIR / experiment_id / "decisions.jsonl") as f:
        return [json.loads(line) for line in f if line.strip()]
