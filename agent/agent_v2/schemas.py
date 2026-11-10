"""Pydantic schemas: the shared hypothesis-state mixin every tool call
carries, the terminal FinalDiagnosis schema, and per-tool argument models.

Design (see plan): every tool argument model extends StepContext, so the
model must restate its current hypothesis state on every turn -- this is
what makes the trace interpretable without needing private chain-of-thought
(spec section 23).
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class HypothesisUpdate(BaseModel):
    label: str = Field(description="Short slug for this hypothesis, e.g. 'authorization_policy_issue'")
    description: str = Field(default="", description="One short sentence describing the hypothesis")
    confidence: float = Field(ge=0.0, le=1.0, description="0.0-1.0 confidence this hypothesis is correct")
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Evidence IDs (from earlier tool results) that support this hypothesis"
    )
    contradicting_evidence: list[str] = Field(
        default_factory=list, description="Evidence IDs (from earlier tool results) that contradict this hypothesis"
    )
    status: Literal["active", "rejected", "confirmed"] = "active"


class StepContext(BaseModel):
    """Mixed into every non-terminal tool's args_schema. Deliberately a FLAT
    list[str] rather than list[HypothesisUpdate]: with 14 tools bound per
    call, a nested-object schema gets duplicated in every tool definition
    Groq receives and alone exceeded the 8000 TPM free-tier budget in
    testing (~10K tokens of schema before any conversation history). The
    richer per-hypothesis evidence-citation schema (HypothesisUpdate) is
    used only once, on the terminal submit_diagnosis call, where it isn't
    multiplied across the tool list.
    """

    hypotheses: list[str] = Field(
        description="Your CURRENT, complete list of hypotheses as 'label:confidence' strings, e.g. "
        "'authorization_policy_issue:0.7'. Restate ALL active ones every time, not just what changed."
    )
    rationale: str = Field(description="One short sentence: why this step.")


# ── Per-tool argument models (all extend StepContext) ───────────────────────

class NoExtraArgs(StepContext):
    pass


class ComponentScopedArgs(StepContext):
    component_id: str = Field(description="A component ID you have already learned about (e.g. from signals, changes, or deployment info).")


class OptionalComponentArgs(StepContext):
    component_id: Optional[str] = Field(default=None, description="Optionally narrow the query to one component ID.")


class TelemetryArgs(StepContext):
    metric_category: Optional[str] = Field(
        default=None,
        description="One of the available metric categories (call once with no category first to see which "
        "categories have data for this case's components). Omit to list categories instead of values.",
    )
    component_id: Optional[str] = Field(default=None, description="Optionally narrow to one component ID.")


class KBSearchArgs(StepContext):
    keyword: Optional[str] = Field(default=None, description="A keyword or short phrase to search KB titles/summaries for.")
    component_id: Optional[str] = Field(default=None, description="Optionally narrow to KB articles covering this component.")
    category_id: Optional[str] = Field(default=None, description="Optionally narrow to KB articles covering this issue category.")


class TeamCapabilityArgs(StepContext):
    component_id: Optional[str] = Field(default=None, description="Look up teams/skills associated with this component.")
    subcategory_id: Optional[str] = Field(default=None, description="Look up teams/skills associated with this issue subcategory.")


class AgentAvailabilityArgs(StepContext):
    team_id: str = Field(description="A team ID (from get_team_capability) to check agent availability within.")


class FinalDiagnosis(StepContext):
    """submit_diagnosis's args_schema -- calling this tool ends the run.
    Overrides `hypotheses` with the richer per-hypothesis evidence-citation
    form -- safe here since this schema is bound only once (not duplicated
    across 14 other tools), unlike StepContext's compact form.
    """

    hypotheses: list[HypothesisUpdate] = Field(
        description="Your final hypothesis list with full evidence citations."
    )
    predicted_product_id: Optional[str] = None
    product_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_component_id: Optional[str] = None
    component_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_category_id: Optional[str] = None
    category_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_subcategory_id: Optional[str] = None
    predicted_root_cause_family: Optional[str] = None
    root_cause_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_causal_change_id: Optional[str] = Field(default=None, description="A real ChangeEvent id you observed, if applicable.")
    causal_change_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_severity: Optional[str] = None
    severity_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    recommended_team_id: Optional[str] = None
    routing_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    evidence_sufficiency: Literal["sufficient", "partial", "insufficient"]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    recommended_next_action: str = Field(
        description="A single non-destructive next action, e.g. 'inspect policy configuration', "
        "'route to Identity team', 'validate certificate', 'request customer confirmation', "
        "'escalate to engineering'. Never a production-changing action."
    )
    human_review_required: bool
    human_review_reason: Optional[str] = None
    evidence_summary: str = Field(description="Concise (2-4 sentence) summary of what evidence was found.")
    unresolved_uncertainties: list[str] = Field(default_factory=list)
