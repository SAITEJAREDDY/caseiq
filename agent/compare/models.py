"""The shared result schema for the three CaseIQ architectures, and the user-facing names.

User-facing names are LLM Only / LLM + Graph / LLM + Graph + Jev. Internal package names (agent_v3, runtime_verifier) appear only in the debug section of the UI.
"""
from dataclasses import dataclass, field
from typing import Optional

MODE_LLM, MODE_GRAPH, MODE_FULL = "llm_only", "llm_graph", "llm_graph_jev"
MODES = (MODE_LLM, MODE_GRAPH, MODE_FULL)
NAMES = {MODE_LLM: "LLM Only", MODE_GRAPH: "LLM + Graph", MODE_FULL: "LLM + Graph + Jev"}
LABELS = {m: n.upper() for m, n in NAMES.items()}                      # LLM ONLY / LLM + GRAPH / LLM + GRAPH + JEV
BADGES = {MODE_LLM: (True, False, False), MODE_GRAPH: (True, True, False), MODE_FULL: (True, True, True)}   # (LLM, Graph, Jev)
# What each architecture is, exactly. LLM + Graph is the UNCHANGED baseline: no early triage, no verification. LLM + Graph + Jev adds Jev in two separate roles:
# early Jev = triage guidance (a provisional category hint from the ticket text, before any graph investigation), late Jev = verification of the finished answer.
FLOW = {MODE_LLM: "Ticket → LLM → Diagnosis", MODE_GRAPH: "Ticket → Agent → Neo4j → Diagnosis",
        MODE_FULL: "Ticket → Early Jev triage (guidance) → Agent → Neo4j → Diagnosis → Late Jev verifier (verification) → Final Action"}
SELECTION_FIELDS = ("issue_category", "root_cause", "affected_component", "causal_change", "owning_team")
FIELD_LABELS = {"issue_category": "Issue category", "root_cause": "Root cause", "affected_component": "Affected component",
                "causal_change": "Causal change", "owning_team": "Owning team"}
PRIMARY_FIELDS = ("issue_category", "root_cause", "affected_component")   # "the diagnosis changed" between two graph-agent results (same vocabulary)
SHARED_FIELDS = ("issue_category", "root_cause")                         # LLM Only vs LLM + Graph: only fields both choose from the same list; free-text components are not comparable

# List-price estimates (labelled estimates, not billing). Mirrors agent/runtime_verifier/run.py without importing it, so the LLM-only path stays graph- and Jev-free.
TOGETHER_USD_PER_M_TOKENS = 0.88
JEV_USD_PER_M_INPUT_TOKENS = 0.042


@dataclass
class ComparisonResult:
    mode: str
    case_id: str
    status: str                                   # DIAGNOSIS_PROPOSED / INSUFFICIENT_EVIDENCE / HUMAN_REVIEW_REQUIRED / CONTRACT_FAILURE
    issue_category: Optional[str]
    root_cause: Optional[str]
    affected_component: Optional[str]
    causal_change: Optional[str]
    owning_team: Optional[str]
    confidence: Optional[float]
    summary: str
    tool_calls: int                               # retrieval tool calls the model chose (the ticket load and the final submit are not counted)
    evidence_count: int
    graph_used: bool
    jev_used: bool
    latency_seconds: float                        # model-call time plus verifier time; Neo4j time is negligible and excluded
    estimated_cost: float
    verification: Optional[dict] = None           # only when Jev was used
    hypotheses: int = 0
    entities: dict = field(default_factory=dict)  # what the graph run observed: changes, incidents, similar cases, components, ...
    selection_ids: Optional[dict] = None          # canonical ids for graph modes (used only by offline evaluation); None for LLM Only
    initial: Optional[dict] = None                # full mode: the agent's diagnosis before verification
    triage: Optional[dict] = None                 # full mode, runs that used early triage: the early Jev suggestion (provisional guidance, never a diagnosis) and what the agent did with it
    extra_tool_calls: int = 0
    run_id: str = ""
    source: str = "stored"                        # "stored" | "live"
    raw: dict = field(default_factory=dict, repr=False, compare=False)

    def selections(self) -> dict:
        return {f: getattr(self, f) for f in SELECTION_FIELDS}

    def to_summary(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "raw"}
        return d
