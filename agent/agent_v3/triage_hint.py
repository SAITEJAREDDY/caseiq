"""The agent-side half of early triage: turns a triage record into a PROVISIONAL hint for the prompt, and classifies what the agent did with it.

Roles (kept apart on purpose)
  early triage  guidance    a category suggestion from the ticket text alone, before any graph investigation. Never evidence, never a diagnosis.
  late verifier verification the Phase 9 checks on the finished answer (agent_v3 knows nothing about it).

This module is deliberately Jev-free and reads no evaluation data: it only formats what the injected `triage(ctx)` callback returned and compares the agent's final
category with the suggestion. It never changes the tool catalog, the action schema or the final schema, so no category, tool or evidence item can be filtered away by
a hint. Without a usable hint `prepare` returns an empty string and every prompt is byte-identical to the unchanged baseline (a test pins this).
"""
from typing import Optional

from agent.agent_v3.catalog import TOOLS_BY_NAME

TRIAGE_PROMPT_VERSION = "early_triage_prompt_v1"
HINT = "hint"      # the only status that produces prompt text; every other status is a fallback to the unchanged workflow
MIN_ALTERNATIVE_SHOWN = 0.05     # a competing category below this is noise, not a competitor; the record still stores the full top list

# what the agent did with the suggestion
CONFIRMED, CHANGED, DROPPED, NO_SUGGESTION, NO_FINAL_ANSWER = "confirmed", "changed", "dropped", "no_suggestion", "no_final_answer"


def _norm(x) -> str:
    return " ".join(str(x or "").lower().split())


def _fmt(entity, p) -> str:
    return f"{entity.alias} = {entity.display_name or entity.canonical_id} ({p:.2f})"


def render(record: dict, chosen, others: list) -> str:
    """The provisional-hint block. `chosen` is the registry entity of the suggested category; `others` are (entity, probability) pairs."""
    tools = [t for t in record.get("suggested_tools") or [] if t.split(" ")[0] in TOOLS_BY_NAME]
    lines = [
        "EARLY TRIAGE HINT (provisional and unverified)",
        "Source: Jev early triage. It read only the ticket text and basic customer/product details; no tool, log, telemetry or graph evidence had been examined.",
        f"Suggested issue category: {chosen.alias} = {chosen.display_name or chosen.canonical_id} (probability {record['probability']:.2f}, {record['uncertainty']} uncertainty).",
    ]
    if others:
        lines.append("Other categories Jev considered: " + "; ".join(_fmt(e, p) for e, p in others) + ".")
    lines.append("This is a prior, not a finding, and it may be wrong. Test it against the evidence you retrieve, weigh the competing categories, and reject or replace it if "
                 "the evidence points elsewhere. It is not evidence and cannot be cited. Choose your final issue_category from the evidence.")
    if tools:
        lines.append("Suggested starting points for this category (advisory only: every tool stays available and no category or evidence is ruled out): " + "; ".join(tools) + ".")
    return "\n".join(lines)


def prepare(record: Optional[dict], registry) -> tuple:
    """(record, hint_text). The record comes back possibly downgraded to a fallback (a suggestion that is not in this graph's taxonomy is unusable); the text is
    empty for every fallback."""
    if record is None or record.get("status") != HINT:
        return record, ""
    by_id = {e.canonical_id: e for e in registry.by_kind("CATEGORY")}
    chosen = by_id.get(record.get("category_id"))
    if chosen is None or not isinstance(record.get("probability"), (int, float)):
        return {**record, "status": "invalid", "fallback": True, "fallback_reason": "the suggested category is not in this graph's taxonomy", "category_id": None}, ""
    if _norm(chosen.display_name) != _norm(record.get("category_name")):      # Jev judged one name and the agent would be shown another: taxonomy drift, so no hint
        return {**record, "status": "invalid", "fallback": True, "category_id": None,
                "fallback_reason": "the category name differs between the graph taxonomy and the list Jev answered from"}, ""
    others = [(by_id[a["category_id"]], a["probability"]) for a in record.get("alternatives") or [] if a.get("category_id") in by_id and a["probability"] >= MIN_ALTERNATIVE_SHOWN]
    return record, render(record, chosen, others)


def outcome(record: Optional[dict], final_diag: Optional[dict], names: dict = None) -> Optional[dict]:
    """Whether the agent confirmed, changed or dropped the suggestion. Descriptive only: it says nothing about which category is correct."""
    if record is None:
        return None
    suggested = record.get("category_id") if record.get("status") == HINT else None
    final = (final_diag or {}).get("predicted_category_id")
    if suggested is None:
        label = NO_SUGGESTION
    elif (final_diag or {}).get("status") == "CONTRACT_FAILURE":
        label = NO_FINAL_ANSWER
    elif final is None:
        label = DROPPED
    elif final == suggested:
        label = CONFIRMED
    else:
        label = CHANGED
    names = names or {}
    alt_ids = [a["category_id"] for a in record.get("alternatives") or []]
    return {"outcome": label, "hint_shown": suggested is not None, "suggested_category_id": suggested, "suggested_category": names.get(suggested),
            "final_category_id": final, "final_category": names.get(final), "final_in_alternatives": bool(final and suggested and final != suggested and final in alt_ids)}
