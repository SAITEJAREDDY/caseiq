"""Pre-registered analysis of the locked benchmark (docs/JEV_LOCKED_BENCHMARK_PROTOCOL.md).

Read-only over stored experiments: no API, graph or hidden-truth call (it reads
the already-scored records). The analysis is fixed by the protocol and this
file's hash is pinned in the locked-benchmark manifest, so it cannot be changed
after the locked run starts. It performs only analyses the protocol lists; it
adds no headline slice.

Reference for "did it generalize" is the VALIDATION experiment named in the
frozen configuration (Stage C), not dev.

Usage:
    # after the locked run:
    python3 -m agent.jev_v2.locked_report --jev <locked jev id> --llm <locked llm id> [--out-dir DIR]

    # rehearsal on STORED validation data (never the locked split), to test this code before it is needed:
    python3 -m agent.jev_v2.locked_report --rehearsal --jev <validation jev id> --llm <validation llm id> \\
        --ref-jev <dev jev id> --ref-llm <dev llm id> --out-dir <a directory outside data/experiments>
"""
import argparse
import json
from pathlib import Path

from agent.jev_v2 import frozen_config, locked_benchmark, stage_c_posthoc, threshold_policy
from agent.jev_v2.registry import load_decisions, load_experiment
from agent.jev_v2.stage_c_report import _by_type, delta_label, newcombe_diff, render, wilson, build

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "experiments"
LOCKED_LABELS = {"title": "Locked benchmark report (pre-registered analysis)", "cur": "locked test", "ref": "validation", "Cur": "Locked test", "Ref": "Validation",
                 "cur_s": "locked", "Cur_s": "Locked"}
REHEARSAL_LABELS = {**LOCKED_LABELS, "title": "REHEARSAL on stored validation data -- NOT locked results", "cur": "rehearsal (validation)", "Cur": "Rehearsal (validation)",
                    "ref": "dev", "Ref": "Dev", "cur_s": "rehearsal", "Cur_s": "Rehearsal"}


def _rate(k, n):
    return None if not n else k / n


def frozen_threshold_evaluation(by_type: dict, cfg: dict) -> dict:
    """How the thresholds frozen from validation behave on this run. Descriptive: nothing is re-selected."""
    out = {}
    for dt, decision in cfg["decisions"].items():
        selection = decision.get("threshold_selection")
        if not decision.get("include_in_locked_test") or not selection or dt not in by_type:
            continue
        pop = threshold_policy.selection_population(by_type[dt], dt)
        block = {"population": len(pop), "population_definition": selection["population_definition"], "tiers": {}}
        for tier, frozen in selection["tiers"].items():
            if frozen.get("selected_threshold") is None:
                block["tiers"][tier] = {"selected_threshold": None, "note": "no threshold was selected on validation; none is evaluated"}
                continue
            th, target = frozen["selected_threshold"], frozen["target_error"]
            auto = [r for r in pop if r["scoring"]["predicted_confidence"] >= th]
            errors = sum(1 for r in auto if not r["scoring"]["correct"])
            lo, hi = wilson(errors, len(auto)) if auto else (None, None)
            err = _rate(errors, len(auto))
            block["tiers"][tier] = {
                "selected_threshold": th, "target_error": target, "automated": len(auto), "errors": errors, "coverage": _rate(len(auto), len(pop)),
                "observed_error": err, "error_upper_95": hi,
                "policy_met_on_this_run": bool(auto) and len(auto) >= threshold_policy.MIN_AUTOMATED and err <= target and hi <= threshold_policy.UPPER_BOUND_FACTOR * target,
                "validation": {k: frozen[k] for k in ("validation_coverage", "validation_automated", "validation_errors", "validation_observed_error", "validation_error_upper_95")},
            }
        if dt == "causal_change":  # the same rule over all decisions, including the trivial only-`none` ones
            everything = [r for r in by_type[dt] if r["scoring"].get("predicted_confidence") is not None and r["scoring"].get("correct") is not None]
            block["all_decisions_including_trivial"] = {}
            for tier, frozen in selection["tiers"].items():
                th = frozen.get("selected_threshold")
                if th is None:
                    continue
                auto = [r for r in everything if r["scoring"]["predicted_confidence"] >= th]
                errors = sum(1 for r in auto if not r["scoring"]["correct"])
                block["all_decisions_including_trivial"][tier] = {"selected_threshold": th, "automated": len(auto), "coverage": _rate(len(auto), len(everything)),
                                                                   "errors": errors, "observed_error": _rate(errors, len(auto))}
        out[dt] = block
    return out


def _reading(label, ref_kn, cur_kn, lower_is_better=False, neutral=False) -> dict:
    """`neutral` is for direction-free metrics (the RC40 abstention share): an interval excluding 0 is reported as higher/lower."""
    (kr, nr), (kc, nc) = ref_kn, cur_kn
    delta = newcombe_diff(kr, nr, kc, nc)
    reading = delta_label(delta, nr, nc, lower_is_better)
    if neutral and reading in ("material degradation", "improvement"):
        reading = "differs from validation (" + ("lower" if delta["ci_high"] < 0 else "higher") + ")"
    return {"metric": label, "reference": {"k": kr, "n": nr, "rate": _rate(kr, nr)}, "current": {"k": kc, "n": nc, "rate": _rate(kc, nc)},
            "delta": delta, "reading": reading}


def preregistered_secondary(cur_jev: list, ref_jev: list, scope: list) -> dict:
    """The co-primary and secondary metrics the protocol names beyond the shared Stage C analysis."""
    cur, ref = _by_type(cur_jev), _by_type(ref_jev)
    out = {}
    if "causal_change" in scope:
        cs, rs = stage_c_posthoc.causal_split(cur["causal_change"]), stage_c_posthoc.causal_split(ref["causal_change"])
        cn, rn = stage_c_posthoc.causal_nontrivial(cur["causal_change"]), stage_c_posthoc.causal_nontrivial(ref["causal_change"])
        lo, hi = cn["wilson_ci"]
        baseline = max(cn["baseline_always_none_nontrivial"], cn["baseline_newest_change_nontrivial"])
        out["causal_change"] = {
            "split_by_true_change": cs, "nontrivial": cn,
            "nontrivial_beats_best_rule": lo is not None and lo > baseline, "nontrivial_best_rule_baseline": baseline,
            "co_primary_readings_vs_validation": [
                _reading("accuracy on non-trivial decisions", (rn["correct_nontrivial"], rn["n_nontrivial"]), (cn["correct_nontrivial"], cn["n_nontrivial"])),
                _reading("detection rate (accuracy when a true change exists)", (rs["change_exists"]["correct"], rs["change_exists"]["n"]), (cs["change_exists"]["correct"], cs["change_exists"]["n"])),
                _reading("no-change false-positive rate (lower is better)", (rs["no_change"]["false_positive"], rs["no_change"]["n"]), (cs["no_change"]["false_positive"], cs["no_change"]["n"]), lower_is_better=True),
            ],
            "group_b_cases": stage_c_posthoc.group_b_detail(cur["causal_change"]),
            "change_id_artifact": stage_c_posthoc.id_artifact_check(cur["causal_change"]),
        }
    if "root_cause" in scope:
        cc, rc = stage_c_posthoc.root_cause_commitment(cur["root_cause"]), stage_c_posthoc.root_cause_commitment(ref["root_cause"])
        out["root_cause"] = {
            "commitment": cc, "detail": stage_c_posthoc.root_cause_detail(cur["root_cause"]),
            "co_primary_readings_vs_validation": [
                _reading("committed accuracy (answers other than RC40)", (round(rc["committed_accuracy"] * rc["committed_n"]), rc["committed_n"]), (round(cc["committed_accuracy"] * cc["committed_n"]), cc["committed_n"])),
                _reading("RC40 abstention share (direction-neutral)", (rc["answered_RC40"], rc["n"]), (cc["answered_RC40"], cc["n"]), neutral=True),
            ],
        }
    return out


def integrity(cfg: dict, jev_exp: dict, llm_exp: dict, rehearsal: bool) -> list:
    checks = []

    def add(label, passed, detail=""):
        checks.append({"check": label, "passed": bool(passed), "detail": detail})

    n_expected = cfg["split"]["expected_case_count"]
    add("Jev and LLM experiments cover the same cases", jev_exp["case_ids"] == llm_exp["case_ids"])
    included = sorted(locked_benchmark.included_decisions(cfg))
    if rehearsal:
        add("REHEARSAL: experiment covers every frozen included decision (it may hold more)", set(included) <= set(jev_exp["decision_types"]), f"{sorted(jev_exp['decision_types'])}")
    else:
        add("decision types equal the frozen included set", sorted(jev_exp["decision_types"]) == included, f"{sorted(jev_exp['decision_types'])}")
    if rehearsal:
        add("REHEARSAL: experiments are stored validation data, not the locked run", jev_exp["dataset_split"] == "validation", jev_exp["dataset_split"])
        return checks
    add("kind is locked_benchmark and split is test", jev_exp["kind"] == "locked_benchmark" and jev_exp["dataset_split"] == "test", f"{jev_exp['kind']}/{jev_exp['dataset_split']}")
    add(f"case count equals the frozen expectation ({n_expected})", jev_exp["num_cases"] == n_expected, str(jev_exp["num_cases"]))
    frozen = (jev_exp["config"].get("frozen_config") or {})
    add("run used the sealed locked configuration", frozen.get("name") == locked_benchmark.NAME and frozen.get("status") == "verified_against_manifest")
    add("run's config digest equals the sealed digest", frozen.get("config_sha256") == frozen_config.sha256_file(frozen_config.config_path(locked_benchmark.NAME)))
    add("no failed cases", not (jev_exp["config"].get("orchestration") or {}).get("failed_cases"))
    add("protocol digest recorded on the run matches the file", (jev_exp["config"].get("pre_registered_protocol") or {}).get("sha256") == frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / cfg["protocol"]["path"]))
    problems = locked_benchmark.verify()
    add("sealed configuration still verifies against the working tree", not problems, "; ".join(problems)[:300])
    return checks


def build_locked(cur_jev: list, cur_llm: list, ref_jev: list, ref_llm: list, cfg: dict) -> dict:
    scope = locked_benchmark.included_decisions(cfg)
    base = build(cur_jev, cur_llm, ref_jev, ref_llm, {}, scope)
    return {"scope": scope, "shared": base, "frozen_thresholds": frozen_threshold_evaluation(_by_type(cur_jev), cfg),
            "preregistered_secondary": preregistered_secondary(cur_jev, ref_jev, scope)}


def _p(x, nd=1):
    return f"{x * 100:.{nd}f}%" if x is not None else "n/a"


def render_extras(report: dict, integrity_checks: list, labels: dict = None) -> str:
    lb = labels or LOCKED_LABELS
    L = ["", "## Frozen thresholds on this run (chosen on validation; nothing re-selected)", ""]
    for dt, block in report["frozen_thresholds"].items():
        L += [f"### {dt}", f"- population: {block['population']} ({block['population_definition']})"]
        for tier, t in block["tiers"].items():
            if t.get("selected_threshold") is None:
                L.append(f"- {tier}: {t['note']}")
                continue
            v = t["validation"]
            L.append(f"- {tier} (target error <= {t['target_error']:.0%}, threshold >= {t['selected_threshold']}): automated {t['automated']} ({_p(t['coverage'])}), errors {t['errors']}, "
                     f"observed error {_p(t['observed_error'])}, Wilson upper {_p(t['error_upper_95'])}; policy met on this run: {t['policy_met_on_this_run']}. "
                     f"On validation: coverage {_p(v['validation_coverage'])}, error {_p(v['validation_observed_error'])}, upper {_p(v['validation_error_upper_95'])}.")
        if "all_decisions_including_trivial" in block:
            for tier, t in block["all_decisions_including_trivial"].items():
                L.append(f"- {tier}, all decisions including trivial only-`none` ones: automated {t['automated']} ({_p(t['coverage'])}), errors {t['errors']}, observed error {_p(t['observed_error'])}")
        L.append("")
    for dt, block in report["shared"]["primitives"].items():
        per_class = block.get("per_class") or {}
        if dt == "causal_change":
            L += ["## Class-level precision and recall: causal_change", "", "Classes are change ids (mostly singletons); the per-class figures are in the JSON. The `none` class:", ""]
            if "none" in per_class:
                c = per_class["none"]
                L.append(f"- `none`: precision {_p(c['precision'])}, recall {_p(c['recall'])}, support {c['support']}")
            L.append("")
            continue
        L += [f"## Class-level precision and recall: {dt}", "", "| Class | Support | Precision | Recall | F1 |", "|---|---:|---:|---:|---:|"]
        for cls, c in sorted(per_class.items()):
            if isinstance(c, dict) and c.get("support"):
                L.append(f"| {cls} | {c['support']} | {_p(c['precision'])} | {_p(c['recall'])} | {_p(c['f1'])} |")
        L.append("")
    L += ["## Paired Jev-versus-LLM outcomes (identical inputs)", "", "| Decision | Both correct | Only Jev | Only LLM | Both wrong | Exact McNemar p | Input parity |", "|---|---:|---:|---:|---:|---:|---:|"]
    for dt, c in report["shared"]["jev_vs_llm"].items():
        pr = c["paired"]
        L.append(f"| {dt} | {pr['both_correct']} | {pr['only_jev_correct']} | {pr['only_llm_correct']} | {pr['neither_correct']} | {pr['mcnemar_exact_p']:.3f} | "
                 f"{c['input_parity']['identical_state_candidates_asof']}/{c['input_parity']['n_pairs']} |")
    L.append("")
    for dt, block in report["preregistered_secondary"].items():
        L += [f"## Pre-registered co-primary and secondary metrics: {dt}", ""]
        if dt == "causal_change":
            cn, cs = block["nontrivial"], block["split_by_true_change"]
            L += [f"- non-trivial decisions (a real change was offered): n={cn['n_nontrivial']} of {cn['n_all']}; accuracy {_p(cn['accuracy_nontrivial'])} [{_p(cn['wilson_ci'][0])}, {_p(cn['wilson_ci'][1])}]; "
                  f"best evidence-blind rule {_p(block['nontrivial_best_rule_baseline'])}; lower bound above it: {block['nontrivial_beats_best_rule']}",
                  f"- true change exists: n={cs['change_exists']['n']}, detection {_p(cs['change_exists']['accuracy'])}, answered `none` {cs['change_exists']['answered_none']}, wrong real change {cs['change_exists']['wrong_real_change']}",
                  f"- no change: n={cs['no_change']['n']}, accuracy {_p(cs['no_change']['accuracy'])}, false positives {cs['no_change']['false_positive']} ({_p(cs['no_change']['false_positive_rate'])})",
                  f"- high-confidence composition: {cn['confidence_ge_0.90']}",
                  f"- group B (true change older than a newer candidate) cases: {len(block['group_b_cases'])}: {block['group_b_cases']}",
                  f"- change-id artifact (descriptive): {block['change_id_artifact']}", ""]
        if dt == "root_cause":
            L += [f"- commitment: {block['commitment']}", f"- by evidence quality: {block['detail']['by_evidence_quality']}", ""]
        L += [f"| Metric | {lb['Ref']} | This run | Delta (pts) [95% CI] | Reading |", "|---|---:|---:|---:|---|"]
        for r in block["co_primary_readings_vs_validation"]:
            d = r["delta"]
            L.append(f"| {r['metric']} | {_p(r['reference']['rate'])} ({r['reference']['k']}/{r['reference']['n']}) | {_p(r['current']['rate'])} ({r['current']['k']}/{r['current']['n']}) | "
                     f"{d['diff'] * 100:+.1f} [{d['ci_low'] * 100:+.1f}, {d['ci_high'] * 100:+.1f}] | {r['reading']} |")
        L.append("")
    L += ["## Integrity checks", "", "| Check | Passed | Detail |", "|---|---|---|"]
    for c in integrity_checks:
        L.append(f"| {c['check']} | {c['passed']} | {c['detail']} |")
    return "\n".join(L) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jev", required=True, help="Jev experiment id (the locked run, or with --rehearsal a stored validation run)")
    parser.add_argument("--llm", required=True)
    parser.add_argument("--ref-jev", help="Only with --rehearsal: reference Jev experiment (default: the validation experiment named in the frozen config)")
    parser.add_argument("--ref-llm", help="Only with --rehearsal")
    parser.add_argument("--rehearsal", action="store_true", help="Test this analysis on stored validation data; writes only to --out-dir (outside data/experiments)")
    parser.add_argument("--out-dir")
    args = parser.parse_args()

    cfg = frozen_config.load(locked_benchmark.NAME)
    ref = cfg["analysis"]["reference"]
    jev_exp, llm_exp = load_experiment(args.jev), load_experiment(args.llm)
    if args.rehearsal:
        if not args.out_dir or EXPERIMENTS_DIR in Path(args.out_dir).resolve().parents:
            parser.error("--rehearsal requires --out-dir outside data/experiments")
        if jev_exp["dataset_split"] == "test" or llm_exp["dataset_split"] == "test":
            parser.error("--rehearsal is for stored non-test data only")
        ref_jev_id, ref_llm_id = args.ref_jev or ref["jev_experiment"], args.ref_llm or ref["llm_experiment"]
        labels = REHEARSAL_LABELS
    else:
        if args.ref_jev or args.ref_llm:
            parser.error("--ref-jev/--ref-llm are for --rehearsal only; the reference is fixed by the frozen configuration")
        ref_jev_id, ref_llm_id = ref["jev_experiment"], ref["llm_experiment"]
        labels = LOCKED_LABELS

    checks = integrity(cfg, jev_exp, llm_exp, args.rehearsal)
    if not args.rehearsal and not all(c["passed"] for c in checks):
        raise SystemExit("integrity checks failed; not producing a locked report:\n" + "\n".join(f"  - {c['check']}: {c['detail']}" for c in checks if not c["passed"]))

    scope = locked_benchmark.included_decisions(cfg)
    cur_jev = [r for r in load_decisions(args.jev) if r["decision_type"] in scope]
    cur_llm = [r for r in load_decisions(args.llm) if r["decision_type"] in scope]
    report = build_locked(cur_jev, cur_llm, load_decisions(ref_jev_id), load_decisions(ref_llm_id), cfg)
    meta = {"jev_val": args.jev, "llm_val": args.llm, "jev_dev": ref_jev_id, "llm_dev": ref_llm_id, "n_cases": jev_exp["num_cases"],
            "protocol_sha256": frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / cfg["protocol"]["path"])}
    out_dir = Path(args.out_dir) if args.out_dir else EXPERIMENTS_DIR / args.jev
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "locked_report_REHEARSAL" if args.rehearsal else "locked_report"
    (out_dir / f"{stem}.json").write_text(json.dumps({"meta": meta, "integrity": checks, "report": report}, indent=2, default=str))
    (out_dir / f"{stem}.md").write_text(render(report["shared"], meta, labels) + render_extras(report, checks, labels))
    print(out_dir / f"{stem}.md")
    for dt, c in report["shared"]["classification"].items():
        print(f"  {dt}: {c['class']}")


if __name__ == "__main__":
    main()
