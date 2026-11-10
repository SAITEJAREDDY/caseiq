"""Runs the Phase 9A agent over a fixed dev cohort. Dev-only by construction: only cohort files written by cohorts.py (split == dev, integrity-checked)
can be run; there is no --case-ids escape hatch.

    python3 -m agent.agent_v3.run_batch --cohort iter50 --tag iter50_a            # runs every case not already persisted under this tag
    python3 -m agent.agent_v3.run_batch --cohort iter50 --tag iter50_a --limit 3   # a few cases only

Infrastructure faults (credits exhausted, provider outage) stop or defer cases; they are never recorded as contract failures.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.agent_v3 import cohorts
from agent.agent_v3.backend import Neo4jBackend
from agent.agent_v3.config import COHORT_DIR, RUNS_DIR
from agent.agent_v3.llm import ProviderCreditError, ProviderUnavailable, TogetherJSONClient
from agent.agent_v3.loop import run_case
from agent.agent_v3.trace import persist_run

WORKERS = 4


def _api_key() -> str:
    import os
    key = os.environ.get("TOGETHER_API_KEY", "")
    if not key:
        raise SystemExit("TOGETHER_API_KEY is not set")
    return key


def done_cases(tag: str) -> dict:
    """case_id -> run_id for runs already persisted under this tag (latest wins)."""
    idx, out = RUNS_DIR / "runs_index.jsonl", {}
    if idx.exists():
        for line in idx.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                if e["run_tag"] == tag:
                    out[e["case_id"]] = e["run_id"]
    return out


def main(cohort_name: str, tag: str, limit: int = None, workers: int = WORKERS) -> dict:
    from agent.graph_v2.db import get_driver

    cohort = cohorts.load(cohort_name)
    todo = [c for c in cohort["case_ids"] if c not in done_cases(tag)]
    if limit:
        todo = todo[:limit]
    print(f"cohort {cohort_name} ({cohort['n_cases']} cases, sha {cohort['case_ids_sha256'][:12]}): {len(todo)} to run under tag {tag!r}", flush=True)
    driver = get_driver()
    driver.verify_connectivity()
    llm = TogetherJSONClient(_api_key())
    log = {"tag": tag, "cohort": cohort_name, "cohort_sha256": cohort["case_ids_sha256"], "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "cases": {}}
    stop = {"credit": False}

    def work(cid):
        if stop["credit"]:
            return cid, "skipped_credit_stop", None
        last = None
        for attempt in (1, 2, 3):
            try:
                with driver.session() as session:
                    result = run_case(cid, Neo4jBackend(session, cid), llm)
                path = persist_run(result, tag)
                return cid, "ok", path.stem
            except ProviderCreditError as e:
                stop["credit"] = True
                return cid, "credit_exhausted", str(e)[:200]
            except ProviderUnavailable as e:
                last = f"unavailable: {e}"
                time.sleep(5 * attempt)
            except Exception as e:  # a harness bug is surfaced, never counted as the model's contract failure
                last = f"harness_error {type(e).__name__}: {e}"
                break
        return cid, "infra_failure", last

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed([ex.submit(work, c) for c in todo]):
            cid, status, detail = fut.result()
            log["cases"][cid] = {"status": status, "detail": detail}
            print(f"  {cid}: {status} {detail if status != 'ok' else ''}", flush=True)
    driver.close()
    log["elapsed_s"] = round(time.time() - t0, 1)
    log["n_ok"] = sum(1 for v in log["cases"].values() if v["status"] == "ok")
    COHORT_DIR.mkdir(parents=True, exist_ok=True)
    (COHORT_DIR / f"batch_{tag}_{int(t0)}.json").write_text(json.dumps(log, indent=1))
    print(f"done: {log['n_ok']}/{len(todo)} ok in {log['elapsed_s']}s", flush=True)
    if stop["credit"]:
        raise SystemExit("STOPPED: the provider reported that credits are exhausted (HTTP 402). Add credits and re-run the same command to resume.")
    return log


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", required=True, choices=list(cohorts.QUOTAS))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    main(a.cohort, a.tag, a.limit, a.workers)
