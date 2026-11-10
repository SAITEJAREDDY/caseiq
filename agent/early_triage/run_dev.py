"""Runs the LLM + Graph + Jev workflow (early Jev triage + the agent + the late verifier) over a FIXED dev case list, for comparison with the stored LLM + Graph baseline.

The case list is every case in the dev `verify100` cohort that already has a stored baseline run (tag `verify100_final`), in sorted order: nothing is chosen by outcome, and the
list is written to `data/early_triage_eval/cases_v1.json` BEFORE any run so it cannot be changed afterwards. Dev cases only; the locked test split is never touched. Records go to
`data/early_triage_eval/runs/` (not the UI's stored-run folder). Resumable: a case with a record is skipped. Infrastructure faults stop or defer cases; they are never scored.

    python3 -m agent.early_triage.run_dev --limit 3      # a few cases first
    python3 -m agent.early_triage.run_dev                # the evaluation set (the first 36 ids of the list, fixed for run time before any result was read)
    python3 -m agent.early_triage.run_dev --all          # every case in the 72-case list (long: several hours of provider time at 4 workers)
"""
import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from agent.agent_v3 import cohorts, evaluate
from agent.agent_v3.config import PROJECT_ROOT
from agent.agent_v3.llm import ProviderCreditError, ProviderUnavailable, TogetherJSONClient
from agent.compare.orchestrator import assert_dev
from agent.runtime_verifier.run import run_verified_case

OUT = PROJECT_ROOT / "data" / "early_triage_eval"
RUNS = OUT / "runs"
CASES_FILE = OUT / "cases_v1.json"
SET_FILE = OUT / "evaluation_set_v1.json"        # the prefix of the list that is evaluated; decided for run time, before any correctness result was read
BASELINE_TAG, COHORT = "verify100_final", "verify100"
WORKERS = 4


def frozen_cases() -> dict:
    """The pre-declared case list. Written once; later calls verify it instead of re-deriving it."""
    if CASES_FILE.exists():
        return json.loads(CASES_FILE.read_text())
    cohort = cohorts.load(COHORT)
    ids = sorted(set(evaluate.latest_runs(BASELINE_TAG)) & set(cohort["case_ids"]))
    OUT.mkdir(parents=True, exist_ok=True)
    spec = {"version": "v1", "created_at": datetime.now(timezone.utc).isoformat(), "split": "dev", "cohort": COHORT, "cohort_sha256": cohort["case_ids_sha256"],
            "baseline_tag": BASELINE_TAG, "n_cases": len(ids), "case_ids": ids, "case_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
            "rule": "every case of the dev verify100 cohort that has a stored LLM + Graph baseline run under the baseline tag, sorted by case id; no outcome was consulted; "
                    "fixed before any early-triage run"}
    CASES_FILE.write_text(json.dumps(spec, indent=1))
    return spec


def evaluation_cases(spec: dict = None) -> list:
    return json.loads(SET_FILE.read_text())["case_ids"] if SET_FILE.exists() else (spec or frozen_cases())["case_ids"]


def done() -> set:
    return {p.stem for p in RUNS.glob("CS*.json")} if RUNS.exists() else set()


def main(limit: int = None, workers: int = WORKERS, everything: bool = False) -> None:
    from agent.graph_v2.db import get_driver

    spec = frozen_cases()
    wanted = spec["case_ids"] if everything else evaluation_cases(spec)
    todo = [c for c in wanted if c not in done()]
    for c in todo:
        assert_dev(c)
    if limit:
        todo = todo[:limit]
    key = os.environ.get("TOGETHER_API_KEY", "")
    if not key:
        raise SystemExit("TOGETHER_API_KEY is not set")
    print(f"{len(wanted)} cases wanted ({spec['n_cases']} in the frozen list, sha {spec['case_ids_sha256'][:12]}); {len(todo)} to run", flush=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    driver, llm, stop = get_driver(), TogetherJSONClient(key), {"credit": False}
    driver.verify_connectivity()

    def work(cid):
        if stop["credit"]:
            return cid, "skipped_credit_stop", None
        last = None
        for attempt in (1, 2, 3):
            try:
                with driver.session() as session:
                    rec = run_verified_case(cid, session, llm, early_triage=True)
                (RUNS / f"{cid}.json").write_text(json.dumps(rec, indent=1, default=str))
                t = rec["early_triage"] or {}
                return cid, "ok", f"triage={t.get('status')}/{(rec['triage_outcome'] or {}).get('outcome')} first={rec['policy_decision']} final={rec['final_policy_decision']} {rec['latency_s']}s"
            except ProviderCreditError as e:
                stop["credit"] = True
                return cid, "credit_exhausted", str(e)[:200]
            except ProviderUnavailable as e:
                last = f"unavailable: {e}"
                time.sleep(5 * attempt)
            except Exception as e:  # a harness bug is surfaced, never scored as the model's failure
                last = f"harness_error {type(e).__name__}: {str(e)[:200]}"
                break
        return cid, "infra_failure", last

    t0 = time.time()
    n_ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(work, c) for c in todo]):
            cid, status, detail = fut.result()
            n_ok += status == "ok"
            print(f"  {cid}: {status} {detail or ''}", flush=True)
    driver.close()
    print(f"done: {n_ok}/{len(todo)} ok in {time.time() - t0:.0f}s; {len(done() & set(wanted))}/{len(wanted)} wanted records in total", flush=True)
    if stop["credit"]:
        raise SystemExit("STOPPED: the provider reported that credits are exhausted (HTTP 402). Add credits and re-run to resume.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--all", action="store_true", help="run the whole 72-case list, not just the evaluation set")
    a = ap.parse_args()
    main(a.limit, a.workers, a.all)
