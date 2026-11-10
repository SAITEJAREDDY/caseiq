"""Run one or more architectures on dev cases from the command line (results are stored and reopen instantly in the UI).

    python3 -m agent.compare.cli CS00729 --modes llm_only                    # cheap: one direct model call per case
    python3 -m agent.compare.cli --smoke --modes llm_only                    # the 16 Phase 9 dev smoke cases
    python3 -m agent.compare.cli CS00009 --modes llm_only llm_graph llm_graph_jev   # all three, in parallel (about $0.06, a few minutes)
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor

from agent.agent_v3.config import COHORT_DIR
from agent.agent_v3.llm import TogetherJSONClient
from agent.compare import orchestrator
from agent.compare.models import MODES, NAMES


def main(cases, modes, workers=4):
    from agent.graph_v2.db import get_driver
    llm, drv = TogetherJSONClient(os.environ["TOGETHER_API_KEY"]), get_driver()

    def one(cid):
        res = orchestrator.run_modes(modes, cid, session_factory=drv.session, llm=llm)
        return cid, res

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for cid, res in ex.map(one, cases):
            parts = []
            for m in modes:
                r = res[m]
                parts.append(f"{NAMES[m]}: " + (f"ERROR {type(r).__name__}: {str(r)[:80]}" if isinstance(r, Exception) else f"{r.status}, root cause {r.root_cause or 'ABSTAIN'}, {r.latency_seconds:.0f}s, ${r.estimated_cost:.3f}"))
            print(cid, " | ".join(parts), flush=True)
    drv.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--modes", nargs="+", default=["llm_only"], choices=list(MODES))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cases = a.cases or ([c["case_id"] for c in json.loads((COHORT_DIR / "phase9_smoke_cases.json").read_text())["cases"]] if a.smoke else [])
    if not cases:
        raise SystemExit("give case ids or --smoke")
    main(cases, a.modes, a.workers)
