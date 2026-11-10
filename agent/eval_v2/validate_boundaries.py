"""Phase 6 boundary validation: proves the evaluator's one-directional
boundary holds (the runtime agent must never import the evaluator or its
hidden-truth access, per spec section 44), and that scoring is deterministic
(spec section 60's "evaluation itself is deterministic when given identical
stored traces and identical evaluation-store version").

Usage:
    python3 -m agent.eval_v2.validate_boundaries
"""
import ast
import json
import sys
from pathlib import Path

from agent.agent_v2.config import AGENT_RUNS_DIR
from agent.graph_v2 import checksums

AGENT_V2_DIR = Path(__file__).resolve().parent.parent / "agent_v2"
EVAL_V2_DIR = Path(__file__).resolve().parent

BANNED_RUNTIME_LITERALS = ["eval_v2", "eval_store", "data/experiments", "data.experiments"]

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg):
    print(f"  ok:   {msg}")


def check_agent_v2_never_imports_eval_v2():
    print("\n[1] agent_v2 (runtime) never imports agent.eval_v2 or data.eval.eval_store")
    hits = []
    for p in AGENT_V2_DIR.glob("*.py"):
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "eval_v2" in alias.name or "eval_store" in alias.name:
                        hits.append((p.name, alias.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "eval_v2" in mod or "eval_store" in mod:
                    hits.append((p.name, mod))
    if hits:
        for pyfile, mod in hits:
            fail(f"{pyfile} imports {mod} -- the runtime agent must never import the evaluator")
    else:
        ok(f"none of {len(list(AGENT_V2_DIR.glob('*.py')))} agent_v2/*.py files import agent.eval_v2 or data.eval.eval_store")


def check_agent_v2_never_references_eval_literals():
    """Scans agent_v2's *runtime* modules (not its own validate_boundaries.py
    -- that file legitimately names 'data.eval.eval_store' in its own checks/
    docstrings, exactly as agent/graph_v2/validate_graph.py and
    agent/agent_v2/validate_boundaries.py already do for their own banned
    names; a boundary tester mentioning the thing it forbids is not a leak)."""
    print("\n[2] agent_v2 source never references eval_v2/eval_store/data.experiments as a string literal")
    hits = []
    for p in AGENT_V2_DIR.glob("*.py"):
        if p.name == "validate_boundaries.py":
            continue
        tree = ast.parse(p.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for banned in BANNED_RUNTIME_LITERALS:
                    if banned in node.value:
                        hits.append((p.name, banned, node.value[:80]))
    if hits:
        for pyfile, banned, literal in hits:
            fail(f"{pyfile} references '{banned}' in a string literal: {literal!r}")
    else:
        ok("no banned literal found in agent_v2 source")


def check_determinism():
    print("\n[3] Re-scoring the same stored run twice yields identical output")
    from agent.eval_v2.metrics import evaluate_run

    run_files = sorted(AGENT_RUNS_DIR.glob("*.json"))
    if not run_files:
        fail("no persisted runs under data/agent_runs/ to test determinism against")
        return
    sample = run_files[0]
    with open(sample) as f:
        run = json.load(f)
    rec1 = json.dumps(evaluate_run(run), sort_keys=True, default=str)
    rec2 = json.dumps(evaluate_run(run), sort_keys=True, default=str)
    if rec1 != rec2:
        fail(f"evaluate_run({sample.name}) produced different output on two calls with identical input")
    else:
        ok(f"evaluate_run({sample.name}) is deterministic (byte-identical across two calls)")


def check_regression_suite_scoreable():
    print("\n[4] The permanent regression suite can be scored from already-persisted runs")
    from agent.eval_v2.metrics import evaluate_run
    from agent.eval_v2.regression_cases import REGRESSION_CASES

    with open(AGENT_RUNS_DIR / "runs_index.jsonl") as f:
        index = [json.loads(line) for line in f if line.strip()]
    cases_with_runs = {entry["case_id"] for entry in index}

    missing = [cid for cid in REGRESSION_CASES if cid not in cases_with_runs]
    if missing:
        fail(
            f"no persisted run exists yet for regression case(s) {missing} -- run "
            "`python3 -m agent.eval_v2.run_experiment --name regression --kind smoke "
            "--regression-suite --run-mode run_and_evaluate` at least once"
        )
        return

    scored = 0
    for cid, scenario in REGRESSION_CASES.items():
        run_id = next(e["run_id"] for e in index if e["case_id"] == cid)
        with open(AGENT_RUNS_DIR / f"{run_id}.json") as f:
            run = json.load(f)
        try:
            evaluate_run(run)
            scored += 1
        except Exception as e:
            fail(f"scoring regression case {cid} ({scenario}) raised: {e}")
    if scored == len(REGRESSION_CASES):
        ok(f"all {scored} regression-suite cases scored without error")


def run():
    FAILS.clear()
    checksums.verify_or_die()
    check_agent_v2_never_imports_eval_v2()
    check_agent_v2_never_references_eval_literals()
    check_determinism()
    check_regression_suite_scoreable()

    print("\n" + "=" * 70)
    if FAILS:
        print(f"PHASE 6 BOUNDARY VALIDATION FAILED: {len(FAILS)} problem(s)")
        sys.exit(1)
    else:
        print("PHASE 6 BOUNDARY VALIDATION PASSED: all checks green")


if __name__ == "__main__":
    run()
