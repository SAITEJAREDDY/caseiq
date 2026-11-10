"""Analysis of the opaque-key control (JEV-025), exactly as pre-registered in
docs/JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md.

Read-only: it reads stored experiments and the registry, calls no API and no graph, imports no hidden truth (every
scoring field it uses was stored by the run), and writes only under data/eval/jev/analysis/opaque_control/.
The decision rules (R1 accuracy, R2 prediction stability, R3 concentration) are implemented here once and applied
identically to Jev and the LLM. Nothing in this module chooses a threshold from the results.

Usage:
    python3 -m agent.jev_v2.opaque_control_report --control-jev EXP --control-llm EXP [--replicate-jev EXP] [--replicate-llm EXP]
"""
import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from agent.jev_v2 import frozen_config, locked_benchmark
from agent.jev_v2.aggregate import build_report, decision_cost_usd, efficiency_summary
from agent.jev_v2.config import FALSE_CONFIDENT_THRESHOLD
from agent.jev_v2.opaque_control import DECISION, KEY_SCHEME, PROTOCOL, STAGE_C_JEV, STAGE_C_LLM
from agent.jev_v2.paired_stats import mcnemar_exact_p, paired_bootstrap_diff
from agent.jev_v2.registry import load_decisions, load_experiment
from agent.jev_v2.stage_c_report import wilson

OUT_DIR = frozen_config.PROJECT_ROOT / "data" / "eval" / "jev" / "analysis" / "opaque_control"
EXPERIMENTS_DIR = frozen_config.PROJECT_ROOT / "data" / "experiments"
MARGIN = 0.03  # M in the protocol: percentage points on P, a convention fixed before the run
ALPHA = 0.05
GROUPS = ("A", "B", "C", "D", "E")


# ── record helpers ────────────────────────────────────────────────────────────────────
def _by_case(records: list) -> dict:
    return {r["case_id"]: r for r in records if r["decision_type"] == DECISION}


def _real(r) -> int:
    return (r.get("candidate_meta") or {}).get("num_real_change_candidates", 0) or 0


def nontrivial(r) -> bool:
    return _real(r) >= 1


def _ok(r) -> int:
    return 1 if r["scoring"].get("correct") is True else 0


def _pred(r):
    return r["scoring"].get("predicted_value")


def group_of(r) -> str:
    """A/B/C/E as in aggregate.causal_change_recency_categories (evaluator v2.1)."""
    truth = r["scoring"].get("ground_truth_value")
    starts = (r.get("candidate_meta") or {}).get("change_started_ats") or {}
    if truth == "none":
        return "C"
    if truth in starts:
        truth_ts = starts[truth] or ""
        return "B" if any((ts or "") > truth_ts for cid, ts in starts.items() if cid != truth) else "A"
    return "E"


def in_group(r, name: str) -> bool:
    return _real(r) >= 2 if name == "D" else group_of(r) == name


def _rate(k, n):
    return None if not n else k / n


# ── per-arm metrics ───────────────────────────────────────────────────────────────────
def arm_metrics(records: list) -> dict:
    n = len(records)
    present = [r for r in records if r["scoring"].get("candidate_answer_present")]
    exists = [r for r in records if r["scoring"].get("ground_truth_value") != "none"]
    absent = [r for r in records if r["scoring"].get("ground_truth_value") == "none"]
    scored = [r for r in records if r["scoring"].get("predicted_confidence") is not None and r["scoring"].get("correct") is not None]
    confs = [r["scoring"]["predicted_confidence"] for r in scored]
    hc = sum(1 for r in scored if not r["scoring"]["correct"] and r["scoring"]["predicted_confidence"] >= FALSE_CONFIDENT_THRESHOLD)
    ok = sum(_ok(r) for r in records)
    lo, hi = wilson(ok, n) if n else (None, None)
    return {
        "n": n, "correct": ok, "accuracy": _rate(ok, n), "accuracy_wilson_ci": [lo, hi],
        "candidate_recall": _rate(len(present), n),
        "conditional_accuracy": _rate(sum(_ok(r) for r in present), len(present)), "n_true_offered": len(present),
        "detection_rate": _rate(sum(_ok(r) for r in exists), len(exists)), "n_true_change_exists": len(exists),
        "no_change_false_positive_rate": _rate(sum(1 for r in absent if r["scoring"].get("false_positive")), len(absent)), "n_no_change": len(absent),
        "distractor_selection_rate": _rate(sum(1 for r in records if r["scoring"].get("distractor_selected")), n),
        "high_confidence_errors": hc, "high_confidence_error_rate": _rate(hc, n),
        "mean_confidence": statistics.fmean(confs) if confs else None,
        "answered_none_share": _rate(sum(1 for r in records if _pred(r) == "none"), n),
    }


def contract_block(records: list) -> dict:
    """LLM: strict and repaired contract behaviour. Jev: request status."""
    n = len(records)
    out = {"n": n, "status_ok": sum(1 for r in records if r.get("status") == "ok")}
    if records and "attempts" in records[0]:
        first_valid = sum(1 for r in records if r.get("first_attempt_valid"))
        out.update({
            "first_attempt_valid": first_valid, "first_attempt_valid_rate": _rate(first_valid, n),
            "first_attempt_failures": dict(Counter(r.get("first_attempt_failure") for r in records if r.get("first_attempt_failure"))),
            "repair_required": sum(1 for r in records if r.get("repair_required")),
            "repair_succeeded": sum(1 for r in records if r.get("repair_succeeded")),
            "unrecoverable": sum(1 for r in records if r.get("unrecoverable_failure")),
            "strict_first_attempt_correct": sum(1 for r in records if r.get("first_attempt_valid") and _ok(r)),
        })
    return out


def efficiency_block(records: list) -> dict:
    e = efficiency_summary(records)
    return {"total_cost_usd": sum(c for c in (decision_cost_usd(r) for r in records) if c is not None),
            "total_input_tokens": e["total_input_tokens"], "mean_input_tokens": e["mean_input_tokens"],
            "p50_latency_ms": e["p50_latency_ms"], "p95_latency_ms": e["p95_latency_ms"], "n": len(records)}


# ── paired comparison ─────────────────────────────────────────────────────────────────
def pair_block(canon: dict, other: dict, cases: list) -> dict:
    """Canonical (reference) vs another arm on the same decisions. delta = other minus canonical."""
    cases = [c for c in cases if c in canon and c in other]
    a = [_ok(canon[c]) for c in cases]
    b_ = [_ok(other[c]) for c in cases]
    cc = sum(1 for x, y in zip(a, b_) if x and y)
    cw = sum(1 for x, y in zip(a, b_) if x and not y)  # b: correct under canonical, wrong under the other arm
    wc = sum(1 for x, y in zip(a, b_) if not x and y)  # c
    ww = sum(1 for x, y in zip(a, b_) if not x and not y)
    same = sum(1 for c in cases if _pred(canon[c]) == _pred(other[c]))
    lo, hi = wilson(same, len(cases)) if cases else (None, None)
    boot = paired_bootstrap_diff(b_, a) if cases else {"diff": None, "ci_low": None, "ci_high": None}
    return {
        "n": len(cases), "canonical_correct_opaque_correct": cc, "b_canonical_correct_opaque_wrong": cw, "c_canonical_wrong_opaque_correct": wc,
        "canonical_wrong_opaque_wrong": ww, "mcnemar_p": mcnemar_exact_p(cw, wc),
        "canonical_accuracy": _rate(sum(a), len(cases)), "opaque_accuracy": _rate(sum(b_), len(cases)),
        "delta": boot["diff"], "delta_ci": [boot["ci_low"], boot["ci_high"]],
        "same_choice": same, "different_choice": len(cases) - same, "semantic_agreement": _rate(same, len(cases)), "semantic_agreement_wilson_ci": [lo, hi],
        "wrong_to_different_wrong": sum(1 for x, y, c in zip(a, b_, cases) if not x and not y and _pred(canon[c]) != _pred(other[c])),
    }


def group_table(canon: dict, other: dict, cases: list) -> dict:
    out = {}
    for g in GROUPS:
        ids = [c for c in cases if c in canon and c in other and in_group(canon[c], g)]
        p = pair_block(canon, other, ids)
        out[g] = {"n": p["n"], "canonical_accuracy": p["canonical_accuracy"], "opaque_accuracy": p["opaque_accuracy"],
                  "b": p["b_canonical_correct_opaque_wrong"], "c": p["c_canonical_wrong_opaque_correct"], "different_choice": p["different_choice"]}
    return out


def _num(cid: str):
    digits = "".join(ch for ch in cid if ch.isdigit())
    return int(digits) if digits else None


def group_b_audit(canon_j, opq_j, canon_l, opq_l, cases: list) -> list:
    rows = []
    for c in cases:
        r = canon_j[c]
        if group_of(r) != "B":
            continue
        truth = r["scoring"]["ground_truth_value"]
        real = [k for k in r["candidates"] if k != "none"]
        highest = max(real, key=lambda k: _num(k) or 0)
        rows.append({
            "case_id": c, "n_candidates_incl_none": len(r["candidates"]), "true": truth, "true_has_highest_id_number": truth == highest,
            "jev_canonical": _pred(canon_j[c]), "jev_opaque": _pred(opq_j[c]), "llm_canonical": _pred(canon_l[c]), "llm_opaque": _pred(opq_l[c]),
            "jev_changed": _pred(canon_j[c]) != _pred(opq_j[c]), "llm_changed": _pred(canon_l[c]) != _pred(opq_l[c]),
            "jev_correct_canonical_opaque": [bool(_ok(canon_j[c])), bool(_ok(opq_j[c]))], "llm_correct_canonical_opaque": [bool(_ok(canon_l[c])), bool(_ok(opq_l[c]))],
        })
    return rows


# ── pre-registered rules ──────────────────────────────────────────────────────────────
def rule_r1(pair_p: dict) -> dict:
    b, c, p, delta, lo = pair_p["b_canonical_correct_opaque_wrong"], pair_p["c_canonical_wrong_opaque_correct"], pair_p["mcnemar_p"], pair_p["delta"], pair_p["delta_ci"][0]
    drop = b > c and p < ALPHA
    material = drop and delta <= -MARGIN
    preserved = (not drop) and lo is not None and lo > -MARGIN
    verdict = "MATERIAL_DROP" if material else ("PRESERVED" if preserved else ("DROP_NOT_MATERIAL" if drop else "UNRESOLVED"))
    return {"verdict": verdict, "drop": drop, "material_drop": material, "preserved": preserved, "b": b, "c": c, "p": p, "delta": delta, "ci_low": lo}


def rule_r2(canon: dict, opaque: dict, replicate: dict, cases_p: list) -> dict:
    cases = [c for c in cases_p if c in canon and c in opaque]
    disagree_opaque = [1 if _pred(canon[c]) != _pred(opaque[c]) else 0 for c in cases]
    d = sum(disagree_opaque)
    out = {"n": len(cases), "disagreements": d, "disagreement_rate": _rate(d, len(cases))}
    if d == 0:
        return {**out, "verdict": "STABLE", "replicate": "not needed (no disagreement)"}
    if not replicate:
        return {**out, "verdict": "REPLICATE_NEEDED", "replicate": "not run"}
    cases = [c for c in cases if c in replicate]
    x = [1 if _pred(canon[c]) != _pred(opaque[c]) else 0 for c in cases]
    y = [1 if _pred(canon[c]) != _pred(replicate[c]) else 0 for c in cases]
    only_opaque = sum(1 for u, v in zip(x, y) if u and not v)
    only_replicate = sum(1 for u, v in zip(x, y) if v and not u)
    p = mcnemar_exact_p(only_opaque, only_replicate)
    excess = (sum(x) - sum(y)) / len(cases)
    sensitive = excess >= MARGIN and p < ALPHA and only_opaque > only_replicate
    return {**out, "n": len(cases), "disagreements": sum(x), "disagreement_rate": _rate(sum(x), len(cases)),
            "replicate_disagreements": sum(y), "replicate_disagreement_rate": _rate(sum(y), len(cases)), "excess": excess,
            "only_under_opaque": only_opaque, "only_under_replicate": only_replicate, "mcnemar_p": p,
            "verdict": "SENSITIVE" if sensitive else "STABLE", "replicate": "run"}


def rule_r3(groups: dict) -> dict:
    b_group = groups["B"]
    net = b_group["b"] - b_group["c"]
    return {"group_b_n": b_group["n"], "group_b_net_loss": net, "cap_applies": net >= 2}


def verdict_for(r1: dict, r2: dict, r3: dict, b: int, c: int) -> dict:
    if r2["verdict"] == "REPLICATE_NEEDED":
        return {"label": "PENDING: canonical replicate needed before the prediction-stability rule can be applied", "code": "pending"}
    if r1["verdict"] == "MATERIAL_DROP" or (r2["verdict"] == "SENSITIVE" and b > c):
        return {"label": "MATERIAL ID DEPENDENCE DETECTED", "code": "material"}
    if r1["verdict"] == "PRESERVED" and r2["verdict"] == "STABLE" and not r3["cap_applies"]:
        return {"label": "NO MATERIAL ID DEPENDENCE DETECTED", "code": "none"}
    return {"label": "POSSIBLE ID SENSITIVITY / INCONCLUSIVE", "code": "possible"}


# ── exploratory (labelled; no decision role) ──────────────────────────────────────────
def probability_shift(canon: dict, opaque: dict, cases: list) -> dict:
    """Jev only: change in the probability given to the true change when it is offered (P decisions)."""
    shifts, signed = [], []
    for c in cases:
        r, o = canon[c], opaque[c]
        truth = r["scoring"].get("ground_truth_value")
        if truth == "none" or not r["scoring"].get("candidate_answer_present"):
            continue
        p1, p2 = (r["scoring"].get("probabilities") or {}).get(truth), (o["scoring"].get("probabilities") or {}).get(truth)
        if p1 is not None and p2 is not None:
            shifts.append(abs(p1 - p2))
            signed.append(p2 - p1)
    if not shifts:
        return {"n": 0}
    return {"n": len(shifts), "mean_abs_shift": statistics.fmean(shifts), "median_abs_shift": statistics.median(shifts),
            "mean_signed_shift_opaque_minus_canonical": statistics.fmean(signed),
            "share_over_0.10": sum(1 for s in shifts if s > 0.10) / len(shifts), "max_abs_shift": max(shifts)}


def flip_anatomy(canon: dict, other: dict, cases: list) -> dict:
    """Exploratory: what the changed answers changed to. `none` versus a real change is the only distinction the options allow
    besides which real change was chosen."""
    kind = lambda v: "none" if v == "none" else ("no answer" if v is None else "real change")
    counts = Counter()
    for c in cases:
        if c in canon and c in other and _pred(canon[c]) != _pred(other[c]):
            a, b = kind(_pred(canon[c])), kind(_pred(other[c]))
            counts[f"{a} -> {b}" + (" (different real change)" if a == b == "real change" else "")] += 1
    return dict(counts)


def systems_under_each_scheme(jev_c: dict, llm_c: dict, jev_o: dict, llm_o: dict, cases: list) -> dict:
    """Exploratory (not pre-registered, no decision role): the Jev-versus-LLM causal-change comparison under each key scheme,
    paired by decision. Shows whether the Stage C lead depends on the option keys."""
    cases_p = [c for c in cases if nontrivial(jev_c[c])]
    out = {}
    for scheme, (j, l) in (("canonical", (jev_c, llm_c)), ("opaque", (jev_o, llm_o))):
        for pop, ids in (("ALL", cases), ("P", cases_p)):
            jf, lf = [_ok(j[c]) for c in ids], [_ok(l[c]) for c in ids]
            only_j = sum(1 for x, y in zip(jf, lf) if x and not y)
            only_l = sum(1 for x, y in zip(jf, lf) if y and not x)
            boot = paired_bootstrap_diff(jf, lf)
            out[f"{scheme}_{pop}"] = {"n": len(ids), "jev_accuracy": sum(jf) / len(ids), "llm_accuracy": sum(lf) / len(ids), "jev_minus_llm": boot["diff"],
                                      "ci": [boot["ci_low"], boot["ci_high"]], "only_jev_correct": only_j, "only_llm_correct": only_l, "mcnemar_p": mcnemar_exact_p(only_j, only_l)}
    return out


def highest_id_context(records: dict, cases: list) -> dict:
    """Context for why the control matters: when a true change was offered alongside another real candidate, how often is the
    true one also the numerically highest id (Stage C data, canonical arm)?"""
    multi = [records[c] for c in cases if records[c]["scoring"].get("ground_truth_value") != "none" and records[c]["scoring"].get("candidate_answer_present") and _real(records[c]) >= 2]
    hit = sum(1 for r in multi if r["scoring"]["ground_truth_value"] == max((k for k in r["candidates"] if k != "none"), key=lambda k: _num(k) or 0))
    return {"n_decisions": len(multi), "true_change_has_highest_id_number": hit}


# ── integrity ─────────────────────────────────────────────────────────────────────────
def integrity(control_exps: dict, control_recs: dict, canon: dict, reference_case_ids: list, replicates: dict = None) -> list:
    checks = []

    def add(label, passed, detail=""):
        checks.append({"check": label, "passed": bool(passed), "detail": detail})

    for label, exp in control_exps.items():
        add(f"{label}: kind validation_control on the validation split, {len(reference_case_ids)} cases in the Stage C order",
            exp["kind"] == "validation_control" and exp["dataset_split"] == "validation" and exp["case_ids"] == reference_case_ids, f"{exp['kind']}/{exp['dataset_split']}/{len(exp['case_ids'])}")
        add(f"{label}: option keys are the pre-registered hashed opaque scheme", exp["config"]["causal_key_mode"] == KEY_SCHEME, exp["config"]["causal_key_mode"])
        protocol = exp["config"].get("pre_registered_protocol") or {}
        add(f"{label}: pre-registered protocol digest recorded on the run equals the file today",
            protocol.get("sha256") == frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / protocol.get("path", "")) and protocol.get("path") == PROTOCOL, (protocol.get("sha256") or "")[:16])
        control = exp["config"]["control"]
        add(f"{label}: input checks passed for all cases before any call (reference equality, only-the-keys-differ, no canonical id in an opaque request)",
            control["input_checks"]["cases_with_problems"] == 0 and control["input_checks"]["checked"] == len(reference_case_ids), str(control["input_checks"]))
        add(f"{label}: locked config and manifest digests at run time equal today's (and the run state was empty)",
            control["locked_config_sha256_at_run"] == frozen_config.load_manifest(locked_benchmark.NAME)["config_sha256"]
            and control["locked_manifest_sha256_at_run"] == frozen_config.sha256_file(locked_benchmark.manifest_path(locked_benchmark.NAME)) and control["locked_run_state_at_run"] is None)
    for label, recs in control_recs.items():
        by = _by_case(recs)
        add(f"{label}: exactly one causal-change decision per case, all status ok", len(by) == len(recs) == len(reference_case_ids) and all(r.get("status") == "ok" for r in recs), f"{len(recs)} records")
        ref = canon["jev" if label.startswith("Jev") else "llm"]
        add(f"{label}: candidates, candidate metadata and candidate recall identical to Stage C for every case (else the control is invalid)",
            all(by[c]["candidates"] == ref[c]["candidates"] and by[c]["candidate_meta"]["ordered_candidate_ids"] == ref[c]["candidate_meta"]["ordered_candidate_ids"]
                and by[c]["scoring"].get("candidate_answer_present") == ref[c]["scoring"].get("candidate_answer_present") for c in reference_case_ids))
        add(f"{label}: every non-trivial decision carries the alias map and every answer maps back into that decision's canonical candidates",
            all((by[c]["candidate_meta"].get("alias_to_id") or {}) or not nontrivial(by[c]) for c in reference_case_ids)
            and all(_pred(by[c]) is None or _pred(by[c]) in by[c]["candidates"] for c in reference_case_ids))
    jev_models = {r.get("jev_model") for r in control_recs["Jev opaque"]}
    add("Jev: every control decision resolved to the model version Stage C used", jev_models == {r.get("jev_model") for r in canon["jev"].values()}, str(jev_models))
    llm_models = {r.get("model") for r in control_recs["LLM opaque"]} | {r.get("model") for r in canon["llm"].values()}
    add("LLM: same model, temperature as Stage C", len(llm_models) == 1 and {r.get("temperature") for r in control_recs["LLM opaque"]} == {r.get("temperature") for r in canon["llm"].values()}, str(llm_models))
    for label, (exp, recs_, ref) in (replicates or {}).items():
        by = _by_case(recs_)
        p_cases = [c for c in reference_case_ids if nontrivial(ref[c])]
        protocol = exp["config"].get("pre_registered_protocol") or {}
        add(f"{label}: kind validation_control, validation split, exactly the non-trivial (P) decisions, canonical keys, protocol digest matches",
            exp["kind"] == "validation_control" and exp["dataset_split"] == "validation" and exp["case_ids"] == p_cases and exp["config"]["causal_key_mode"] == "canonical"
            and protocol.get("sha256") == frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / protocol.get("path", "")), f"{len(exp['case_ids'])} cases")
        add(f"{label}: one decision per case, all status ok, inputs identical to Stage C (candidates, order, candidate metadata)",
            len(by) == len(recs_) == len(p_cases) and all(r.get("status") == "ok" for r in recs_)
            and all(by[c]["candidates"] == ref[c]["candidates"] and json.dumps(by[c]["candidate_meta"], sort_keys=True) == json.dumps(ref[c]["candidate_meta"], sort_keys=True) for c in p_cases))
    pins = frozen_config.load_manifest(locked_benchmark.NAME)["pinned_files"]
    add("Stage C experiments and decisions are byte-identical to the digests the locked freeze pinned",
        all(frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / pins[k]["path"]) == pins[k]["sha256"]
            for k in ("stage_c_jev_experiment", "stage_c_jev_decisions", "stage_c_llm_experiment", "stage_c_llm_decisions", "stage_c_report", "stage_c_protocol")))
    add("locked benchmark verification is clean (config, manifest, 44 pinned sources, protocol, split files unchanged)", locked_benchmark.verify() == [], str(locked_benchmark.verify()[:2]))
    add("no locked run-state marker exists", locked_benchmark.read_run_state() is None)
    registry = [json.loads(line) for line in open(EXPERIMENTS_DIR / "registry.jsonl") if line.strip()]
    add("registry: no experiment carries dataset_split 'test' or kind 'locked_benchmark'", not any(r.get("dataset_split") == "test" or r.get("kind") == "locked_benchmark" for r in registry),
        str(dict(Counter((r.get("dataset_split"), r.get("kind")) for r in registry if r.get("kind") in ("validation", "validation_control")))))
    locked_benchmark.assert_not_locked_ids(reference_case_ids)
    add("every control case id is in the validation split", True)
    return checks


# ── build ─────────────────────────────────────────────────────────────────────────────
def system_block(name: str, canon: dict, opaque: dict, replicate: dict, cases: list) -> dict:
    cases_p = [c for c in cases if nontrivial(canon[c])]
    cases_t = [c for c in cases if not nontrivial(canon[c])]
    all_pair, p_pair, t_pair = pair_block(canon, opaque, cases), pair_block(canon, opaque, cases_p), pair_block(canon, opaque, cases_t)
    groups = group_table(canon, opaque, cases)
    r1, r2, r3 = rule_r1(p_pair), rule_r2(canon, opaque, replicate, cases_p), rule_r3(groups)
    verdict = verdict_for(r1, r2, r3, p_pair["b_canonical_correct_opaque_wrong"], p_pair["c_canonical_wrong_opaque_correct"])
    canon_recs, opaque_recs = [canon[c] for c in cases], [opaque[c] for c in cases]
    block = {
        "system": name, "n_all": len(cases), "n_nontrivial": len(cases_p), "n_trivial": len(cases_t),
        "metrics": {"ALL": {"canonical": arm_metrics(canon_recs), "opaque": arm_metrics(opaque_recs)},
                    "P": {"canonical": arm_metrics([canon[c] for c in cases_p]), "opaque": arm_metrics([opaque[c] for c in cases_p])}},
        "pairs": {"ALL": all_pair, "P": p_pair, "T": t_pair}, "groups": groups, "flip_anatomy_P": flip_anatomy(canon, opaque, cases_p),
        "answered_none_share_P": {"canonical": arm_metrics([canon[c] for c in cases_p])["answered_none_share"], "opaque": arm_metrics([opaque[c] for c in cases_p])["answered_none_share"]},
        "rules": {"R1": r1, "R2": r2, "R3": r3}, "verdict": verdict,
        "contract": {"canonical": contract_block(canon_recs), "opaque": contract_block(opaque_recs)},
        "efficiency": {"canonical": efficiency_block(canon_recs), "opaque": efficiency_block(opaque_recs)},
        "recall_identical": arm_metrics(canon_recs)["candidate_recall"] == arm_metrics(opaque_recs)["candidate_recall"],
    }
    if replicate:
        rc = [c for c in cases_p if c in replicate]
        block["replicate"] = {"n": len(rc), "pair_vs_canonical": pair_block(canon, replicate, rc), "metrics": arm_metrics([replicate[c] for c in rc]),
                              "contract": contract_block([replicate[c] for c in rc]), "efficiency": efficiency_block([replicate[c] for c in rc])}
        block["opaque_vs_replicate_on_P"] = pair_block(replicate, opaque, rc)
        block["flip_anatomy_replicate_vs_canonical_P"] = flip_anatomy(canon, replicate, rc)
        block["answered_none_share_P"]["replicate"] = arm_metrics([replicate[c] for c in rc])["answered_none_share"]
    return block


def build(control_jev: str, control_llm: str, replicate_jev: str = None, replicate_llm: str = None) -> dict:
    canon = {"jev": _by_case(load_decisions(STAGE_C_JEV)), "llm": _by_case(load_decisions(STAGE_C_LLM))}
    stage_c = load_experiment(STAGE_C_JEV)
    case_ids = stage_c["case_ids"]
    exps = {"Jev opaque": load_experiment(control_jev), "LLM opaque": load_experiment(control_llm)}
    recs = {"Jev opaque": load_decisions(control_jev), "LLM opaque": load_decisions(control_llm)}
    opaque = {"jev": _by_case(recs["Jev opaque"]), "llm": _by_case(recs["LLM opaque"])}
    replicate = {"jev": _by_case(load_decisions(replicate_jev)) if replicate_jev else None, "llm": _by_case(load_decisions(replicate_llm)) if replicate_llm else None}
    # Cross-check: the ALL-population accuracy computed here equals the accuracy the registry stored for the Stage C causal block.
    stored = {s: build_report(list(canon[s].values()))[DECISION]["accuracy"] for s in ("jev", "llm")}
    computed = {s: arm_metrics(list(canon[s].values()))["accuracy"] for s in ("jev", "llm")}
    report = {
        "protocol": PROTOCOL, "protocol_sha256": frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / PROTOCOL), "margin_M": MARGIN, "alpha": ALPHA,
        "experiments": {"reference_jev": STAGE_C_JEV, "reference_llm": STAGE_C_LLM, "control_jev": control_jev, "control_llm": control_llm,
                        "replicate_jev": replicate_jev, "replicate_llm": replicate_llm},
        "integrity": integrity(exps, recs, canon, case_ids, {label: (load_experiment(eid), load_decisions(eid), canon[s]) for label, eid, s in
                                                             (("Jev replicate", replicate_jev, "jev"), ("LLM replicate", replicate_llm, "llm")) if eid}),
        "cross_check_stage_c_accuracy": {"stored": stored, "recomputed": computed, "equal": all(abs(stored[s] - computed[s]) < 1e-12 for s in stored)},
        "jev": system_block("Jev", canon["jev"], opaque["jev"], replicate["jev"], case_ids),
        "llm": system_block("LLM", canon["llm"], opaque["llm"], replicate["llm"], case_ids),
        "group_b_audit": group_b_audit(canon["jev"], opaque["jev"], canon["llm"], opaque["llm"], case_ids),
        "exploratory": {"jev_vs_llm_under_each_scheme": systems_under_each_scheme(canon["jev"], canon["llm"], opaque["jev"], opaque["llm"], case_ids),
                        "jev_probability_shift_on_true_change": probability_shift(canon["jev"], opaque["jev"], [c for c in case_ids if nontrivial(canon["jev"][c])]),
                        "highest_id_context": highest_id_context(canon["jev"], case_ids)},
        "cost": {"jev_opaque_usd": sum(c for c in (decision_cost_usd(r) for r in recs["Jev opaque"]) if c is not None),
                 "llm_opaque_usd": sum(c for c in (decision_cost_usd(r) for r in recs["LLM opaque"]) if c is not None),
                 "decisions_per_system": len(case_ids)},
    }
    return report


# ── markdown ──────────────────────────────────────────────────────────────────────────
def _p(x, nd=1):
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def _pp(x, nd=1):
    return "n/a" if x is None else f"{x * 100:+.{nd}f}"


def _ci(ci):
    return "n/a" if not ci or ci[0] is None else f"[{ci[0] * 100:.1f}, {ci[1] * 100:.1f}]"


def _metric_rows(block: dict, pop: str) -> list:
    can, opq = block["metrics"][pop]["canonical"], block["metrics"][pop]["opaque"]
    pair = block["pairs"][pop]
    rows = [("Accuracy", _p(can["accuracy"]), _p(opq["accuracy"]), f"{_pp(pair['delta'])} pp {_ci(pair['delta_ci'])}"),
            ("Conditional accuracy (true change offered)", _p(can["conditional_accuracy"]), _p(opq["conditional_accuracy"]), _pp(None if can["conditional_accuracy"] is None else opq["conditional_accuracy"] - can["conditional_accuracy"])),
            ("Candidate recall", _p(can["candidate_recall"]), _p(opq["candidate_recall"]), "identical" if can["candidate_recall"] == opq["candidate_recall"] else "DIFFERS"),
            ("Detection rate (a true change exists)", f"{_p(can['detection_rate'])} (n={can['n_true_change_exists']})", f"{_p(opq['detection_rate'])}", _pp(None if can["detection_rate"] is None else opq["detection_rate"] - can["detection_rate"])),
            ("No-change false-positive rate", f"{_p(can['no_change_false_positive_rate'])} (n={can['n_no_change']})", _p(opq["no_change_false_positive_rate"]), _pp(None if can["no_change_false_positive_rate"] is None else opq["no_change_false_positive_rate"] - can["no_change_false_positive_rate"])),
            ("Distractor-selection rate", _p(can["distractor_selection_rate"]), _p(opq["distractor_selection_rate"]), _pp(None if can["distractor_selection_rate"] is None else opq["distractor_selection_rate"] - can["distractor_selection_rate"])),
            ("High-confidence errors (wrong at conf >= 0.90)", str(can["high_confidence_errors"]), str(opq["high_confidence_errors"]), f"{opq['high_confidence_errors'] - can['high_confidence_errors']:+d}"),
            ("Semantic agreement (same choice in both arms)", "", f"{_p(pair['semantic_agreement'])} {_ci(pair['semantic_agreement_wilson_ci'])}", f"{pair['different_choice']} of {pair['n']} differ")]
    return rows


def _system_md(block: dict, title: str) -> list:
    v = block["verdict"]
    lines = [f"## {title}", "", f"Decisions: {block['n_all']} (P non-trivial {block['n_nontrivial']}, T none-only {block['n_trivial']}).", ""]
    for pop, label in (("P", "Primary population P (a real change was offered)"), ("ALL", "All decisions (comparable to the Stage C headline)")):
        lines += [f"### {label}", "", "| Metric | Canonical ids | Opaque keys | Delta (opaque - canonical) |", "|---|---:|---:|---:|"]
        lines += [f"| {m} | {a} | {b} | {d} |" for m, a, b, d in _metric_rows(block, pop)]
        pr = block["pairs"][pop]
        lines += ["", f"Paired outcomes (canonical / opaque): correct/correct {pr['canonical_correct_opaque_correct']}, correct/wrong {pr['b_canonical_correct_opaque_wrong']}, "
                      f"wrong/correct {pr['c_canonical_wrong_opaque_correct']}, wrong/wrong {pr['canonical_wrong_opaque_wrong']} "
                      f"(of which a different wrong choice: {pr['wrong_to_different_wrong']}). Exact McNemar p = {pr['mcnemar_p']:.3f}.", ""]
    t = block["pairs"]["T"]
    lines += [f"Negative control T (none-only decisions, byte-identical input): the same choice in {t['same_choice']} of {t['n']}; correct/wrong {t['b_canonical_correct_opaque_wrong']}, wrong/correct {t['c_canonical_wrong_opaque_correct']}.", ""]
    c, o = block["contract"]["canonical"], block["contract"]["opaque"]
    if "first_attempt_valid" in c:
        lines += [f"Contract (all decisions): first-attempt valid {c['first_attempt_valid']} of {c['n']} canonical vs {o['first_attempt_valid']} of {o['n']} opaque; repair required {c['repair_required']} vs {o['repair_required']}; "
                  f"unrecoverable {c['unrecoverable']} vs {o['unrecoverable']}; first-attempt failures canonical {c['first_attempt_failures']} vs opaque {o['first_attempt_failures']}; "
                  f"strict first-attempt correct {c['strict_first_attempt_correct']} vs {o['strict_first_attempt_correct']}.", ""]
    r1, r2, r3 = block["rules"]["R1"], block["rules"]["R2"], block["rules"]["R3"]
    lines += ["### Pre-registered rules", "",
              f"- R1 accuracy on P: **{r1['verdict']}** (b={r1['b']}, c={r1['c']}, McNemar p={r1['p']:.3f}, delta {_pp(r1['delta'])} pp, 95% CI lower bound {_pp(r1['ci_low'])} pp; M = {MARGIN * 100:.0f} pp).",
              f"- R2 prediction stability on P: **{r2['verdict']}** (disagreements {r2['disagreements']} of {r2['n']} = {_p(r2['disagreement_rate'])}; replicate: {r2['replicate']}"
              + (f"; replicate disagreement {r2['replicate_disagreements']} of {r2['n']} = {_p(r2['replicate_disagreement_rate'])}, excess {_pp(r2['excess'])} pp, only-under-opaque {r2['only_under_opaque']} vs only-under-replicate {r2['only_under_replicate']}, McNemar p={r2['mcnemar_p']:.3f}" if "excess" in r2 else "") + ").",
              f"- R3 concentration: group B n={r3['group_b_n']}, net loss {r3['group_b_net_loss']}, cap {'APPLIES' if r3['cap_applies'] else 'does not apply'}.",
              f"- **Verdict: {v['label']}.**", ""]
    an = block["answered_none_share_P"]
    lines += [f"Exploratory (no decision role): share of P decisions answered `none` {_p(an['canonical'])} canonical, {_p(an['opaque'])} opaque" + (f", {_p(an['replicate'])} canonical replicate" if "replicate" in an else "")
              + f". What the changed answers changed to (canonical -> opaque): {block['flip_anatomy_P']}" + (f"; canonical -> replicate: {block['flip_anatomy_replicate_vs_canonical_P']}" if "flip_anatomy_replicate_vs_canonical_P" in block else "") + ".", ""]
    if "replicate" in block:
        rp = block["replicate"]
        lines += [f"Canonical replicate on P ({rp['n']} decisions): accuracy {_p(rp['metrics']['accuracy'])} against {_p(block['metrics']['P']['canonical']['accuracy'])} in Stage C and {_p(block['metrics']['P']['opaque']['accuracy'])} under opaque keys; "
                  f"the replicate differs from Stage C on {rp['pair_vs_canonical']['different_choice']} decisions (correct/wrong {rp['pair_vs_canonical']['b_canonical_correct_opaque_wrong']}, wrong/correct {rp['pair_vs_canonical']['c_canonical_wrong_opaque_correct']}). "
                  f"Opaque against the replicate: {block['opaque_vs_replicate_on_P']['different_choice']} different choices.", ""]
    return lines


def to_markdown(r: dict) -> str:
    ex = r["experiments"]
    lines = ["# Opaque-key control: measured results (generated)", "",
             f"Protocol `{r['protocol']}` (sha256 `{r['protocol_sha256']}`), M = {MARGIN * 100:.0f} pp, alpha = {ALPHA}.", "",
             "| Role | Experiment |", "|---|---|"] + [f"| {k} | `{v}` |" for k, v in ex.items() if v]
    lines += ["", "## A. Control integrity", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {c['check']} | {'pass' if c['passed'] else '**FAIL**'} |" for c in r["integrity"]]
    cc = r["cross_check_stage_c_accuracy"]
    lines += ["", f"Stage C causal-change accuracy recomputed here equals the stored registry value: {cc['equal']} (Jev {cc['recomputed']['jev']:.4f}, LLM {cc['recomputed']['llm']:.4f}).", ""]
    lines += _system_md(r["jev"], "B. Jev") + _system_md(r["llm"], "C. LLM baseline")
    lines += ["## D. Recency groups (canonical accuracy / opaque accuracy; b = correct-to-wrong, c = wrong-to-correct flips; differ = different choice)", "",
              "| Group | n | Jev canonical | Jev opaque | Jev b/c | Jev differ | LLM canonical | LLM opaque | LLM b/c | LLM differ |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    labels = {"A": "A true change is the newest", "B": "B true change older than a newer candidate", "C": "C no causal change", "D": "D two or more real candidates (overlaps)", "E": "E true change not offered"}
    for g in GROUPS:
        j, l = r["jev"]["groups"][g], r["llm"]["groups"][g]
        lines.append(f"| {labels[g]} | {j['n']} | {_p(j['canonical_accuracy'])} | {_p(j['opaque_accuracy'])} | {j['b']}/{j['c']} | {j['different_choice']} | {_p(l['canonical_accuracy'])} | {_p(l['opaque_accuracy'])} | {l['b']}/{l['c']} | {l['different_choice']} |")
    lines += ["", "### Group B audit (small sample: this cannot establish or exclude dependence by itself)", "",
              "| Case | Candidates (incl. none) | True | True has highest id | Jev canonical | Jev opaque | LLM canonical | LLM opaque | Jev changed | LLM changed |", "|---|---:|---|---|---|---|---|---|---|---|"]
    for a in r["group_b_audit"]:
        lines.append(f"| {a['case_id']} | {a['n_candidates_incl_none']} | {a['true']} | {'yes' if a['true_has_highest_id_number'] else 'no'} | {a['jev_canonical']} | {a['jev_opaque']} | {a['llm_canonical']} | {a['llm_opaque']} | {'yes' if a['jev_changed'] else 'no'} | {'yes' if a['llm_changed'] else 'no'} |")
    ex_ = r["exploratory"]
    lines += ["", "## E. Pre-registered verdicts (mechanical)", "", f"- Jev (the gate): **{r['jev']['verdict']['label']}**", f"- LLM (informative, not a gate): **{r['llm']['verdict']['label']}**", "",
              "## Exploratory (labelled, no decision role)", "",
              "- Jev versus the LLM, paired by decision, under each key scheme (Jev minus LLM accuracy with a paired 95% interval; exact McNemar on decisions only one of them got right):", "",
              "| Keys | Population | n | Jev | LLM | Jev - LLM | only Jev right / only LLM right | McNemar p |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for k, v in ex_["jev_vs_llm_under_each_scheme"].items():
        scheme, pop = k.split("_")
        lines.append(f"| {scheme} | {pop} | {v['n']} | {_p(v['jev_accuracy'])} | {_p(v['llm_accuracy'])} | {_pp(v['jev_minus_llm'])} pp {_ci(v['ci'])} | {v['only_jev_correct']} / {v['only_llm_correct']} | {v['mcnemar_p']:.3f} |")
    lines += ["",
              f"- Jev: absolute change in the probability given to the true change, over decisions where it was offered: {json.dumps(ex_['jev_probability_shift_on_true_change'])}.",
              f"- Context: when the true change was offered next to another real candidate ({ex_['highest_id_context']['n_decisions']} decisions), its id number was the highest in {ex_['highest_id_context']['true_change_has_highest_id_number']}.", "",
              "## Cost and latency (8 workers, as in Stage C)", "", "| System | Arm | Decisions | Cost (USD) | Mean input tokens | P50 latency (ms) | P95 latency (ms) |", "|---|---|---:|---:|---:|---:|---:|"]
    for s, name in (("jev", "Jev"), ("llm", "LLM")):
        for arm in ("canonical", "opaque"):
            e = r[s]["efficiency"][arm]
            lines.append(f"| {name} | {arm} (all decisions) | {e['n']} | {e['total_cost_usd']:.4f} | {e['mean_input_tokens']:.0f} | {e['p50_latency_ms']:.0f} | {e['p95_latency_ms']:.0f} |")
    lines += ["", f"Control cost (this run only): Jev ${r['cost']['jev_opaque_usd']:.4f}, LLM ${r['cost']['llm_opaque_usd']:.4f}; Turbo pricing is a versioned assumption.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-jev", required=True)
    parser.add_argument("--control-llm", required=True)
    parser.add_argument("--replicate-jev")
    parser.add_argument("--replicate-llm")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()
    report = build(args.control_jev, args.control_llm, args.replicate_jev, args.replicate_llm)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "opaque_control.json").write_text(json.dumps(report, indent=2, default=str))
    (out / "opaque_control.md").write_text(to_markdown(report))
    print(f"wrote {out}/opaque_control.json and .md")
    print(f"Jev: {report['jev']['verdict']['label']}\nLLM: {report['llm']['verdict']['label']}")
    failed = [c["check"] for c in report["integrity"] if not c["passed"]]
    if failed:
        print("INTEGRITY FAILURES:", failed)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
