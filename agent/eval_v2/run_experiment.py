"""Phase 6 experiment CLI (spec section 42): run-and-evaluate or
evaluate-existing, over a locked split / explicit case IDs / the permanent
regression suite. Deliberately does not default to a large case count --
spec section 51's staged sizing (smoke -> engineering -> baseline ->
locked_benchmark) is the caller's responsibility via --kind/--n.

Usage:
    # smoke: run fresh + evaluate 15 dev-split cases
    python3 -m agent.eval_v2.run_experiment --name smoke_v1 --kind smoke \
        --split dev --n 15 --run-mode run_and_evaluate

    # permanent regression suite
    python3 -m agent.eval_v2.run_experiment --name regression_v1 --kind smoke \
        --regression-suite --run-mode run_and_evaluate

    # score whatever is already on disk for explicit case ids, no fresh run
    python3 -m agent.eval_v2.run_experiment --name rescope --kind adhoc \
        --case-ids CS00191 CS00002 --run-mode evaluate_existing

    # locked benchmark (test split) -- requires --kind locked_benchmark
    python3 -m agent.eval_v2.run_experiment --name locked_v1 \
        --kind locked_benchmark --split test --run-mode run_and_evaluate
"""
import argparse
import json

from agent.agent_v2.config import AGENT_RUNS_DIR
from agent.eval_v2.aggregate import build_aggregate
from agent.eval_v2.metrics import evaluate_run
from agent.eval_v2.regression_cases import regression_case_ids
from agent.eval_v2.registry import create_experiment, persist_experiment
from agent.eval_v2.reports import render_report
from agent.eval_v2.splits import case_ids_for_split

_VERSION_KEYS = [
    "model_provider", "model_name", "temperature", "prompt_version", "toolset_version",
    "output_schema_version", "agent_loop_version", "repair_layer_version", "graph_version",
]


def _agent_version_fields_from_runs(runs: list) -> dict:
    """Derives the experiment's agent-version block from what the scored
    runs actually recorded (post Phase-6-fix, this is accurate) rather than
    trusting live config.py, which could drift from what a given run was
    actually generated with. Flags heterogeneity rather than silently
    picking one value when runs don't agree (e.g. an evaluate_existing call
    mixing runs from two different code states)."""
    if not runs:
        return {"homogeneous": None, "note": "no runs scored"}
    distinct = {k: {r.get(k) for r in runs} for k in _VERSION_KEYS}
    homogeneous = all(len(v) <= 1 for v in distinct.values())
    if homogeneous:
        return {**{k: next(iter(v)) if v else None for k, v in distinct.items()}, "homogeneous": True}
    return {"homogeneous": False, "distinct_values": {k: sorted(v, key=str) for k, v in distinct.items()}}


def _run_and_evaluate(case_ids: list) -> list:
    from agent.agent_v2 import trace as agent_trace
    from agent.agent_v2.loop import run_case
    from agent.graph_v2.db import get_driver

    driver = get_driver()
    runs = []
    try:
        with driver.session() as session:
            for cid in case_ids:
                print(f"  running {cid}...", flush=True)
                try:
                    result = run_case(cid, session)
                    path = agent_trace.persist_run(result)
                    with open(path) as f:
                        runs.append(json.load(f))
                    print(f"    stop_reason={result['stop_reason']} tool_calls={result['num_tool_calls']}")
                except Exception as e:
                    print(f"    FAILED: {e}")
    finally:
        driver.close()
    return runs


def _evaluate_existing(case_ids: list, explicit_run_ids=None) -> list:
    if explicit_run_ids:
        paths = [AGENT_RUNS_DIR / f"{rid}.json" for rid in explicit_run_ids]
    else:
        latest_by_case = {}
        with open(AGENT_RUNS_DIR / "runs_index.jsonl") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry["case_id"] in case_ids:
                    latest_by_case[entry["case_id"]] = entry["run_id"]  # later lines are more recent -> overwrite
        missing = set(case_ids) - set(latest_by_case)
        if missing:
            raise ValueError(f"No persisted run found for: {sorted(missing)} -- run with --run-mode run_and_evaluate first")
        paths = [AGENT_RUNS_DIR / f"{rid}.json" for rid in latest_by_case.values()]

    runs = []
    for path in paths:
        with open(path) as f:
            runs.append(json.load(f))
    return runs


def run_experiment(name, kind, case_ids, dataset_split_label, run_mode, explicit_run_ids=None) -> dict:
    print(f"Experiment '{name}' ({kind}): {len(case_ids)} cases, mode={run_mode}")

    if run_mode == "run_and_evaluate":
        runs = _run_and_evaluate(case_ids)
    else:
        runs = _evaluate_existing(case_ids, explicit_run_ids=explicit_run_ids)

    case_records = []
    for run in runs:
        try:
            case_records.append(evaluate_run(run))
        except Exception as e:
            print(f"  scoring FAILED for {run.get('case_id')}: {e}")

    print(f"Scored {len(case_records)}/{len(case_ids)} cases")
    aggregate = build_aggregate(case_records)

    experiment = create_experiment(
        name=name,
        kind=kind,
        dataset_split=dataset_split_label,
        case_ids=case_ids,
        agent_version_fields=_agent_version_fields_from_runs(runs),
        run_mode=run_mode,
        run_ids=[r.get("run_id") for r in runs],
        aggregate=aggregate,
    )
    exp_dir = persist_experiment(experiment, case_records)

    report_md = render_report(experiment)
    with open(exp_dir / "report.md", "w") as f:
        f.write(report_md)

    print(f"\nExperiment persisted to {exp_dir}")
    print(f"experiment_id: {experiment['experiment_id']}")
    return experiment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--kind", choices=["smoke", "engineering", "baseline", "locked_benchmark", "adhoc"], default="adhoc")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--split", choices=["dev", "validation", "test"])
    group.add_argument("--case-ids", nargs="+")
    group.add_argument("--regression-suite", action="store_true")
    parser.add_argument("--n", type=int, help="Limit to first N case ids (after split/regression selection)")
    parser.add_argument("--run-mode", choices=["run_and_evaluate", "evaluate_existing"], required=True)
    parser.add_argument("--run-ids", nargs="+", help="Explicit run ids to score (evaluate_existing mode only)")
    args = parser.parse_args()

    if args.split == "test" and args.kind != "locked_benchmark":
        parser.error("--split test requires --kind locked_benchmark (the locked test set is not for routine experiments)")

    if args.regression_suite:
        case_ids = regression_case_ids()
        dataset_split_label = "regression_suite"
    elif args.split:
        case_ids = case_ids_for_split(args.split)
        dataset_split_label = args.split
    else:
        case_ids = args.case_ids
        dataset_split_label = "explicit_case_ids"

    if args.n:
        case_ids = case_ids[: args.n]

    run_experiment(
        name=args.name, kind=args.kind, case_ids=case_ids, dataset_split_label=dataset_split_label,
        run_mode=args.run_mode, explicit_run_ids=args.run_ids,
    )


if __name__ == "__main__":
    main()
