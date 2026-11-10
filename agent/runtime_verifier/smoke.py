"""Phase 9 smoke run: the fixed dev smoke set through the full runtime (agent -> verifier -> policy -> optional second round). Dev cases only.

    python3 -m agent.runtime_verifier.smoke [--skip CS00729 ...] [--workers 4]
"""
import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent.agent_v3 import config as A
from agent.agent_v3.llm import TogetherJSONClient
from agent.runtime_verifier.run import persist, run_verified_case

SMOKE = A.COHORT_DIR / "phase9_smoke_cases.json"


def main(skip=(), workers=4):
    from agent.graph_v2.db import get_driver
    cases = [c["case_id"] for c in json.loads(SMOKE.read_text())["cases"] if c["case_id"] not in skip]
    pool = set(json.loads((A.PROJECT_ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"])
    assert set(cases) <= pool, "smoke cases must be dev cases"
    llm, drv = TogetherJSONClient(os.environ["TOGETHER_API_KEY"]), get_driver()

    def work(cid):
        try:
            with drv.session() as s:
                rec = run_verified_case(cid, s, llm)
            persist(rec)
            return cid, rec, None
        except Exception as e:  # noqa: BLE001 - reported, never hidden
            return cid, None, f"{type(e).__name__}: {str(e)[:200]}"

    done = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for f in as_completed([ex.submit(work, c) for c in cases]):
            cid, rec, err = f.result()
            done[cid] = (rec, err)
            print(f"  {cid}: " + (f"ERROR {err}" if err else f"{rec['policy_decision']} -> {rec['final_policy_decision']} (extra round: {rec['additional_investigation_performed']}, {rec['latency_s']}s)"), flush=True)
    drv.close()
    ok = [r for r, e in done.values() if r]
    print(f"\ncompleted end-to-end: {len(ok)}/{len(cases)}; errors: {[c for c, (r, e) in done.items() if e]}")
    print("first decisions:", dict(Counter(r["policy_decision"] for r in ok)), "| final:", dict(Counter(r["final_policy_decision"] for r in ok)),
          "| additional round:", sum(r["additional_investigation_performed"] for r in ok))
    print(f"total est. cost ${sum(r['cost_usd_estimate'] for r in ok):.3f}; mean latency {sum(r['latency_s'] for r in ok)/max(1,len(ok)):.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", nargs="*", default=[])
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    main(a.skip, a.workers)
