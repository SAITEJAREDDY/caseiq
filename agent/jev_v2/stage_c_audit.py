"""Stage C review: audit of the stored validation artifacts, and the authoritative dev-versus-validation
tables built from the metrics the registry stores.

Read-only over stored experiments and the registry. It calls no API and no graph, imports no hidden truth,
and reads no test-case id: split membership is checked only against the dev and validation lists.

Usage:
    python3 -m agent.jev_v2.stage_c_audit [--out-dir data/eval/jev/analysis/stage_c_review]
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from agent.eval_v2.splits import case_ids_for_split, load_splits
from agent.jev_v2 import frozen_config, locked_benchmark
from agent.jev_v2.aggregate import _percentile
from agent.jev_v2.registry import load_decisions, load_experiment
from agent.jev_v2.stage_c_report import delta_label, newcombe_diff, ratio_ci, wilson

EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "experiments"
DEFAULT_OUT = Path(__file__).resolve().parent.parent.parent / "data" / "eval" / "jev" / "analysis" / "stage_c_review"

STAGE_C_JEV = "exp_stage_c_validation_jev_20260923T184036Z_fa984004"
STAGE_C_LLM = "exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a"
DEV_JEV = "exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24"
DEV_LLM = "exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff"
DEV_CAUSAL_RUNS = {"causal v3 run": "exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8",
                   "causal v3 repeat run": "exp_causal_change_v3_repeat_dev100_jev_20260923T174042Z_aee6568c"}
PRIMITIVES = ["issue_category", "root_cause", "causal_change", "owning_team", "evidence_sufficiency", "incident_relationship"]


def _exp(experiment_id: str) -> dict:
    return load_experiment(experiment_id)


def _row(label: str, dev_kn: tuple, val_kn: tuple, dev_ci=None, val_ci=None, lower_is_better=False) -> dict:
    (kd, nd), (kv, nv) = dev_kn, val_kn
    delta = newcombe_diff(kd, nd, kv, nv)
    return {"metric": label, "dev": {"k": kd, "n": nd, "rate": kd / nd if nd else None, "stored_ci": dev_ci},
            "validation": {"k": kv, "n": nv, "rate": kv / nv if nv else None, "stored_ci": val_ci},
            "delta": delta, "ratio": ratio_ci(kd, nd, kv, nv), "reading": delta_label(delta, nd, nv, lower_is_better)}


def _ci(block: dict):
    ci = block.get("bootstrap_ci_accuracy") or {}
    return [ci.get("ci_low"), ci.get("ci_high")] if ci else None


def _k(rate: float, n: int) -> int:
    return round(rate * n)


# ── audit ─────────────────────────────────────────────────────────────────────────────
def audit() -> list:
    checks = []

    def add(label, passed, detail=""):
        checks.append({"check": label, "passed": bool(passed), "detail": detail})

    registry = [json.loads(line) for line in open(EXPERIMENTS_DIR / "registry.jsonl") if line.strip()]
    stage_c = [r for r in registry if r.get("kind") == "validation"]
    add("registry holds exactly one validation Jev experiment and one validation LLM experiment", sorted(r["experiment_id"] for r in stage_c) == sorted([STAGE_C_JEV, STAGE_C_LLM]),
        f"{[r['experiment_id'] for r in stage_c]}")

    jev, llm = _exp(STAGE_C_JEV), _exp(STAGE_C_LLM)
    stage_b = frozen_config.load("stage_b_frozen_v1")
    manifest = frozen_config.load_manifest("stage_b_frozen_v1")
    stage_b_sha = frozen_config.sha256_file(frozen_config.config_path("stage_b_frozen_v1"))
    for label, exp in (("Jev", jev), ("LLM", llm)):
        fc = exp["config"].get("frozen_config") or {}
        add(f"{label}: split is validation and kind is validation", exp["dataset_split"] == "validation" and exp["kind"] == "validation", f"{exp['dataset_split']}/{exp['kind']}")
        add(f"{label}: ran under stage_b_frozen_v1, verified against its manifest (not --pre-freeze)", fc.get("name") == "stage_b_frozen_v1" and fc.get("status") == "verified_against_manifest", str(fc))
        add(f"{label}: recorded config digest equals the Stage B config file and its manifest", fc.get("config_sha256") == stage_b_sha == manifest["config_sha256"], fc.get("config_sha256", "")[:16])
        add(f"{label}: candidate-generation versions equal the frozen ones", exp["config"]["candidate_generation_versions"] == {dt: d["candidate_generation_version"] for dt, d in stage_b["decisions"].items()})
        add(f"{label}: root-cause context is the frozen v4_operational", exp["config"]["context_version"] == stage_b["decisions"]["root_cause"]["context_version"] == "v4_operational")
        add(f"{label}: causal key mode is the frozen canonical", exp["config"]["causal_key_mode"] == "canonical")
        add(f"{label}: evaluator, question-set, candidate bundle and pricing versions equal the frozen ones",
            (exp["evaluator_version"], exp["question_set_version"], exp["candidate_strategy_version"], exp["config"]["pricing_version"])
            == (stage_b["evaluator_version"], stage_b["question_set_version"], stage_b["candidate_strategy_bundle"], stage_b["pricing_version"]),
            f"{exp['evaluator_version']}/{exp['question_set_version']}/{exp['candidate_strategy_version']}/{exp['config']['pricing_version']}")
        add(f"{label}: orchestration completed with no failed cases", not (exp["config"].get("orchestration") or {}).get("failed_cases"), str(exp["config"].get("orchestration")))
    add("Jev: requested model is the frozen jev-1.13.0", jev["config"]["jev_model_requested"] == stage_b["jev"]["model_requested"], jev["config"]["jev_model_requested"])
    add("LLM: model, temperature, max tokens and repair allowance equal the frozen ones",
        (llm["config"]["llm_model"], llm["config"]["llm_temperature"], llm["config"]["llm_max_tokens"], llm["config"]["llm_repair_max_attempts"])
        == (stage_b["llm_baseline"]["model"], stage_b["llm_baseline"]["temperature"], stage_b["llm_baseline"]["max_tokens"], stage_b["llm_baseline"]["repair_max_attempts"]))

    jev_records, llm_records = load_decisions(STAGE_C_JEV), load_decisions(STAGE_C_LLM)
    add("Jev: every decision resolved to the frozen model version", {r.get("jev_model") for r in jev_records} == {stage_b["jev"]["model_resolved_at_freeze"]},
        str(dict(Counter(r.get("jev_model") for r in jev_records))))
    for label, records in (("Jev", jev_records), ("LLM", llm_records)):
        seen = {(r["decision_type"], r["question_version"], r["candidate_generation_version"]) for r in records}
        want = {(dt, d["question_version"], d["candidate_generation_version"]) for dt, d in stage_b["decisions"].items()}
        add(f"{label}: every record carries the frozen question and candidate-generation version of its decision", seen == want, f"{sorted(seen)}")

    validation_ids = case_ids_for_split("validation")
    add("Jev and LLM experiments contain exactly the validation split (750 cases, same order)", jev["case_ids"] == llm["case_ids"] == validation_ids and len(validation_ids) == 750, str(len(jev["case_ids"])))
    add("case-id digest recorded on the run equals the digest of the validation ids", jev["config"]["case_ids_sha256"] == frozen_config.sha256_json(validation_ids), jev["config"]["case_ids_sha256"][:16])
    add("decision files contain no case outside the experiment's case list", {r["case_id"] for r in jev_records} == set(jev["case_ids"]) and {r["case_id"] for r in llm_records} == set(llm["case_ids"]))
    add("decision counts: 750 per choice decision, incident decisions equal for both systems",
        all(Counter(r["decision_type"] for r in jev_records)[dt] == 750 for dt in PRIMITIVES[:5]) and Counter(r["decision_type"] for r in jev_records) == Counter(r["decision_type"] for r in llm_records),
        str(dict(Counter(r["decision_type"] for r in jev_records))))
    protocol = jev["config"].get("pre_registered_protocol") or {}
    add("pre-registered Stage C protocol digest recorded on the run matches the file today", protocol.get("sha256") == frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / protocol.get("path", "")), protocol.get("sha256", "")[:16])

    if locked_benchmark.manifest_path().exists():
        pins = frozen_config.load_manifest(locked_benchmark.NAME)["pinned_files"]
        unchanged = all(frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / pins[k]["path"]) == pins[k]["sha256"]
                        for k in ("stage_c_jev_experiment", "stage_c_jev_decisions", "stage_c_llm_experiment", "stage_c_llm_decisions", "stage_c_report", "stage_c_protocol"))
        add("Stage C experiments, report and protocol are byte-identical to what the locked freeze pinned (immutable)", unchanged)

    # ── no locked access, from registry / marker / guard metadata only ────────────────
    add("registry: no experiment carries dataset_split 'test' or kind 'locked_benchmark'", not any(r.get("dataset_split") == "test" or r.get("kind") == "locked_benchmark" for r in registry),
        str(dict(Counter((r.get("dataset_split"), r.get("kind")) for r in registry))))
    assignment = load_splits()
    allowed = {cid for cid, split in assignment.items() if split in ("dev", "validation")}  # test entries are dropped immediately and never used
    del assignment
    outside = []
    for r in registry:
        ids = (json.loads((EXPERIMENTS_DIR / r["experiment_id"] / "experiment.json").read_text()).get("case_ids")) or []
        outside += [(r["experiment_id"], c) for c in ids if c not in allowed]
    add(f"registry: every case id used by all {len(registry)} registered experiments is in the dev or validation split", not outside, f"{len(outside)} outside")
    checkpoint = EXPERIMENTS_DIR.parent / "eval" / "jev" / "checkpoints" / "stage_c_validation.jsonl"
    ck_ids = [json.loads(line)["case_id"] for line in open(checkpoint) if line.strip()]
    add("Stage C checkpoint holds exactly the validation case ids", sorted(ck_ids) == sorted(validation_ids), str(len(ck_ids)))
    add("no locked run-state marker exists (the locked holdout has not started)", locked_benchmark.read_run_state() is None)
    add("no access log exists to consult (none is kept by the split loader); the evidence is the registry, the marker and the guard checks",
        True, "the split loader keeps no log; see Phase 7 boundary validator checks [8], [9], [10]")
    return checks


# ── authoritative tables ──────────────────────────────────────────────────────────────
def authoritative_table() -> dict:
    dev, val = _exp(DEV_JEV)["report"], _exp(STAGE_C_JEV)["report"]
    rows = []
    for dt, label in (("issue_category", "Issue category accuracy"), ("root_cause", "Root cause accuracy"), ("causal_change", "Causal change accuracy")):
        rows.append(_row(label, (_k(dev[dt]["accuracy"], dev[dt]["n_decisions"]), dev[dt]["n_decisions"]), (_k(val[dt]["accuracy"], val[dt]["n_decisions"]), val[dt]["n_decisions"]), _ci(dev[dt]), _ci(val[dt])))
    dt_, vt_ = dev["owning_team"]["owning_team_metrics"], val["owning_team"]["owning_team_metrics"]
    n_d, n_v = dev["owning_team"]["n_decisions"], val["owning_team"]["n_decisions"]
    rows.append(_row("Owning team primary accuracy", (_k(dt_["primary_accuracy"], n_d), n_d), (_k(vt_["primary_accuracy"], n_v), n_v)))
    rows.append(_row("Owning team acceptable accuracy", (_k(dt_["acceptable_accuracy"], n_d), n_d), (_k(vt_["acceptable_accuracy"], n_v), n_v)))
    for dt, label in (("evidence_sufficiency", "Evidence sufficiency accuracy"), ("incident_relationship", "Incident relationship accuracy")):
        rows.append(_row(label, (_k(dev[dt]["accuracy"], dev[dt]["n_decisions"]), dev[dt]["n_decisions"]), (_k(val[dt]["accuracy"], val[dt]["n_decisions"]), val[dt]["n_decisions"]), _ci(dev[dt]), _ci(val[dt])))
    recall_rows = []
    for dt, label in (("issue_category", "Issue category"), ("root_cause", "Root cause"), ("causal_change", "Causal change")):
        d, v = dev[dt]["candidate_recall"], val[dt]["candidate_recall"]
        recall_rows.append(_row(f"{label} candidate recall", (_k(d["candidate_recall"], d["n_with_known_candidate_set"]), d["n_with_known_candidate_set"]),
                                (_k(v["candidate_recall"], v["n_with_known_candidate_set"]), v["n_with_known_candidate_set"])))
        recall_rows[-1]["candidate_counts"] = {"dev": {k: d.get(k) for k in ("avg_candidate_count", "median_candidate_count", "p90_candidate_count")},
                                               "validation": {k: v.get(k) for k in ("avg_candidate_count", "median_candidate_count", "p90_candidate_count")}}
    for key, label in (("primary_candidate_recall", "Owning team primary candidate recall"), ("acceptable_candidate_recall", "Owning team acceptable candidate recall")):
        recall_rows.append(_row(label, (_k(dt_[key], n_d), n_d), (_k(vt_[key], n_v), n_v)))
    dev_causal_runs = {label: (lambda r: {"accuracy": r["causal_change"]["accuracy"], "n": r["causal_change"]["n_decisions"]})(_exp(eid)["report"]) for label, eid in DEV_CAUSAL_RUNS.items()}
    dev_causal_runs["final dev comparison run"] = {"accuracy": dev["causal_change"]["accuracy"], "n": dev["causal_change"]["n_decisions"]}
    return {"accuracy_rows": rows, "recall_rows": recall_rows, "dev_causal_runs": dev_causal_runs}


def cross_check_against_stage_c_report(table: dict) -> list:
    """Stored registry values must equal the values the Stage C report recomputed from the decision records."""
    report = json.loads((EXPERIMENTS_DIR / STAGE_C_JEV / "stage_c_report.json").read_text())["report"]["generalization"]
    by = {r["metric"]: r for r in report}
    mapping = {"Issue category accuracy": "Issue category accuracy", "Root cause accuracy": "Root cause accuracy", "Causal change accuracy": "Causal change accuracy",
               "Owning team primary accuracy": "Owning team primary accuracy", "Owning team acceptable accuracy": "Owning team acceptable accuracy",
               "Evidence sufficiency accuracy": "Evidence sufficiency accuracy", "Incident relationship accuracy": "Incident relationship accuracy",
               "Root cause candidate recall": "Root cause candidate recall", "Causal change candidate recall": "Causal change candidate recall",
               "Owning team primary candidate recall": "Owning team primary candidate recall", "Owning team acceptable candidate recall": "Owning team acceptable candidate recall"}
    out = []
    for r in table["accuracy_rows"] + table["recall_rows"]:
        if r["metric"] in mapping:
            other = by[mapping[r["metric"]]]
            same = (r["dev"]["k"], r["dev"]["n"], r["validation"]["k"], r["validation"]["n"]) == (other["dev"]["k"], other["dev"]["n"], other["validation"]["k"], other["validation"]["n"])
            out.append({"metric": r["metric"], "stored_equals_recomputed": same})
    return out


def operations() -> dict:
    out = {}
    for stage, jev_id, llm_id in (("dev (sequential)", DEV_JEV, DEV_LLM), ("validation (8 workers)", STAGE_C_JEV, STAGE_C_LLM)):
        block = {}
        for system, exp_id in (("jev", jev_id), ("llm", llm_id)):
            records, rep = load_decisions(exp_id), _exp(exp_id)["report"]
            per = {}
            for dt in PRIMITIVES:
                eff, con = rep[dt]["efficiency"], rep[dt]["contract"]
                lat = [r["latency_ms"] for r in records if r["decision_type"] == dt and r.get("latency_ms") is not None]
                per[dt] = {"n": rep[dt]["n_decisions"], "p50_ms": eff["p50_latency_ms"], "p90_ms": _percentile(lat, 0.90), "p95_ms": eff["p95_latency_ms"],
                           "cost_per_decision_usd": eff["cost_per_decision_usd"], "cost_per_1000_usd": eff["cost_per_1000_decisions_usd"],
                           "first_attempt_valid": con.get("first_attempt_valid"), "repair_required": con.get("repair_required"),
                           "unrecoverable": con.get("unrecoverable_failures"), "api_errors": con.get("request_or_api_errors")}
            block[system] = per
        out[stage] = block
    return out


def paired(experiment_id: str) -> dict:
    path = EXPERIMENTS_DIR / experiment_id / "comparison_jev_vs_llm.json"
    comparison = json.loads(path.read_text())["comparison"]
    return {dt: {k: c["paired"][k] for k in ("both_correct", "only_jev_correct", "only_llm_correct", "neither_correct", "mcnemar_exact_p")}
            | {"jev_minus_llm_ci": c["paired"]["jev_minus_llm_accuracy_ci"], "n_pairs": c["n_pairs"]} for dt, c in comparison.items()}


def build() -> dict:
    table = authoritative_table()
    return {"audit": audit(), "authoritative": table, "cross_check": cross_check_against_stage_c_report(table), "operations": operations(),
            "paired": {"dev": paired(DEV_JEV), "validation": paired(STAGE_C_JEV)},
            "experiments": {"stage_c_jev": STAGE_C_JEV, "stage_c_llm": STAGE_C_LLM, "dev_jev": DEV_JEV, "dev_llm": DEV_LLM}}


def _p(x, nd=1):
    return f"{x * 100:.{nd}f}%" if x is not None else "n/a"


def to_markdown(r: dict) -> str:
    L = ["# Stage C review: audit and authoritative tables (machine-generated)", "", f"Stage C: Jev `{STAGE_C_JEV}`, LLM `{STAGE_C_LLM}`. Dev reference: Jev `{DEV_JEV}`, LLM `{DEV_LLM}`.", "",
         "## Audit", "", "| Check | Passed | Detail |", "|---|---|---|"]
    L += [f"| {c['check']} | {c['passed']} | {str(c['detail'])[:110]} |" for c in r["audit"]]
    L += ["", "## Dev versus validation (stored registry values)", "", "| Metric | Dev | Validation | Delta pts [95% CI] | Val/dev ratio | Reading |", "|---|---:|---:|---:|---:|---|"]
    for row in r["authoritative"]["accuracy_rows"] + r["authoritative"]["recall_rows"]:
        d, v, dl, ra = row["dev"], row["validation"], row["delta"], row["ratio"]
        rr = f"{ra['ratio']:.2f} [{ra['ci_low']:.2f}, {ra['ci_high']:.2f}]" if ra.get("ci_low") is not None else (f"{ra['ratio']:.2f}" if ra.get("ratio") else "n/a")
        L.append(f"| {row['metric']} | {_p(d['rate'])} ({d['k']}/{d['n']}) | {_p(v['rate'])} ({v['k']}/{v['n']}) | {dl['diff'] * 100:+.1f} [{dl['ci_low'] * 100:+.1f}, {dl['ci_high'] * 100:+.1f}] | {rr} | {row['reading']} |")
    L += ["", f"Dev causal-change runs (stored): {r['authoritative']['dev_causal_runs']}", "", f"Stored values equal the recomputed Stage C values for {sum(c['stored_equals_recomputed'] for c in r['cross_check'])}/{len(r['cross_check'])} metrics.", ""]
    L += ["## Operations, dev versus validation (Jev / LLM)", "", "| Stage | Decision | Jev P50/P90/P95 ms | LLM P50/P90/P95 ms | Jev $ per 1k | LLM $ per 1k | LLM first-attempt valid | Jev API errors |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for stage, block in r["operations"].items():
        for dt in PRIMITIVES:
            j, l = block["jev"][dt], block["llm"][dt]
            L.append(f"| {stage} | {dt} | {j['p50_ms']:.0f}/{j['p90_ms']:.0f}/{j['p95_ms']:.0f} | {l['p50_ms']:.0f}/{l['p90_ms']:.0f}/{l['p95_ms']:.0f} | {j['cost_per_1000_usd']:.3f} | {l['cost_per_1000_usd']:.3f} | {l['first_attempt_valid']}/{l['n']} | {j['api_errors']} |")
    L += ["", "## Paired outcomes", "", "| Split | Decision | Both correct | Only Jev | Only LLM | Both wrong | McNemar p |", "|---|---|---:|---:|---:|---:|---:|"]
    for split, block in r["paired"].items():
        for dt in PRIMITIVES:
            p = block[dt]
            L.append(f"| {split} | {dt} | {p['both_correct']} | {p['only_jev_correct']} | {p['only_llm_correct']} | {p['neither_correct']} | {p['mcnemar_exact_p']:.3f} |")
    return "\n".join(L) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    result = build()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stage_c_review.json").write_text(json.dumps(result, indent=2, default=str))
    (out / "stage_c_review.md").write_text(to_markdown(result))
    failed = [c for c in result["audit"] if not c["passed"]]
    print(out / "stage_c_review.md")
    print(f"audit: {len(result['audit']) - len(failed)}/{len(result['audit'])} checks passed")
    for c in failed:
        print(f"  FAILED: {c['check']} -- {c['detail']}")


if __name__ == "__main__":
    main()
