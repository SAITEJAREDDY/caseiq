"""Basic aggregate view over STORED dev results (not a benchmark). Only cases that have a stored result for all three architectures are compared, and N is always shown.
The accuracy rows use the offline evaluation module and are computed only on request."""
import json

from agent.agent_v3.config import PROJECT_ROOT
from agent.compare import adapters
from agent.compare.models import MODE_FULL, MODE_GRAPH, MODE_LLM, MODES, NAMES


def comparable_cases() -> list:
    pool = set(json.loads((PROJECT_ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"])
    return sorted(set(adapters.llm_index()) & set(adapters.graph_index()) & set(adapters.full_index()) & pool)


def aggregate(include_truth: bool = True) -> dict:
    cases = comparable_cases()
    results = {c: {m: adapters.load_stored(m, c) for m in MODES} for c in cases}
    n = len(cases)
    if not n:
        return {"n": 0, "cases": [], "rows": [], "note": "No dev case has a stored result for all three architectures yet."}
    mean = lambda vals: sum(vals) / len(vals)
    scores = {}
    if include_truth:
        from agent.compare import evaluation
        scores = {c: evaluation.score_all(c, results[c])["scores"] for c in cases}
    per_mode = {}
    for m in MODES:
        rs = [results[c][m] for c in cases]
        d = {"abstention": sum(1 for r in rs if not r.root_cause) / n, "tools": mean([r.tool_calls for r in rs]), "latency": mean([r.latency_seconds for r in rs]),
             "cost": mean([r.estimated_cost for r in rs]),
             "human_review": (sum(1 for r in rs if r.verification["final_decision"] in ("HUMAN_REVIEW", "PRIORITY_REVIEW")) / n) if m == MODE_FULL else None}
        if include_truth:
            for f, key in (("root_cause", "rc"), ("issue_category", "cat")):
                v = [scores[c][m][f] for c in cases]
                d[f"{key}_correct"], d[f"{key}_answered"] = v.count("correct"), n - v.count("abstain")
        per_mode[m] = d
    pct = lambda x: f"{x * 100:.0f}%"
    rows = []
    if include_truth:
        rows += [{"Metric": "Root-cause accuracy (of all N)", **{NAMES[m]: pct(per_mode[m]["rc_correct"] / n) for m in MODES}},
                 {"Metric": "Root-cause accuracy (of answered)", **{NAMES[m]: (pct(per_mode[m]["rc_correct"] / per_mode[m]["rc_answered"]) if per_mode[m]["rc_answered"] else "—") for m in MODES}},
                 {"Metric": "Issue-category accuracy (of all N)", **{NAMES[m]: pct(per_mode[m]["cat_correct"] / n) for m in MODES}}]
    rows += [{"Metric": "Abstention rate (no root cause)", **{NAMES[m]: pct(per_mode[m]["abstention"]) for m in MODES}},
             {"Metric": "Human-review rate", **{NAMES[m]: ("—" if per_mode[m]["human_review"] is None else pct(per_mode[m]["human_review"])) for m in MODES}},
             {"Metric": "Early Jev triage used", **{NAMES[m]: (f"{sum(1 for c in cases if results[c][m].triage)}/{n}" if m == MODE_FULL else "—") for m in MODES}},
             {"Metric": "Avg tool calls", **{NAMES[m]: f"{per_mode[m]['tools']:.1f}" for m in MODES}},
             {"Metric": "Avg latency (model + verifier)", **{NAMES[m]: f"{per_mode[m]['latency']:.0f}s" for m in MODES}},
             {"Metric": "Avg est. cost", **{NAMES[m]: f"${per_mode[m]['cost']:.3f}" for m in MODES}}]
    return {"n": n, "cases": cases, "rows": rows, "per_mode": per_mode,
            "note": f"N = {n} dev cases with a stored result for every architecture. The three results per case were produced by separate runs (the LLM + Graph and LLM + Graph + Jev agent runs "
                    "are independent and not deterministic), and the cases were chosen for coverage, not sampled: this is a look at stored runs, not a benchmark. LLM + Graph + Jev runs made before "
                    "early triage existed used late verification only (see the early-triage row)."}
