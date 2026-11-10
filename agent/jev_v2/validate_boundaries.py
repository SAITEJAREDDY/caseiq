"""Phase 7 boundary validation (spec sections 64-66): the observable-state/
question/candidate/client construction side must never import hidden truth;
only scoring.py may. Plus a runtime leakage-guard test and a time-boundary
re-test through the SAME raw tool functions Phase 5/6 already validated.

Usage:
    python3 -m agent.jev_v2.validate_boundaries
"""
import ast
import json
import sys
from pathlib import Path

from agent.graph_v2 import checksums
from agent.graph_v2.db import get_driver

JEV_V2_DIR = Path(__file__).resolve().parent

# Every module here that constructs what gets SENT to Jev/the LLM -- must never import hidden truth.
OBSERVABLE_SIDE_MODULES = ["state_builder.py", "candidates.py", "questions.py", "client.py", "decisions.py", "llm_baseline.py", "reference_data.py"]
BANNED_IMPORT_SUBSTRINGS = ["eval_store", "agent.eval_v2.ground_truth", "eval_v2.ground_truth"]

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg):
    print(f"  ok:   {msg}")


def check_observable_side_never_imports_hidden_truth():
    print("\n[1] state_builder/candidates/questions/client/decisions/llm_baseline/reference_data never import hidden truth")
    hits = []
    for fname in OBSERVABLE_SIDE_MODULES:
        path = JEV_V2_DIR / fname
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(b in alias.name for b in BANNED_IMPORT_SUBSTRINGS):
                        hits.append((fname, alias.name))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if any(b in mod for b in BANNED_IMPORT_SUBSTRINGS):
                    hits.append((fname, mod))
    if hits:
        for fname, mod in hits:
            fail(f"{fname} imports {mod} -- the observable-construction side must never see hidden truth")
    else:
        ok(f"none of {len(OBSERVABLE_SIDE_MODULES)} observable-side modules import eval_store/ground_truth")


def check_leakage_guard_fires():
    print("\n[2] The runtime leakage guard rejects a deliberately-poisoned payload")
    from agent.jev_v2.client import LeakageGuardError, assert_no_leakage

    poisoned = {"state": {"ticket": "some text", "gt_root_cause_id": "RC04"}, "questions": {}}
    clean = {"state": {"ticket": "some text", "product": "P002"}, "questions": {}}
    try:
        assert_no_leakage(poisoned)
        fail("assert_no_leakage did not raise on a payload containing 'gt_root_cause_id'")
    except LeakageGuardError:
        ok("assert_no_leakage correctly rejected a poisoned payload")
    try:
        assert_no_leakage(clean)
        ok("assert_no_leakage correctly passed a clean payload")
    except LeakageGuardError as e:
        fail(f"assert_no_leakage incorrectly rejected a clean payload: {e}")


def check_time_boundary():
    print("\n[3] Time-boundary re-test through agent.agent_v2.tools' raw functions (reused, not re-derived)")
    from agent.agent_v2.tools import q_active_incidents, q_recent_changes, q_technical_signals

    driver = get_driver()
    try:
        with driver.session() as session:
            case_id = "CS00191"
            before = q_recent_changes(session, case_id, "2024-10-10 20:00:00")
            after = q_recent_changes(session, case_id, "2024-10-11 00:00:00")
            before_ids = {c["evidence_id"] for c in before["recent_changes"]}
            after_ids = {c["evidence_id"] for c in after["recent_changes"]}
            if "CH030460" in before_ids:
                fail("q_recent_changes leaked CH030460 at an as_of before its own timestamp")
            elif "CH030460" not in after_ids:
                fail("q_recent_changes did not surface CH030460 even at the case's own created_date")
            else:
                ok("q_recent_changes: CH030460 hidden before its own timestamp, visible after")

            sig_before = q_technical_signals(session, case_id, "2024-10-10 20:00:00")
            sig_after = q_technical_signals(session, case_id, "2024-10-11 00:00:00")
            if "SG0000943" in {s["evidence_id"] for s in sig_before["signals"]}:
                fail("q_technical_signals leaked SG0000943 before its own timestamp")
            elif "SG0000943" not in {s["evidence_id"] for s in sig_after["signals"]}:
                fail("q_technical_signals did not surface SG0000943 even at the case's own created_date")
            else:
                ok("q_technical_signals: SG0000943 hidden before its own timestamp, visible after")

            inc = q_active_incidents(session, case_id, "1900-01-01 00:00:00")
            if inc["incidents"]:
                fail("q_active_incidents returned incidents at an impossibly early as_of")
            else:
                ok("q_active_incidents: correctly empty at an impossibly early as_of")
    finally:
        driver.close()


def check_determinism():
    print("\n[4] Re-scoring the same stored decision record twice yields identical output")
    import json

    from agent.eval_v2.config import EXPERIMENTS_DIR
    from agent.jev_v2.scoring import score_decision

    candidates = sorted(EXPERIMENTS_DIR.glob("*/decisions.jsonl"))
    if not candidates:
        print("  (skipped: no Phase 7 experiment has been run yet -- nothing to re-score)")
        return
    with open(candidates[0]) as f:
        first_line = f.readline()
    if not first_line.strip():
        print("  (skipped: decisions.jsonl is empty)")
        return
    raw = json.loads(first_line)
    raw.pop("scoring", None)
    raw.pop("stratification", None)
    rec1 = json.dumps(score_decision(raw), sort_keys=True, default=str)
    rec2 = json.dumps(score_decision(raw), sort_keys=True, default=str)
    if rec1 != rec2:
        fail("score_decision produced different output on two calls with identical input")
    else:
        ok(f"score_decision is deterministic (byte-identical across two calls, sample: {candidates[0].parent.name})")


def check_candidate_v3_is_observable_only():
    print("\n[5] candidate_generation_v3 is observable-only and its payloads pass the leakage guard")
    from unittest import mock

    from data.eval import eval_store
    from agent.eval_v2 import ground_truth
    from agent.jev_v2 import candidates as candidates_mod
    from agent.jev_v2 import state_builder
    from agent.jev_v2.client import BANNED_SUBSTRINGS, LeakageGuardError, _flatten, assert_no_leakage
    from agent.jev_v2.questions import build_question

    # A dev case whose true cause is a deployment (the JEV-013 case) and the
    # canonical CS00191 case. Building candidates must never call anything that reads hidden truth.
    tripwires = [mock.patch.object(ground_truth, "get_hidden_truth", side_effect=AssertionError("hidden truth read while building candidates"))]
    for name in dir(eval_store):
        obj = getattr(eval_store, name)
        if callable(obj) and getattr(obj, "__module__", None) == eval_store.__name__ and not name.startswith("_"):
            tripwires.append(mock.patch.object(eval_store, name, side_effect=AssertionError(f"eval_store.{name} called while building candidates")))
    driver = get_driver()
    try:
        with driver.session() as session:
            for tw in tripwires:
                tw.start()
            try:
                for case_id in ("CS00001", "CS00191"):
                    as_of = state_builder.get_case_context(session, case_id)["created_date"]
                    for key_mode in ("canonical", "opaque"):
                        cands, meta = candidates_mod.causal_change_candidates(session, case_id, as_of, version="v3", key_mode=key_mode)
                        state = state_builder.causal_change_state(session, case_id, as_of)
                        question = build_question("causal_change", candidates_mod.model_facing_candidates(cands, meta))
                        try:
                            assert_no_leakage({"state": state, "questions": {"causal_change": question}})
                        except LeakageGuardError as e:
                            fail(f"{case_id} ({key_mode}): leakage guard rejected the v3 payload: {e}")
                            continue
                        keys, values = [], []
                        _flatten(meta, keys, values)
                        bad = [b for b in BANNED_SUBSTRINGS if b in " ".join(keys).lower() and b != "causal"]
                        if bad:
                            fail(f"{case_id} ({key_mode}): candidate metadata keys contain banned substring(s) {bad}")
                        else:
                            ok(f"{case_id} ({key_mode}): v3 candidates built with hidden-truth readers tripwired; payload and metadata keys clean")
            except AssertionError as e:
                fail(str(e))
            finally:
                for tw in tripwires:
                    try:
                        tw.stop()
                    except RuntimeError:
                        pass
    finally:
        driver.close()


def check_stored_payloads_are_clean():
    print("\n[6] Every stored Jev/LLM input (state and option sets) re-passes the leakage guard")
    import json

    from agent.eval_v2.config import EXPERIMENTS_DIR
    from agent.jev_v2.client import LeakageGuardError, assert_no_leakage

    scanned = bad = 0
    for path in sorted(EXPERIMENTS_DIR.glob("exp_*/decisions.jsonl")):
        exp_file = path.parent / "experiment.json"
        if not exp_file.exists() or json.loads(exp_file.read_text()).get("experiment_type") not in ("jev_primitive", "llm_primitive_baseline"):
            continue
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                scanned += 1
                try:
                    assert_no_leakage({"state": rec.get("state"), "questions": {"q": {"criteria": rec.get("candidates") or {}}}})
                except LeakageGuardError as e:
                    bad += 1
                    if bad <= 3:
                        fail(f"{path.parent.name}/{rec.get('decision_id')}: {e}")
    if bad:
        fail(f"{bad} of {scanned} stored decision inputs contain banned content")
    else:
        ok(f"{scanned} stored decision inputs across all Phase 7 experiments are clean")


def check_frozen_config():
    print("\n[7] The Stage B frozen configuration matches the working tree")
    from agent.jev_v2 import frozen_config

    name = "stage_b_frozen_v1"
    if not frozen_config.config_path(name).exists():
        print("  (skipped: no frozen configuration has been written)")
        return
    problems = frozen_config.verify(name) if frozen_config.manifest_path(name).exists() else frozen_config.verify_versions(frozen_config.load(name))
    scope = "full manifest verification" if frozen_config.manifest_path(name).exists() else "versions only; manifest not written yet"
    if problems:
        for p in problems:
            fail(p)
    else:
        ok(f"{name}: {scope} passed")


def check_split_guards():
    print("\n[8] The CLI refuses validation/test splits without their explicit kind (no network is reached)")
    import subprocess

    from agent.eval_v2.config import EXPERIMENTS_DIR

    before = len(list(EXPERIMENTS_DIR.glob("exp_*")))
    for split in ("validation", "test"):
        result = subprocess.run([sys.executable, "-m", "agent.jev_v2.run_experiment", "--name", "guard_check", "--kind", "engineering", "--split", split, "--n", "1"],
                                cwd=JEV_V2_DIR.parent.parent, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 or "requires --kind" not in result.stderr:
            fail(f"--split {split} with --kind engineering was not refused (returncode {result.returncode})")
        else:
            ok(f"--split {split} refused without its explicit kind")
    if len(list(EXPERIMENTS_DIR.glob("exp_*"))) != before:
        fail("a guard check created an experiment directory")


def check_locked_freeze():
    print("\n[9] The locked-benchmark freeze is sealed, verifies against the working tree, and the holdout is unused")
    from agent.jev_v2 import locked_benchmark

    problems = locked_benchmark.verify() + locked_benchmark.verify_environment()
    if problems:
        fail("locked_benchmark_frozen_v1 does not verify: " + "; ".join(problems))
    else:
        ok(f"{locked_benchmark.NAME}: sealed, {len(locked_benchmark.frozen_config.load_manifest(locked_benchmark.NAME)['source_file_sha256'])} source files, protocol, Stage B freeze and Stage C artifacts all match")
    registry_rows = [json.loads(line) for line in open(locked_benchmark.REGISTRY_FILE) if line.strip()]
    on_test = [r["experiment_id"] for r in registry_rows if r.get("dataset_split") == "test"]
    state = locked_benchmark.read_run_state()
    if state is None:
        if on_test or locked_benchmark._registered_locked_runs():
            fail(f"no run-state marker exists but the registry holds locked/test experiments: {on_test[:3]}")
        else:
            ok("the locked holdout is unused: no run-state marker, no locked_benchmark or test-split experiment in the registry")
    else:
        ok(f"a locked run has started ('{state['run_name']}'); the sealed configuration is unchanged since (verified above)")


def check_locked_guards():
    print("\n[10] The locked split cannot be reached around its guards (no network, no test-case id is loaded)")
    import contextlib
    import io
    import subprocess
    from unittest import mock

    from agent.eval_v2 import splits
    from agent.eval_v2.config import EXPERIMENTS_DIR
    from agent.jev_v2 import locked_benchmark
    from agent.jev_v2 import run_experiment as rx

    before = len(list(EXPERIMENTS_DIR.glob("exp_*")))
    base = [sys.executable, "-m", "agent.jev_v2.run_experiment"]
    attempts = {
        "--split test without a frozen configuration": ["--name", "locked_benchmark_run", "--kind", "locked_benchmark", "--split", "test", "--compare-llm"],
        "--split test with the non-locked Stage B freeze": ["--name", "locked_benchmark_run", "--kind", "locked_benchmark", "--split", "test", "--compare-llm", "--frozen-config", "stage_b_frozen_v1"],
        "the locked configuration on the validation split": ["--name", "locked_benchmark_run", "--kind", "validation", "--split", "validation", "--compare-llm", "--frozen-config", "locked_benchmark_frozen_v1"],
        "the locked configuration with a subset or overrides": ["--name", "locked_benchmark_run", "--kind", "locked_benchmark", "--split", "test", "--compare-llm", "--frozen-config", "locked_benchmark_frozen_v1", "--n", "5", "--decision-types", "causal_change"],
        "explicit case ids outside dev and validation": ["--name", "guard_check", "--kind", "engineering", "--case-ids", "CS_NOT_IN_DEV_OR_VALIDATION"],
    }
    for label, argv in attempts.items():
        result = subprocess.run(base + argv, cwd=JEV_V2_DIR.parent.parent, capture_output=True, text=True, timeout=180)
        if result.returncode == 0:
            fail(f"NOT refused: {label}")
        else:
            ok(f"refused: {label}")

    if locked_benchmark.read_run_state() is None:
        requested = []
        real = splits.case_ids_for_split

        def watching(split):
            requested.append(split)
            if split == "test":
                raise AssertionError("the test split's case ids were requested")
            return real(split)

        argv = ["run_experiment", "--name", "locked_benchmark_run", "--kind", "locked_benchmark", "--split", "test", "--compare-llm",
                "--frozen-config", "locked_benchmark_frozen_v1", "--check-only"]
        try:
            with mock.patch.object(rx, "case_ids_for_split", watching), mock.patch.object(splits, "case_ids_for_split", watching), \
                    mock.patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
                rx.main()
            ok(f"--check-only passes every pre-run guard and requested only these splits' ids: {sorted(set(requested))} (never test)")
        except Exception as exc:  # noqa: BLE001
            fail(f"--check-only failed or touched the test split: {exc}")
        if locked_benchmark.RUN_STATE_FILE.exists():
            fail("--check-only wrote a run-state marker")
    else:
        ok("a locked run has started; the pre-run --check-only test is skipped (the one-shot guard now applies)")
    if len(list(EXPERIMENTS_DIR.glob("exp_*"))) != before:
        fail("a guard check created an experiment directory")


def check_opaque_control():
    print("\n[11] The opaque-key control used validation cases only and changed no sealed file; the v1 supersession record matches the sealed artifacts")
    from agent.jev_v2 import frozen_config, locked_benchmark
    from agent.jev_v2.registry import load_experiment

    rows = [json.loads(line) for line in open(locked_benchmark.REGISTRY_FILE) if line.strip()]
    control = [r for r in rows if r.get("kind") == "validation_control"]
    if not control:
        print("  (skipped: no opaque-key control has been run)")
    for r in control:
        exp = load_experiment(r["experiment_id"])
        try:
            locked_benchmark.assert_not_locked_ids(exp["case_ids"])
            in_split = True
        except SystemExit:
            in_split = False
        protocol = exp["config"].get("pre_registered_protocol") or {}
        clean = (exp["dataset_split"] == "validation" and in_split and protocol.get("sha256") == frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / protocol.get("path", "")))
        if clean:
            ok(f"{r['experiment_id']}: validation only ({len(exp['case_ids'])} cases, all in dev or validation), pre-registered protocol digest matches")
        else:
            fail(f"{r['experiment_id']}: not a clean validation-only control (split {exp['dataset_split']}, in dev/validation {in_split})")
        control_info = exp["config"].get("control") or {}
        manifest = frozen_config.load_manifest(locked_benchmark.NAME)
        if control_info.get("locked_config_sha256_at_run") != manifest["config_sha256"] or control_info.get("locked_run_state_at_run") is not None:
            fail(f"{r['experiment_id']}: the locked configuration digest at run time differs from the sealed one")
    record_path = locked_benchmark.FROZEN_DIR / f"{locked_benchmark.NAME}_superseded.json"
    if record_path.exists():
        record = json.loads(record_path.read_text())
        manifest = frozen_config.load_manifest(locked_benchmark.NAME)
        same = (record["preserved"]["config_sha256"] == frozen_config.sha256_file(frozen_config.config_path(locked_benchmark.NAME)) == manifest["config_sha256"]
                and record["preserved"]["manifest_sha256"] == frozen_config.sha256_file(locked_benchmark.manifest_path(locked_benchmark.NAME)))
        if same and record["status"] == "superseded_before_use" and locked_benchmark.read_run_state() is None:
            ok(f"{locked_benchmark.NAME} is recorded as superseded before use; its configuration and manifest are byte-identical to what was sealed")
        else:
            fail(f"the supersession record does not match the sealed artifacts (status {record.get('status')})")
        if not (record.get("enforcement") or {}).get("machine_enforced"):
            print("  NOTE: the supersession is a record only; the sealed runner does not read it, so run_experiment would still accept the v1 command (JEV-036)")


def run():
    FAILS.clear()
    checksums.verify_or_die()
    check_observable_side_never_imports_hidden_truth()
    check_leakage_guard_fires()
    check_time_boundary()
    check_determinism()
    check_candidate_v3_is_observable_only()
    check_stored_payloads_are_clean()
    check_frozen_config()
    check_split_guards()
    check_locked_freeze()
    check_locked_guards()
    check_opaque_control()

    print("\n" + "=" * 70)
    if FAILS:
        print(f"PHASE 7 BOUNDARY VALIDATION FAILED: {len(FAILS)} problem(s)")
        sys.exit(1)
    else:
        print("PHASE 7 BOUNDARY VALIDATION PASSED: all checks green")


if __name__ == "__main__":
    run()
