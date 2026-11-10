"""Record that a locked-benchmark freeze was superseded before use (JEV-036).

This writes ONE new file next to the freeze, `<name>_superseded.json`. It changes neither the sealed configuration
nor its manifest nor any pinned source: their digests are read, checked and recorded so the preservation is
verifiable. It refuses to run unless the opaque-key control's pre-registered Jev verdict is "material".

The record is a declaration. The sealed runner does not read it (making the runner refuse a superseded freeze means
editing sealed sources, which is a separate decision recorded in JEV-036), so the record says so explicitly.

Usage:
    python3 -m agent.jev_v2.supersede_locked_benchmark [--report data/eval/jev/analysis/opaque_control/opaque_control.json]
"""
import argparse
import json
from datetime import datetime, timezone

from agent.jev_v2 import frozen_config, locked_benchmark

DEFAULT_REPORT = frozen_config.PROJECT_ROOT / "data" / "eval" / "jev" / "analysis" / "opaque_control" / "opaque_control.json"


def record_path(name: str = locked_benchmark.NAME):
    return frozen_config.FROZEN_DIR / f"{name}_superseded.json"


def build_record(report: dict) -> dict:
    jev, llm, ex = report["jev"], report["llm"], report["exploratory"]["jev_vs_llm_under_each_scheme"]
    r2, r1 = jev["rules"]["R2"], jev["rules"]["R1"]
    manifest = frozen_config.load_manifest(locked_benchmark.NAME)
    return {
        "freeze_version": locked_benchmark.NAME,
        "status": "superseded_before_use",
        "superseded_at": datetime.now(timezone.utc).isoformat(),
        "reason_short": "opaque-key control: Jev's causal-change predictions depend on the option-key identity",
        "reason": ("The pre-registered validation control (docs/JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md, rule R2) found that Jev's choices change systematically when "
                   "the canonical change ids are replaced by opaque keys, beyond run-to-run noise. The pre-registered consequence, and the task instruction, is that a "
                   "freeze whose causal-change decision runs on canonical ids is not used for the locked benchmark. Aggregate accuracy was preserved (R1), so this is "
                   "a sensitivity finding, not an accuracy loss; see docs/JEV_OPAQUE_KEY_CONTROL.md."),
        "evidence": {
            "experiments": report["experiments"], "protocol": report["protocol"], "protocol_sha256": report["protocol_sha256"],
            "jev_verdict": jev["verdict"]["label"], "llm_verdict": llm["verdict"]["label"],
            "jev": {"population_P": jev["n_nontrivial"], "semantic_disagreements_opaque": r2["disagreements"], "semantic_disagreements_canonical_replicate": r2["replicate_disagreements"],
                    "excess_disagreement": r2["excess"], "only_under_opaque": r2["only_under_opaque"], "only_under_replicate": r2["only_under_replicate"], "mcnemar_p": r2["mcnemar_p"],
                    "direction_of_changed_answers": jev["flip_anatomy_P"], "accuracy_P_canonical": jev["metrics"]["P"]["canonical"]["accuracy"], "accuracy_P_opaque": jev["metrics"]["P"]["opaque"]["accuracy"],
                    "r1_b_c_p": [r1["b"], r1["c"], r1["p"]]},
            "jev_minus_llm_all_decisions": {"canonical_keys": ex["canonical_ALL"]["jev_minus_llm"], "opaque_keys": ex["opaque_ALL"]["jev_minus_llm"]},
        },
        "preserved": {
            "config_sha256": frozen_config.sha256_file(frozen_config.config_path(locked_benchmark.NAME)),
            "manifest_sha256": frozen_config.sha256_file(locked_benchmark.manifest_path(locked_benchmark.NAME)),
            "matches_manifest_recorded_config_sha256": frozen_config.sha256_file(frozen_config.config_path(locked_benchmark.NAME)) == manifest["config_sha256"],
            "note": "the sealed configuration, its manifest and every pinned source were not modified",
        },
        "locked_split": {"opened": False, "run_state_marker": locked_benchmark.read_run_state(), "note": "no locked experiment exists and no locked case was run, counted or previewed"},
        "enforcement": {"machine_enforced": False,
                        "note": "this record is a declaration. The sealed run_experiment/locked_benchmark do not read it, so the runner would still accept the v1 command. "
                                "Making verify() refuse a superseded freeze requires editing the sealed locked_benchmark.py; that edit was blocked and is left as a user decision (JEV-036)."},
        "successor": {"status": "proposed, not created", "proposal": "docs/JEV_OPAQUE_KEY_CONTROL.md, section 'Proposed replacement configuration'"},
        "reversal": "Only by an explicit user decision that is logged in docs/JEV_ISSUE_LOG.md; deleting this record without one would be tampering with the audit trail.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    path = record_path()
    if path.exists():
        raise SystemExit(f"{path.name} already exists; a supersession record is never rewritten")
    report = json.loads(open(args.report).read())
    if report["jev"]["verdict"]["code"] != "material":
        raise SystemExit(f"the Jev verdict is {report['jev']['verdict']['label']!r}; supersession is only recorded for a material verdict")
    if locked_benchmark.read_run_state() is not None:
        raise SystemExit("a locked run state exists; supersession-before-use no longer applies")
    problems = locked_benchmark.verify()
    if problems:
        raise SystemExit(f"the freeze does not verify, so the record would not describe an intact freeze: {problems[:2]}")
    record = build_record(report)
    path.write_text(json.dumps(record, indent=2))
    print(f"wrote {path}")
    print(json.dumps(record["preserved"], indent=2))


if __name__ == "__main__":
    main()
