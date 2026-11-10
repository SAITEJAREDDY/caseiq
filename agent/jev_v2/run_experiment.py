"""Phase 7 experiment CLI (spec sections 50/79's staged progression:
smoke -> engineering -> validation -> locked_benchmark).

Usage:
    # Stage A smoke test: one decision type, a handful of dev cases
    python3 -m agent.jev_v2.run_experiment --name smoke_v1 --kind smoke \
        --split dev --n 20 --decision-types issue_category

    # the permanent regression suite, all six decisions
    python3 -m agent.jev_v2.run_experiment --name regression_v1 --kind smoke \
        --regression-suite

    # root-cause context ablation
    python3 -m agent.jev_v2.run_experiment --name rc_ablation_v3 --kind engineering \
        --split dev --n 50 --decision-types root_cause --context-version v3_technical

    # causal change under a specific candidate-generation version (JEV-013)
    python3 -m agent.jev_v2.run_experiment --name causal_v3 --kind engineering \
        --split dev --n 100 --decision-types causal_change --candidate-version causal_change=v3

    # head-to-head against the LLM primitive baseline, under the frozen Stage B settings
    python3 -m agent.jev_v2.run_experiment --name compare_v1 --kind engineering \
        --split dev --n 100 --compare-llm --frozen-config stage_b_frozen_v1 --pre-freeze

    # the locked test split -- requires --kind locked_benchmark AND the sealed locked configuration; the
    # configuration supplies every setting (no overrides, no subsets), and the holdout is one-shot
    python3 -m agent.jev_v2.run_experiment --name locked_benchmark_run --kind locked_benchmark --split test \
        --compare-llm --frozen-config locked_benchmark_frozen_v1
    # verify every guard and print the plan without loading case ids, calling an API or writing a marker
    python3 -m agent.jev_v2.run_experiment --name locked_benchmark_run --kind locked_benchmark --split test \
        --compare-llm --frozen-config locked_benchmark_frozen_v1 --check-only
"""
import argparse
import json

from agent.eval_v2.splits import case_ids_for_split
from agent.graph_v2.db import get_driver
from agent.jev_v2 import frozen_config, llm_baseline, locked_benchmark, parallel_runner
from agent.jev_v2.aggregate import build_report
from agent.jev_v2.client import JevClient
from agent.jev_v2.config import (
    CANDIDATE_GENERATION_VERSIONS,
    DEFAULT_CONTEXT_VERSION,
    LLM_BASELINE_MAX_TOKENS,
    LLM_BASELINE_MODEL,
    LLM_BASELINE_TEMPERATURE,
    LLM_REPAIR_MAX_ATTEMPTS,
    PRICING_VERSION,
)
from agent.jev_v2.decisions import DECISION_TYPES, run_decision
from agent.jev_v2.reference_data import all_root_causes  # noqa: F401 (ensures reference CSVs load early, surfaces path errors fast)
from agent.jev_v2.registry import create_experiment, persist_experiment
from agent.jev_v2.regression_decisions import regression_case_ids
from agent.jev_v2.reports import render_comparison_table, render_report
from agent.jev_v2.scoring import score_decision


def _run_over_cases(client, case_ids: list, decision_types: list, context_version: str, use_llm: bool,
                    candidate_versions: dict = None, causal_key_mode: str = "canonical") -> list:
    driver = get_driver()
    records = []
    try:
        with driver.session() as session:
            for i, case_id in enumerate(case_ids, start=1):
                from agent.jev_v2.state_builder import get_case_context

                ctx = get_case_context(session, case_id)
                if "error" in ctx:
                    print(f"  skipping {case_id}: {ctx['error']}")
                    continue
                as_of = ctx["created_date"]  # T0: ticket-only investigation point (spec section 4's "decision timestamp")

                for dt in decision_types:
                    if use_llm:
                        raw_records = llm_baseline.run_llm_decisions(session, case_id, dt, as_of, context_version, candidate_versions, causal_key_mode)
                    else:
                        raw_records = run_decision(client, session, case_id, dt, as_of, context_version, candidate_versions, causal_key_mode)
                    for raw in raw_records:
                        records.append(score_decision(raw))
                if i % 10 == 0 or i == len(case_ids):
                    print(f"  [{'llm' if use_llm else 'jev'}] {i}/{len(case_ids)} cases, {len(records)} decisions", flush=True)
    finally:
        driver.close()
    return records


def _effective_candidate_versions(decision_types: list, overrides: dict) -> dict:
    merged = {**CANDIDATE_GENERATION_VERSIONS, **(overrides or {})}
    return {dt: merged[dt] for dt in decision_types}


def _sha256_of(path) -> str:
    import hashlib

    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_experiment(name, kind, case_ids, split_label, decision_types, context_version, compare_llm, baseline_experiment_id=None,
                   candidate_versions=None, causal_key_mode="canonical", jev_model=None, frozen=None,
                   workers=1, resume=False, protocol=None) -> dict:
    versions = _effective_candidate_versions(decision_types, candidate_versions)
    print(f"Experiment '{name}' ({kind}): {len(case_ids)} cases, decisions={decision_types}, context={context_version}, candidates={versions}, causal_key_mode={causal_key_mode}")

    jev_client = JevClient(model=jev_model)
    common = {
        "context_version": context_version, "candidate_generation_versions": versions, "causal_key_mode": causal_key_mode,
        "jev_model_requested": jev_client.model, "frozen_config": frozen, "pricing_version": PRICING_VERSION,
        "orchestration": {"runner": "parallel_v1" if workers > 1 else "sequential", "workers": workers},
        "case_ids_sha256": frozen_config.sha256_json(case_ids),
    }
    if protocol:
        common["pre_registered_protocol"] = {"path": str(protocol), "sha256": _sha256_of(protocol)}

    llm_records = None
    if workers > 1:
        # Inputs are built once per decision and sent to both systems (see parallel_runner).
        jev_records, llm_records, failed = parallel_runner.run(
            case_ids, decision_types, context_version, candidate_versions, causal_key_mode, jev_client, compare_llm,
            workers=workers, checkpoint_name=name, resume=resume)
        if failed:
            raise SystemExit(f"{len(failed)} case(s) failed after retries: {failed[:10]}. Nothing was persisted; re-run with --resume to retry only those cases.")
        common["orchestration"]["failed_cases"] = []
    else:
        jev_records = _run_over_cases(jev_client, case_ids, decision_types, context_version, False, candidate_versions, causal_key_mode)
    print(f"Jev: scored {len(jev_records)} decisions")

    if not compare_llm:
        jev_report = build_report(jev_records)
        experiment = create_experiment(
            name, kind, "jev_primitive", decision_types, case_ids, split_label,
            {**common, "comparison_baseline_experiment_id": baseline_experiment_id}, jev_report,
        )
        exp_dir = persist_experiment(experiment, jev_records)
        with open(exp_dir / "report.md", "w") as f:
            f.write(render_report(experiment))
        print(f"\nExperiment persisted to {exp_dir}\nexperiment_id: {experiment['experiment_id']}")
        return experiment

    # --compare-llm: also run the LLM baseline over the same cases, persist as two experiments plus a paired comparison
    if llm_records is None:
        llm_records = _run_over_cases(None, case_ids, decision_types, context_version, True, candidate_versions, causal_key_mode)
    print(f"LLM baseline: scored {len(llm_records)} decisions")

    jev_report = build_report(jev_records)
    llm_report = build_report(llm_records)

    jev_experiment = create_experiment(f"{name}_jev", kind, "jev_primitive", decision_types, case_ids, split_label, common, jev_report)
    jev_dir = persist_experiment(jev_experiment, jev_records)
    with open(jev_dir / "report.md", "w") as f:
        f.write(render_report(jev_experiment))

    llm_config = {
        **common, "llm_model": LLM_BASELINE_MODEL, "llm_temperature": LLM_BASELINE_TEMPERATURE, "llm_max_tokens": LLM_BASELINE_MAX_TOKENS,
        "llm_repair_max_attempts": LLM_REPAIR_MAX_ATTEMPTS, "paired_jev_experiment_id": jev_experiment["experiment_id"],
    }
    llm_experiment = create_experiment(f"{name}_llm", kind, "llm_primitive_baseline", decision_types, case_ids, split_label, llm_config, llm_report)
    llm_dir = persist_experiment(llm_experiment, llm_records)
    with open(llm_dir / "report.md", "w") as f:
        f.write(render_report(llm_experiment))

    with open(jev_dir / "comparison_vs_llm.md", "w") as f:
        f.write(render_comparison_table(jev_report, llm_report))

    from agent.jev_v2.compare_jev_llm import write_comparison

    paths = write_comparison(jev_experiment, jev_records, llm_experiment, llm_records, jev_dir)
    print(f"\nJev experiment: {jev_dir}\nLLM experiment: {llm_dir}\nPaired comparison: {paths['markdown']}")
    return {"jev": jev_experiment, "llm": llm_experiment}


def _parse_candidate_versions(pairs: list) -> dict:
    out = {}
    for pair in pairs or []:
        decision, _, version = pair.partition("=")
        if decision not in DECISION_TYPES or not version:
            raise SystemExit(f"--candidate-version expects DECISION=VERSION with a known decision type, got {pair!r}")
        out[decision] = version
    return out


def _locked_preflight(parser, args, cfg) -> None:
    """Every check a locked run must pass before anything is loaded or called. Exits on the first violation."""
    if cfg is None:
        parser.error("--split test / --kind locked_benchmark require --frozen-config locked_benchmark_frozen_v1 (the sealed locked-benchmark "
                     "configuration); the locked test set is not for routine experiments")
    if args.split != "test" or args.kind != "locked_benchmark":
        parser.error("the locked-benchmark configuration is used only with --split test --kind locked_benchmark")
    if not args.compare_llm:
        parser.error("the locked benchmark runs Jev and the LLM baseline together; pass --compare-llm")
    if args.name != cfg["run"]["name"]:
        parser.error(f"the locked run's name is fixed by the configuration: --name {cfg['run']['name']}")
    overrides = [flag for flag, value in (("--n", args.n), ("--decision-types", args.decision_types), ("--context-version", args.context_version),
                                          ("--candidate-version", args.candidate_version), ("--causal-key-mode", args.causal_key_mode),
                                          ("--jev-model", args.jev_model), ("--baseline-experiment-id", args.baseline_experiment_id),
                                          ("--protocol", args.protocol), ("--workers", args.workers), ("--pre-freeze", args.pre_freeze)) if value]
    if overrides:
        parser.error(f"the locked configuration supplies every setting and runs the whole split; remove {', '.join(overrides)}")
    problems = locked_benchmark.verify(args.frozen_config) + locked_benchmark.verify_environment()
    if problems:
        parser.error("the locked configuration does not match the working tree:\n  - " + "\n  - ".join(problems))
    locked_benchmark.check_run_allowed(args.name, args.resume, frozen_config.sha256_file(frozen_config.config_path(args.frozen_config)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--kind", choices=["smoke", "engineering", "validation", "locked_benchmark", "adhoc"], default="adhoc")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--split", choices=["dev", "validation", "test"])
    group.add_argument("--case-ids", nargs="+")
    group.add_argument("--regression-suite", action="store_true")
    parser.add_argument("--n", type=int, help="Limit to first N case ids (after split/regression selection)")
    parser.add_argument("--decision-types", nargs="+", choices=DECISION_TYPES, default=None)
    parser.add_argument("--context-version", default=None, help="Only affects root_cause; ignored by other decision types")
    parser.add_argument("--compare-llm", action="store_true", help="Also run the LLM primitive baseline over the same cases")
    parser.add_argument("--baseline-experiment-id", help="Optional immutable experiment to link as a controlled comparison baseline")
    parser.add_argument("--candidate-version", action="append", metavar="DECISION=VERSION",
                        help="Override a decision's candidate-generation version (only causal_change has more than one: v2, v3)")
    parser.add_argument("--causal-key-mode", choices=["canonical", "opaque"], default=None,
                        help="opaque = diagnostic control that replaces change ids with id-free option aliases (v3 only)")
    parser.add_argument("--jev-model", default=None, help="Explicit Jev model id (default: JEV_MODEL env / jev-latest alias)")
    parser.add_argument("--frozen-config", metavar="NAME", help="Take every version from data/eval/jev/NAME.json and refuse to run if code/data drifted from its manifest")
    parser.add_argument("--workers", type=int, default=None, help="Concurrent cases (parallel_runner). >1 also checkpoints every finished case under data/eval/jev/checkpoints/")
    parser.add_argument("--resume", action="store_true", help="With --workers: continue an interrupted run of the same --name from its checkpoint")
    parser.add_argument("--protocol", metavar="PATH", help="Pre-registered analysis protocol document; its sha256 is recorded on the experiment")
    parser.add_argument("--check-only", action="store_true", help="Run every pre-run guard, print the plan and exit: loads no case ids, calls no API, writes no marker")
    parser.add_argument("--pre-freeze", action="store_true", help="With --frozen-config: check versions only (no manifest yet). Recorded on the experiment; Stage C never uses it.")
    args = parser.parse_args()

    if args.split == "test" and args.kind != "locked_benchmark":
        parser.error("--split test requires --kind locked_benchmark (the locked test set is not for routine experiments)")
    if args.split == "validation" and args.kind != "validation":
        parser.error("--split validation requires --kind validation (Stage C is an explicit checkpoint)")

    locked_cfg = None
    if args.frozen_config:
        loaded = frozen_config.load(args.frozen_config)
        locked_cfg = loaded if locked_benchmark.is_locked_config(loaded) else None
    if args.split == "test" or args.kind == "locked_benchmark" or locked_cfg is not None:
        _locked_preflight(parser, args, locked_cfg)

    frozen = None
    workers, protocol = args.workers or 1, args.protocol
    context_version = args.context_version or DEFAULT_CONTEXT_VERSION
    candidate_versions = _parse_candidate_versions(args.candidate_version)
    causal_key_mode = args.causal_key_mode or "canonical"
    jev_model = args.jev_model
    decision_types = args.decision_types or DECISION_TYPES

    if locked_cfg is not None:
        settings = locked_benchmark.run_settings(locked_cfg)
        context_version, candidate_versions = settings["context_version"], settings["candidate_versions"]
        causal_key_mode, jev_model, decision_types = settings["causal_key_mode"], settings["jev_model"], settings["decision_types"]
        workers, protocol = settings["workers"], settings["protocol"]
        frozen = {"name": args.frozen_config, "config_sha256": frozen_config.sha256_file(frozen_config.config_path(args.frozen_config)),
                  "manifest_sha256": frozen_config.sha256_file(locked_benchmark.manifest_path(args.frozen_config)),
                  "status": "verified_against_manifest", "locked_benchmark": True}
    elif args.frozen_config:
        overrides = [flag for flag, value in (("--context-version", args.context_version), ("--candidate-version", args.candidate_version),
                                              ("--causal-key-mode", args.causal_key_mode), ("--jev-model", args.jev_model)) if value]
        if overrides:
            parser.error(f"--frozen-config supplies every version; remove {', '.join(overrides)}")
        cfg = frozen_config.load(args.frozen_config)
        problems = frozen_config.verify_versions(cfg) if args.pre_freeze else frozen_config.verify(args.frozen_config)
        if problems:
            parser.error("frozen configuration does not match the working tree:\n  - " + "\n  - ".join(problems))
        settings = frozen_config.run_settings(cfg)
        context_version, candidate_versions = settings["context_version"], settings["candidate_versions"]
        causal_key_mode, jev_model = settings["causal_key_mode"], settings["jev_model"]
        decision_types = args.decision_types or settings["decision_types"]
        frozen = {"name": args.frozen_config, "config_sha256": frozen_config.sha256_file(frozen_config.config_path(args.frozen_config)),
                  "status": "pre_freeze_versions_only" if args.pre_freeze else "verified_against_manifest"}
        if args.pre_freeze:
            print("WARNING: --pre-freeze checks versions only; this run is not a Stage C-valid frozen run.")

    if args.check_only:
        print(f"Pre-run guards passed for '{args.name}' (kind={args.kind}, split={args.split or 'explicit ids'}); nothing was loaded, called or written.")
        print(f"  decisions={decision_types}, context={context_version}, candidates={candidate_versions}, causal_key_mode={causal_key_mode}, jev_model={jev_model}, workers={workers}")
        if frozen:
            print(f"  frozen config {frozen['name']} sha256={frozen['config_sha256']}")
        if locked_cfg is not None:
            print(f"  would run the whole locked split ({settings['expected_case_count']} cases per the split manifest) with protocol {protocol}")
        return

    if args.regression_suite:
        case_ids = regression_case_ids()
        split_label = "regression_suite"
        locked_benchmark.assert_not_locked_ids(case_ids)
    elif args.split:
        case_ids = case_ids_for_split(args.split)
        split_label = args.split
    else:
        case_ids = args.case_ids
        split_label = "explicit_case_ids"
        locked_benchmark.assert_not_locked_ids(case_ids)

    if args.n:
        case_ids = case_ids[: args.n]

    if args.baseline_experiment_id:
        from agent.jev_v2.registry import load_experiment

        baseline = load_experiment(args.baseline_experiment_id)
        if baseline.get("case_ids") != case_ids:
            parser.error("--baseline-experiment-id must contain exactly the same ordered case IDs as this experiment")
        if baseline.get("dataset_split") != split_label:
            parser.error("--baseline-experiment-id must use the same split label")

    if locked_cfg is not None:
        locked_benchmark.assert_case_ids(case_ids, locked_cfg)
        driver = get_driver()
        try:
            graph_problems = locked_benchmark.check_graph_counts(driver, locked_cfg)
        finally:
            driver.close()
        if graph_problems:
            parser.error("the runtime graph is not the frozen one:\n  - " + "\n  - ".join(graph_problems))
        locked_benchmark.record_run_start(args.name, frozen["config_sha256"], frozen["manifest_sha256"], args.resume)

    result = run_experiment(args.name, args.kind, case_ids, split_label, decision_types, context_version, args.compare_llm, args.baseline_experiment_id,
                            candidate_versions, causal_key_mode, jev_model, frozen, workers, args.resume, protocol)
    if locked_cfg is not None:
        locked_benchmark.record_run_complete({"jev": result["jev"]["experiment_id"], "llm": result["llm"]["experiment_id"]})


if __name__ == "__main__":
    main()
