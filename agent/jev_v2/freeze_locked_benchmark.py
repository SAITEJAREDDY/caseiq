"""Builds and seals the locked-benchmark configuration.

Two separate, deliberate steps (so the configuration can be reviewed before it
becomes immutable):

    python3 -m agent.jev_v2.freeze_locked_benchmark --build-config
    python3 -m agent.jev_v2.freeze_locked_benchmark --seal

--build-config derives locked_benchmark_frozen_v1.json from the Stage B freeze,
the Stage C selection decisions recorded below, and the thresholds that
`threshold_policy_v1` selects on VALIDATION decisions. It refuses to overwrite
an existing file. --seal writes the manifest of sha256 pins and then runs the
full verification; it refuses to run twice. A sealed freeze is immutable: a
change needs a new freeze version.

Neither step reads any test-case id or record. The split is pinned by hashing
its files, and its size is read from the split manifest's own counts.
"""
import argparse
import json
from datetime import datetime, timezone
from importlib import metadata

from agent.eval_v2.registry import dataset_checksum_digest
from agent.jev_v2 import frozen_config, locked_benchmark, threshold_policy
from agent.jev_v2 import config as jev_config
from agent.jev_v2.locked_benchmark import NAME, PROJECT_ROOT
from agent.jev_v2.registry import load_decisions, load_experiment

STAGE_C_JEV = "exp_stage_c_validation_jev_20260923T184036Z_fa984004"
STAGE_C_LLM = "exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a"
RUN_NAME = "locked_benchmark_run"
COMMAND = f"python3 -m agent.jev_v2.run_experiment --name {RUN_NAME} --kind locked_benchmark --split test --compare-llm --frozen-config {NAME}"

COMMON_SECONDARY = ["candidate_recall", "candidate_count_distribution", "macro_f1", "per_class_precision_recall", "false_confident_rate", "brier", "ece",
                    "reliability_buckets", "automation_grid", "target_error_coverage", "frozen_thresholds", "difficulty_archetype_slices",
                    "evidence_sufficiency_slices", "candidate_size_bins", "failure_categories", "jev_vs_llm_paired_test", "latency_p50_p90_p95", "cost_per_decision_and_per_1000",
                    "contract_failures"]

# Stage C selection decisions. Inclusion in the locked test and runtime candidacy are separate decisions.
SELECTION = {
    "causal_change": {
        "include_in_locked_test": True, "stage_c_class": "candidate_for_locked_benchmark",
        "runtime_status": "runtime_candidate_conditional: conditional on the locked result; two qualifiers travel with it (JEV-028: 41% of decisions are trivially determined by candidate generation; JEV-025: the change-id artifact is unresolved on validation)",
        "reason": "The only primitive to clear the pre-registered Stage C rubric: 89.3% [87.2, 91.6] against a 71.3% evidence-blind rule, stable against dev, 0.4% false-confident, candidate recall 100%.",
        "primary_metric": "accuracy",
        "co_primary_metrics": ["accuracy_nontrivial", "detection_rate", "no_change_false_positive_rate"],
        "secondary_metrics": ["conditional_accuracy", "recency_groups_A_to_E", "distractor_selection_rate", "change_id_artifact_descriptive"] + COMMON_SECONDARY,
    },
    "issue_category": {
        "include_in_locked_test": True, "stage_c_class": "supporting_only",
        "runtime_status": "supporting_signal: stable and calibrated, with a validation automation region; the LLM ties it on accuracy, so its value is cost, latency and calibrated deferral",
        "reason": "Generalization confirmed on validation (73.0% to 78.4%, ECE 0.030), cheap to measure, and a frozen automation threshold exists that has not yet been tested on unseen data.",
        "primary_metric": "accuracy",
        "co_primary_metrics": [],
        "secondary_metrics": COMMON_SECONDARY,
    },
    "root_cause": {
        "include_in_locked_test": True, "stage_c_class": "supporting_only",
        "runtime_status": "supporting_only: degraded from dev (48.0% to 37.2%) and abstains with RC40 on 40% of decisions; usable only with human review",
        "reason": "Scientific completeness, not a deployment claim: it re-tests once on unseen data whether the Jev lead over the LLM (+16.5 points on validation) holds, and whether the dev-to-validation drop repeats.",
        "primary_metric": "accuracy",
        "co_primary_metrics": ["conditional_accuracy", "committed_accuracy_excluding_RC40"],
        "secondary_metrics": ["rc40_abstention_share", "root_cause_by_evidence_quality"] + COMMON_SECONDARY,
    },
    "owning_team": {
        "include_in_locked_test": True, "stage_c_class": "supporting_only",
        "runtime_status": "supporting_only: generalizes and is far ahead of the LLM, but 37.6% primary accuracy and 5.3% false-confident; a routing suggestion with human confirmation at most",
        "reason": "Scientific completeness: candidate coverage (99.7% to 99.9%) and the Jev lead over the LLM (+23.1 points) generalized on validation and are re-tested once on unseen data.",
        "primary_metric": "acceptable_accuracy",
        "co_primary_metrics": ["primary_accuracy"],
        "secondary_metrics": ["conditional_primary_accuracy", "conditional_acceptable_accuracy", "primary_candidate_recall", "acceptable_candidate_recall", "high_confidence_routing_errors"] + COMMON_SECONDARY,
    },
    "evidence_sufficiency": {
        "include_in_locked_test": False, "stage_c_class": "weak_deprioritize",
        "runtime_status": "deprioritize",
        "reason": "12.4% against a 92.9% majority baseline on validation (the LLM, 41.9%, is also below it). Excluded so the untouched test data stay available to any redesigned version; another measurement of this version would add little.",
        "primary_metric": "macro_f1", "co_primary_metrics": [], "secondary_metrics": [],
    },
    "incident_relationship": {
        "include_in_locked_test": False, "stage_c_class": "weak_deprioritize",
        "runtime_status": "deprioritize (borderline insufficient evidence: the sample is interpretable but cannot separate Jev from the baseline)",
        "reason": "82.6% against a 78.0% 'never related' baseline (lower bound below it); Jev found 8 of 29 related incidents. Excluded to preserve untouched data for a redesign that supplies more true-related incidents.",
        "primary_metric": "balanced_accuracy", "co_primary_metrics": [], "secondary_metrics": [],
    },
}


def _population_definition(dt: str) -> str:
    if dt == "causal_change":
        return "decisions that offered at least one real change (decisions offering only `none` are resolved by candidate generation and excluded)"
    return "every decision of the primitive"


def build_config() -> dict:
    stage_b = frozen_config.load(locked_benchmark.STAGE_B_NAME)
    stage_c_jev = load_experiment(STAGE_C_JEV)
    validation_decisions = load_decisions(STAGE_C_JEV)

    decisions = {}
    for dt, base in stage_b["decisions"].items():
        entry = {**base, **SELECTION[dt]}
        if entry["include_in_locked_test"]:
            selection = threshold_policy.select([r for r in validation_decisions if r["decision_type"] == dt], dt)
            entry["threshold_selection"] = {"policy_version": threshold_policy.POLICY_VERSION, "selected_on": "validation (Stage C Jev experiment)",
                                            "population_definition": _population_definition(dt), "population_n": selection["population"],
                                            "tiers": selection["tiers"], "validation_grid_table": selection["grid_table"]}
        decisions[dt] = entry

    return {
        "phase": 7, "stage": locked_benchmark.STAGE, "freeze_version": NAME,
        "description": "The exact configuration of the one-shot locked-test benchmark. Every setting is explicit; nothing is 'auto', 'latest' or free. Derived from stage_b_frozen_v1 plus the Stage C selection "
                       "decisions. Sealed by a manifest of sha256 pins; run_experiment refuses to run on any drift, and the holdout is one-shot (locked_benchmark_run_state.json).",
        "derived_from": {"freeze_version": stage_b["freeze_version"], "config_sha256": frozen_config.sha256_file(frozen_config.config_path(locked_benchmark.STAGE_B_NAME))},
        "stage_c": {"protocol": "docs/JEV_STAGE_C_PROTOCOL.md", "jev_experiment": STAGE_C_JEV, "llm_experiment": STAGE_C_LLM,
                    "validation_case_ids_sha256": stage_c_jev["config"]["case_ids_sha256"], "note": "Stage C results are immutable inputs to this freeze; nothing here re-derives or edits them."},
        "split": {"split": "test", "split_version": stage_b["split_version"], "cases": "the whole locked test split, every case, in stored (sorted case id) order; no subset",
                  "expected_case_count": json.loads(locked_benchmark.SPLIT_MANIFEST.read_text())["overall_counts"]["test"],
                  "case_count_source": "data/eval/splits/split_manifest_v1.json overall_counts.test (pre-existing manifest metadata; no test id is read to freeze)",
                  "split_file": "data/eval/splits/case_splits_v1.json", "split_manifest": "data/eval/splits/split_manifest_v1.json",
                  "decision_time": stage_b["cohort"]["decision_time"]},
        "graph": {"nodes": 116868, "relationships": 325539, "note": "checked live before the run starts"},
        "decisions": decisions,
        "context_version_note": stage_b["context_version_note"],
        "jev": stage_b["jev"], "llm_baseline": stage_b["llm_baseline"],
        "evaluator_version": stage_b["evaluator_version"], "question_set_version": stage_b["question_set_version"],
        "candidate_strategy_bundle": stage_b["candidate_strategy_bundle"], "pricing_version": stage_b["pricing_version"],
        "confidence": {"jev": "the API `confidence` field as delivered (JEV-032: not the probability of the chosen option)",
                       "llm": "the self-reported confidence the model writes (a coarse number with few distinct values)",
                       "comparability": "not comparable across systems; calibration is reported per system and never ranked against the other",
                       "false_confident_threshold": jev_config.FALSE_CONFIDENT_THRESHOLD, "confidence_buckets": [list(b) for b in jev_config.CONFIDENCE_BUCKETS]},
        "orchestration": {"runner": "parallel_v1", "workers": 8, "case_attempts": 3,
                          "note": "Workers change scheduling, not inputs: each decision's input is built once and sent to both systems. Latencies are therefore measured under 8-way concurrency, as in Stage C."},
        "run": {"name": RUN_NAME, "command": COMMAND, "compare_llm": True,
                "resume": "only of the same run name under the same configuration, and only to complete cases that did not finish; completed cases are never re-sent"},
        "statistics": {
            "bootstrap": {"resamples": jev_config.BOOTSTRAP_RESAMPLES, "seed": jev_config.BOOTSTRAP_SEED, "method": "Phase 6 percentile bootstrap (agent.eval_v2.aggregate._bootstrap_ci)"},
            "proportion_ci": "Wilson 95%", "difference_vs_validation": "Newcombe hybrid-score 95% interval for two independent proportions (locked minus validation)",
            "ratio_vs_validation": "seeded parametric bootstrap of locked/validation",
            "jev_vs_llm": "paired by (case, decision, incident) on identical inputs verified by hash; exact two-sided McNemar test; paired bootstrap 95% interval of the accuracy difference",
            "reading_labels": "material degradation / plausible sampling variation / improvement / insufficient sample (either side under 30); no fixed percentage threshold; interval-based only",
            "multiplicity": "no adjustment; p-values are reported unadjusted and marginal values are not interpreted",
            "reference": "Stage C validation experiments (not dev)"},
        "analysis": {
            "reference": {"split": "validation", "jev_experiment": STAGE_C_JEV, "llm_experiment": STAGE_C_LLM},
            "slice_dimensions": {"difficulty_archetype": ["clear", "customer_misdiagnosis", "dependency_root_cause", "multi_component_symptoms", "vague", "wrong_product_mentioned"],
                                 "evidence_sufficiency": ["sufficient", "partially_sufficient", "insufficient"]},
            "slice_rules": "a slice under 30 decisions is marked small; a slice is flagged 'confidence does not track accuracy' when it has >= 30 decisions and (mean confidence - accuracy) exceeds the overall value by >= 0.10",
            "candidate_size_bins": "each distinct size when there are six or fewer distinct sizes, otherwise terciles of the locked distribution; empty bins are dropped",
            "causal_recency_groups": {"A": "true change is the newest candidate", "B": "true change is visible and strictly older than another candidate (ties count as A)", "C": "no causal change", "D": "two or more real candidates offered (cuts across A/B/C)", "E": "true change not offered"},
            "automation_grid": jev_config.AUTOMATION_THRESHOLDS, "target_error_rates": jev_config.TARGET_ERROR_RATES,
            "failure_categories": "invalid output or API error; candidate missing; wrong at confidence >= 0.90; wrong at lower confidence; correct at confidence < 0.50; correct otherwise (+ causal, incident, sufficiency sub-categories as in Stage C)",
            "capability_rubric": {"T1": "lower 95% bound of accuracy above the best evidence-blind rule", "T2": "no material degradation against validation and candidate recall >= 0.95 (owning team judged on acceptable recall)",
                                  "T3": "accuracy >= 0.85 and false-confident rate <= 0.05", "T4": "at least 100 decisions",
                                  "headline": "owning team is read on PRIMARY-team accuracy, as in Stage C (acceptable accuracy is the pre-registered primary metric of the report, reported alongside)"},
            "exploratory_rule": "any analysis not listed in the protocol is exploratory and must be labelled as such; none may be a headline"},
        "threshold_policy": {"version": threshold_policy.POLICY_VERSION, "grid": jev_config.AUTOMATION_THRESHOLDS, "tiers": threshold_policy.TIERS,
                             "upper_bound_factor": threshold_policy.UPPER_BOUND_FACTOR, "min_automated": threshold_policy.MIN_AUTOMATED,
                             "selected_on": "validation only", "text": "see agent/jev_v2/threshold_policy.py (pinned) and the protocol; thresholds below in each decision's threshold_selection are FIXED and are only evaluated, never re-selected, on the locked run"},
        "cost_accounting": {"tokens": "provider-returned usage summed over every attempt", "jev_price_per_m_input_usd": jev_config.JEV_PRICE_PER_M_INPUT_USD, "jev_price_per_m_output_usd": jev_config.JEV_PRICE_PER_M_OUTPUT_USD,
                            "llm_price_per_m_usd": [jev_config.LLM_PRICE_PER_M_INPUT_USD, jev_config.LLM_PRICE_PER_M_OUTPUT_USD],
                            "llm_price_note": "ASSUMPTION: the Together pricing page lists no separate Turbo row for the Llama 3.3 70B model id; the Llama 3.3 70B serverless price is applied",
                            "reported": "cost per decision and per 1,000 decisions, per decision type", "pricing_version": stage_b["pricing_version"]},
        "latency": {"measure": "client-side wall-clock milliseconds per request as recorded in each decision record", "percentiles": "P50, P90, P95 (nearest-rank, aggregate._percentile)",
                    "conditions": "8-way concurrency, both systems"},
        "protocol": {"path": locked_benchmark.PROTOCOL_REL},
        "one_shot": {"marker": "data/eval/jev/locked_benchmark_run_state.json", "rule": "written before the first call; afterwards only --resume of the same run under the same configuration is accepted; any change to this file or any pinned file invalidates the run as a holdout benchmark"},
        "rationale": {
            "inclusion": "Inclusion in the locked test (measure once on the final holdout) is separate from runtime candidacy. Evidence sufficiency and incident relationship are excluded to keep untouched data for possible redesigns.",
            "causal_key_mode": "canonical, the validated configuration. JEV-025 (change-id artifact) is unresolved on validation; switching to opaque keys would run an unvalidated configuration. If the opaque control on validation shows reliance, a new freeze version (opaque keys) is required before any locked run.",
            "workers": "8, as in Stage C, so latency is measured under the same conditions.",
            "thresholds": "selected on validation by a versioned policy that never relaxes itself; root cause and owning team have none because no grid threshold came near the policy."},
    }


def seal() -> None:
    manifest_file = frozen_config.manifest_path(NAME)
    if manifest_file.exists():
        raise SystemExit(f"{manifest_file.name} already exists. A sealed freeze is immutable; create locked_benchmark_frozen_v2 instead.")
    if locked_benchmark.RUN_STATE_FILE.exists():
        raise SystemExit("a locked run has already started; sealing now would not create a valid holdout")
    cfg = frozen_config.load(NAME)
    problems = frozen_config.verify_versions(cfg)
    if problems:
        raise SystemExit("cannot seal, the code does not match the config:\n  - " + "\n  - ".join(problems))

    def pin(rel):
        path = PROJECT_ROOT / rel
        if not path.exists():
            raise SystemExit(f"cannot pin missing file {rel}")
        return {"path": rel, "sha256": frozen_config.sha256_file(path)}

    stage_c_dir = "data/experiments/"
    manifest = {
        "freeze_version": NAME, "sealed_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": frozen_config.sha256_file(frozen_config.config_path(NAME)),
        "split_file_sha256": frozen_config.sha256_file(frozen_config.SPLIT_FILE),
        "split_manifest_sha256": frozen_config.sha256_file(locked_benchmark.SPLIT_MANIFEST),
        "source_file_sha256": {rel: frozen_config.sha256_file(PROJECT_ROOT / rel) for rel in locked_benchmark.pinned_source_files()},
        "pinned_files": {
            "protocol": pin(cfg["protocol"]["path"]),
            "stage_b_config": pin("data/eval/jev/stage_b_frozen_v1.json"), "stage_b_manifest": pin("data/eval/jev/stage_b_frozen_v1_manifest.json"),
            "stage_c_protocol": pin("docs/JEV_STAGE_C_PROTOCOL.md"),
            "stage_c_jev_experiment": pin(f"{stage_c_dir}{STAGE_C_JEV}/experiment.json"), "stage_c_jev_decisions": pin(f"{stage_c_dir}{STAGE_C_JEV}/decisions.jsonl"),
            "stage_c_llm_experiment": pin(f"{stage_c_dir}{STAGE_C_LLM}/experiment.json"), "stage_c_llm_decisions": pin(f"{stage_c_dir}{STAGE_C_LLM}/decisions.jsonl"),
            "stage_c_report": pin(f"{stage_c_dir}{STAGE_C_JEV}/stage_c_report.json"),
        },
        "dataset_checksum_digest": dataset_checksum_digest(),
        "environment_at_seal": {pkg: (metadata.version(pkg) if _installed(pkg) else None) for pkg in list(locked_benchmark.EXPECTED_ENVIRONMENT) + locked_benchmark.FORBIDDEN_PACKAGES},
        "note": "The locked run must use --frozen-config locked_benchmark_frozen_v1 with no overrides. Editing this configuration or any pinned file makes verification fail; after the run starts that invalidates the benchmark.",
    }
    manifest_file.write_text(json.dumps(manifest, indent=2))
    problems = locked_benchmark.verify() + locked_benchmark.verify_environment()
    if problems:
        manifest_file.unlink()
        raise SystemExit("seal verification failed immediately after writing; manifest removed:\n  - " + "\n  - ".join(problems))
    print(f"sealed: {manifest_file}\nconfig sha256: {manifest['config_sha256']}\nmanifest sha256: {frozen_config.sha256_file(manifest_file)}\n"
          f"pinned source files: {len(manifest['source_file_sha256'])}; other pinned files: {len(manifest['pinned_files'])}; verification clean")


def _installed(pkg: str) -> bool:
    try:
        metadata.version(pkg)
        return True
    except metadata.PackageNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-config", action="store_true")
    group.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    if args.build_config:
        path = frozen_config.config_path(NAME)
        if path.exists():
            raise SystemExit(f"{path.name} already exists; a configuration is not rebuilt in place. Create a new freeze version instead.")
        path.write_text(json.dumps(build_config(), indent=2))
        print(f"wrote {path} (not sealed yet: review it, then run --seal)")
    else:
        seal()


if __name__ == "__main__":
    main()
