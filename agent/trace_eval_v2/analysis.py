"""Phase 8 analysis: stored judge outputs + reference labels -> the capability report. Read-only (no API, no graph); hidden truth enters only through the stored reference labels, and only here,
after every judge has answered. Nothing in this module changes a question, a label or a threshold.

The capability rubric and its constants are pre-registered in docs/TRACE_EVAL_PREREGISTRATION.md (its sha256 is recorded on every experiment). They are conventions fixed before the main
run, not derived from results.
"""
import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from agent.jev_v2.aggregate import decision_cost_usd
from agent.trace_eval_v2 import metrics as M
from agent.trace_eval_v2 import scorer
from agent.trace_eval_v2.config import EXPERIMENTS_DIR, JUDGMENT_IDS, JUDGMENTS, TRACE_EVAL_DIR
from agent.trace_eval_v2.experiments import load_experiment_record, load_judgments
from agent.trace_eval_v2.perturbations import DESCRIPTIONS, EXPECTED

OUT_DIR = TRACE_EVAL_DIR / "analysis"
BINARY_JUDGMENTS = ["support", "missed_evidence", "distractor_anchor", "premature_close", "final_consistency"]
TIERS = scorer.REVIEW_TIERS

# ── pre-registered capability rubric ─────────────────────────────────────────────────────
AUC_USEFUL = 0.65          # a judge must reach this AUC, with a bootstrap lower bound above 0.5, to count as carrying any signal
AUC_STRONG = 0.80          # Strong Jev: AUC at least this ...
AUC_STRONG_LOWER = 0.70    # ... with a lower bound at least this
LLM_ADVANTAGE = 0.05       # Better LLM: LLM AUC exceeds Jev's by at least this, paired-bootstrap interval above 0
DET_TIE = 0.02             # Better deterministic: an observable-only rule within this of the best judge (or better)
DIRECTION_MIN = 0.80       # metamorphic direction consistency needed for Strong
STABILITY_MIN = 0.85       # share of P5/P6 variants within tolerance needed for Strong
ECE_MAX = 0.15
MIN_CLASS_N = 8            # fewer positives or negatives than this: the category is provisional


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


# ── loading ──────────────────────────────────────────────────────────────────────────
def load_bundle(jev_id: str, llm_id: str) -> dict:
    ref = {}
    for line in open(EXPERIMENTS_DIR / jev_id / "reference_labels.jsonl"):
        if line.strip():
            r = json.loads(line)
            ref[r["trace_key"]] = r
    return {"jev_exp": load_experiment_record(jev_id), "llm_exp": load_experiment_record(llm_id), "jev_raw": load_judgments(jev_id), "llm_raw": load_judgments(llm_id), "ref": ref}


def score_all(b: dict) -> dict:
    rows = {"jev": [], "llm": [], "det": []}
    for judge, raws in (("jev", b["jev_raw"]), ("llm", b["llm_raw"])):
        for raw in raws:
            meta = b["ref"][raw["trace_key"]]
            r = scorer.score_row(raw, meta, meta["labels"])
            r["base_key"] = meta.get("base_key")
            rows[judge].append(r)
    for key, meta in b["ref"].items():
        base = meta["baselines"]
        for j in BINARY_JUDGMENTS:
            rows["det"].append({**scorer.baseline_row(j, meta, meta["labels"], base[j], "det_observable"), "base_key": meta.get("base_key")})
        for name in ("human_review_agent_flag", "human_review_defect_rule"):
            rows["det"].append({**scorer.baseline_row("human_review", meta, meta["labels"], base[name], name), "base_key": meta.get("base_key")})
    return rows


def _originals(rows: list) -> list:
    return [r for r in rows if r["variant"] is None]


def _binary(rows: list, judgment: str, judge: str = None) -> list:
    return [{"key": r["trace_key"], "p": r["p"], "y": r["y"]} for r in rows if r["judgment"] == judgment and (judge is None or r["judge"] == judge)
            and r["valid"] and r["p"] is not None and r["y"] is not None]


# ── corpus description ───────────────────────────────────────────────────────────────
def corpus_description(b: dict) -> dict:
    ref = b["ref"]
    orig = [v for v in ref.values() if v["variant"] is None]
    var = [v for v in ref.values() if v["variant"] is not None]
    cnt = lambda f, rows=orig: dict(Counter(f(v) for v in rows))
    labels = lambda j: cnt(lambda v: str(v["labels"]["labels"][j]["label"]))
    return {
        "n_original_traces": len(orig), "n_variants": len(var), "variants_by_perturbation": dict(Counter(v["variant"] for v in var)),
        "cases": len({v["case_id"] for v in orig}), "archetype": cnt(lambda v: v["labels"]["stratification"]["difficulty_archetype"]),
        "evidence_sufficiency": cnt(lambda v: v["labels"]["stratification"]["evidence_sufficiency"]), "outcome": cnt(lambda v: v["labels"]["outcome"]["label"]),
        "quadrant": cnt(lambda v: v["labels"]["quadrant"]), "process": cnt(lambda v: v["labels"]["process"]["label"]),
        "reference_labels": {j: labels(j) for j in JUDGMENTS} | {"human_review_process_only": labels("human_review_process_only")},
        "incident_involved": cnt(lambda v: v["labels"]["stratification"]["incident_involved"]), "dependency_driven": cnt(lambda v: v["labels"]["stratification"]["dependency_driven"]),
        "customer_misdiagnosis": cnt(lambda v: v["labels"]["stratification"]["customer_misdiagnosis"]),
        "agent_confidence": cnt(lambda v: _conf_bucket(v)), "invalid_tool_calls_per_trace": cnt(lambda v: v["labels"]["facts"]["n_errors"]),
        "redundant_calls_per_trace": cnt(lambda v: v["labels"]["facts"]["n_redundant"]), "diagnostic_calls_per_trace": cnt(lambda v: v["labels"]["facts"]["n_diagnostic_calls"]),
        "tokens": {"median": statistics.median([v["approx_tokens"] for v in orig]), "max": max(v["approx_tokens"] for v in orig)},
    }


def _conf_bucket(meta: dict) -> str:
    c = meta["labels"]["phase6"]["overall_confidence"] or 0
    return "high (>=0.8)" if c >= 0.8 else "mid (0.5-0.8)" if c >= 0.5 else "low (<0.5)"


# ── performance ──────────────────────────────────────────────────────────────────────
def performance(rows: dict) -> dict:
    out = {}
    for j in BINARY_JUDGMENTS:
        out[j] = {}
        for judge in ("jev", "llm", "det"):
            data = _binary(_originals(rows[judge]), j, None if judge != "det" else "det_observable")
            rep = M.binary_report(data)
            allr = [r for r in _originals(rows[judge]) if r["judgment"] == j and (judge != "det" or r["judge"] == "det_observable")]
            rep["n_invalid"] = sum(1 for r in allr if not r["valid"])
            rep["n_excluded_middle_band"] = sum(1 for r in allr if r["valid"] and r["y"] is None)
            out[j][judge] = rep
        if j == "support":  # the ambiguous middle band, and the wider binary view
            for judge in ("jev", "llm"):
                bands = defaultdict(list)
                wide = []
                for r in _originals(rows[judge]):
                    if r["judgment"] == "support" and r["valid"] and r["p"] is not None:
                        bands[r["ref"]].append(r["p"])
                        wide.append({"key": r["trace_key"], "p": r["p"], "y": int(r["ref"] in ("SUPPORTED", "PARTIALLY_SUPPORTED"))})
                out[j][judge]["mean_p_yes_by_reference_band"] = {k: {"n": len(v), "mean_p_yes": _mean(v)} for k, v in sorted(bands.items())}
                out[j][judge]["wide_view_supported_or_partial_vs_unsupported"] = M.binary_report(wide)
    return out


def paired_comparison(rows: dict) -> dict:
    out = {}
    for j in BINARY_JUDGMENTS:
        jev = {r["key"]: r for r in _binary(_originals(rows["jev"]), j)}
        llm = {r["key"]: r for r in _binary(_originals(rows["llm"]), j)}
        correct = lambda d: {k: ((r["p"] >= 0.5) == (r["y"] == 1)) for k, r in d.items()}
        out[j] = {"accuracy": M.paired_correct(correct(jev), correct(llm)), "auc_diff_jev_minus_llm": M.paired_auc_diff(list(jev.values()), list(llm.values()))}
        det = {r["key"]: r for r in _binary(_originals(rows["det"]), j, "det_observable")}
        out[j]["auc_diff_jev_minus_det"] = M.paired_auc_diff(list(jev.values()), list(det.values()))
        out[j]["auc_diff_llm_minus_det"] = M.paired_auc_diff(list(llm.values()), list(det.values()))
    return out


# ── metamorphic ──────────────────────────────────────────────────────────────────────
def metamorphic(b: dict, rows: dict) -> dict:
    out = {}
    for judge in ("jev", "llm"):
        idx = {(r["trace_key"], r["judgment"]): r for r in rows[judge]}
        acc = defaultdict(list)
        for key, meta in b["ref"].items():
            if meta["variant"] is None:
                continue
            base_key = meta["base_key"]
            for j, direction in (meta["expected"] or {}).items():
                rb, rv = idx.get((base_key, j)), idx.get((key, j))
                field = "p_level" if j == "human_review" else "p"
                if rb and rv and rb["valid"] and rv["valid"] and rb.get(field) is not None and rv.get(field) is not None:
                    acc[(meta["variant"], j, direction)].append((rb[field], rv[field]))
        out[judge] = {f"{p}|{j}": {**M.directional(pairs, d), "perturbation": p, "judgment": j} for (p, j, d), pairs in sorted(acc.items())}
    return out


def metamorphic_summary(mm: dict) -> dict:
    """Per judge and judgment: pooled consistency over the perturbations that have an expected direction (P1 to P4) and over the stability perturbations (P5, P6)."""
    out = {}
    for judge, cells in mm.items():
        per = defaultdict(lambda: {"directional": [0, 0], "stable": [0, 0]})
        for c in cells.values():
            kind = "stable" if c["expected"] == "stable" else "directional"
            per[c["judgment"]][kind][0] += c["consistent"]
            per[c["judgment"]][kind][1] += c["n"]
        out[judge] = {j: {"directional_rate": (v["directional"][0] / v["directional"][1]) if v["directional"][1] else None, "directional_n": v["directional"][1],
                          "stability_rate": (v["stable"][0] / v["stable"][1]) if v["stable"][1] else None, "stability_n": v["stable"][1]} for j, v in per.items()}
    return out


def variant_absolute(b: dict, rows: dict) -> dict:
    """Secondary: judges scored against the reference labels recomputed for the synthetic variants (marked synthetic)."""
    out = {}
    for judge in ("jev", "llm"):
        out[judge] = {}
        for j in BINARY_JUDGMENTS:
            data = [{"key": r["trace_key"], "p": r["p"], "y": r["y"]} for r in rows[judge] if r["variant"] is not None and r["judgment"] == j and r["valid"] and r["p"] is not None and r["y"] is not None]
            out[judge][j] = {k: v for k, v in M.binary_report(data, with_ci=False).items() if k in ("n", "n_positive", "accuracy", "roc_auc", "f1")}
    return out


# ── human review ─────────────────────────────────────────────────────────────────────
def review_analysis(b: dict, rows: dict) -> dict:
    out = {}
    for ref_name, ref_field in (("full_policy", "ref"), ("process_only", "ref_process_only")):
        block = {}
        for judge in ("jev", "llm"):
            rs = [r for r in _originals(rows[judge]) if r["judgment"] == "human_review" and r["valid"] and r["pred"] in TIERS]
            data = [{"ref": r[ref_field], "pred": r["pred"], "p_auto": r.get("p_auto")} for r in rs]
            block[judge] = {"review_report": M.review_report(data), "tiers": M.choice_report(data, TIERS), "simulation": M.review_simulation(data) if judge == "jev" else None,
                            "n_invalid": sum(1 for r in _originals(rows[judge]) if r["judgment"] == "human_review" and not (r["valid"] and r["pred"] in TIERS))}
        agent = []
        for key, meta in b["ref"].items():
            if meta["variant"] is not None:
                continue
            ref = meta["labels"]["labels"]["human_review" if ref_name == "full_policy" else "human_review_process_only"]["label"]
            agent.append({"ref": ref, "pred": "HUMAN_REVIEW" if meta["baselines"]["human_review_agent_flag"] else "AUTO_CLOSE", "p_auto": 0.0 if meta["baselines"]["human_review_agent_flag"] else 1.0})
        rule = [{"ref": meta["labels"]["labels"]["human_review" if ref_name == "full_policy" else "human_review_process_only"]["label"],
                 "pred": "HUMAN_REVIEW" if meta["baselines"]["human_review_defect_rule"] else "AUTO_CLOSE"} for meta in b["ref"].values() if meta["variant"] is None]
        block["baseline_agent_flag"] = M.review_report(agent)
        block["baseline_defect_rule"] = M.review_report(rule)
        # tier discrimination: PRIORITY versus the rest, scored on P(PRIORITY) for Jev and the hard choice for the LLM
        pri = {}
        for judge in ("jev", "llm"):
            data = []
            for r in _originals(rows[judge]):
                if r["judgment"] == "human_review" and r["valid"] and r["pred"] in TIERS:
                    p = (r["probs"] or {}).get("PRIORITY_REVIEW") if r.get("probs") else (1.0 if r["pred"] == "PRIORITY_REVIEW" else 0.0)
                    if p is not None:
                        data.append({"key": r["trace_key"], "p": p, "y": int(r[ref_field] == "PRIORITY_REVIEW")})
            pri[judge] = M.binary_report(data)
        block["priority_vs_rest"] = pri
        out[ref_name] = block
    return out


# ── the 2x2 ──────────────────────────────────────────────────────────────────────────
def judged_good_process(p: dict) -> bool:
    """A descriptive conjunction of the five independent judgments (never a composite score): supported, and no missed evidence, anchoring, premature close or inconsistency."""
    return p["support"] >= 0.5 and p["missed_evidence"] < 0.5 and p["distractor_anchor"] < 0.5 and p["premature_close"] < 0.5 and p["final_consistency"] >= 0.5


def quadrant_analysis(b: dict, rows: dict) -> dict:
    out = {}
    for judge in ("jev", "llm"):
        by_trace = defaultdict(dict)
        for r in _originals(rows[judge]):
            if r["valid"]:
                by_trace[r["trace_key"]][r["judgment"]] = r
        groups = defaultdict(list)
        for key, meta in b["ref"].items():
            if meta["variant"] is not None or key not in by_trace:
                continue
            lab = meta["labels"]
            defects = len(lab["process"]["defects"])
            groups[lab["quadrant"]].append((key, meta, by_trace[key]))
            if lab["outcome"]["label"] != "CORRECT" and defects <= 1:
                groups["C_proxy_wrong_with_at_most_one_defect"].append((key, meta, by_trace[key]))
        block = {}
        for name, members in sorted(groups.items()):
            complete = [(k, m, t) for k, m, t in members if all(j in t and t[j]["p"] is not None for j in BINARY_JUDGMENTS)]
            entry = {"n": len(members), "n_complete": len(complete)}
            if complete:
                probs = [{j: t[j]["p"] for j in BINARY_JUDGMENTS} for _, _, t in complete]
                entry["mean_p_yes"] = {j: _mean([p[j] for p in probs]) for j in BINARY_JUDGMENTS}
                entry["judged_good_process"] = sum(1 for p in probs if judged_good_process(p))
                entry["reference_good_process"] = sum(1 for _, m, _ in complete if m["labels"]["process"]["label"] == "GOOD")
                entry["defects_flagged_by_judge"] = _mean([(p["missed_evidence"] >= 0.5) + (p["distractor_anchor"] >= 0.5) + (p["premature_close"] >= 0.5) + (p["support"] < 0.5) + (p["final_consistency"] < 0.5) for p in probs])
                entry["defects_in_reference"] = _mean([len(m["labels"]["process"]["defects"]) for _, m, _ in complete])
            tiers = Counter(t["human_review"]["pred"] for _, _, t in members if "human_review" in t and t["human_review"].get("pred"))
            entry["review_tier_chosen"] = dict(tiers)
            entry["auto_closed"] = tiers.get("AUTO_CLOSE", 0)
            block[name] = entry
        out[judge] = block
    return out


# ── slices, length, taxonomy, cost ───────────────────────────────────────────────────
def _slice_key(meta: dict, dim: str):
    lab = meta["labels"]
    if dim == "archetype":
        return lab["stratification"]["difficulty_archetype"]
    if dim == "evidence_sufficiency":
        return lab["stratification"]["evidence_sufficiency"]
    if dim == "final_outcome":
        return lab["outcome"]["label"]
    if dim == "agent_confidence":
        return _conf_bucket(meta)
    if dim == "tool_calls":
        n = lab["facts"]["n_diagnostic_calls"]
        return "<=5" if n <= 5 else "6" if n == 6 else ">=7"
    if dim == "hypothesis_revisions":
        n = lab["phase6"]["hypothesis_revisions"] or 0
        return "0" if n == 0 else "1" if n == 1 else ">=2"
    if dim == "invalid_tool_calls":
        n = lab["facts"]["n_errors"]
        return "1" if n <= 1 else "2" if n == 2 else ">=3"
    raise ValueError(dim)


def slices(b: dict, rows: dict) -> dict:
    dims = ["archetype", "evidence_sufficiency", "final_outcome", "agent_confidence", "tool_calls", "hypothesis_revisions", "invalid_tool_calls"]
    out = {}
    for dim in dims:
        out[dim] = {}
        for judge in ("jev", "llm"):
            cells = defaultdict(lambda: defaultdict(lambda: [0, 0]))
            for r in _originals(rows[judge]):
                if r["judgment"] in BINARY_JUDGMENTS and r["valid"] and r["p"] is not None and r["y"] is not None:
                    key = _slice_key(b["ref"][r["trace_key"]], dim)
                    ok = (r["p"] >= 0.5) == (r["y"] == 1)
                    cells[key][r["judgment"]][0] += ok
                    cells[key][r["judgment"]][1] += 1
            out[dim][judge] = {k: {"n_traces": len({r["trace_key"] for r in _originals(rows[judge]) if _slice_key(b["ref"][r["trace_key"]], dim) == k and r["judgment"] == "support"}),
                                   "accuracy_by_judgment": {j: (v[0] / v[1] if v[1] else None) for j, v in cj.items()}, "n_by_judgment": {j: v[1] for j, v in cj.items()},
                                   "pooled_accuracy": (sum(v[0] for v in cj.values()) / max(1, sum(v[1] for v in cj.values())))} for k, cj in sorted(cells.items())}
    return out


def length_sensitivity(b: dict, rows: dict) -> dict:
    tokens = {k: m["approx_tokens"] for k, m in b["ref"].items() if m["variant"] is None}
    bins = M.bins_by_terciles(tokens)
    edges = {name: [min(v for k, v in tokens.items() if bins[k] == name), max(v for k, v in tokens.items() if bins[k] == name)] for name in ("short", "medium", "long")}
    out = {"bins_approx_tokens": edges}
    for judge in ("jev", "llm"):
        out[judge] = {}
        for name in ("short", "medium", "long"):
            rs = [r for r in _originals(rows[judge]) if bins.get(r["trace_key"]) == name]
            binary = [{"p": r["p"], "y": r["y"]} for r in rs if r["judgment"] in BINARY_JUDGMENTS and r["valid"] and r["p"] is not None and r["y"] is not None]
            lat = [r["latency_ms"] for r in rs if r["latency_ms"] is not None]
            costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
            out[judge][name] = {"n_traces": len({r["trace_key"] for r in rs}), "n_decisions": len(binary), "accuracy": M._rate(sum(1 for r in binary if (r["p"] >= 0.5) == (r["y"] == 1)), len(binary)),
                                "brier": M.brier(binary), "ece": M.ece(binary), "p50_latency_ms": M.percentile(lat, 0.5), "p95_latency_ms": M.percentile(lat, 0.95),
                                "cost_per_1000": (sum(costs) / len(costs) * 1000) if costs else None}
    return out


def failure_taxonomy(rows: dict) -> dict:
    out = {}
    for judge in ("jev", "llm"):
        c = Counter()
        for r in _originals(rows[judge]):
            if not r["valid"] or r["p"] is None:
                continue
            j = r["judgment"]
            if j == "human_review":
                if r["pred"] == "AUTO_CLOSE" and r["ref"] != "AUTO_CLOSE":
                    c["unsafe auto-close"] += 1
                if r["pred"] not in (None, "AUTO_CLOSE") and r["ref"] == "AUTO_CLOSE":
                    c["unnecessary human review"] += 1
                if r["ref"] == "PRIORITY_REVIEW" and r["pred"] != "PRIORITY_REVIEW":
                    c["priority under-escalation"] += 1
                continue
            if r["y"] is None:
                continue
            yes = r["p"] >= 0.5
            names = {"support": ("false support", "false unsupported"), "missed_evidence": ("false missed-evidence alarm", "missed missed-evidence"),
                     "distractor_anchor": ("false anchoring alarm", "missed distractor anchoring"), "premature_close": ("false premature alarm", "missed premature closure"),
                     "final_consistency": ("missed final inconsistency", "false inconsistency alarm")}[j]
            if yes and r["y"] == 0:
                c[names[0]] += 1
            if not yes and r["y"] == 1:
                c[names[1]] += 1
        out[judge] = dict(sorted(c.items()))
    return out


def cost_latency_contract(rows: dict, b: dict) -> dict:
    out = {}
    for judge in ("jev", "llm"):
        out[judge] = {}
        for j in JUDGMENTS + ["ALL"]:
            rs = [r for r in rows[judge] if j == "ALL" or r["judgment"] == j]
            lat = [r["latency_ms"] for r in rs if r["latency_ms"] is not None]
            costs = [r["cost_usd"] for r in rs if r["cost_usd"] is not None]
            toks = [r["input_tokens"] for r in rs if r.get("input_tokens")]
            entry = {"n": len(rs), "p50_latency_ms": M.percentile(lat, 0.5), "p95_latency_ms": M.percentile(lat, 0.95), "total_cost_usd": sum(costs), "cost_per_1000_judgments_usd": (sum(costs) / len(costs) * 1000) if costs else None,
                     "mean_input_tokens": _mean(toks), "not_ok": sum(1 for r in rs if r["status"] != "ok"), "no_typed_answer": sum(1 for r in rs if not r["valid"])}
            if judge == "llm":
                c = [r["contract"] for r in rs]
                entry.update({"first_attempt_valid": sum(1 for x in c if x.get("first_attempt_valid")), "repair_required": sum(1 for x in c if x.get("repair_required")),
                              "repair_succeeded": sum(1 for x in c if x.get("repair_succeeded")), "unrecoverable": sum(1 for x in c if x.get("unrecoverable")),
                              "first_attempt_failures": dict(Counter(x.get("first_attempt_failure") for x in c if x.get("first_attempt_failure")))})
            out[judge][j] = entry
    out["jev_models_resolved"] = b["jev_exp"]["config"].get("jev_models_resolved")
    return out


# ── capability map ───────────────────────────────────────────────────────────────────
def classify_binary(j: str, perf: dict, paired: dict, mm_sum: dict) -> dict:
    jev, llm, det = perf[j]["jev"], perf[j]["llm"], perf[j]["det"]
    thin = min(jev["n_positive"], jev["n"] - jev["n_positive"]) < MIN_CLASS_N
    auc = lambda r: r.get("roc_auc")
    ci_low = lambda r: (r.get("roc_auc_ci") or {}).get("ci_low")
    jev_auc, llm_auc, det_auc = auc(jev), auc(llm), auc(det)
    reasons = []
    directional = mm_sum["jev"].get(j, {})
    dir_ok = directional.get("directional_rate") is None or directional["directional_rate"] >= DIRECTION_MIN
    stab_ok = directional.get("stability_rate") is None or directional["stability_rate"] >= STABILITY_MIN
    best = max(x for x in (jev_auc, llm_auc) if x is not None) if any(x is not None for x in (jev_auc, llm_auc)) else None
    if best is None:
        category = "Weak"
        reasons.append("no AUC could be computed")
    elif det_auc is not None and j != "distractor_anchor" and det_auc >= best - DET_TIE:
        category = "Better deterministic"
        reasons.append(f"an observable-only rule reaches AUC {det_auc:.2f} against Jev {jev_auc:.2f} and the LLM {llm_auc:.2f}")
    elif (jev_auc is None or jev_auc < AUC_USEFUL or (ci_low(jev) or 0) <= 0.5) and (llm_auc is None or llm_auc < AUC_USEFUL or (ci_low(llm) or 0) <= 0.5):
        category = "Weak"
        reasons.append(f"neither judge carries a reliable signal (Jev AUC {jev_auc}, LLM AUC {llm_auc})")
    else:
        diff = paired[j]["auc_diff_jev_minus_llm"]
        llm_better = llm_auc is not None and jev_auc is not None and llm_auc - jev_auc >= LLM_ADVANTAGE and diff["ci_high"] is not None and diff["ci_high"] < 0
        if llm_better:
            category = "Better LLM"
            reasons.append(f"the LLM's AUC exceeds Jev's by {llm_auc - jev_auc:.2f}, paired interval excludes 0")
        elif (jev_auc is not None and jev_auc >= AUC_STRONG and (ci_low(jev) or 0) >= AUC_STRONG_LOWER and dir_ok and stab_ok and (jev["ece"] is not None and jev["ece"] <= ECE_MAX)
              and (llm_auc is None or jev_auc >= llm_auc - 0.02)):
            category = "Strong Jev use case"
            reasons.append(f"Jev AUC {jev_auc:.2f} (lower bound {ci_low(jev):.2f}), directional {directional.get('directional_rate')}, stable {directional.get('stability_rate')}, ECE {jev['ece']:.2f}")
        elif jev_auc is not None and jev_auc >= AUC_USEFUL and (ci_low(jev) or 0) > 0.5:
            category = "Useful supporting signal"
            reasons.append(f"Jev AUC {jev_auc:.2f} (lower bound {ci_low(jev):.2f}) clears the signal bar but not every Strong condition (directional ok: {dir_ok}, stable ok: {stab_ok}, ECE {jev['ece']})")
        else:
            category = "Weak"
            reasons.append("Jev does not clear the signal bar; the LLM does but by a margin the paired interval does not separate")
    return {"judgment": j, "category": category + (" (provisional: thin class)" if thin else ""), "provisional": thin, "reasons": reasons, "jev_auc": jev_auc, "llm_auc": llm_auc, "det_auc": det_auc,
            "jev_auc_ci": [(jev.get("roc_auc_ci") or {}).get("ci_low"), (jev.get("roc_auc_ci") or {}).get("ci_high")], "n_positive": jev["n_positive"], "n": jev["n"],
            "directional": directional}


def classify_review(review: dict, perf_tiers: dict) -> dict:
    """J6 is judged on two operational questions, each on the full policy: does the judge avoid unsafe auto-close, and does it separate PRIORITY from the rest. If the corpus holds fewer than
    MIN_CLASS_N clean traces, auto-close precision cannot be established and that is stated."""
    full = review["full_policy"]
    jev, llm = full["jev"]["review_report"], full["llm"]["review_report"]
    n_clean = jev["n_clean"]
    reasons = []
    unsafe_ok = jev["unsafe_auto_close_count"] == 0 or (jev["unsafe_auto_close_rate"] is not None and jev["unsafe_auto_close_rate"] <= 0.05)
    pri = full["priority_vs_rest"]
    jev_auc, llm_auc = pri["jev"]["roc_auc"], pri["llm"]["roc_auc"]
    if n_clean < MIN_CLASS_N:
        reasons.append(f"only {n_clean} clean traces in the corpus: auto-close precision cannot be established")
    reasons.append(f"Jev auto-closed {jev['auto_close_count']} traces, {jev['unsafe_auto_close_count']} unsafe; the LLM auto-closed {llm['auto_close_count']}, {llm['unsafe_auto_close_count']} unsafe")
    reasons.append(f"PRIORITY vs rest AUC: Jev {jev_auc}, LLM {llm_auc}")
    if not unsafe_ok:
        category = "Weak (unsafe as an auto-close gate)"
    elif jev_auc is not None and jev_auc >= AUC_USEFUL and (pri["jev"].get("roc_auc_ci") or {}).get("ci_low", 0) and pri["jev"]["roc_auc_ci"]["ci_low"] > 0.5:
        category = "Useful supporting signal"
    else:
        category = "Weak"
    if n_clean < MIN_CLASS_N:
        category += " (provisional: thin class)"
    return {"judgment": "human_review", "category": category, "reasons": reasons, "n_clean": n_clean}


def capability_map(perf: dict, paired: dict, mm_sum: dict, review: dict) -> list:
    rows = [classify_binary(j, perf, paired, mm_sum) for j in BINARY_JUDGMENTS]
    rows.append(classify_review(review, None))
    return rows


# ── build and render ─────────────────────────────────────────────────────────────────
def build(jev_id: str, llm_id: str) -> dict:
    b = load_bundle(jev_id, llm_id)
    rows = score_all(b)
    perf, paired = performance(rows), paired_comparison(rows)
    mm = metamorphic(b, rows)
    mm_sum = metamorphic_summary(mm)
    review = review_analysis(b, rows)
    return {
        "experiments": {"jev": jev_id, "llm": llm_id, "jev_config": b["jev_exp"]["config"], "llm_config": b["llm_exp"]["config"]},
        "corpus": corpus_description(b), "performance": perf, "paired": paired, "metamorphic": mm, "metamorphic_summary": mm_sum, "variants_absolute": variant_absolute(b, rows),
        "review": review, "quadrants": quadrant_analysis(b, rows), "slices": slices(b, rows), "length": length_sensitivity(b, rows), "taxonomy": failure_taxonomy(rows),
        "cost_latency_contract": cost_latency_contract(rows, b), "capability_map": capability_map(perf, paired, mm_sum, review),
        "rubric": {"AUC_USEFUL": AUC_USEFUL, "AUC_STRONG": AUC_STRONG, "AUC_STRONG_LOWER": AUC_STRONG_LOWER, "LLM_ADVANTAGE": LLM_ADVANTAGE, "DET_TIE": DET_TIE, "DIRECTION_MIN": DIRECTION_MIN,
                   "STABILITY_MIN": STABILITY_MIN, "ECE_MAX": ECE_MAX, "MIN_CLASS_N": MIN_CLASS_N},
    }


def _p(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _pct(x, nd=1):
    return "n/a" if x is None else f"{x * 100:.{nd}f}%"


def _ci(ci):
    return "n/a" if not ci or ci[0] is None else f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def to_markdown(r: dict) -> str:
    perf, cap = r["performance"], r["capability_map"]
    lines = ["# Phase 8 trace evaluation: measured results (generated)", "", f"Jev experiment `{r['experiments']['jev']}`, LLM experiment `{r['experiments']['llm']}`.", "",
             "## Corpus", "", f"{r['corpus']['n_original_traces']} original traces ({r['corpus']['cases']} cases) and {r['corpus']['n_variants']} synthetic variants {r['corpus']['variants_by_perturbation']}.", "",
             f"Outcome {r['corpus']['outcome']}; quadrant {r['corpus']['quadrant']}; archetype {r['corpus']['archetype']}.", "", "Reference labels:", ""]
    for j, dist in r["corpus"]["reference_labels"].items():
        lines.append(f"- {j}: {dist}")
    lines += ["", "## Performance on original traces (Jev / LLM / observable-only rule)", "",
              "| Judgment | n (pos) | Judge | Accuracy | F1 | Precision | Recall | ROC-AUC [95% CI] | PR-AUC | Brier | ECE | False-confident |", "|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|---:|"]
    for j in BINARY_JUDGMENTS:
        for judge in ("jev", "llm", "det"):
            x = perf[j][judge]
            lines.append(f"| {JUDGMENT_IDS[j]} {j} | {x['n']} ({x['n_positive']}) | {judge} | {_pct(x['accuracy'])} | {_p(x['f1'])} | {_p(x['precision'])} | {_p(x['recall'])} | {_p(x['roc_auc'])} {_ci([(x.get('roc_auc_ci') or {}).get('ci_low'), (x.get('roc_auc_ci') or {}).get('ci_high')])} | {_p(x['pr_auc'])} | {_p(x['brier'])} | {_p(x['ece'])} | {x['false_confident']['n_false_confident']}/{x['false_confident']['n_confident']} |")
    lines += ["", "## Jev versus the LLM judge (paired, exact McNemar on correct-at-0.5; AUC difference by paired bootstrap)", "", "| Judgment | Only Jev right | Only LLM right | McNemar p | AUC Jev - LLM [95% CI] | AUC Jev - rule [95% CI] |", "|---|---:|---:|---:|---|---|"]
    for j in BINARY_JUDGMENTS:
        pc = r["paired"][j]
        d1, d2 = pc["auc_diff_jev_minus_llm"], pc["auc_diff_jev_minus_det"]
        lines.append(f"| {JUDGMENT_IDS[j]} {j} | {pc['accuracy']['only_first_correct']} | {pc['accuracy']['only_second_correct']} | {_p(pc['accuracy']['mcnemar_p'], 3)} | {_p(d1['diff'])} {_ci([d1['ci_low'], d1['ci_high']])} | {_p(d2['diff'])} {_ci([d2['ci_low'], d2['ci_high']])} |")
    lines += ["", "## Perturbations (direction each judgment should move; share of variants that moved that way)", "", "| Perturbation | Judgment | Expected | n | Jev consistent | Jev material (>=0.05) | Jev mean delta | LLM consistent | LLM mean delta |", "|---|---|---|---:|---|---:|---:|---|---:|"]
    for k, jc in r["metamorphic"]["jev"].items():
        lc = r["metamorphic"]["llm"].get(k, {})
        lines.append(f"| {jc['perturbation']} {DESCRIPTIONS[jc['perturbation']][:60]} | {jc['judgment']} | {jc['expected']} | {jc['n']} | {jc['consistent']}/{jc['n']} ({_pct(jc['consistency_rate'], 0)}) | {jc.get('material', 'n/a')} | {_p(jc['mean_delta'], 3)} | {lc.get('consistent', 'n/a')}/{lc.get('n', 'n/a')} | {_p(lc.get('mean_delta'), 3)} |")
    lines += ["", "## Capability map (pre-registered rubric)", "", "| Judgment | Category | Jev AUC | LLM AUC | Rule AUC | Reasons |", "|---|---|---:|---:|---:|---|"]
    for c in cap:
        lines.append(f"| {JUDGMENT_IDS.get(c['judgment'], '')} {c['judgment']} | **{c['category']}** | {_p(c.get('jev_auc'))} | {_p(c.get('llm_auc'))} | {_p(c.get('det_auc'))} | {'; '.join(c['reasons'])} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jev", required=True)
    parser.add_argument("--llm", required=True)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    report = build(args.jev, args.llm)
    out = Path(args.out_dir) if args.out_dir else OUT_DIR / args.jev
    out.mkdir(parents=True, exist_ok=True)
    (out / "trace_eval_report.json").write_text(json.dumps(report, indent=2, default=str))
    (out / "trace_eval_report.md").write_text(to_markdown(report))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
