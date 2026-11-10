"""Deterministic contract-compliance classification (spec sections 22, 24,
49, 50): string-rule based, not an LLM judge -- classifies tool-call errors
already recorded in a run's trace_steps, and summarizes repair_events
(present on runs generated after the Phase 6 loop.py instrumentation; absent
on older runs, which are reported as "repair status unknown", never as
clean).
"""
import re

_UNKNOWN_TOOL_RE = re.compile(r"unknown tool")
_VALIDATION_ERROR_RE = re.compile(r"validation error|field required|literal_error|type=missing", re.IGNORECASE)
_NEO4J_ERROR_RE = re.compile(r"neo\.clienterror|neo\.transienterror|cypher", re.IGNORECASE)


def classify_tool_error(error_message: str) -> str:
    if not error_message:
        return "none"
    if _UNKNOWN_TOOL_RE.search(error_message):
        return "unknown_tool"
    if _VALIDATION_ERROR_RE.search(error_message):
        return "validation_error"
    if _NEO4J_ERROR_RE.search(error_message):
        return "neo4j_error"
    return "other"


def tool_use_metrics(trace_steps: list) -> dict:
    diagnostic_steps = [s for s in trace_steps if s.get("tool_name") != "submit_diagnosis"]
    tool_names = [s.get("tool_name") for s in diagnostic_steps]
    unique_tools = len(set(tool_names))
    redundant = sum(1 for s in trace_steps if s.get("redundant"))
    errors = [s for s in trace_steps if s.get("status") == "error"]
    error_types = [
        classify_tool_error((s.get("result_summary") or {}).get("error", "") if isinstance(s.get("result_summary"), dict) else "")
        for s in errors
    ]

    return {
        "total_steps": len(trace_steps),
        "diagnostic_tool_calls": len(diagnostic_steps),
        "unique_tool_types": unique_tools,
        "redundant_calls": redundant,
        "tool_errors": len(errors),
        "unknown_tool_calls": error_types.count("unknown_tool"),
        "validation_errors": error_types.count("validation_error"),
        "neo4j_errors": error_types.count("neo4j_error"),
        "other_errors": error_types.count("other"),
    }


def repair_summary(run: dict) -> dict:
    if "repair_events" not in run:
        return {
            "repair_status_known": False,
            "repair_event_count": None,
            "hypothesis_normalization_repairs": None,
            "final_diagnosis_repairs": None,
            "final_diagnosis_fallbacks": None,
        }
    events = run.get("repair_events") or []
    kinds = [e.get("kind") for e in events]
    return {
        "repair_status_known": True,
        "repair_event_count": len(events),
        "hypothesis_normalization_repairs": kinds.count("hypothesis_normalization"),
        "final_diagnosis_repairs": kinds.count("final_diagnosis_repair"),
        "final_diagnosis_fallbacks": kinds.count("final_diagnosis_fallback"),
    }


def is_clean_run(run: dict, tool_metrics: dict, repair: dict) -> bool:
    """A clean run: repair status must be KNOWN and zero, no tool errors, no
    citation violations, and the model itself ended the loop (not a forced
    submit or a total tool-calling failure)."""
    if not repair.get("repair_status_known"):
        return False
    if repair.get("repair_event_count", 0) > 0:
        return False
    if tool_metrics.get("tool_errors", 0) > 0:
        return False
    if len(run.get("citation_violations") or []) > 0:
        return False
    if run.get("stop_reason") != "model_submitted":
        return False
    return True
