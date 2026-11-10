"""The tool catalog, the per-turn action schema and the deterministic action validator (Phase 9A sections 8, 11, 12, 14).

The catalog is the single central definition of what the model may call. The prompt text, the JSON schema handed to the provider, the
validator and the exported machine-readable contract (`agent/contracts/agent_contract_v1.json`) are all generated from it, so they cannot
drift apart. Tools return evidence, never answers; nothing here adds a diagnostic shortcut.

The model is constrained by the provider's schema enforcement where the provider supports it, but every action is validated again
here before anything executes, and nothing is ever silently rewritten: an invalid proposal is rejected with a structured error.
"""
import json
from dataclasses import dataclass
from typing import Optional

from agent.agent_v3.config import KEYWORD_MAX, LABEL_MAX, MAX_HYPOTHESES
from agent.agent_v3.registry import CITABLE_KINDS, ID_RE, ObservedEntityRegistry

HYPOTHESIS_STATUSES = ("active", "rejected", "confirmed")  # the Phase 5 semantics, unchanged
METRIC_FAMILIES = ("Application", "Capacity", "Compute", "Data", "Database", "Identity", "Integration", "Networking", "Security", "Storage")
SUBMIT = "submit_diagnosis"
ACTION_FIELDS = ("hypotheses", "tool", "component", "metric_category", "keyword", "team")
ARG_FIELDS = ("component", "metric_category", "keyword", "team")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    purpose: str
    required: tuple = ()
    optional: tuple = ()
    returns: str = ""
    needs: Optional[str] = None  # availability precondition: an observed "component" or "team" alias must exist in the registry


TOOLS = (
    ToolSpec("get_customer_deployment", "What the customer runs: products, versions, environments, regions and each product's components.",
             returns="deployments with PRODUCT and COMPONENT aliases"),
    ToolSpec("get_component_topology", "A component's dependency graph and owning teams.", required=("component",), needs="component",
             returns="upstream/downstream COMPONENT aliases, external dependencies, TEAM aliases"),
    ToolSpec("get_technical_signals", "Observed technical error signals for this case (HTTP errors, auth/authz and TLS failures, database errors, "
             "timeouts). This is the closest thing to a log feed; there is no raw log search.", optional=("component",),
             returns="signal evidence items with timestamps"),
    ToolSpec("get_telemetry", "Summarised telemetry findings by metric category. Call once with metric_category null to list the categories "
             "that have data, then again with one category.", optional=("metric_category", "component"),
             returns="a category list, or telemetry finding evidence items"),
    ToolSpec("get_recent_changes", "Non-deployment changes near this case's time (policy, config, firewall, DNS, certificate, feature flag, capacity). "
             "May include changes unrelated to this case.", optional=("component",), returns="change evidence items (CHANGE aliases)"),
    ToolSpec("get_deployment_history", "Recent deployments (version changes) near this case's time. May include unrelated deployments.",
             optional=("component",), returns="deployment evidence items (CHANGE aliases)"),
    ToolSpec("get_configuration_history", "Configuration snapshots captured for this case (flags, limits, TLS versions, pool sizes).",
             optional=("component",), returns="configuration evidence items"),
    ToolSpec("get_service_health", "Platform service-health events for one component.", required=("component",), needs="component",
             returns="health-event evidence items"),
    ToolSpec("get_active_incidents", "Incidents whose time and region overlap this case. Overlap does not imply relevance.",
             returns="incident evidence items (INCIDENT aliases)"),
    ToolSpec("get_similar_cases", "Similar already-resolved cases and how they were diagnosed. A similar case's outcome is not proof for this case.",
             returns="similar-case evidence items"),
    ToolSpec("search_knowledge_base", "Knowledge-base articles by keyword and/or component. Some are outdated or only partly applicable.",
             optional=("keyword", "component"), returns="article evidence items"),
    ToolSpec("get_team_capability", "Which teams typically own a component and what skills they use.", required=("component",), needs="component",
             returns="TEAM aliases with roles and weights"),
    ToolSpec("get_agent_availability", "Support-agent availability and skills within one team.", required=("team",), needs="team",
             returns="agent availability rows"),
    ToolSpec(SUBMIT, "End the investigation. You will then be asked for the structured diagnosis. Choose it when you can conclude, when the evidence "
             "is insufficient, or when a person should review.", returns="(ends the run)"),
)
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
TOOL_NAMES = tuple(t.name for t in TOOLS)

# case context is executed by the harness as step 1 (it was the first call in 300/300 baseline traces) and is not model-selectable.
HARNESS_TOOLS = ("get_case_context",)

_ARG_DOC = {"component": "COMPONENT alias", "metric_category": "one of " + "/".join(METRIC_FAMILIES), "keyword": f"short text (max {KEYWORD_MAX} chars)",
            "team": "TEAM alias"}


def available_tools(registry: ObservedEntityRegistry) -> list:
    """State-dependent availability: a tool whose required argument has no valid value yet is not offered (the baseline called component-scoped
    tools before it had seen any component: 227 of 300 traces)."""
    has = {"component": bool(registry.by_kind("COMPONENT")), "team": bool(registry.by_kind("TEAM"))}
    return [t.name for t in TOOLS if t.needs is None or has[t.needs]]


def catalog_text() -> str:
    lines = []
    for t in TOOLS:
        args = ", ".join([f"{a} ({_ARG_DOC[a]}, required)" for a in t.required] + [f"{a} ({_ARG_DOC[a]}, optional)" for a in t.optional]) or "none"
        needs = f" Offered once you have seen a {t.needs}." if t.needs else ""
        lines.append(f"- {t.name}: {t.purpose}{needs} Arguments: {args}.")
    return "\n".join(lines)


# ── schemas handed to the provider ────────────────────────────────────────────

def _enum(values) -> dict:
    return {"type": "string", "enum": list(values)}


def nullable(inner: dict) -> dict:
    return {"anyOf": [inner, {"type": "null"}]}


def alias_or_null(aliases) -> dict:
    return nullable(_enum(aliases)) if aliases else {"type": "null"}


def citation_array(aliases) -> dict:
    return {"type": "array", "items": _enum(aliases), "uniqueItems": True} if aliases else {"type": "array", "maxItems": 0}


def hypothesis_schema(registry: ObservedEntityRegistry) -> dict:
    cites = registry.aliases(*CITABLE_KINDS)
    return {"type": "array", "minItems": 1, "maxItems": MAX_HYPOTHESES, "items": {
        "type": "object", "additionalProperties": False,
        "required": ["label", "confidence", "status", "supporting_evidence", "contradicting_evidence"],
        "properties": {
            "label": {"type": "string", "maxLength": LABEL_MAX},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "status": _enum(HYPOTHESIS_STATUSES),
            "supporting_evidence": citation_array(cites),
            "contradicting_evidence": citation_array(cites),
        }}}


def action_schema(registry: ObservedEntityRegistry) -> dict:
    props = {
        "hypotheses": hypothesis_schema(registry),
        "tool": _enum(available_tools(registry)),
        "component": alias_or_null(registry.aliases("COMPONENT")),
        "metric_category": nullable(_enum(METRIC_FAMILIES)),
        "keyword": nullable({"type": "string", "maxLength": KEYWORD_MAX}),
        "team": alias_or_null(registry.aliases("TEAM")),
    }
    return {"type": "object", "additionalProperties": False, "required": list(ACTION_FIELDS), "properties": props}


# ── deterministic validation ─────────────────────────────────────────────────

def err(code: str, field: str, detail: str = "") -> dict:
    return {"code": code, "field": field, "detail": detail}


def parse_json(raw) -> tuple:
    """(object, error|None). A model reply that is not a JSON object is a contract error, never guessed at."""
    if isinstance(raw, dict):
        return raw, None
    try:
        obj = json.loads(raw)
    except (TypeError, ValueError) as e:
        return None, err("not_json", "$", str(e)[:120])
    if not isinstance(obj, dict):
        return None, err("not_json", "$", "top-level value is not an object")
    return obj, None


def check_alias(value, kinds, registry: ObservedEntityRegistry, field: str) -> Optional[dict]:
    """None when `value` is an alias of one of `kinds` that the registry holds; else the reason it is not."""
    if not isinstance(value, str):
        return err("bad_type", field, "expected an alias string")
    if ID_RE.search(value):
        return err("canonical_id_used", field, "an internal id was written instead of an alias")
    ent = registry.get(value)
    if ent is None:
        return err("unknown_alias", field, f"{value!r} is not in the registry")
    if ent.kind not in kinds:
        return err("alias_wrong_kind", field, f"{value!r} is a {ent.kind} alias; expected {'/'.join(kinds)}")
    return None


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_hypotheses(hyps, registry: ObservedEntityRegistry, field: str = "hypotheses") -> list:
    errors = []
    if not isinstance(hyps, list):
        return [err("bad_type", field, "expected a list")]
    if len(hyps) == 0:
        errors.append(err("hypotheses_empty", field, "state at least one hypothesis every turn (a low-confidence one is fine); the hypothesis state may not be empty"))
    if len(hyps) > MAX_HYPOTHESES:
        errors.append(err("too_many_hypotheses", field, f"at most {MAX_HYPOTHESES}"))
    keys = {"label", "confidence", "status", "supporting_evidence", "contradicting_evidence"}
    for i, h in enumerate(hyps):
        f = f"{field}[{i}]"
        if not isinstance(h, dict):
            errors.append(err("bad_type", f, "expected an object"))
            continue
        for k in sorted(keys - set(h)):
            errors.append(err("missing_field", f"{f}.{k}"))
        for k in sorted(set(h) - keys):
            errors.append(err("unknown_field", f"{f}.{k}"))
        if "label" in h and (not isinstance(h["label"], str) or not h["label"].strip() or len(h["label"]) > LABEL_MAX):
            errors.append(err("bad_value", f"{f}.label", f"non-empty text up to {LABEL_MAX} chars"))
        if "confidence" in h and (not _is_number(h["confidence"]) or not 0 <= h["confidence"] <= 1):
            errors.append(err("confidence_range", f"{f}.confidence", "a number between 0 and 1"))
        if "status" in h and h["status"] not in HYPOTHESIS_STATUSES:
            errors.append(err("bad_enum", f"{f}.status", f"one of {list(HYPOTHESIS_STATUSES)}"))
        seen_any = []
        for k in ("supporting_evidence", "contradicting_evidence"):
            if k not in h:
                continue
            errors += validate_citations(h[k], registry, f"{f}.{k}")
            if isinstance(h[k], list):
                seen_any += [x for x in h[k] if isinstance(x, str)]
        if len(seen_any) != len(set(seen_any)):
            errors.append(err("duplicate_evidence", f, "the same evidence is cited twice within one hypothesis"))
    return errors


def validate_citations(cites, registry: ObservedEntityRegistry, field: str) -> list:
    """Every cited item must be an evidence alias the agent actually retrieved (the registry only ever holds retrieved items), once."""
    if not isinstance(cites, list):
        return [err("bad_type", field, "expected a list of evidence aliases")]
    errors = []
    for i, c in enumerate(cites):
        e = check_alias(c, CITABLE_KINDS, registry, f"{field}[{i}]")
        if e:
            if e["code"] == "unknown_alias":
                e = err("evidence_not_retrieved", e["field"], f"{c!r} is not evidence you retrieved")
            errors.append(e)
    strs = [c for c in cites if isinstance(c, str)]
    if len(strs) != len(set(strs)):
        errors.append(err("duplicate_evidence", field, "the same evidence alias appears twice"))
    return errors


def validate_action(raw, registry: ObservedEntityRegistry) -> tuple:
    """(action|None, errors). Runs before any tool executes. Never repairs: a bad proposal is rejected as it stands."""
    obj, e = parse_json(raw)
    if e:
        return None, [e]
    errors = []
    for k in ACTION_FIELDS:
        if k not in obj:
            errors.append(err("missing_field", k))
    for k in sorted(set(obj) - set(ACTION_FIELDS)):
        errors.append(err("unknown_field", k, "not part of the action schema"))
    if "hypotheses" in obj:
        errors += validate_hypotheses(obj["hypotheses"], registry)
    tool = obj.get("tool")
    if "tool" in obj:
        if tool not in TOOLS_BY_NAME:
            errors.append(err("unknown_tool", "tool", f"{tool!r} is not a registered tool; registered: {list(TOOL_NAMES)}"))
        elif tool not in available_tools(registry):
            errors.append(err("tool_unavailable", "tool", f"{tool} needs a {TOOLS_BY_NAME[tool].needs} you have not seen yet"))
    spec = TOOLS_BY_NAME.get(tool)
    if spec is not None:
        for a in ARG_FIELDS:
            if a not in obj:
                continue
            v = obj[a]
            allowed = a in spec.required or a in spec.optional
            if v is None:
                if a in spec.required:
                    errors.append(err("argument_required", a, f"{tool} requires {a}"))
                continue
            if not allowed:
                errors.append(err("argument_not_allowed", a, f"{tool} does not take {a}; set it to null"))
            elif a in ("component", "team"):
                e = check_alias(v, (a.upper(),), registry, a)
                if e:
                    errors.append(e)
            elif a == "metric_category" and v not in METRIC_FAMILIES:
                errors.append(err("bad_enum", a, f"one of {list(METRIC_FAMILIES)}"))
            elif a == "keyword" and (not isinstance(v, str) or not v.strip() or len(v) > KEYWORD_MAX):
                errors.append(err("bad_value", a, f"non-empty text up to {KEYWORD_MAX} chars"))
    return (None if errors else obj), errors


def canonical_args(action: dict, registry: ObservedEntityRegistry) -> dict:
    """Validated alias arguments -> the canonical arguments the Phase 5 query functions take."""
    out = {}
    if action.get("component"):
        out["component_id"] = registry.canonical(action["component"])
    if action.get("team"):
        out["team_id"] = registry.canonical(action["team"])
    if action.get("metric_category"):
        out["metric_category"] = action["metric_category"]
    if action.get("keyword"):
        out["keyword"] = action["keyword"]
    return out


def alias_args(action: dict) -> dict:
    return {a: action[a] for a in ARG_FIELDS if action.get(a) is not None}


def export_contract_tools() -> list:
    return [{"name": t.name, "purpose": t.purpose, "required": list(t.required), "optional": list(t.optional), "returns": t.returns,
             "available_when": (f"a {t.needs} alias has been observed" if t.needs else "always"),
             "error_semantics": "an invalid proposal is rejected before execution with a structured error and does not consume tool budget; "
                                "it consumes one of the tool-contract repairs"} for t in TOOLS] + [
        {"name": "get_case_context", "purpose": "The case as reported. Executed by the harness as step 1; not model-selectable.", "required": [],
         "optional": [], "returns": "case report", "available_when": "harness only", "error_semantics": "n/a"}]
