"""Run the baseline agent against one case and display the trace + result.

Usage:
    python3 -m agent.agent_v2.run_single --case-id CS00191
"""
import argparse
import json

from agent.graph_v2.db import get_driver
from agent.agent_v2.loop import run_case
from agent.agent_v2.trace import persist_run


def main(case_id: str):
    driver = get_driver()
    driver.verify_connectivity()
    try:
        with driver.session() as session:
            print(f"Investigating {case_id}...")
            result = run_case(case_id, session)
    finally:
        driver.close()

    print(f"\n{'=' * 70}\nTRACE\n{'=' * 70}")
    for s in result["trace_steps"]:
        print(f"\nStep {s['step']}  (as_of={s['sim_clock']}, {s['latency_ms']}ms, status={s['status']}"
              f"{', REDUNDANT' if s.get('redundant') else ''})")
        print(f"  tool: {s['tool_name']}")
        non_meta_args = {k: v for k, v in s["args"].items() if k not in ("hypotheses", "rationale")}
        if non_meta_args:
            print(f"  args: {non_meta_args}")
        print(f"  rationale: {s['rationale']}")
        for h in s["hypotheses"]:
            if isinstance(h, dict):
                print(f"  hypothesis: {h['label']} (conf={h['confidence']}, status={h['status']})")
            else:
                print(f"  hypothesis: {h}")
        if s["tool_name"] != "submit_diagnosis":
            print(f"  result: {json.dumps(s['result_summary'], default=str)[:400]}")

    print(f"\n{'=' * 70}\nFINAL DIAGNOSIS\n{'=' * 70}")
    print(json.dumps(result["final_diagnosis"], indent=2, default=str))

    print(f"\nstop_reason: {result['stop_reason']}")
    print(f"tool calls: {result['num_tool_calls']}   llm calls: {result['num_llm_calls']}")
    print(f"token usage: {result['token_usage']}")
    if result["citation_violations"]:
        print(f"CITATION VIOLATIONS (invented evidence IDs): {result['citation_violations']}")
    else:
        print("citation check: all cited evidence IDs traced to real tool results")

    path = persist_run(result)
    print(f"\nRun persisted to: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()
    main(args.case_id)
