"""
LLM client — Groq (openai/gpt-oss-120b) via LCEL + RunnableWithMessageHistory.
LangSmith tracing fires automatically once LANGCHAIN_TRACING_V2 is set in env.
"""
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import settings first — sets LANGCHAIN_* env vars before LangChain initialises
import config.settings as cfg  # noqa: F401

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from agent.memory import get_session_history, clear_session
from agent.prompts import SYSTEM_PROMPT
from agent.cost_callback import CostTrackingCallback

_cost_cb = CostTrackingCallback()


# ── LLM ──────────────────────────────────────────────────────────────────────

_llm = ChatGroq(
    api_key=cfg.GROQ_API_KEY,
    model_name=cfg.GROQ_MODEL,
    temperature=cfg.GROQ_TEMP,
    max_tokens=cfg.GROQ_MAX_TOKENS,
    model_kwargs={"reasoning_effort": cfg.GROQ_REASONING_EFFORT},
    callbacks=[_cost_cb],
)

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

# Base chain: prompt → LLM
_chain = _PROMPT | _llm


# ── Public API ────────────────────────────────────────────────────────────────

def build_chain(session_id: str = "default") -> RunnableWithMessageHistory:
    """Return a chain bound to a named session (rolling window of last 5 exchanges)."""
    return RunnableWithMessageHistory(
        _chain,
        lambda sid: get_session_history(sid, k=cfg.MEMORY_WINDOW_SIZE),
        input_messages_key="input",
        history_messages_key="history",
    )


def ask(chain: RunnableWithMessageHistory, message: str,
        session_id: str = "default") -> str:
    """Send a message and return the LLM's text response."""
    result = chain.invoke(
        {"input": message},
        config={"configurable": {"session_id": session_id}},
    )
    return result.content


def ask_with_usage(chain: RunnableWithMessageHistory, message: str,
                   session_id: str = "default") -> tuple[str, dict]:
    """
    Send a message and return (response_text, token_usage_dict).
    token_usage_dict keys: prompt_tokens, completion_tokens, total_tokens
    """
    result = chain.invoke(
        {"input": message},
        config={"configurable": {"session_id": session_id}},
    )
    usage = result.response_metadata.get("token_usage") or \
            result.response_metadata.get("usage") or {}
    return result.content, usage


def new_session(session_id: str = "default") -> RunnableWithMessageHistory:
    """Clear history for session_id and return a fresh chain."""
    clear_session(session_id)
    return build_chain(session_id)


# ── Case extraction with confidence scoring ───────────────────────────────────

_extract_llm = ChatGroq(
    api_key=cfg.GROQ_API_KEY,
    model_name=cfg.GROQ_MODEL,
    temperature=0.0,
    max_tokens=300,   # only needs a small JSON blob
)

_EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "human",
        """You are a support case classifier. Extract the product and rate your confidence.

Available products:
{products}

Return ONLY valid JSON (no markdown fences, no explanation):
{{
  "title": "short case title under 10 words",
  "product": "exact product name from the list above, or null if unsure",
  "keyword_confidence": 0.0,
  "confidence_reasoning": "one sentence explaining why this confidence level"
}}

keyword_confidence scoring guide:
- 0.90-1.00 : user explicitly named the product
- 0.70-0.89 : strong product-specific technical keywords present
- 0.50-0.69 : some relevant keywords but intent is ambiguous
- 0.00-0.49 : vague, off-topic, or no recognisable product indicators

Support input: {input}""",
    )
])

_extract_chain = _EXTRACT_PROMPT | _extract_llm


def gpt_extract_case(user_input: str, product_names: list[str]) -> dict:
    """
    Call the LLM to extract the product and a keyword confidence score from
    raw free-text user input.

    Parameters
    ----------
    user_input    : the raw text the user submitted
    product_names : list of valid product names pulled from Neo4j

    Returns
    -------
    {
        "title":                str,
        "product":              str | None,   # exact name or None
        "keyword_confidence":   float,        # 0.0 – 1.0
        "confidence_reasoning": str,
    }
    """
    import json
    import re

    products_str = "\n".join(f"- {name}" for name in product_names)
    try:
        raw = _extract_chain.invoke(
            {"input": user_input, "products": products_str}
        ).content.strip()
        # Strip markdown code fences if model wrapped the JSON
        raw = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", raw, flags=re.DOTALL).strip()
        data = json.loads(raw)
        return {
            "title":                data.get("title", user_input[:60]),
            "product":              data.get("product") or None,
            "keyword_confidence":   min(1.0, max(0.0, float(data.get("keyword_confidence", 0.0)))),
            "confidence_reasoning": data.get("confidence_reasoning", ""),
        }
    except Exception:
        return {
            "title":                user_input[:60],
            "product":              None,
            "keyword_confidence":   0.0,
            "confidence_reasoning": "Extraction failed — falling back to semantic search.",
        }


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.rule import Rule
    from rich.text import Text
    from rich import box

    console = Console()

    console.print()
    console.print(Rule("[bold cyan]LLM Client Test[/bold cyan]"))
    console.print(f"  Model            : [yellow]{cfg.GROQ_MODEL}[/yellow]")
    console.print(f"  Temperature      : {cfg.GROQ_TEMP}")
    console.print(f"  Reasoning effort : [yellow]{cfg.GROQ_REASONING_EFFORT}[/yellow]")
    console.print(f"  Memory window    : last {cfg.MEMORY_WINDOW_SIZE} exchanges")
    console.print(f"  LangSmith project: [italic]{cfg.LANGCHAIN_PROJECT}[/italic]")
    console.print()

    test_message = (
        "A gold tier customer cannot process refunds on "
        "Payment Gateway v2 — error code 4023"
    )

    console.print(Panel(
        Text(test_message, style="white"),
        title="[yellow]Input[/yellow]",
        expand=False,
    ))

    chain = new_session("llm_test")
    t0 = time.time()
    response, usage = ask_with_usage(chain, test_message, session_id="llm_test")
    elapsed = (time.time() - t0) * 1000

    # Full response
    console.print(Panel(
        Text(response, style="bright_green"),
        title="[bold green]Response[/bold green]",
    ))

    # Token count table
    prompt_tokens     = usage.get("prompt_tokens", "—")
    completion_tokens = usage.get("completion_tokens", "—")
    total_tokens      = usage.get("total_tokens", "—")

    t = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
    t.add_column("Metric",          style="dim")
    t.add_column("Value",           justify="right")
    t.add_row("Prompt tokens",      str(prompt_tokens))
    t.add_row("Completion tokens",  str(completion_tokens))
    t.add_row("Total tokens",       str(total_tokens))
    t.add_row("Latency",            f"{elapsed:.0f} ms")
    console.print(t)

    console.print(
        f"[bold]LangSmith:[/bold] smith.langchain.com "
        f"→ Project: [italic]{cfg.LANGCHAIN_PROJECT}[/italic]"
    )
    console.print("[dim]This run should appear as a new trace in the project.[/dim]\n")
