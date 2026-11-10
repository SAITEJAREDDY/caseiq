"""
CaseIQ evaluation runner.

Usage:
    python3 run_evals.py            # run all 6 eval categories
    python3 run_evals.py --dry-run  # skip LLM + Neo4j calls, show structure only

What happens:
  1. Initialises a timestamped LangSmith experiment
  2. Runs all 6 eval categories (eval_judge.py)
  3. Logs every test result to LangSmith (non-blocking)
  4. Prints a full Rich table to terminal
  5. Finalises the experiment with a summary run
"""
from __future__ import annotations

import sys
import time
import argparse
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.panel import Panel
from rich.text import Text
from rich import box

import config.settings as cfg  # noqa: F401  — sets LANGCHAIN_* env vars
from langsmith_eval_logger import eval_logger
from eval_judge import EVAL_REGISTRY, run_all_evals

console = Console()
EVAL_RUNS_DIR = PROJECT_ROOT / "data" / "eval_runs"

# ── Category metadata for display ─────────────────────────────────────────────
_CATEGORY_META = {
    "eval_1_skill_match":           ("Eval 1", "Skill Match",            "Agents returned cover required skills"),
    "eval_2_confidence_calibration":("Eval 2", "Confidence Calibration", "HIGH-conf extractions map to correct product"),
    "eval_3_semantic_search":       ("Eval 3", "Semantic Search",        "Sentence-transformer routes to correct product"),
    "eval_4_graceful_degradation":  ("Eval 4", "Graceful Degradation",   "Vague inputs reach manual picker"),
    "eval_5_latency":               ("Eval 5", "Latency",                "Graph recommendation < 10 s"),
    "eval_6_resolution_time":       ("Eval 6", "Resolution Time",        "Top agents save ≥ 1 hr vs random"),
}


# ── Dry-run stubs (show structure without hitting external services) ───────────
def _dry_run_results() -> list[dict]:
    stubs = [
        ("eval_1_skill_match",            "Payment Gateway — SK001+SK002",     True,  94.0),
        ("eval_1_skill_match",            "SSO Module — SK007+SK009",           True,  88.0),
        ("eval_1_skill_match",            "Analytics — SK014+SK013",            True,  91.0),
        ("eval_2_confidence_calibration", "Explicit Payment Gateway mention",   True,  0.97),
        ("eval_2_confidence_calibration", "Explicit SSO mention",               True,  0.93),
        ("eval_2_confidence_calibration", "Explicit Analytics mention",         True,  0.91),
        ("eval_3_semantic_search",        "Payment keywords — no name",         True,  0.82),
        ("eval_3_semantic_search",        "Auth / login keywords — no name",    True,  0.79),
        ("eval_3_semantic_search",        "Reporting keywords — no name",       True,  0.84),
        ("eval_3_semantic_search",        "SAML / federated identity",          False, 0.58),
        ("eval_3_semantic_search",        "Revenue / billing theme",            True,  0.76),
        ("eval_4_graceful_degradation",   "Pure urgency — no content",          True,  None),
        ("eval_4_graceful_degradation",   "Gibberish input",                    True,  None),
        ("eval_4_graceful_degradation",   "Vague break complaint",              True,  None),
        ("eval_5_latency",                "Scenario A — Payment Gateway",       True,  1.23),
        ("eval_5_latency",                "Scenario B — SSO Module",            True,  1.41),
        ("eval_5_latency",                "Scenario C — Analytics",             True,  1.38),
        ("eval_6_resolution_time",        "Payment Gateway resolved cases",     True,  28.5),
        ("eval_6_resolution_time",        "SSO Module resolved cases",          True,  24.1),
        ("eval_6_resolution_time",        "Analytics resolved cases",           True,  31.8),
    ]
    return [
        {
            "eval_category": cat,
            "label":         label,
            "test_input":    {"stub": True},
            "output":        {"stub": True, "score": score},
            "passed":        passed,
            "score":         score,
            "metadata":      {"passed": passed, "dry_run": True},
            "tags":          [cat, "dry_run"],
        }
        for cat, label, passed, score in stubs
    ]


# ── Pretty console output ──────────────────────────────────────────────────────

def _print_category_header(category: str) -> None:
    _, name, description = _CATEGORY_META.get(category, ("", category, ""))
    console.print()
    console.rule(f"[bold cyan]{name}[/bold cyan]  [dim]{description}[/dim]")


def _print_result(r: dict) -> None:
    icon   = "✓" if r["passed"] else "✗"
    color  = "green" if r["passed"] else "red"
    label  = r["label"]
    score_str = ""
    if r["score"] is not None:
        cat = r["eval_category"]
        if "latency" in cat:
            score_str = f"  [{r['score']:.2f}s]"
        elif "resolution" in cat:
            score_str = f"  [{r['score']:.1f}% faster]"
        elif isinstance(r["score"], float) and r["score"] <= 1.0:
            score_str = f"  [{r['score']:.0%}]"
        else:
            score_str = f"  [{r['score']:.0f}]"

    console.print(
        f"  [{color}]{icon}[/{color}]  {label}[dim]{score_str}[/dim]"
    )

    # Show key output fields inline (non-error cases)
    out = r.get("output", {})
    if "error" in out:
        console.print(f"     [red]Error: {out['error']}[/red]")


def _print_summary_table(results: list[dict], elapsed_total: float) -> None:
    console.print()
    console.rule("[bold]Summary[/bold]")

    # Per-category breakdown
    by_cat: dict[str, list[bool]] = {}
    for r in results:
        by_cat.setdefault(r["eval_category"], []).append(r["passed"])

    tbl = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold magenta")
    tbl.add_column("#",           style="dim",   width=6)
    tbl.add_column("Category",    style="white", min_width=28)
    tbl.add_column("Passed",      justify="center")
    tbl.add_column("Total",       justify="center")
    tbl.add_column("Pass Rate",   justify="right")

    grand_pass = grand_total = 0

    for cat, (num, name, _) in _CATEGORY_META.items():
        passed_list = by_cat.get(cat, [])
        p  = sum(passed_list)
        t  = len(passed_list)
        pr = p / t if t else 0
        grand_pass  += p
        grand_total += t
        color = "green" if pr == 1.0 else ("yellow" if pr >= 0.5 else "red")
        tbl.add_row(
            num, name,
            f"[{color}]{p}[/{color}]",
            str(t),
            f"[{color}]{pr:.0%}[/{color}]",
        )

    tbl.add_section()
    overall = grand_pass / grand_total if grand_total else 0
    color   = "green" if overall >= 0.9 else ("yellow" if overall >= 0.7 else "red")
    tbl.add_row(
        "", "[bold]TOTAL[/bold]",
        f"[bold {color}]{grand_pass}[/bold {color}]",
        f"[bold]{grand_total}[/bold]",
        f"[bold {color}]{overall:.0%}[/bold {color}]",
    )
    console.print(tbl)
    console.print(f"  Total eval time: [dim]{elapsed_total:.1f}s[/dim]")

    return grand_pass, grand_total, overall


def _format_metric(category: str, score: float | int | None) -> str:
    if score is None:
        return ""
    if "latency" in category:
        return f"{float(score):.2f}s"
    if "resolution" in category:
        return f"{float(score):.1f}% faster"
    if isinstance(score, float) and score <= 1.0:
        return f"{score:.0%}"
    return f"{score:.0f}"


def _write_local_eval_report(
    *,
    experiment_name: str,
    dry_run: bool,
    results: list[dict],
    elapsed_seconds: float,
    total_passed: int,
    total_tests: int,
    pass_rate: float,
) -> Path:
    by_cat: dict[str, list[dict]] = {}
    for result in results:
        by_cat.setdefault(result["eval_category"], []).append(result)

    categories = []
    for cat, (_, name, _) in _CATEGORY_META.items():
        cat_results = by_cat.get(cat, [])
        passed = sum(1 for r in cat_results if r["passed"])
        total = len(cat_results)
        categories.append({
            "id": cat,
            "name": name,
            "passed": passed,
            "total": total,
            "pass_rate": passed / total if total else 0,
        })

    report = {
        "experiment_name": experiment_name,
        "project": cfg.LANGCHAIN_PROJECT,
        "dataset": "support-intelligence-evals",
        "run_type": "dry_run" if dry_run else "live",
        "ran_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed_seconds, 2),
        "total_passed": total_passed,
        "total_tests": total_tests,
        "pass_rate": pass_rate,
        "categories": categories,
        "results": [
            {
                "category": _CATEGORY_META.get(r["eval_category"], ("", r["eval_category"], ""))[1],
                "label": r["label"],
                "passed": r["passed"],
                "score": r.get("score"),
                "metric": _format_metric(r["eval_category"], r.get("score")),
            }
            for r in results
        ],
    }

    EVAL_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_RUNS_DIR / f"{experiment_name}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


# ── Main ───────────────────────────────────────────────────────────────────────

def run_evals(dry_run: bool = False) -> None:
    console.print()
    console.print(Panel(
        Text(
            f"CaseIQ · Automated Evaluation Suite\n"
            f"{'DRY RUN — no external calls' if dry_run else 'Live run — Neo4j + Groq + LangSmith'}\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            justify="center",
        ),
        title="[bold cyan]CaseIQ Evals[/bold cyan]",
        expand=False,
    ))

    # ── 1. Initialise LangSmith experiment ────────────────────────────────────
    experiment_name = eval_logger.initialize_experiment("evals-support-intelligence")
    console.print(f"\n  Experiment : [yellow]{experiment_name}[/yellow]")
    console.print(f"  LangSmith  : smith.langchain.com → {cfg.LANGCHAIN_PROJECT}\n")

    # ── 2. Run all evals ──────────────────────────────────────────────────────
    t_start = time.perf_counter()

    if dry_run:
        console.print("[dim]Dry run — generating stub results and logging to LangSmith…[/dim]")
        all_results = _dry_run_results()
        # Still log stubs to LangSmith so the experiment appears with real data
        prev_cat = None
        for r in all_results:
            if r["eval_category"] != prev_cat:
                _print_category_header(r["eval_category"])
                prev_cat = r["eval_category"]
            _print_result(r)
            eval_logger.log_eval_result(
                eval_category   = r["eval_category"],
                test_input      = r["test_input"],
                output          = r["output"],
                passed          = r["passed"],
                score_or_metric = r.get("score"),
                metadata        = r.get("metadata"),
                tags            = r.get("tags"),
            )
    else:
        all_results = []
        for cat_name, fn in EVAL_REGISTRY:
            _print_category_header(fn.__name__)
            try:
                cat_results = fn()
            except Exception as exc:
                console.print(f"  [red]CATEGORY FAILED: {exc}[/red]")
                cat_results = [{
                    "eval_category": fn.__name__,
                    "label":         f"{cat_name} — CATEGORY ERROR",
                    "test_input":    {},
                    "output":        {"error": str(exc)},
                    "passed":        False,
                    "score":         None,
                    "metadata":      {"category_error": True},
                    "tags":          [fn.__name__, "error"],
                }]
            for r in cat_results:
                _print_result(r)
                # ── 3. Log each result to LangSmith ───────────────────────────
                eval_logger.log_eval_result(
                    eval_category   = r["eval_category"],
                    test_input      = r["test_input"],
                    output          = r["output"],
                    passed          = r["passed"],
                    score_or_metric = r.get("score"),
                    metadata        = r.get("metadata"),
                    tags            = r.get("tags"),
                )
            all_results.extend(cat_results)

    elapsed = time.perf_counter() - t_start

    # ── 4. Summary table ──────────────────────────────────────────────────────
    grand_pass, grand_total, overall = _print_summary_table(all_results, elapsed)

    report_path = _write_local_eval_report(
        experiment_name = experiment_name,
        dry_run         = dry_run,
        results         = all_results,
        elapsed_seconds = elapsed,
        total_passed    = grand_pass,
        total_tests     = grand_total,
        pass_rate       = overall,
    )
    console.print(f"  Local report: [cyan]{report_path}[/cyan]")

    # ── 5. Finalise LangSmith experiment ──────────────────────────────────────
    eval_logger.finalize_experiment(
        total_passed = grand_pass,
        total_tests  = grand_total,
        pass_rate    = overall,
    )

    # ── 6. Interview talking points ───────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold]For the interview:[/bold]\n\n"
        f"  1. Open [underline]smith.langchain.com[/underline]\n"
        f"  2. Projects → [cyan]{cfg.LANGCHAIN_PROJECT}[/cyan]\n"
        f"  3. Datasets & Testing → [yellow]{eval_logger._dataset_id and 'support-intelligence-evals' or 'support-intelligence-evals'}[/yellow]\n"
        f"  4. Filter traces by tag: [yellow]{experiment_name}[/yellow]\n\n"
        f"  Each re-run creates a new timestamped experiment so you can\n"
        f"  compare improvement across versions side-by-side.",
        title="[bold green]LangSmith View[/bold green]",
        expand=False,
    ))
    console.print()


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run CaseIQ evaluation suite and log results to LangSmith."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip Neo4j/LLM calls and log stub results to LangSmith instead.",
    )
    args = parser.parse_args()
    run_evals(dry_run=args.dry_run)
