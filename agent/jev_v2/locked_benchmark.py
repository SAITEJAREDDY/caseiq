"""Locked-benchmark freeze: verification and the one-shot guard.

Files under data/eval/jev/:

  locked_benchmark_frozen_v1.json            every setting of the final holdout run
  locked_benchmark_frozen_v1_manifest.json   sha256 pins (config, split file, split manifest, every
                                             project source file the run and its analysis import,
                                             the pre-registered protocol, the Stage B freeze, the
                                             Stage C experiment artifacts, the Phase 1-3 digest)
  locked_benchmark_run_state.json            written by the FIRST locked run, before its first call

`verify()` returns a list of problems; empty means the working tree is exactly
what was frozen. `run_experiment` refuses a locked run unless it is empty.

The holdout is one-shot: once the run-state marker exists, only a `--resume` of
that same run under the same configuration is accepted. Editing the frozen
configuration (or any pinned file) after the run started makes `verify()` fail
and the benchmark invalid; a changed benchmark needs a new version
(locked_benchmark_frozen_v2, ...) and would be reported as no longer a holdout.

Nothing here imports hidden truth and nothing here reads test-case ids: the
split is pinned by hashing its files, and its size comes from the split
manifest's own recorded counts.
"""
import ast
import hashlib
import json
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from agent.jev_v2 import frozen_config
from agent.jev_v2.frozen_config import FROZEN_DIR, PROJECT_ROOT, sha256_file

NAME = "locked_benchmark_frozen_v1"
STAGE = "locked_benchmark_frozen"
STAGE_B_NAME = "stage_b_frozen_v1"
PROTOCOL_REL = "docs/JEV_LOCKED_BENCHMARK_PROTOCOL.md"
SPLIT_MANIFEST = PROJECT_ROOT / "data" / "eval" / "splits" / "split_manifest_v1.json"
RUN_STATE_FILE = FROZEN_DIR / "locked_benchmark_run_state.json"
REGISTRY_FILE = PROJECT_ROOT / "data" / "experiments" / "registry.jsonl"

# Entry points whose import closure defines what the locked run does and how it is analysed.
ENTRY_MODULES = [
    "agent.jev_v2.run_experiment", "agent.jev_v2.parallel_runner", "agent.jev_v2.locked_report",
    "agent.jev_v2.stage_c_report", "agent.jev_v2.stage_c_posthoc", "agent.jev_v2.threshold_policy",
    "agent.jev_v2.locked_benchmark",
]
# Graph-building code cannot change what a read-only run sees (the graph itself is pinned by its counts).
EXCLUDED_FROM_PINS = ("agent/graph_v2/loaders/", "agent/graph_v2/build_graph.py", "agent/graph_v2/validate_graph.py", "agent/graph_v2/schema.py")
EXPECTED_ENVIRONMENT = {"tenacity": "8.5.0", "langchain": "0.2.16", "langchain-core": "0.2.43", "langchain-community": "0.2.16", "streamlit": "1.35.0"}
FORBIDDEN_PACKAGES = ["typesafe-sdk"]


# ── pinned source files (static import closure) ─────────────────────────────────────
def _module_path(module: str):
    base = PROJECT_ROOT / Path(*module.split("."))
    if base.with_suffix(".py").exists():
        return base.with_suffix(".py")
    if (base / "__init__.py").exists():
        return base / "__init__.py"
    return None


def _imported_modules(path: Path) -> set:
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def pinned_source_files() -> list:
    """Every project source file reachable by import from the run and analysis entry points."""
    seen, stack = {}, list(ENTRY_MODULES)
    while stack:
        module = stack.pop()
        if module in seen or module.split(".")[0] not in ("agent", "config", "data"):
            continue
        path = _module_path(module)
        if path is None:
            continue
        seen[module] = path
        stack.extend(_imported_modules(path))
    rels = sorted(str(p.relative_to(PROJECT_ROOT)) for p in seen.values())
    return [r for r in rels if not r.startswith(EXCLUDED_FROM_PINS)]


# ── config helpers ──────────────────────────────────────────────────────────────────
def is_locked_config(cfg: dict) -> bool:
    return bool(cfg) and cfg.get("stage") == STAGE


def included_decisions(cfg: dict) -> list:
    return [dt for dt, d in cfg["decisions"].items() if d.get("include_in_locked_test")]


def run_settings(cfg: dict) -> dict:
    """The settings run_experiment applies, taken only from the frozen file. Excluded decisions are pinned in
    the config for the record but never run."""
    decisions = cfg["decisions"]
    return {
        "candidate_versions": {dt: d["candidate_generation_version"] for dt, d in decisions.items()},
        "context_version": decisions["root_cause"]["context_version"],
        "causal_key_mode": decisions["causal_change"].get("key_mode", "canonical"),
        "jev_model": cfg["jev"]["model_requested"],
        "decision_types": included_decisions(cfg),
        "workers": cfg["orchestration"]["workers"],
        "protocol": cfg["protocol"]["path"],
        "expected_case_count": cfg["split"]["expected_case_count"],
    }


def manifest_path(name: str = NAME) -> Path:
    return frozen_config.manifest_path(name)


# ── verification ────────────────────────────────────────────────────────────────────
def verify_environment() -> list:
    problems = []
    for pkg, want in EXPECTED_ENVIRONMENT.items():
        try:
            have = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            problems.append(f"required package missing: {pkg}=={want}")
            continue
        if have != want:
            problems.append(f"pinned package drift: {pkg} is {have}, expected {want}")
    for pkg in FORBIDDEN_PACKAGES:
        try:
            metadata.version(pkg)
            problems.append(f"forbidden package installed: {pkg} (it forces tenacity>=9 and breaks the pinned stack)")
        except metadata.PackageNotFoundError:
            pass
    return problems


def verify(name: str = NAME, run_state_file: Path = None) -> list:
    """Full verification of the locked configuration against its manifest. Reads no test-case ids."""
    cfg = frozen_config.load(name)
    problems = []
    if not is_locked_config(cfg):
        return [f"{name} is not a locked-benchmark configuration (stage != {STAGE})"]
    problems += frozen_config.verify_versions(cfg)
    if not manifest_path(name).exists():
        return problems + [f"manifest {manifest_path(name).name} does not exist -- the configuration has not been sealed yet"]
    manifest = frozen_config.load_manifest(name)

    if sha256_file(frozen_config.config_path(name)) != manifest["config_sha256"]:
        problems.append("locked configuration file content changed since it was sealed")
    if sha256_file(frozen_config.SPLIT_FILE) != manifest["split_file_sha256"]:
        problems.append("split file content changed since it was sealed")
    if sha256_file(SPLIT_MANIFEST) != manifest["split_manifest_sha256"]:
        problems.append("split manifest content changed since it was sealed")
    for rel, digest in manifest["source_file_sha256"].items():
        path = PROJECT_ROOT / rel
        if not path.exists():
            problems.append(f"pinned source file missing: {rel}")
        elif sha256_file(path) != digest:
            problems.append(f"pinned source file changed: {rel}")
    for label, entry in manifest["pinned_files"].items():
        path = PROJECT_ROOT / entry["path"]
        if not path.exists():
            problems.append(f"pinned file missing: {label} ({entry['path']})")
        elif sha256_file(path) != entry["sha256"]:
            problems.append(f"pinned file changed: {label} ({entry['path']})")

    problems += [f"Stage B freeze: {p}" for p in frozen_config.verify(STAGE_B_NAME)]
    if cfg["derived_from"]["config_sha256"] != sha256_file(frozen_config.config_path(STAGE_B_NAME)):
        problems.append("derived_from Stage B config digest does not match the Stage B config on disk")

    from agent.eval_v2.registry import dataset_checksum_digest

    if dataset_checksum_digest() != manifest["dataset_checksum_digest"]:
        problems.append("Phase 1-3 dataset checksum digest changed since it was sealed")
    if json.loads(SPLIT_MANIFEST.read_text())["overall_counts"]["test"] != cfg["split"]["expected_case_count"]:
        problems.append("expected locked case count no longer matches the split manifest")

    state = read_run_state(run_state_file)
    if state and state["config_sha256"] != sha256_file(frozen_config.config_path(name)):
        problems.append("the locked configuration changed after the locked run started: that run is no longer a valid holdout benchmark")
    return problems


def check_graph_counts(driver, cfg: dict) -> list:
    """Live check that the runtime graph is the frozen one (read-only)."""
    expected = cfg["graph"]
    with driver.session() as session:
        nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    problems = []
    if nodes != expected["nodes"]:
        problems.append(f"graph node count {nodes} != frozen {expected['nodes']}")
    if rels != expected["relationships"]:
        problems.append(f"graph relationship count {rels} != frozen {expected['relationships']}")
    return problems


def assert_case_ids(case_ids: list, cfg: dict) -> None:
    """Called only by a real locked run, after it has loaded its case ids."""
    if len(case_ids) != cfg["split"]["expected_case_count"]:
        raise SystemExit(f"locked case list has {len(case_ids)} cases, the frozen configuration expects {cfg['split']['expected_case_count']}")


# ── access guard for non-locked runs ────────────────────────────────────────────────
def assert_not_locked_ids(case_ids: list, load_splits=None) -> None:
    """Refuse explicit case ids (--case-ids / --regression-suite) that are not in dev or validation, so the
    test split cannot be reached around the --split guard. Only the dev and validation ids are materialized;
    the test ids are never selected, counted or printed."""
    if load_splits is None:
        from agent.eval_v2.splits import load_splits as _load
        load_splits = _load
    assignment = load_splits()
    allowed = {cid for cid, split in assignment.items() if split in ("dev", "validation")}
    del assignment
    outside = [cid for cid in case_ids if cid not in allowed]
    if outside:
        raise SystemExit(f"{len(outside)} explicit case id(s) are not in the dev or validation split (for example {outside[0]}); "
                         "the locked split is reachable only through --split test --kind locked_benchmark --frozen-config locked_benchmark_frozen_v1")


# ── one-shot run state ──────────────────────────────────────────────────────────────
def read_run_state(path: Path = None):
    path = path or RUN_STATE_FILE
    return json.loads(path.read_text()) if Path(path).exists() else None


def _registered_locked_runs(registry_file: Path = None) -> list:
    registry_file = registry_file or REGISTRY_FILE
    if not Path(registry_file).exists():
        return []
    rows = [json.loads(line) for line in open(registry_file) if line.strip()]
    return [r["experiment_id"] for r in rows if r.get("kind") == "locked_benchmark"]


def check_run_allowed(run_name: str, resume: bool, config_sha256: str, state_file: Path = None, registry_file: Path = None) -> None:
    """One-shot rule. Raises SystemExit with the reason when the run must not start."""
    state = read_run_state(state_file)
    registered = _registered_locked_runs(registry_file)
    if state is None:
        if registered:
            raise SystemExit(f"the registry already holds locked_benchmark experiment(s) {registered[:2]} but no run-state marker exists; refusing (holdout status unknown)")
        if resume:
            raise SystemExit("--resume was given but no locked run has started")
        return
    if state["config_sha256"] != config_sha256:
        raise SystemExit("the locked configuration differs from the one the locked run started under: that run is no longer a valid holdout benchmark. "
                         "A changed benchmark needs a new version (locked_benchmark_frozen_v2) and would not be a holdout.")
    if not resume or run_name != state["run_name"]:
        raise SystemExit(f"the locked holdout was already started by run '{state['run_name']}' at {state['started_at']}. "
                         "Only --resume of that same run is accepted; a second run would no longer be a one-shot holdout.")


def record_run_start(run_name: str, config_sha256: str, manifest_sha256: str, resume: bool, state_file: Path = None) -> dict:
    state_file = Path(state_file or RUN_STATE_FILE)
    existing = read_run_state(state_file)
    if existing is None:
        state = {"freeze_version": NAME, "config_sha256": config_sha256, "manifest_sha256": manifest_sha256, "run_name": run_name,
                 "started_at": datetime.now(timezone.utc).isoformat(), "resumed_at": [], "completed_at": None, "experiment_ids": None}
    else:
        state = existing
        state["resumed_at"].append(datetime.now(timezone.utc).isoformat())
    state_file.write_text(json.dumps(state, indent=2))
    return state


def record_run_complete(experiment_ids: dict, state_file: Path = None) -> None:
    state_file = Path(state_file or RUN_STATE_FILE)
    state = read_run_state(state_file)
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    state["experiment_ids"] = experiment_ids
    state_file.write_text(json.dumps(state, indent=2))


def sha256_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
