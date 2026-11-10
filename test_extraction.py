"""
Smoke-tests for the dual-confidence extraction pipeline.

Usage:
    python test_extraction.py

Each test case exercises a different confidence path through the pipeline.
No Streamlit imports needed — all test targets are pure Python functions.
"""
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich import box

console = Console()

# ── helpers ────────────────────────────────────────────────────────────────────

def _verdict(ext: dict) -> str:
    if ext.get("auto_assign"):
        return "[bold green]AUTO-ASSIGN[/bold green]"
    if ext.get("needs_confirmation"):
        return "[bold yellow]NEEDS CONFIRM[/bold yellow]"
    if ext.get("needs_manual_selection"):
        return "[bold red]MANUAL PICK[/bold red]"
    return "[dim]unknown[/dim]"


def run_test(label: str, user_input: str, expected_path: str) -> bool:
    """Run one extraction and print the result. Returns True if path matches."""
    from agent.llm_client import gpt_extract_case
    from agent.semantic_search import SemanticMatcher
    from agent.graph_client import get_all_products
    import config.settings as cfg

    catalog      = get_all_products()
    product_names = [p["name"] for p in catalog]
    name_to_id   = {p["name"]: p["product_id"] for p in catalog}

    # ── Step 1: keyword extraction ────────────────────────────────────────────
    kw     = gpt_extract_case(user_input, product_names)
    kconf  = kw["keyword_confidence"]

    product    = None
    product_id = None
    match_type = "unknown"
    auto_assign              = False
    needs_confirmation       = False
    needs_manual_selection   = False
    semantic_similarity      = None

    if kconf >= cfg.CONF_HIGH and kw["product"] and kw["product"] in name_to_id:
        product    = kw["product"]
        product_id = name_to_id[kw["product"]]
        match_type = "keyword_high"
        auto_assign = True

    elif kconf >= cfg.CONF_MEDIUM and kw["product"] and kw["product"] in name_to_id:
        product    = kw["product"]
        product_id = name_to_id[kw["product"]]
        match_type = "keyword_medium"
        needs_confirmation = True

    else:
        # ── Step 2: semantic search ────────────────────────────────────────────
        matcher = SemanticMatcher()
        sem     = matcher.find_closest_product(user_input)
        semantic_similarity = sem.get("similarity_score", 0.0)

        if sem["confidence_level"] == "HIGH" and sem["product_id"]:
            product    = sem["product"]
            product_id = sem["product_id"]
            match_type = "semantic_high"
            auto_assign = True
        elif sem["confidence_level"] in ("MEDIUM", "LOW") and sem["product_id"]:
            product    = sem["product"]
            product_id = sem["product_id"]
            match_type = "semantic_medium"
            needs_confirmation = True
        else:
            match_type = "insufficient"
            needs_manual_selection = True

    result = dict(
        title=kw["title"],
        product=product,
        product_id=product_id,
        keyword_confidence=kconf,
        semantic_similarity=semantic_similarity,
        match_type=match_type,
        auto_assign=auto_assign,
        needs_confirmation=needs_confirmation,
        needs_manual_selection=needs_manual_selection,
        explanation=kw.get("confidence_reasoning", ""),
    )

    actual_path = (
        "auto_assign"       if auto_assign             else
        "needs_confirmation" if needs_confirmation      else
        "needs_manual_selection"
    )
    passed = actual_path == expected_path

    # print summary row
    console.print(f"\n[bold]{'✓' if passed else '✗'}  {label}[/bold]")
    console.print(f"   Input      : [italic]{user_input[:80]}[/italic]")
    console.print(f"   Product    : [cyan]{product or 'None'}[/cyan]  (id={product_id})")
    console.print(f"   Keyword    : {kconf:.2f}  |  Semantic: "
                  f"{f'{semantic_similarity:.2f}' if semantic_similarity is not None else 'n/a'}")
    console.print(f"   Match type : {match_type}")
    console.print(f"   Path       : {_verdict(result)}  (expected {expected_path})")
    if not passed:
        console.print(f"   [bold red]MISMATCH — got {actual_path!r}, expected {expected_path!r}[/bold red]")

    return passed


# ── Test cases ─────────────────────────────────────────────────────────────────

TESTS = [
    {
        "label":    "1 · Explicit product name → keyword HIGH",
        "input":    "Customer can't log in through SSO Integration Module — "
                    "getting a 401 Unauthorized on every OAuth callback.",
        "expected": "auto_assign",
    },
    {
        "label":    "2 · Ambiguous payment issue → keyword MEDIUM or semantic",
        "input":    "Payment keeps failing at checkout — customer says card is valid "
                    "but transactions are rejected with error code 4023.",
        "expected": "auto_assign",        # likely high for payment gateway
    },
    {
        "label":    "3 · Vague auth / login complaint → semantic search",
        "input":    "Users cannot sign in after the maintenance window last night.",
        "expected": "needs_confirmation", # ambiguous between SSO / gateway
    },
    {
        "label":    "4 · Analytics-sounding query → semantic search",
        "input":    "The charts and graphs in the reporting section are loading "
                    "extremely slowly — takes 30 seconds to render.",
        "expected": "auto_assign",        # analytics dashboard keywords
    },
    {
        "label":    "5 · Completely vague / off-topic → INSUFFICIENT",
        "input":    "It broke again. Please help ASAP!!!",
        "expected": "needs_manual_selection",
    },
    {
        "label":    "6 · Nonsense input → INSUFFICIENT",
        "input":    "asdfgh xyz qwerty 1234 foobar",
        "expected": "needs_manual_selection",
    },
]


def main():
    console.print()
    console.print(Rule("[bold cyan]CaseIQ — Extraction Pipeline Tests[/bold cyan]"))
    console.print("Testing 6 scenarios across the keyword→semantic→manual fallback chain.\n")

    results  = []
    for tc in TESTS:
        try:
            passed = run_test(tc["label"], tc["input"], tc["expected"])
            results.append(passed)
        except Exception as exc:
            console.print(f"   [red]ERROR: {exc}[/red]")
            results.append(False)

    passed_count = sum(results)
    total        = len(results)

    console.print()
    console.print(Rule())
    if passed_count == total:
        console.print(f"[bold green]{passed_count}/{total} tests passed ✓[/bold green]")
    else:
        failed = [TESTS[i]["label"] for i, p in enumerate(results) if not p]
        console.print(f"[bold yellow]{passed_count}/{total} tests passed[/bold yellow]")
        console.print("[dim]Note: Medium-confidence tests may differ by run depending on "
                      "LLM confidence distribution — that is expected behaviour.[/dim]")
        for f in failed:
            console.print(f"   [red]✗  {f}[/red]")
    console.print()


if __name__ == "__main__":
    main()
