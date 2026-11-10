"""Loader and verifier for the Stage B frozen configuration.

The frozen configuration is two files under data/eval/jev/ (same
config-plus-manifest layout as Phase 6's split files):

  <name>.json            the explicit per-decision settings Stage C must use
  <name>_manifest.json   sha256 of that file, of the split file, of the input
                         model-defining source files, the Phase 1-3 dataset
                         digest, the dev cohort id list, and the reference
                         experiments the freeze was measured on

`verify()` returns a list of problems; an empty list means the code and data
in the working tree are exactly what was frozen. `run_experiment
--frozen-config <name>` refuses to run unless it is empty, and takes every
version from the file -- there is no "auto" setting to drift.

Nothing here imports hidden truth.
"""
import hashlib
import json
from pathlib import Path

from agent.jev_v2 import config as jev_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FROZEN_DIR = PROJECT_ROOT / "data" / "eval" / "jev"
SPLIT_FILE = PROJECT_ROOT / "data" / "eval" / "splits" / "case_splits_v1.json"

# Source files whose content determines what Jev/the LLM is shown or how a
# decision is scored. Reporting/rendering modules are deliberately excluded.
FROZEN_SOURCE_FILES = [
    "agent/jev_v2/candidates.py",
    "agent/jev_v2/questions.py",
    "agent/jev_v2/state_builder.py",
    "agent/jev_v2/reference_data.py",
    "agent/jev_v2/scoring.py",
    "agent/jev_v2/decisions.py",
    "agent/jev_v2/llm_baseline.py",
    "agent/jev_v2/client.py",
    "agent/agent_v2/tools.py",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def config_path(name: str) -> Path:
    return FROZEN_DIR / f"{name}.json"


def manifest_path(name: str) -> Path:
    return FROZEN_DIR / f"{name}_manifest.json"


def load(name: str) -> dict:
    with open(config_path(name)) as f:
        return json.load(f)


def load_manifest(name: str) -> dict:
    with open(manifest_path(name)) as f:
        return json.load(f)


def run_settings(cfg: dict) -> dict:
    """The settings run_experiment applies, taken only from the frozen file."""
    decisions = cfg["decisions"]
    return {
        "candidate_versions": {dt: d["candidate_generation_version"] for dt, d in decisions.items()},
        "context_version": decisions["root_cause"]["context_version"],
        "causal_key_mode": decisions["causal_change"].get("key_mode", "canonical"),
        "jev_model": cfg["jev"]["model_requested"],
        "decision_types": list(decisions),
    }


def verify_versions(cfg: dict) -> list:
    """Checks that need no manifest: does the code still carry the frozen versions."""
    problems = []
    decisions = cfg["decisions"]
    for dt, d in decisions.items():
        if jev_config.QUESTION_VERSIONS.get(dt) != d["question_version"]:
            problems.append(f"question version drift for {dt}: code={jev_config.QUESTION_VERSIONS.get(dt)} frozen={d['question_version']}")
        if jev_config.CANDIDATE_GENERATION_VERSIONS.get(dt) != d["candidate_generation_version"]:
            problems.append(f"candidate generation version drift for {dt}: code={jev_config.CANDIDATE_GENERATION_VERSIONS.get(dt)} frozen={d['candidate_generation_version']}")
    checks = {
        "evaluator_version": (jev_config.EVALUATOR_VERSION, cfg["evaluator_version"]),
        "question_set_version": (jev_config.QUESTION_SET_VERSION, cfg["question_set_version"]),
        "candidate_strategy_bundle": (jev_config.CANDIDATE_STRATEGY_VERSION, cfg["candidate_strategy_bundle"]),
        "pricing_version": (jev_config.PRICING_VERSION, cfg["pricing_version"]),
        "llm model": (jev_config.LLM_BASELINE_MODEL, cfg["llm_baseline"]["model"]),
        "llm temperature": (jev_config.LLM_BASELINE_TEMPERATURE, cfg["llm_baseline"]["temperature"]),
        "llm max_tokens": (jev_config.LLM_BASELINE_MAX_TOKENS, cfg["llm_baseline"]["max_tokens"]),
        "llm repair attempts": (jev_config.LLM_REPAIR_MAX_ATTEMPTS, cfg["llm_baseline"]["repair_max_attempts"]),
        "jev endpoint": (jev_config.TYPESAFE_SYSTEM_ONE_PATH, cfg["jev"]["api_endpoint"]),
    }
    for label, (actual, frozen) in checks.items():
        if actual != frozen:
            problems.append(f"{label} drift: code={actual} frozen={frozen}")
    return problems


def verify(name: str) -> list:
    """Full verification against the manifest. Returns a list of problems."""
    cfg = load(name)
    problems = verify_versions(cfg)
    if not manifest_path(name).exists():
        return problems + [f"manifest {manifest_path(name).name} does not exist -- the configuration has not been frozen yet"]
    manifest = load_manifest(name)

    if sha256_file(config_path(name)) != manifest["config_sha256"]:
        problems.append("frozen config file content changed since it was frozen")
    if sha256_file(SPLIT_FILE) != manifest["split_file_sha256"]:
        problems.append("split file content changed since it was frozen")
    for rel, digest in manifest["source_file_sha256"].items():
        path = PROJECT_ROOT / rel
        if not path.exists():
            problems.append(f"frozen source file missing: {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"frozen source file changed: {rel}")

    from agent.eval_v2.registry import dataset_checksum_digest
    from agent.eval_v2.splits import case_ids_for_split

    if dataset_checksum_digest() != manifest["dataset_checksum_digest"]:
        problems.append("Phase 1-3 dataset checksum digest changed since it was frozen")
    cohort = cfg["cohort"]
    ids = case_ids_for_split(cohort["split"])[: cohort["n_cases"]]
    if sha256_json(ids) != manifest["cohort_case_ids_sha256"]:
        problems.append("dev cohort case-id list changed since it was frozen")
    return problems
