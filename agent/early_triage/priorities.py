"""Advisory starting tools per issue category. Hand-written from what each category means (never from any label or outcome) and not validated: it is a hint about where to
look first, shown to the agent as such. It removes nothing: every tool stays available and no category or evidence is filtered. Loaded against the real tool catalog."""
from agent.agent_v3.catalog import METRIC_FAMILIES, TOOLS_BY_NAME

_T, _S = "get_technical_signals", "get_telemetry"
SUGGESTED = {
    "IC01": [(_T, None), (_S, "Identity"), ("get_recent_changes", None)],                          # Identity / Authentication
    "IC02": [(_T, None), ("get_configuration_history", None), ("get_recent_changes", None)],       # Authorization / Permissions
    "IC03": [(_T, None), (_S, "Networking"), ("get_active_incidents", None)],                      # Networking / Connectivity
    "IC04": [(_S, "Application"), (_T, None), ("get_deployment_history", None)],                   # Performance / Latency
    "IC05": [("get_active_incidents", None), ("get_service_health", None), (_S, "Application")],   # Reliability / Availability
    "IC06": [("get_deployment_history", None), ("get_recent_changes", None), ("get_configuration_history", None)],   # Deployment / Upgrade
    "IC07": [("get_configuration_history", None), ("get_recent_changes", None)],                   # Configuration
    "IC08": [(_S, "Data"), (_T, None), ("get_deployment_history", None)],                          # Data / Corruption
    "IC09": [(_T, None), (_S, "Integration"), ("get_recent_changes", None)],                       # Integration / API
    "IC10": [("get_customer_deployment", None), ("get_configuration_history", None)],              # Provisioning / Onboarding
    "IC11": [(_T, None), (_S, "Security"), ("get_recent_changes", None)],                          # Security
    "IC12": [("get_configuration_history", None), ("get_recent_changes", None), ("search_knowledge_base", None)],   # Compliance
    "IC13": [(_T, None), ("get_similar_cases", None), ("search_knowledge_base", None)],            # Billing / Commerce
    "IC14": [(_T, None), ("get_deployment_history", None), ("get_similar_cases", None)],           # User Experience / Functional Defect
    "IC15": [(_S, "Database"), (_S, "Storage"), (_T, None)],                                       # Storage / Database
    "IC16": [(_S, "Capacity"), ("get_recent_changes", None), ("get_service_health", None)],        # Capacity / Scaling
    "IC17": [("get_component_topology", None), ("get_active_incidents", None), ("get_service_health", None)],       # Third-Party / Dependency
    "IC18": [],                                                                                    # Unknown / Other: nothing to prioritise
}
NEEDS_COMPONENT = {"get_component_topology", "get_service_health"}      # only offered once the agent has seen a component


def _valid() -> None:
    for cat, items in SUGGESTED.items():
        for tool, family in items:
            assert tool in TOOLS_BY_NAME, (cat, tool)
            assert family is None or family in METRIC_FAMILIES, (cat, family)
            assert family is None or tool == _S, (cat, tool)


_valid()


def suggest(category_id: str) -> list:
    """Display strings, one per suggested starting point, e.g. 'get_telemetry (metric_category Networking)'."""
    out = []
    for tool, family in SUGGESTED.get(category_id, []):
        note = f"metric_category {family}" if family else ("once a component is known" if tool in NEEDS_COMPONENT else "")
        out.append(f"{tool} ({note})" if note else tool)
    return out
