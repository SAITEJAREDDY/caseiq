"""
Customer Support Intelligence Agent — comparison demo.
Each scenario runs twice: once WITHOUT graph data, once WITH graph data.
Demonstrates why graph-grounded reasoning outperforms raw LLM responses.

Usage:
    python agent/main.py              # interactive picker
    python agent/main.py --scenario A
    python agent/main.py --scenario B
    python agent/main.py --scenario C
    python agent/main.py --all        # run all 3 in sequence
"""
import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config.settings as cfg

from rich.console import Console
from rich.rule import Rule

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from agent.graph_client import (
    find_similar_cases,
    find_best_agents,
    find_kb_articles,
    get_full_recommendation,
    close_driver,
)
from agent.llm_client import new_session, ask
from agent.utils import format_executive_context, build_citation_block

console = Console()

# ── Scenario definitions ──────────────────────────────────────────────────────

SCENARIOS = cfg.SCENARIOS

# ── No-graph LLM chain (single-shot, no memory, no graph context) ─────────────

_raw_llm = ChatGroq(
    api_key=cfg.GROQ_API_KEY,
    model_name=cfg.GROQ_MODEL,
    temperature=cfg.GROQ_TEMP,
    max_tokens=cfg.GROQ_MAX_TOKENS,
    model_kwargs={"reasoning_effort": "low"},  # low effort for baseline; saves TPM for the graph-augmented call
)

_NO_GRAPH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a senior customer support advisor at an enterprise software company. "
            "Answer using ONLY your general knowledge — no internal systems, no databases.\n\n"
            "For the given support case respond in exactly this structure:\n"
            "1. **2 Best Agents to Assign** — describe the ideal role/seniority profile and explain why\n"
            "2. **3 Most Relevant Resources** — name specific documentation, runbooks, or KB categories to consult and explain why each matters\n"
            "3. **Estimated Resolution Time** — give a time range based on typical cases of this type\n"
            "4. **Escalation Risk Assessment** — rate the risk and state what conditions would trigger escalation\n\n"
            "Be concise. Match the depth of each section. Do not add sections outside this structure."
        ),
    ),
    ("human", "Support case: {input}"),
])

_no_graph_chain = _NO_GRAPH_PROMPT | _raw_llm


# format_executive_context and build_citation_block live in agent/utils.py
# (imported at the top of this file)


# ── Display ───────────────────────────────────────────────────────────────────

def display_comparison(
    key:              str,
    scenario:         dict,
    without_response: str,
    with_response:    str,
    citation:         str,
) -> None:
    divider = "=" * 64

    console.print()
    console.print(f"[bold white]{divider}[/bold white]")
    console.print(f"[bold yellow]SCENARIO {key}: {scenario['label'].upper()}[/bold yellow]")
    console.print(f"[bold white]{divider}[/bold white]")
    console.print(f"[dim]{scenario['description']}[/dim]")
    console.print()

    # WITHOUT GRAPH
    console.print("[bold red]WITHOUT GRAPH:[/bold red]")
    console.print()
    for line in without_response.splitlines():
        console.print(f"  {line}")
    console.print()

    # WITH GRAPH
    console.print("[bold green]WITH GRAPH:[/bold green]")
    console.print()
    for line in with_response.splitlines():
        console.print(f"  {line}")
    console.print()

    # Citation block
    console.print("[bold cyan]" + citation + "[/bold cyan]")
    console.print()
    console.print(
        f"[dim]LangSmith trace → smith.langchain.com "
        f"| Project: {cfg.LANGCHAIN_PROJECT}[/dim]"
    )
    console.print()


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_scenario(key: str) -> None:
    scenario = SCENARIOS[key]

    console.print(f"\n[dim]Running Scenario {key}: {scenario['label']}...[/dim]")

    # ── WITHOUT GRAPH ──────────────────────────────────────────────────────────
    console.print("[dim]  • Calling LLM without graph data...[/dim]")
    t0 = time.time()
    no_graph_result = _no_graph_chain.invoke({"input": scenario["description"]})
    without_response = no_graph_result.content
    no_graph_ms = (time.time() - t0) * 1000

    # ── Graph traversal ────────────────────────────────────────────────────────
    console.print("[dim]  • Traversing knowledge graph (4 hops)...[/dim]")
    t1 = time.time()
    similar       = find_similar_cases(scenario["description"], scenario["product_id"])
    agents        = find_best_agents(scenario["product_id"], scenario["required_skills"])
    articles      = find_kb_articles(scenario["product_id"])
    recommendation = get_full_recommendation(scenario["customer_id"], scenario["product_id"])
    graph_ms = (time.time() - t1) * 1000

    # ── WITH GRAPH ─────────────────────────────────────────────────────────────
    console.print("[dim]  • Calling LLM with graph intelligence...[/dim]")
    context = format_executive_context(scenario, similar, agents, articles, recommendation)
    chain = new_session(f"scenario_{key}_graph")
    t2 = time.time()
    with_response = ask(chain, context, session_id=f"scenario_{key}_graph")
    with_graph_ms = (time.time() - t2) * 1000

    console.print(
        f"[dim]  ✓ Done — "
        f"no-graph LLM {no_graph_ms:.0f}ms | "
        f"graph traversal {graph_ms:.0f}ms | "
        f"graph LLM {with_graph_ms:.0f}ms[/dim]"
    )

    # ── Citation block ─────────────────────────────────────────────────────────
    citation = build_citation_block(similar, agents, articles)

    # ── Display ────────────────────────────────────────────────────────────────
    display_comparison(key, scenario, without_response, with_response, citation)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Support Intelligence Agent — comparison demo")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--scenario", choices=["A", "B", "C"],
                       help="Run a specific scenario")
    group.add_argument("--all", action="store_true",
                       help="Run all 3 scenarios in sequence")
    args = parser.parse_args()

    console.print(Rule("[bold cyan]Customer Support Intelligence Agent[/bold cyan]"))
    console.print(f"  Model            : [yellow]{cfg.GROQ_MODEL}[/yellow]")
    console.print(f"  Reasoning effort : [yellow]{cfg.GROQ_REASONING_EFFORT}[/yellow]")
    console.print(f"  Graph            : [yellow]{cfg.NEO4J_URI}[/yellow]")
    console.print(f"  LangSmith        : [yellow]{cfg.LANGCHAIN_PROJECT}[/yellow]")

    _TPM_COOLDOWN = 62  # seconds between scenarios to avoid 8k TPM limit

    try:
        if args.all:
            keys = ["A", "B", "C"]
            for i, key in enumerate(keys):
                run_scenario(key)
                if i < len(keys) - 1:
                    console.print(
                        f"[dim]  ⏳ Rate-limit cooldown ({_TPM_COOLDOWN}s)...[/dim]"
                    )
                    time.sleep(_TPM_COOLDOWN)
        elif args.scenario:
            run_scenario(args.scenario)
        else:
            console.print("\nAvailable scenarios:")
            for key, s in SCENARIOS.items():
                console.print(f"  [bold cyan]{key}[/bold cyan] — {s['label']}")
            console.print()
            choice = console.input(
                "[bold]Select scenario (A / B / C / all): [/bold]"
            ).strip().upper()
            if choice == "ALL":
                keys = ["A", "B", "C"]
                for i, key in enumerate(keys):
                    run_scenario(key)
                    if i < len(keys) - 1:
                        console.print(
                            f"[dim]  ⏳ Rate-limit cooldown ({_TPM_COOLDOWN}s)...[/dim]"
                        )
                        time.sleep(_TPM_COOLDOWN)
            elif choice in SCENARIOS:
                run_scenario(choice)
            else:
                console.print(f"[red]Invalid choice: {choice}[/red]")
                sys.exit(1)
    finally:
        close_driver()


if __name__ == "__main__":
    main()
