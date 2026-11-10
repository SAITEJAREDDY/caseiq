"""Seals the Stage B frozen configuration by writing its manifest.

Run once, after every code and config change is finished:

    python3 -m agent.jev_v2.freeze_stage_b --config stage_b_frozen_v1 \
        --reference causal_change_v3=<experiment id> --reference jev_vs_llm_jev=<id> ...

It refuses to overwrite an existing manifest (a freeze is immutable; a new
freeze needs a new freeze_version), checks that the reference experiments were
run with exactly the frozen versions and resolved to the frozen Jev model, and
finishes by running the full verification. It reads no hidden truth.
"""
import argparse
import json
from datetime import datetime, timezone

from agent.eval_v2.registry import dataset_checksum_digest
from agent.eval_v2.splits import case_ids_for_split
from agent.jev_v2 import frozen_config
from agent.jev_v2.registry import load_decisions, load_experiment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="stage_b_frozen_v1")
    parser.add_argument("--reference", action="append", default=[], metavar="LABEL=EXPERIMENT_ID")
    args = parser.parse_args()

    manifest_file = frozen_config.manifest_path(args.config)
    if manifest_file.exists():
        raise SystemExit(f"{manifest_file.name} already exists. A freeze is immutable; create a new freeze_version instead.")
    cfg = frozen_config.load(args.config)
    problems = frozen_config.verify_versions(cfg)
    if problems:
        raise SystemExit("cannot freeze, the code does not match the config:\n  - " + "\n  - ".join(problems))

    cohort = cfg["cohort"]
    cohort_ids = case_ids_for_split(cohort["split"])[: cohort["n_cases"]]

    references = {}
    for pair in args.reference:
        label, _, experiment_id = pair.partition("=")
        experiment = load_experiment(experiment_id)
        if experiment["case_ids"] != cohort_ids:
            raise SystemExit(f"reference {label} ({experiment_id}) does not use the frozen cohort")
        resolved = sorted({r.get("jev_model") for r in load_decisions(experiment_id) if r.get("jev_model")})
        if experiment["experiment_type"] == "jev_primitive" and resolved != [cfg["jev"]["model_resolved_at_freeze"]]:
            raise SystemExit(f"reference {label}: Jev resolved to {resolved}, not the frozen {cfg['jev']['model_resolved_at_freeze']}")
        references[label] = {
            "experiment_id": experiment_id, "experiment_type": experiment["experiment_type"], "num_cases": experiment["num_cases"],
            "evaluator_version": experiment["evaluator_version"], "candidate_generation_versions": experiment["config"].get("candidate_generation_versions"),
            "frozen_config_status": (experiment["config"].get("frozen_config") or {}).get("status"),
        }

    manifest = {
        "freeze_version": cfg["freeze_version"],
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": frozen_config.sha256_file(frozen_config.config_path(args.config)),
        "split_file_sha256": frozen_config.sha256_file(frozen_config.SPLIT_FILE),
        "source_file_sha256": {rel: frozen_config.sha256_file(frozen_config.PROJECT_ROOT / rel) for rel in frozen_config.FROZEN_SOURCE_FILES},
        "dataset_checksum_digest": dataset_checksum_digest(),
        "cohort_case_ids_sha256": frozen_config.sha256_json(cohort_ids),
        "cohort_case_ids": cohort_ids,
        "reference_experiments": references,
        "note": "Stage C must run with --frozen-config and no overrides. Editing any file listed here, the config, the split file, or the Phase 1-3 data makes verification fail.",
    }
    manifest_file.write_text(json.dumps(manifest, indent=2))
    problems = frozen_config.verify(args.config)
    if problems:
        manifest_file.unlink()
        raise SystemExit("freeze verification failed immediately after writing; manifest removed:\n  - " + "\n  - ".join(problems))
    print(f"frozen: {manifest_file}\nsource files hashed: {len(manifest['source_file_sha256'])}; reference experiments: {len(references)}; verification clean")


if __name__ == "__main__":
    main()
