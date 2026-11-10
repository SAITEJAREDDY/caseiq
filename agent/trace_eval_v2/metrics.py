"""Pure metric functions for Phase 8 (no I/O, no hidden truth, no API). Everything is deterministic given its inputs; bootstrap intervals use Phase 6's seed and resample count.

Conventions. A binary judgment row carries `p` (the judge's probability of the YES condition), `y` (the reference label, 1 or 0), and optionally `conf`. A decision is "yes" when
p >= 0.5. A choice row carries `pred`, `ref` and `conf`. Confidence figures are each judge's own and are never ranked across judges: Jev reports typed probabilities, the LLM
reports a self-stated number.
"""
import math
import random
from collections import Counter, defaultdict

from agent.eval_v2.config import AUTOMATION_THRESHOLDS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, FALSE_CONFIDENT_THRESHOLD
from agent.jev_v2.paired_stats import mcnemar_exact_p
from agent.jev_v2.stage_c_report import wilson


def _rate(k, n):
    return None if not n else k / n


def confusion(rows: list) -> dict:
    tp = sum(1 for r in rows if r["y"] == 1 and r["p"] >= 0.5)
    fp = sum(1 for r in rows if r["y"] == 0 and r["p"] >= 0.5)
    fn = sum(1 for r in rows if r["y"] == 1 and r["p"] < 0.5)
    tn = sum(1 for r in rows if r["y"] == 0 and r["p"] < 0.5)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def prf(c: dict) -> dict:
    precision = _rate(c["tp"], c["tp"] + c["fp"])
    recall = _rate(c["tp"], c["tp"] + c["fn"])
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1, "specificity": _rate(c["tn"], c["tn"] + c["fp"])}


def roc_auc(rows: list):
    """Mann-Whitney formulation with midranks; None when a class is absent."""
    pos = [r["p"] for r in rows if r["y"] == 1]
    neg = [r["p"] for r in rows if r["y"] == 0]
    if not pos or not neg:
        return None
    wins = sum((1.0 if p > q else 0.5 if p == q else 0.0) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def average_precision(rows: list):
    """PR-AUC as average precision over descending score, ties handled as one block."""
    n_pos = sum(1 for r in rows if r["y"] == 1)
    if not n_pos:
        return None
    ordered = sorted(rows, key=lambda r: -r["p"])
    tp = fp = 0
    ap = 0.0
    i = 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j]["p"] == ordered[i]["p"]:
            j += 1
        block_pos = sum(1 for r in ordered[i:j] if r["y"] == 1)
        block_neg = (j - i) - block_pos
        if block_pos:
            tp_new, fp_new = tp + block_pos, fp + block_neg
            ap += (block_pos / n_pos) * (tp_new / (tp_new + fp_new))
            tp, fp = tp_new, fp_new
        else:
            fp += block_neg
        i = j
    return ap


def brier(rows: list):
    return _rate(sum((r["p"] - r["y"]) ** 2 for r in rows), len(rows))


def ece(rows: list, bins: int = 10):
    """Expected calibration error of P(yes): equal-width bins, weighted mean |mean predicted - observed frequency|."""
    if not rows:
        return None
    buckets = defaultdict(list)
    for r in rows:
        buckets[min(bins - 1, int(r["p"] * bins))].append(r)
    return sum(len(b) / len(rows) * abs(sum(x["p"] for x in b) / len(b) - sum(x["y"] for x in b) / len(b)) for b in buckets.values())


def false_confident(rows: list, threshold: float = FALSE_CONFIDENT_THRESHOLD) -> dict:
    """Wrong yes/no decisions made with confidence max(p, 1-p) >= threshold."""
    conf = [r for r in rows if max(r["p"], 1 - r["p"]) >= threshold]
    wrong = [r for r in conf if (r["p"] >= 0.5) != (r["y"] == 1)]
    return {"n_confident": len(conf), "n_false_confident": len(wrong), "rate_among_confident": _rate(len(wrong), len(conf)), "rate_overall": _rate(len(wrong), len(rows))}


def bootstrap(rows: list, fn, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict:
    """Percentile bootstrap of any row-level statistic (resampling traces with replacement)."""
    if not rows:
        return {"point": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    stats = []
    for _ in range(resamples):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        v = fn(sample)
        if v is not None:
            stats.append(v)
    stats.sort()
    point = fn(rows)
    if len(stats) < resamples * 0.5:
        return {"point": point, "ci_low": None, "ci_high": None, "note": "statistic undefined in most resamples"}
    return {"point": point, "ci_low": stats[int(0.025 * len(stats))], "ci_high": stats[min(len(stats) - 1, int(0.975 * len(stats)))]}


def binary_report(rows: list, with_ci: bool = True) -> dict:
    n = len(rows)
    c = confusion(rows)
    correct = c["tp"] + c["tn"]
    lo, hi = wilson(correct, n) if n else (None, None)
    out = {"n": n, "n_positive": c["tp"] + c["fn"], "prevalence": _rate(c["tp"] + c["fn"], n), "accuracy": _rate(correct, n), "accuracy_wilson_ci": [lo, hi], **c, **prf(c),
           "roc_auc": roc_auc(rows), "pr_auc": average_precision(rows), "brier": brier(rows), "ece": ece(rows), "false_confident": false_confident(rows),
           "majority_baseline_accuracy": _rate(max(c["tp"] + c["fn"], c["fp"] + c["tn"]), n)}
    if with_ci and n:
        out["f1_ci"] = bootstrap(rows, lambda s: prf(confusion(s))["f1"])
        out["roc_auc_ci"] = bootstrap(rows, roc_auc)
    return out


def choice_report(rows: list, classes: list) -> dict:
    n = len(rows)
    correct = sum(1 for r in rows if r["pred"] == r["ref"])
    matrix = {ref: {pred: sum(1 for r in rows if r["ref"] == ref and r["pred"] == pred) for pred in classes + ["invalid"]} for ref in classes}
    per_class, f1s = {}, []
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[o][c] for o in classes if o != c)
        fn = sum(matrix[c][p] for p in classes + ["invalid"] if p != c)
        prec, rec = _rate(tp, tp + fp), _rate(tp, tp + fn)
        f1 = None if prec is None or rec is None or prec + rec == 0 else 2 * prec * rec / (prec + rec)
        per_class[c] = {"support": sum(matrix[c].values()), "precision": prec, "recall": rec, "f1": f1}
        if per_class[c]["support"]:
            f1s.append(f1 or 0.0)
    lo, hi = wilson(correct, n) if n else (None, None)
    return {"n": n, "accuracy": _rate(correct, n), "accuracy_wilson_ci": [lo, hi], "macro_f1": (sum(f1s) / len(f1s)) if f1s else None, "per_class": per_class, "confusion": matrix,
            "majority_baseline_accuracy": _rate(max(Counter(r["ref"] for r in rows).values()), n) if rows else None}


# ── human review: automation simulation ───────────────────────────────────────────────
def review_simulation(rows: list, thresholds: list = None) -> list:
    """rows: {"p_auto": P(AUTO_CLOSE) or None, "ref": tier, "pred": tier}. For each threshold: auto-close when p_auto >= t. Unsafe auto-close is an auto-closed trace whose reference tier is not
    AUTO_CLOSE. Priority-review recall is measured on argmax, independent of the threshold."""
    thresholds = thresholds or AUTOMATION_THRESHOLDS
    scored = [r for r in rows if r.get("p_auto") is not None]
    out = []
    for t in thresholds:
        auto = [r for r in scored if r["p_auto"] >= t]
        unsafe = [r for r in auto if r["ref"] != "AUTO_CLOSE"]
        lo, hi = wilson(len(unsafe), len(auto)) if auto else (None, None)
        out.append({"threshold": t, "n": len(scored), "auto_close": len(auto), "auto_close_coverage": _rate(len(auto), len(scored)), "unsafe_auto_close": len(unsafe),
                    "unsafe_rate_among_auto_closed": _rate(len(unsafe), len(auto)), "unsafe_wilson_ci": [lo, hi], "unsafe_rate_of_all_traces": _rate(len(unsafe), len(scored)),
                    "review_rate": _rate(len(scored) - len(auto), len(scored)),
                    "problematic_caught": _rate(sum(1 for r in scored if r["ref"] != "AUTO_CLOSE" and r["p_auto"] < t), sum(1 for r in scored if r["ref"] != "AUTO_CLOSE"))})
    return out


def review_report(rows: list) -> dict:
    """The operational J6 metrics on argmax decisions plus the tier confusion."""
    prob = [r for r in rows if r["ref"] != "AUTO_CLOSE"]
    clean = [r for r in rows if r["ref"] == "AUTO_CLOSE"]
    pri = [r for r in rows if r["ref"] == "PRIORITY_REVIEW"]
    auto_pred = [r for r in rows if r["pred"] == "AUTO_CLOSE"]
    return {
        "n": len(rows), "n_problematic": len(prob), "n_clean": len(clean), "n_priority": len(pri),
        "review_recall_on_problematic": _rate(sum(1 for r in prob if r["pred"] != "AUTO_CLOSE"), len(prob)),
        "false_review_rate_on_clean": _rate(sum(1 for r in clean if r["pred"] != "AUTO_CLOSE"), len(clean)),
        "priority_review_recall": _rate(sum(1 for r in pri if r["pred"] == "PRIORITY_REVIEW"), len(pri)),
        "priority_under_escalation": _rate(sum(1 for r in pri if r["pred"] != "PRIORITY_REVIEW"), len(pri)),
        "auto_close_precision": _rate(sum(1 for r in auto_pred if r["ref"] == "AUTO_CLOSE"), len(auto_pred)),
        "auto_close_coverage": _rate(len(auto_pred), len(rows)), "unsafe_auto_close_rate": _rate(sum(1 for r in auto_pred if r["ref"] != "AUTO_CLOSE"), len(auto_pred)),
        "unsafe_auto_close_count": sum(1 for r in auto_pred if r["ref"] != "AUTO_CLOSE"), "auto_close_count": len(auto_pred),
    }


def paired_auc_diff(rows_a: list, rows_b: list, resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict:
    """Bootstrap interval for AUC(a) - AUC(b) over the same traces (rows carry `key`, `p`, `y`; resampling is by trace)."""
    a = {r["key"]: r for r in rows_a}
    b = {r["key"]: r for r in rows_b}
    keys = sorted(k for k in a if k in b)
    if not keys:
        return {"n": 0, "diff": None, "ci_low": None, "ci_high": None}
    rng = random.Random(seed)
    diffs = []
    for _ in range(resamples):
        sample = [keys[rng.randrange(len(keys))] for _ in keys]
        auc_a, auc_b = roc_auc([a[k] for k in sample]), roc_auc([b[k] for k in sample])
        if auc_a is not None and auc_b is not None:
            diffs.append(auc_a - auc_b)
    diffs.sort()
    point_a, point_b = roc_auc([a[k] for k in keys]), roc_auc([b[k] for k in keys])
    point = None if point_a is None or point_b is None else point_a - point_b
    if len(diffs) < resamples * 0.5:
        return {"n": len(keys), "diff": point, "ci_low": None, "ci_high": None}
    return {"n": len(keys), "diff": point, "ci_low": diffs[int(0.025 * len(diffs))], "ci_high": diffs[min(len(diffs) - 1, int(0.975 * len(diffs)))]}


# ── paired comparison ─────────────────────────────────────────────────────────────────
def paired_correct(a: dict, b: dict) -> dict:
    """a, b: {trace_key: bool correct}. Exact McNemar on the discordant pairs."""
    keys = [k for k in a if k in b]
    only_a = sum(1 for k in keys if a[k] and not b[k])
    only_b = sum(1 for k in keys if b[k] and not a[k])
    return {"n": len(keys), "only_first_correct": only_a, "only_second_correct": only_b, "both_correct": sum(1 for k in keys if a[k] and b[k]), "both_wrong": sum(1 for k in keys if not a[k] and not b[k]),
            "mcnemar_p": mcnemar_exact_p(only_a, only_b)}


# ── metamorphic evaluation ────────────────────────────────────────────────────────────
def directional(pairs: list, expected: str, margin: float = 0.05, stable_tolerance: float = 0.10) -> dict:
    """pairs: [(p_base, p_variant)]. expected in {"up", "down", "stable"}. Reports how often the variant moved the expected way."""
    n = len(pairs)
    deltas = [v - b for b, v in pairs]
    up = sum(1 for d in deltas if d > 1e-9)
    down = sum(1 for d in deltas if d < -1e-9)
    flat = n - up - down
    out = {"n": n, "expected": expected, "mean_delta": (sum(deltas) / n) if n else None, "median_delta": sorted(deltas)[n // 2] if n else None, "moved_up": up, "moved_down": down, "flat": flat}
    if expected == "up":
        out.update({"consistent": up, "consistency_rate": _rate(up, n), "material": sum(1 for d in deltas if d >= margin), "material_rate": _rate(sum(1 for d in deltas if d >= margin), n), "wrong_way": down})
    elif expected == "down":
        out.update({"consistent": down, "consistency_rate": _rate(down, n), "material": sum(1 for d in deltas if d <= -margin), "material_rate": _rate(sum(1 for d in deltas if d <= -margin), n), "wrong_way": up})
    else:
        within = sum(1 for d in deltas if abs(d) <= stable_tolerance)
        out.update({"consistent": within, "consistency_rate": _rate(within, n), "mean_abs_delta": (sum(abs(d) for d in deltas) / n) if n else None,
                    "decision_flips": sum(1 for b, v in pairs if (b >= 0.5) != (v >= 0.5))})
    lo, hi = wilson(out["consistent"], n) if n else (None, None)
    out["consistency_wilson_ci"] = [lo, hi]
    return out


def percentile(values: list, q: float):
    if not values:
        return None
    vs = sorted(values)
    return vs[min(len(vs) - 1, int(q * len(vs)))]


def bins_by_terciles(values: dict) -> dict:
    """{key: value} -> {key: 'short'|'medium'|'long'} by the actual distribution (terciles)."""
    vs = sorted(values.values())
    if not vs:
        return {}
    lo, hi = vs[len(vs) // 3], vs[(2 * len(vs)) // 3]
    return {k: ("short" if v < lo else "medium" if v < hi else "long") for k, v in values.items()}
