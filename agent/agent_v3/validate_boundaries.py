"""Phase 9A boundary validator (spec section 44). Exits non-zero if any check fails.

    python3 -m agent.agent_v3.validate_boundaries --pin     # once, before any live run: records sha256 of the frozen Phase 1-8 inputs
    python3 -m agent.agent_v3.validate_boundaries           # every check

Checks: the runtime import closure and source text hold no hidden-truth reader, no Phase 6/7/8 module and no Jev call; the registry is built from
observable state only; aliases carry no truth encoding; canonical ids never reach a prompt or schema (real graph, stub model); stored runs respect the
budgets and use only dev cases; the frozen earlier-phase files and the graph are unchanged; the environment pins hold.
"""
import ast
import hashlib
import json
import re
import sys
from importlib import metadata
from pathlib import Path

from agent.agent_v3 import cohorts
from agent.agent_v3 import config as C
from agent.agent_v3 import contract_export
from agent.agent_v3.registry import KINDS, ObservedEntityRegistry

ROOT = C.PROJECT_ROOT
PKG = ROOT / "agent" / "agent_v3"
RUNTIME = ("registry", "catalog", "final_contract", "loop", "prompts", "llm", "backend", "config", "trace", "contract_export", "triage_hint")
FORBIDDEN_MODULE = re.compile(r"^(agent\.(eval_v2|trace_eval_v2|jev_v2)|data\.eval)")
FORBIDDEN_TEXT = ("gt_", "ground_truth", "eval_store", "get_hidden_truth", "evaluation_label", "jev_v2", "typesafe", "locked_benchmark", "case_splits")
ALLOWED_SOURCES = {"taxonomy", "prose", "get_case_context", "get_customer_deployment", "get_component_topology", "get_technical_signals", "get_telemetry",
                   "get_recent_changes", "get_deployment_history", "get_configuration_history", "get_service_health", "get_active_incidents",
                   "get_similar_cases", "search_knowledge_base", "get_team_capability", "get_agent_availability"}
PIN_PATH = C.COHORT_DIR / "frozen_inputs_9a.json"
PINNED_GLOBS = ("agent/agent_v2/*.py", "agent/eval_v2/*.py", "agent/trace_eval_v2/*.py", "agent/jev_v2/*.py", "agent/graph_v2/*.py", "agent/graph_v2/**/*.py",
                "data/eval/eval_store.py", "data/eval/splits/*.json", "data/eval/trace_eval/*.json", "data/eval/trace_eval/*.jsonl", "data/experiments/registry.jsonl",
                "data/agent_runs/runs_index.jsonl", "data/phase2/*.csv", "data/phase3/*.csv", "data/raw_v2/*.csv")
GRAPH_COUNTS = (116_868, 325_539)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pinned_files() -> dict:
    out = {}
    for g in PINNED_GLOBS:
        for p in sorted(ROOT.glob(g)):
            if p.is_file() and "__pycache__" not in p.parts:
                out[str(p.relative_to(ROOT))] = _sha(p)
    return out


def _resolve(mod: str):
    p = ROOT / (mod.replace(".", "/") + ".py")
    if p.exists():
        return p
    p = ROOT / mod.replace(".", "/") / "__init__.py"
    return p if p.exists() else None


def import_closure(start_files) -> set:
    seen, todo = set(), list(start_files)
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        for n in ast.walk(ast.parse(f.read_text())):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module] + [f"{n.module}.{a.name}" for a in n.names]) if isinstance(n, ast.ImportFrom) and n.module else []
            for m in mods:
                if m and m.split(".")[0] in ("agent", "data"):
                    p = _resolve(m)
                    if p:
                        todo.append(p)
    return seen


def check_import_closure():
    closure = import_closure([PKG / f"{m}.py" for m in RUNTIME])
    bad = sorted({str(f.relative_to(ROOT)) for f in closure if FORBIDDEN_MODULE.match(".".join(f.relative_to(ROOT).with_suffix("").parts).replace(".__init__", ""))})
    return not bad, f"{len(closure)} modules in the runtime import closure; forbidden: {bad}"


def check_source_text():
    hits = []
    for m in RUNTIME:
        text = (PKG / f"{m}.py").read_text()
        for w in FORBIDDEN_TEXT:
            if w in text:
                hits.append(f"{m}.py contains {w!r}")
    return not hits, hits or "no hidden-truth marker, evaluation store, Jev client or split file is referenced by any runtime module"


def check_contract_and_budgets():
    ok = contract_export.matches_file() and C.MAX_TOOL_CONTRACT_REPAIRS == 2 and C.MAX_FINAL_CONTRACT_REPAIRS == 1
    return ok, f"contract JSON matches code; budgets tool={C.MAX_TOOL_CONTRACT_REPAIRS} final={C.MAX_FINAL_CONTRACT_REPAIRS}; model {C.MODEL_NAME} (Phase 5 baseline model)"


def check_model_unchanged():
    from agent.agent_v2 import config as p5
    return (C.MODEL_NAME, C.MODEL_PROVIDER, C.TEMPERATURE) == (p5.AGENT_MODEL_NAME, p5.AGENT_MODEL_PROVIDER, p5.AGENT_TEMPERATURE), f"{C.MODEL_NAME} via {C.MODEL_PROVIDER} at {C.TEMPERATURE}"


def check_alias_properties():
    pat = re.compile("^(" + "|".join(KINDS) + ")_[BCDFGHJKLMNPQRSTVWXZ]{3}$")
    reg = ObservedEntityRegistry("CS00001")
    ids = [f"CM{n:03d}" for n in range(1, 400)]
    aliases = [reg.add("COMPONENT", i, source_tool="x", step=1, clock="t").alias for i in ids]
    fmt_ok = all(pat.match(a) for a in aliases) and len(set(aliases)) == len(ids)
    codes = [a.split("_")[1] for a in aliases]
    # no order encoding: the alias code sequence must not be monotone in the id sequence (rank correlation near zero)
    ranks = {c: r for r, c in enumerate(sorted(codes))}
    n = len(codes)
    d2 = sum((ranks[codes[i]] - i) ** 2 for i in range(n))
    rho = 1 - 6 * d2 / (n * (n * n - 1))
    other = ObservedEntityRegistry("CS00002").add("COMPONENT", "CM001", source_tool="x", step=1, clock="t").alias != aliases[0]
    return fmt_ok and abs(rho) < 0.15 and other, f"format ok={fmt_ok}, spearman(id order, alias order)={rho:.3f}, case-keyed={other}"


def check_real_graph_leak_free():
    from agent.agent_v3 import dry_run
    from agent.agent_v3.backend import Neo4jBackend
    from agent.agent_v3.loop import run_case
    from agent.graph_v2.db import get_driver

    pool = json.loads(cohorts.POOL_PATH.read_text())["case_ids"]
    used = set(cohorts.load("iter50")["case_ids"]) | set(cohorts.load("verify100")["case_ids"])
    ids = [c for c in sorted(pool) if c not in used][:3]
    drv, notes = get_driver(), []
    try:
        for cid in ids:
            with drv.session() as s:
                r = run_case(cid, Neo4jBackend(s, cid), dry_run.StubPolicy(7))  # StubPolicy asserts no canonical id in any prompt or schema
            srcs = {e["source_tool"] for e in r["alias_mappings"].values()}
            if not srcs <= ALLOWED_SOURCES:
                return False, f"{cid}: registry source outside the observable set: {sorted(srcs - ALLOWED_SOURCES)}"
            notes.append(f"{cid}:{len(r['alias_mappings'])} entities")
    finally:
        drv.close()
    return True, "stub-model replay on real dev cases outside both cohorts: no canonical id in any prompt/schema; registry sources observable-only; " + ", ".join(notes)


def _stored_runs():
    idx = C.RUNS_DIR / "runs_index.jsonl"
    if not idx.exists():
        return []
    return [json.loads((C.RUNS_DIR / f"{json.loads(l)['run_id']}.json").read_text()) for l in idx.read_text().splitlines() if l.strip()]


def check_stored_runs():
    from agent.agent_v3.final_contract import ALL_STATUSES
    pat = re.compile("^(" + "|".join(KINDS) + ")_[BCDFGHJKLMNPQRSTVWXZ]{3}$")
    runs, problems = _stored_runs(), []
    for r in runs:
        if r["model_name"] != C.MODEL_NAME:
            problems.append(f"{r['run_id']}: model {r['model_name']}")
        if len(r["tool_contract_repairs"]) > C.MAX_TOOL_CONTRACT_REPAIRS or (1 if r["final_contract_repair"] else 0) > C.MAX_FINAL_CONTRACT_REPAIRS:
            problems.append(f"{r['run_id']}: repair budget exceeded")
        if r["final_status"] not in ALL_STATUSES:
            problems.append(f"{r['run_id']}: status {r['final_status']}")
        if not {e["source_tool"] for e in r["alias_mappings"].values()} <= ALLOWED_SOURCES:
            problems.append(f"{r['run_id']}: non-observable registry source")
        if not all(pat.match(a) for a in r["alias_mappings"]):
            problems.append(f"{r['run_id']}: alias outside the alias pattern")
        if r["final_status"] != "CONTRACT_FAILURE" and r["contract_failure"]:
            problems.append(f"{r['run_id']}: contract_failure recorded but status {r['final_status']}")
    return not problems, problems or f"{len(runs)} stored run(s): budgets respected, statuses valid, registry sources observable, aliases well-formed"


def check_dev_only():
    from agent.eval_v2.splits import case_ids_for_split
    dev = set(case_ids_for_split("dev"))
    bad = [c for n in cohorts.QUOTAS for c in cohorts.load(n)["case_ids"] if c not in dev]
    bad += [r["case_id"] for r in _stored_runs() if r["case_id"] not in dev]
    reg = [json.loads(l) for l in (ROOT / "data" / "experiments" / "registry.jsonl").read_text().splitlines() if l.strip()]
    locked = [e for e in reg if "locked" in json.dumps(e).lower() and "superseded" not in json.dumps(e).lower() and e.get("experiment_type") == "locked_benchmark"]
    disjoint = not set(cohorts.load("iter50")["case_ids"]) & set(cohorts.load("verify100")["case_ids"])
    return not bad and not locked and disjoint, f"cohorts and stored runs are dev-only ({len(bad)} outside dev); cohorts disjoint={disjoint}; locked-benchmark experiments={len(locked)}"


def check_frozen_inputs():
    if not PIN_PATH.exists():
        return False, "no pin file; run with --pin before the first live run"
    pinned, now = json.loads(PIN_PATH.read_text())["files"], pinned_files()
    changed = sorted(k for k in pinned if now.get(k) != pinned[k])
    added = sorted(k for k in now if k not in pinned)
    return not changed and not added, f"{len(pinned)} frozen Phase 1-8 files; changed={changed[:5]}; added={added[:5]}"


def check_environment():
    pins = {"tenacity": "8.5.0", "langchain": "0.2.16", "langchain-core": "0.2.43", "langchain-community": "0.2.16", "streamlit": "1.35.0"}
    bad = {k: metadata.version(k) for k, v in pins.items() if metadata.version(k) != v}
    try:
        metadata.version("typesafe-sdk")
        sdk = True
    except metadata.PackageNotFoundError:
        sdk = False
    return not bad and not sdk, f"pins held={not bad} {bad}; typesafe-sdk installed={sdk}"


def check_graph_counts():
    from agent.graph_v2.db import get_driver
    drv = get_driver()
    try:
        with drv.session() as s:
            n = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            r = s.run("MATCH ()-[x]->() RETURN count(x) AS c").single()["c"]
    finally:
        drv.close()
    return (n, r) == GRAPH_COUNTS, f"{n:,} nodes / {r:,} relationships (expected {GRAPH_COUNTS[0]:,} / {GRAPH_COUNTS[1]:,})"


CHECKS = [("runtime import closure holds no hidden-truth/eval/Jev module", check_import_closure), ("runtime source text holds no hidden-truth marker or Jev call", check_source_text),
          ("machine-readable contract matches code; repair budgets", check_contract_and_budgets), ("model/provider/temperature unchanged from Phase 5", check_model_unchanged),
          ("aliases: well-formed, keyed on case, no order encoding", check_alias_properties), ("real-graph replay: no canonical id reaches the model; registry observable-only", check_real_graph_leak_free),
          ("stored runs: budgets, statuses, registry sources, aliases", check_stored_runs), ("dev-only: cohorts, runs, no locked experiment, cohorts disjoint", check_dev_only),
          ("frozen Phase 1-8 files unchanged", check_frozen_inputs), ("environment pins; typesafe-sdk absent", check_environment), ("graph counts unchanged", check_graph_counts)]


if __name__ == "__main__":
    if "--pin" in sys.argv:
        if PIN_PATH.exists():
            sys.exit(f"{PIN_PATH.name} already exists; the pin is fixed once written")
        PIN_PATH.write_text(json.dumps({"purpose": "sha256 of the frozen Phase 1-8 inputs at the start of Phase 9A", "files": pinned_files()}, indent=1))
        print(f"pinned {len(json.loads(PIN_PATH.read_text())['files'])} files")
        sys.exit(0)
    failed = 0
    for i, (name, fn) in enumerate(CHECKS, 1):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        failed += not ok
        print(f"{i:>2}. [{'PASS' if ok else 'FAIL'}] {name}\n      {detail}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    sys.exit(1 if failed else 0)
