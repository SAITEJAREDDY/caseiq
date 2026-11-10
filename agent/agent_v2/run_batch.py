"""Run the baseline agent across a controlled list of cases, persisting each
run independently.

Usage:
    python3 -m agent.agent_v2.run_batch --case-ids CS00191 CS00002 CS00003
    python3 -m agent.agent_v2.run_batch --n 10
"""
import argparse
import json
import time

from agent.graph_v2.config import DATA_RAW_V2
from agent.graph_v2.db import get_driver, read_csv
from agent.agent_v2.loop import run_case
from agent.agent_v2.trace import persist_run


def _first_n_case_ids(n: int) -> list:
    rows = read_csv(DATA_RAW_V2 / "case_observable.csv")
    return sorted(r["id"] for r in rows)[:n]


def main(case_ids: list):
    driver = get_driver()
    driver.verify_connectivity()
    results = []
    try:
        for case_id in case_ids:
            print(f"\n{'#' * 70}\n# {case_id}\n{'#' * 70}")
            t0 = time.time()
            try:
                with driver.session() as session:
                    result = run_case(case_id, session)
                path = persist_run(result)
                elapsed = time.time() - t0
                fd = result["final_diagnosis"]
                print(f"  stop_reason={result['stop_reason']}  tool_calls={result['num_tool_calls']}  "
                      f"llm_calls={result['num_llm_calls']}  tokens={result['token_usage']['total_tokens']}  "
                      f"elapsed={elapsed:.1f}s")
                print(f"  evidence_sufficiency={fd['evidence_sufficiency']}  "
                      f"overall_confidence={fd['overall_confidence']}  "
                      f"human_review_required={fd['human_review_required']}")
                if result["citation_violations"]:
                    print(f"  CITATION VIOLATIONS: {result['citation_violations']}")
                print(f"  -> {path}")
                results.append({"case_id": case_id, "ok": True, "stop_reason": result["stop_reason"],
                                 "num_tool_calls": result["num_tool_calls"],
                                 "citation_violations": len(result["citation_violations"])})
            except Exception as e:
                print(f"  RUN FAILED: {e}")
                results.append({"case_id": case_id, "ok": False, "error": str(e)})
    finally:
        driver.close()

    print(f"\n{'=' * 70}\nBATCH SUMMARY\n{'=' * 70}")
    print(json.dumps(results, indent=2))
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok_count}/{len(results)} runs completed successfully")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case-ids", nargs="+", help="explicit list of case IDs")
    group.add_argument("--n", type=int, help="first N cases by case id")
    args = parser.parse_args()
    ids = args.case_ids if args.case_ids else _first_n_case_ids(args.n)
    main(ids)
