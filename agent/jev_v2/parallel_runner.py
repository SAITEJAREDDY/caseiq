"""Concurrent, checkpointed orchestration for large Phase 7 runs (Stage C).

This changes HOW cases are dispatched, not what is sent. Each case builds its
inputs once with the same hashed functions the sequential path uses
(`decisions.build_inputs` / `build_incident_inputs`, `questions.build_question`,
`decisions._call_one`, `llm_baseline.run_llm_decision`), then sends that single
input to Jev and, when asked, to the LLM baseline -- so both systems see
byte-identical state and options by construction.

Separation of concerns: worker threads only build inputs and call the two
models; they never touch hidden truth. Scoring (`scoring.score_decision`,
the one place hidden truth is read) happens afterwards, in the calling
thread, on each returned record.

Robustness for a long, paid run:
  - every completed case is appended to a checkpoint file immediately, so an
    interruption loses at most the in-flight cases; `resume=True` skips
    completed cases and never re-sends them;
  - a case that hits a transient graph/API error is retried in a fresh session;
    a case that still fails is reported (and blocks persisting a partial
    experiment) -- results are never dropped or altered because of their values.

Records come back in the original case order regardless of completion order.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent.graph_v2.db import get_driver
from agent.jev_v2 import candidates as candidates_mod
from agent.jev_v2 import decisions as decisions_mod
from agent.jev_v2 import llm_baseline, questions, state_builder
from agent.jev_v2.scoring import score_decision

CHECKPOINT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "eval" / "jev" / "checkpoints"
CASE_ATTEMPTS = 3


def _process_case(driver, case_id, decision_types, context_version, candidate_versions, causal_key_mode, jev_client, run_llm):
    """Build inputs once per decision and send them to Jev (and the LLM).
    Returns (jev_raw_records, llm_raw_records). Raises on graph/API failure."""
    jev_records, llm_records = [], []
    with driver.session() as session:
        ctx = state_builder.get_case_context(session, case_id)
        if "error" in ctx:
            raise RuntimeError(f"case context unavailable: {ctx['error']}")
        as_of = ctx["created_date"]  # T0 -- identical to the sequential path
        for dt in decision_types:
            if dt == "incident_relationship":
                for state, incident_id, meta in decisions_mod.build_incident_inputs(session, case_id, as_of):
                    q = questions.build_question(dt, None)
                    rec = decisions_mod._call_one(jev_client, case_id, dt, state, q, None, meta, as_of, context_version)
                    rec["incident_id"] = incident_id
                    jev_records.append(rec)
                    if run_llm:
                        lrec = llm_baseline.run_llm_decision(dt, case_id, state, q, None, meta, as_of, context_version)
                        lrec["incident_id"] = incident_id
                        llm_records.append(lrec)
                continue
            state, cands, cmeta = decisions_mod.build_inputs(session, case_id, dt, as_of, context_version, candidate_versions, causal_key_mode)
            q_jev = questions.build_question(dt, candidates_mod.model_facing_candidates(cands, cmeta))
            jev_records.append(decisions_mod._call_one(jev_client, case_id, dt, state, q_jev, cands, cmeta, as_of, context_version))
            if run_llm:
                llm_records.append(llm_baseline.run_llm_decision(dt, case_id, state, questions.build_question(dt, cands), cands, cmeta, as_of, context_version))
    return jev_records, llm_records


def _worker(driver, case_id, *args):
    last = None
    for attempt in range(1, CASE_ATTEMPTS + 1):
        try:
            return case_id, _process_case(driver, case_id, *args), None
        except Exception as e:  # transient Neo4j/network problems: retry the whole case in a fresh session
            last = f"{type(e).__name__}: {str(e)[:300]}"
            time.sleep(2.0 * attempt)
    return case_id, None, last


def _load_checkpoint(path: Path) -> dict:
    done = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    done[row["case_id"]] = row
    return done


def run(case_ids, decision_types, context_version, candidate_versions, causal_key_mode, jev_client, run_llm,
        workers=8, checkpoint_name=None, resume=False, progress_every=25):
    """Returns (jev_scored_records, llm_scored_records, failed_case_ids) in case order."""
    checkpoint_path = None
    done = {}
    if checkpoint_name:
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        checkpoint_path = CHECKPOINT_DIR / f"{checkpoint_name}.jsonl"
        if checkpoint_path.exists() and not resume:
            raise SystemExit(f"{checkpoint_path} already exists; pass --resume to continue that run, or choose a new --name")
        done = _load_checkpoint(checkpoint_path) if resume else {}
        done = {cid: row for cid, row in done.items() if cid in set(case_ids)}
        if done:
            print(f"resuming: {len(done)} of {len(case_ids)} cases already complete", flush=True)

    pending = [c for c in case_ids if c not in done]
    failed = []
    started = time.time()
    driver = get_driver()
    ckpt_file = open(checkpoint_path, "a") if checkpoint_path else None
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_worker, driver, cid, decision_types, context_version, candidate_versions, causal_key_mode, jev_client, run_llm) for cid in pending]
            completed = 0
            for fut in as_completed(futures):
                case_id, result, error = fut.result()
                completed += 1
                if error:
                    failed.append((case_id, error))
                    print(f"  FAILED {case_id}: {error}", flush=True)
                else:
                    jev_raw, llm_raw = result
                    # Scoring reads hidden truth, so it happens here (main thread), after the models have answered.
                    row = {"case_id": case_id, "jev": [score_decision(r) for r in jev_raw], "llm": [score_decision(r) for r in llm_raw]}
                    done[case_id] = row
                    if ckpt_file:
                        ckpt_file.write(json.dumps(row, default=str) + "\n")
                        ckpt_file.flush()
                if completed % progress_every == 0 or completed == len(pending):
                    elapsed = time.time() - started
                    eta = elapsed / completed * (len(pending) - completed)
                    print(f"  {len(done)}/{len(case_ids)} cases done ({completed}/{len(pending)} this session, {len(failed)} failed), "
                          f"elapsed {elapsed / 60:.1f} min, eta {eta / 60:.1f} min", flush=True)
    finally:
        driver.close()
        if ckpt_file:
            ckpt_file.close()

    jev_records = [r for cid in case_ids if cid in done for r in done[cid]["jev"]]
    llm_records = [r for cid in case_ids if cid in done for r in done[cid]["llm"]]
    return jev_records, llm_records, [cid for cid, _ in failed]
