"""Deterministic development trace pool and corpus (Phase 8, sections 23 to 25).

Dev cases only. The pool is a fixed-seed stratified sample of the dev split; completed Phase 5 traces are reused when valid,
and the Phase 5 agent is run, unchanged, for the rest. Nothing here reads a Jev or LLM-judge output: corpus selection
depends only on the pool's Phase 6 scores and evaluation-only case facts, so it cannot favour any judge.

Usage:
    python3 -m agent.trace_eval_v2.corpus --build-pool            # writes data/eval/trace_eval/pool_v1.json, prints the plan, no API call
    python3 -m agent.trace_eval_v2.corpus --generate              # runs the missing pool cases through the Phase 5 agent (parallel)
"""
import argparse
import hashlib
import json
import random
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.eval_v2.splits import case_ids_for_split
from agent.eval_v2.stratify import stratify_case
from agent.trace_eval_v2.config import AGENT_RUNS_DIR, CORPUS_TARGET, CORPUS_VERSION, POOL_SEED, POOL_SIZE, POOL_VERSION, RUN_WORKERS, TRACE_EVAL_DIR

POOL_PATH = TRACE_EVAL_DIR / "pool_v1.json"
CONTEXT_PATH = TRACE_EVAL_DIR / "pool_context_v1.jsonl"  # observable review context per trace (ticket, evidence inventory): model-facing side
LABELS_PATH = TRACE_EVAL_DIR / "pool_labels_v1.jsonl"    # evaluation-only reference labels per trace: evaluator side, never read by a judge
CORPUS_PATH = TRACE_EVAL_DIR / "corpus_v1.json"


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def assert_dev_only(case_ids: list) -> None:
    dev = set(case_ids_for_split("dev"))
    outside = [c for c in case_ids if c not in dev]
    if outside:
        raise SystemExit(f"{len(outside)} case id(s) are not in the dev split (for example {outside[0]}); Phase 8 uses dev cases only")


def build_pool(size: int = POOL_SIZE, seed: int = POOL_SEED) -> dict:
    """All dev cases with insufficient or partially sufficient evidence (rare, and the low-evidence slices need them), plus a
    proportional, seeded sample of the sufficient strata (by difficulty archetype) up to `size`."""
    dev = case_ids_for_split("dev")
    strata = defaultdict(list)
    info = {}
    for cid in dev:
        s = stratify_case(cid)
        info[cid] = s
        strata[s["stratum_key"]].append(cid)
    rare = sorted(cid for cid in dev if info[cid]["evidence_sufficiency"] != "sufficient")
    sufficient_strata = {k: sorted(v) for k, v in strata.items() if k.endswith("|sufficient")}
    need = max(0, size - len(rare))
    total = sum(len(v) for v in sufficient_strata.values())
    quotas = {k: need * len(v) / total for k, v in sufficient_strata.items()}
    base = {k: int(q) for k, q in quotas.items()}
    for k in sorted(quotas, key=lambda k: (-(quotas[k] - base[k]), k))[: need - sum(base.values())]:
        base[k] += 1
    rng = random.Random(seed)
    sampled = []
    for k in sorted(sufficient_strata):
        ids = list(sufficient_strata[k])
        rng.shuffle(ids)
        sampled += ids[: base[k]]
    case_ids = sorted(set(rare) | set(sampled))
    pool = {
        "pool_version": POOL_VERSION, "seed": seed, "target_size": size, "split": "dev", "n_cases": len(case_ids), "case_ids": case_ids,
        "method": "all dev cases whose evidence sufficiency is not 'sufficient' (16 insufficient + partially sufficient), plus a seeded stratified sample of "
                  "the 'sufficient' strata (largest-remainder allocation by difficulty archetype). Not population-representative by design.",
        "stratum_counts": {k: sum(1 for c in case_ids if info[c]["stratum_key"] == k) for k in sorted(strata)},
    }
    pool["case_ids_sha256"] = _sha(case_ids)
    return pool


def write_pool(pool: dict) -> None:
    TRACE_EVAL_DIR.mkdir(parents=True, exist_ok=True)
    if POOL_PATH.exists():
        existing = json.loads(POOL_PATH.read_text())
        if existing["case_ids_sha256"] != pool["case_ids_sha256"]:
            raise SystemExit(f"{POOL_PATH.name} exists with different case ids; the pool is fixed once written")
        return
    POOL_PATH.write_text(json.dumps(pool, indent=2))


def load_pool() -> dict:
    return json.loads(POOL_PATH.read_text())


def reusable_runs(case_ids: list) -> dict:
    """case_id -> stored run (latest first). Valid means: a dev case in the pool, instrumented by the Phase 6 loop (repair_events recorded, so
    repair status is known) and produced by the same loop/prompt/toolset/schema versions the pool is generated with."""
    from agent.agent_v2 import config as agent_cfg

    want = {"prompt_version": agent_cfg.PROMPT_VERSION, "toolset_version": agent_cfg.TOOLSET_VERSION, "output_schema_version": agent_cfg.OUTPUT_SCHEMA_VERSION,
            "agent_loop_version": agent_cfg.AGENT_LOOP_VERSION, "repair_layer_version": agent_cfg.REPAIR_LAYER_VERSION, "model_name": agent_cfg.AGENT_MODEL_NAME}
    latest, wanted = {}, set(case_ids)
    for line in open(AGENT_RUNS_DIR / "runs_index.jsonl"):
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["case_id"] not in wanted:
            continue
        run = json.loads((AGENT_RUNS_DIR / f"{entry['run_id']}.json").read_text())
        if "repair_events" in run and all(run.get(k) == v for k, v in want.items()):
            latest[entry["case_id"]] = run  # later index lines are more recent
    return latest


def generate(case_ids: list, workers: int = RUN_WORKERS) -> dict:
    """Runs the unchanged Phase 5 agent for each case (parallel; one session per worker). Returns {case_id: run_id}."""
    from agent.agent_v2 import trace as agent_trace
    from agent.agent_v2.loop import run_case
    from agent.graph_v2.db import get_driver

    assert_dev_only(case_ids)
    driver = get_driver()

    def work(cid):
        last = None
        for attempt in (1, 2, 3):
            try:
                with driver.session() as session:
                    return cid, run_case(cid, session), None
            except Exception as e:  # noqa: BLE001 - a transient graph/API failure retries the whole run
                last = f"{type(e).__name__}: {str(e)[:200]}"
                time.sleep(3.0 * attempt)
        return cid, None, last

    done, failed, started = {}, [], time.time()
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(work, cid) for cid in case_ids]
            for i, fut in enumerate(as_completed(futures), start=1):
                cid, result, error = fut.result()
                if error:
                    failed.append((cid, error))
                    print(f"  FAILED {cid}: {error}", flush=True)
                else:
                    path = agent_trace.persist_run(result)  # persisted from the main thread
                    done[cid] = path.stem
                if i % 20 == 0 or i == len(futures):
                    print(f"  {i}/{len(futures)} runs ({len(failed)} failed), {(time.time() - started) / 60:.1f} min", flush=True)
    finally:
        driver.close()
    if failed:
        print(f"{len(failed)} case(s) failed after retries: {failed[:5]}")
    return done


# ── labels, context and the selected corpus ─────────────────────────────────────────────
def build_records(pool: dict, workers: int = 4) -> list:
    """For every pool trace: the observable review context and the evaluation-only reference labels. Writes both files (fixed once written)."""
    from agent.graph_v2.db import get_driver
    from agent.trace_eval_v2.labels import compute_labels
    from agent.trace_eval_v2.trace_loader import load_trace
    from agent.trace_eval_v2.trace_projection import build_review_context

    runs = reusable_runs(pool["case_ids"])
    missing = [c for c in pool["case_ids"] if c not in runs]
    driver = get_driver()
    records = []
    try:
        with driver.session() as session:
            for cid in pool["case_ids"]:
                if cid not in runs:
                    continue
                trace = load_trace(runs[cid])
                ctx = build_review_context(session, cid, trace.submit_step.clock if trace.submit_step else trace.steps[-1].clock)
                labels = compute_labels(trace, {i["id"] for i in ctx["inventory"]})
                records.append({"run_id": trace.run_id, "case_id": cid, "context": ctx, "labels": labels})
    finally:
        driver.close()
    print(f"built {len(records)} records; {len(missing)} pool cases have no valid run: {missing[:10]}")
    return records


def write_records(records: list) -> None:
    if CONTEXT_PATH.exists():
        raise SystemExit(f"{CONTEXT_PATH.name} exists; the pool records are fixed once written")
    with open(CONTEXT_PATH, "w") as f:
        for r in records:
            f.write(json.dumps({"run_id": r["run_id"], "case_id": r["case_id"], "context": r["context"]}, default=str) + "\n")
    with open(LABELS_PATH, "w") as f:
        for r in records:
            f.write(json.dumps({"run_id": r["run_id"], "case_id": r["case_id"], "labels": r["labels"]}, default=str) + "\n")


def load_context() -> dict:
    return {json.loads(l)["run_id"]: json.loads(l)["context"] for l in open(CONTEXT_PATH) if l.strip()}


def load_labels() -> dict:
    return {json.loads(l)["run_id"]: json.loads(l)["labels"] for l in open(LABELS_PATH) if l.strip()}


def select_corpus(labels: dict, target: int = CORPUS_TARGET, seed: int = POOL_SEED) -> dict:
    """The evaluation corpus: every pool trace that has a property the study needs to see (there are few, because the baseline agent's traces are almost all defective), then a
    seeded stratified fill by difficulty archetype up to `target`. Reads only reference labels and Phase 6 scores, never a judge's output. Not population-representative by design."""
    props = {
        "outcome_correct": lambda v: v["outcome"]["label"] == "CORRECT",
        "process_good": lambda v: v["process"]["label"] == "GOOD",
        "auto_close_reference": lambda v: "AUTO_CLOSE" in (v["labels"]["human_review"]["label"], v["labels"]["human_review_process_only"]["label"]),
        "support_supported": lambda v: v["labels"]["support"]["label"] == "SUPPORTED",
        "distractor_anchoring": lambda v: bool(v["labels"]["distractor_anchor"]["label"]),
        "final_inconsistency": lambda v: not v["labels"]["final_consistency"]["label"],
        "insufficient_evidence_case": lambda v: v["stratification"]["evidence_sufficiency"] == "insufficient",
        "retrieved_critical_evidence": lambda v: v["facts"]["n_retrieved_critical"] > 0,
    }
    chosen, by_prop = {}, {}
    for name, fn in props.items():
        members = sorted(rid for rid, v in labels.items() if fn(v))
        by_prop[name] = len(members)
        for rid in members:
            chosen.setdefault(rid, []).append(name)
    if len(chosen) > target:
        rng = random.Random(f"{seed}|trim")
        keep = sorted(chosen, key=lambda r: (-len(chosen[r]), r))
        head = keep[: target // 2]
        rest = [r for r in keep[target // 2:]]
        rng.shuffle(rest)
        chosen = {r: chosen[r] for r in head + rest[: target - len(head)]}
    remaining = defaultdict(list)
    for rid in sorted(labels):
        if rid not in chosen:
            remaining[labels[rid]["stratification"]["difficulty_archetype"]].append(rid)
    need = target - len(chosen)
    total = sum(len(v) for v in remaining.values())
    rng = random.Random(f"{seed}|fill")
    fill = []
    if need > 0 and total:
        quotas = {k: need * len(v) / total for k, v in remaining.items()}
        base = {k: int(q) for k, q in quotas.items()}
        for k in sorted(quotas, key=lambda k: (-(quotas[k] - base[k]), k))[: need - sum(base.values())]:
            base[k] += 1
        for k in sorted(remaining):
            ids = list(remaining[k])
            rng.shuffle(ids)
            fill += ids[: base[k]]
    run_ids = sorted(set(chosen) | set(fill))
    corpus = {"corpus_version": CORPUS_VERSION, "seed": seed, "target": target, "n_traces": len(run_ids), "run_ids": run_ids,
              "case_ids": sorted(labels[r]["stratification"]["case_id"] for r in run_ids), "properties_pool_counts": by_prop,
              "included_by_property": len(chosen), "filled_by_archetype_stratified_sample": len(fill),
              "note": "enriched for rare properties on purpose; prevalences in this corpus are not population rates"}
    corpus["run_ids_sha256"] = _sha(run_ids)
    return corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-pool", action="store_true")
    group.add_argument("--generate", action="store_true")
    group.add_argument("--build-records", action="store_true", help="compute review context and reference labels for every pool trace (no API call)")
    group.add_argument("--select-corpus", action="store_true", help="choose the evaluation corpus from the pool's labels (no API call)")
    args = parser.parse_args()
    if args.build_records:
        write_records(build_records(load_pool()))
        return
    if args.select_corpus:
        corpus = select_corpus(load_labels())
        if CORPUS_PATH.exists():
            raise SystemExit(f"{CORPUS_PATH.name} exists; the corpus is fixed once written")
        CORPUS_PATH.write_text(json.dumps(corpus, indent=2))
        print(json.dumps({k: v for k, v in corpus.items() if k not in ("run_ids", "case_ids")}, indent=2))
        return
    if args.build_pool:
        pool = build_pool()
        write_pool(pool)
        have = reusable_runs(pool["case_ids"])
        print(json.dumps({k: v for k, v in pool.items() if k != "case_ids"}, indent=2))
        print(f"reusable stored runs: {len(have)}; to generate: {pool['n_cases'] - len(have)}")
        return
    pool = load_pool()
    assert_dev_only(pool["case_ids"])
    have = reusable_runs(pool["case_ids"])
    missing = [c for c in pool["case_ids"] if c not in have]
    print(f"pool {pool['n_cases']} dev cases; {len(have)} reusable runs; generating {len(missing)}", flush=True)
    generate(missing)


if __name__ == "__main__":
    main()
