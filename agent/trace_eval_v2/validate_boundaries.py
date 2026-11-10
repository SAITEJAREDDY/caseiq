"""Phase 8 boundary validation: proves that nothing evaluation-only can reach a judge, that the two judges see identical inputs, and that the study stayed on dev traces.

Usage:
    python3 -m agent.trace_eval_v2.validate_boundaries
"""
import ast
import json
import sys
from pathlib import Path

from agent.graph_v2 import checksums

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent.parent
FAILS = []

# Everything a judge's input is built from or sent through.
MODEL_FACING = ["models", "trace_loader", "trace_projection", "questions", "guard", "jev_evaluator", "llm_evaluator"]
# Modules that hold or use hidden truth or reference labels.
EVALUATOR_SIDE = ["labels", "perturbations", "scorer", "analysis", "corpus", "experiments", "metrics", "cli"]
BANNED_FOR_MODEL_FACING = {"agent.eval_v2.ground_truth", "data.eval.eval_store", "agent.eval_v2.stratify", "agent.eval_v2.metrics", "agent.eval_v2.evidence", "agent.eval_v2.aggregate",
                           *{f"agent.trace_eval_v2.{m}" for m in EVALUATOR_SIDE}}


def _has_key(obj, name: str) -> bool:
    if isinstance(obj, dict):
        return name in obj or any(_has_key(v, name) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_key(v, name) for v in obj)
    return False


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg):
    print(f"  ok:   {msg}")


def _imports_of(path: Path) -> set:
    tree = ast.parse(path.read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.add(mod)
            out |= {f"{mod}.{a.name}" for a in node.names}
    return out


def _module_file(module: str):
    base = ROOT / Path(*module.split("."))
    if base.with_suffix(".py").exists():
        return base.with_suffix(".py")
    if (base / "__init__.py").exists():
        return base / "__init__.py"
    return None


def static_closure(start_modules: list) -> dict:
    """module -> the module that first imported it, over every project module reachable by imports (function-level imports included)."""
    seen, queue = {}, [(m, None) for m in start_modules]
    while queue:
        mod, via = queue.pop()
        if mod in seen:
            continue
        path = _module_file(mod)
        if path is None:
            continue
        seen[mod] = via
        for imp in _imports_of(path):
            head = imp.split(".")[0]
            if head in ("agent", "data", "config") and imp not in seen:
                queue.append((imp, mod))
    return seen


def check_model_facing_import_closure():
    print("\n[1] Nothing a judge input is built from can import hidden truth, Phase 6 scoring or an evaluator-side Phase 8 module")
    closure = static_closure([f"agent.trace_eval_v2.{m}" for m in MODEL_FACING])
    bad = {m: via for m, via in closure.items() if m in BANNED_FOR_MODEL_FACING}
    if bad:
        for m, via in bad.items():
            fail(f"{m} is reachable from the model-facing side (imported by {via})")
    else:
        ok(f"the import closure of the {len(MODEL_FACING)} model-facing modules ({len(closure)} project modules) contains none of the {len(BANNED_FOR_MODEL_FACING)} banned modules")
    for m in MODEL_FACING:
        text = (PKG / f"{m}.py").read_text()
        if "get_hidden_truth" in text and m != "guard":
            fail(f"{m}.py mentions get_hidden_truth")


def check_runtime_never_imports_phase8():
    print("\n[2] The Phase 5 runtime agent and the sealed Phase 7 code never import Phase 8")
    hits = []
    for folder in ("agent/agent_v2", "agent/jev_v2", "agent/eval_v2", "agent/graph_v2"):
        for p in (ROOT / folder).glob("*.py"):
            if any(i.startswith("agent.trace_eval_v2") for i in _imports_of(p)):
                hits.append(str(p.relative_to(ROOT)))
    if hits:
        fail(f"imported Phase 8: {hits}")
    else:
        ok("no file under agent_v2, jev_v2, eval_v2 or graph_v2 imports agent.trace_eval_v2 (one-directional)")


def _experiments(kind_types=("trace_eval_jev", "trace_eval_llm")) -> list:
    from agent.trace_eval_v2.config import EXPERIMENTS_DIR

    out = []
    for path in sorted(EXPERIMENTS_DIR.glob("exp_trace_eval_*/experiment.json")):
        rec = json.loads(path.read_text())
        if rec.get("experiment_type") in kind_types:
            out.append(rec)
    return out


def check_stored_packets_are_clean():
    print("\n[3] Every stored judge input passes the leakage guard, carries no rationale, and matches its recorded digest")
    from agent.trace_eval_v2 import questions
    from agent.trace_eval_v2.config import EXPERIMENTS_DIR, JUDGMENTS
    from agent.trace_eval_v2.guard import LeakageError, assert_request_clean
    from agent.trace_eval_v2.experiments import _sha
    from agent.trace_eval_v2.trace_projection import state_json

    scanned = bad = 0
    for rec in _experiments():
        for line in open(EXPERIMENTS_DIR / rec["experiment_id"] / "packets.jsonl"):
            if not line.strip():
                continue
            p = json.loads(line)
            scanned += 1
            try:
                for j in JUDGMENTS:
                    assert_request_clean(p["state"], questions.jev_question(j))
                if _has_key(p["state"], "rationale"):
                    raise LeakageError("a rationale field is present")
                if _sha(state_json(p["state"])) != p["state_sha256"]:
                    raise LeakageError("the stored packet does not match its recorded digest")
            except LeakageError as e:
                bad += 1
                if bad <= 3:
                    fail(f"{rec['experiment_id']}/{p['trace_key']}: {e}")
    if not scanned:
        print("  (skipped: no Phase 8 experiment yet)")
    elif bad:
        fail(f"{bad} of {scanned} stored packets are not clean")
    else:
        ok(f"{scanned} stored packets across {len(_experiments())} experiments pass the guard, hold no rationale and match their digests")


def check_projection_reads_no_hidden_truth():
    print("\n[4] Building a packet from a real trace never calls a hidden-truth reader (tripwires)")
    from unittest import mock

    from agent.eval_v2 import ground_truth
    from agent.trace_eval_v2 import corpus
    from data.eval import eval_store
    from agent.trace_eval_v2.trace_loader import load_run, load_trace
    from agent.trace_eval_v2.trace_projection import project

    if not corpus.CONTEXT_PATH.exists():
        print("  (skipped: no pool context yet)")
        return
    ctx = corpus.load_context()
    rids = sorted(ctx)[:3]
    calls = []

    def tripwire(name):
        def f(*a, **k):
            calls.append(name)
            raise AssertionError(f"{name} was called while building a packet")
        return f

    patches = [mock.patch.object(eval_store, n, tripwire(f"eval_store.{n}")) for n in dir(eval_store) if n.startswith("get_")]
    patches += [mock.patch.object(ground_truth, "get_hidden_truth", tripwire("get_hidden_truth"))]
    for p in patches:
        p.start()
    try:
        for rid in rids:
            project(load_trace(load_run(rid)), ctx[rid])
        ok(f"projected {len(rids)} stored traces with every eval_store reader and get_hidden_truth tripwired: none was called")
    except AssertionError as e:
        fail(str(e))
    finally:
        for p in patches:
            p.stop()


def check_reference_labels_deterministic():
    print("\n[5] Reference labels are deterministic and reproduce the stored pool labels")
    from agent.trace_eval_v2 import corpus
    from agent.trace_eval_v2.labels import compute_labels
    from agent.trace_eval_v2.trace_loader import load_run, load_trace

    if not corpus.LABELS_PATH.exists():
        print("  (skipped: no pool labels yet)")
        return
    stored, ctx = corpus.load_labels(), corpus.load_context()
    rids = sorted(stored)[::25][:12]
    bad = 0
    for rid in rids:
        trace = load_trace(load_run(rid))
        ids = {i["id"] for i in ctx[rid]["inventory"]}
        a = json.dumps(compute_labels(trace, ids), sort_keys=True, default=str)
        b = json.dumps(compute_labels(trace, ids), sort_keys=True, default=str)
        if a != b or a != json.dumps(stored[rid], sort_keys=True, default=str):
            bad += 1
    if bad:
        fail(f"{bad} of {len(rids)} traces did not reproduce their stored labels byte for byte")
    else:
        ok(f"{len(rids)} traces re-labelled twice: byte-identical to each other and to the stored pool labels")


def check_packets_reproducible():
    print("\n[6] The stored packets are reproducible from the stored trace, context and alias scheme")
    from agent.trace_eval_v2 import corpus
    from agent.trace_eval_v2.config import EXPERIMENTS_DIR
    from agent.trace_eval_v2.experiments import _sha
    from agent.trace_eval_v2.trace_loader import load_run, load_trace
    from agent.trace_eval_v2.trace_projection import project, state_json

    exps = [e for e in _experiments(("trace_eval_jev",)) if e["n_original_traces"] >= 100]
    if not exps:
        print("  (skipped: no main experiment yet)")
        return
    rec = exps[-1]
    ctx = corpus.load_context()
    stored = {}
    for line in open(EXPERIMENTS_DIR / rec["experiment_id"] / "packets.jsonl"):
        p = json.loads(line)
        stored[p["trace_key"]] = p["state_sha256"]
    originals = [k for k in stored if "#" not in k][:20]
    bad = [k for k in originals if _sha(state_json(project(load_trace(load_run(k)), ctx[k])[0])) != stored[k]]
    if bad:
        fail(f"{len(bad)} packets do not reproduce: {bad[:2]}")
    else:
        ok(f"{len(originals)} stored packets of {rec['experiment_id']} re-projected to the identical digest")


def check_judge_parity_on_stored_runs():
    print("\n[7] For every registered run, Jev and the LLM judge were given the same packets and the same questions")
    from agent.trace_eval_v2.config import EXPERIMENTS_DIR

    by_name = {}
    for rec in _experiments():
        stem = rec["name"].rsplit("_", 1)[0]
        by_name.setdefault(stem, {})[rec["experiment_type"]] = rec
    checked = 0
    for stem, pair in by_name.items():
        if len(pair) != 2:
            fail(f"{stem}: only one judge's experiment is registered")
            continue
        j, l = pair["trace_eval_jev"], pair["trace_eval_llm"]
        pj = {json.loads(x)["trace_key"]: json.loads(x)["state_sha256"] for x in open(EXPERIMENTS_DIR / j["experiment_id"] / "packets.jsonl") if x.strip()}
        pl = {json.loads(x)["trace_key"]: json.loads(x)["state_sha256"] for x in open(EXPERIMENTS_DIR / l["experiment_id"] / "packets.jsonl") if x.strip()}
        qj, ql = j["config"]["question_versions"], l["config"]["question_versions"]
        kj = {(json.loads(x)["trace_key"], json.loads(x)["judgment"]) for x in open(EXPERIMENTS_DIR / j["experiment_id"] / "judgments.jsonl") if x.strip()}
        kl = {(json.loads(x)["trace_key"], json.loads(x)["judgment"]) for x in open(EXPERIMENTS_DIR / l["experiment_id"] / "judgments.jsonl") if x.strip()}
        if pj != pl or qj != ql or kj != kl or j["config"]["projection_version"] != l["config"]["projection_version"]:
            fail(f"{stem}: the two judges' packets, question versions or judged items differ")
        else:
            checked += 1
            ok(f"{stem}: {len(pj)} identical packets, identical question versions, {len(kj)} judged (trace, judgment) pairs each")


def check_dev_only_and_no_locked_access():
    print("\n[8] Phase 8 used dev traces only and did not touch the validation or locked splits")
    from agent.eval_v2.config import EXPERIMENTS_DIR
    from agent.eval_v2.splits import load_splits
    from agent.jev_v2 import locked_benchmark

    assignment = load_splits()
    dev = {c for c, s in assignment.items() if s == "dev"}
    del assignment
    bad = []
    for rec in _experiments():
        bad += [(rec["experiment_id"], c) for c in rec["case_ids"] if c not in dev]
        if rec["dataset_split"] != "dev":
            bad.append((rec["experiment_id"], f"split {rec['dataset_split']}"))
    from agent.trace_eval_v2 import corpus

    if corpus.POOL_PATH.exists():
        bad += [("pool", c) for c in corpus.load_pool()["case_ids"] if c not in dev]
    if corpus.CORPUS_PATH.exists():
        bad += [("corpus", c) for c in json.loads(corpus.CORPUS_PATH.read_text())["case_ids"] if c not in dev]
    if bad:
        fail(f"non-dev material: {bad[:3]}")
    else:
        ok(f"the pool, the corpus and all {len(_experiments())} Phase 8 experiments contain only dev cases")
    registry = [json.loads(l) for l in open(EXPERIMENTS_DIR / "registry.jsonl") if l.strip()]
    p8 = [r for r in registry if str(r.get("experiment_type", "")).startswith("trace_eval")]
    if any(r.get("dataset_split") != "dev" for r in p8):
        fail("a Phase 8 registry entry is not on the dev split")
    if any(r.get("dataset_split") == "test" or r.get("kind") == "locked_benchmark" for r in registry):
        fail("the registry holds a test-split or locked_benchmark experiment")
    if locked_benchmark.read_run_state() is not None:
        fail("a locked run-state marker exists")
    ok(f"{len(p8)} Phase 8 registry entries; no locked or test experiment in the registry; no locked run-state marker")


def check_environment():
    print("\n[9] The dependency-safe environment is intact")
    from importlib import metadata

    if metadata.version("tenacity") != "8.5.0":
        fail(f"tenacity is {metadata.version('tenacity')}")
    else:
        ok("tenacity==8.5.0")
    try:
        metadata.version("typesafe-sdk")
        fail("typesafe-sdk is installed")
    except metadata.PackageNotFoundError:
        ok("typesafe-sdk is absent")


def run():
    FAILS.clear()
    checksums.verify_or_die()
    check_model_facing_import_closure()
    check_runtime_never_imports_phase8()
    check_stored_packets_are_clean()
    check_projection_reads_no_hidden_truth()
    check_reference_labels_deterministic()
    check_packets_reproducible()
    check_judge_parity_on_stored_runs()
    check_dev_only_and_no_locked_access()
    check_environment()
    print("\n" + "=" * 70)
    if FAILS:
        print(f"PHASE 8 BOUNDARY VALIDATION FAILED: {len(FAILS)} problem(s)")
        sys.exit(1)
    print("PHASE 8 BOUNDARY VALIDATION PASSED: all checks green")


if __name__ == "__main__":
    run()
