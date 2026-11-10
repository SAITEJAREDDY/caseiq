"""Canonical in-memory trace representation (evaluator side, canonical ids). The model-facing projection is built from it by
trace_projection.py, which aliases every internal id; nothing in this module is ever sent to Jev or the LLM judge as is."""
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# Every internal id shape found in the graph and in tool results. Kind is the entity type a reader can already see from the tool result
# (a signal is returned by get_technical_signals, a change by get_recent_changes), so the alias prefix reveals nothing new.
ID_KINDS = [
    (r"CS\d{4,}:CM\d{3}:[A-Z0-9_]+", "TEL"),  # a telemetry finding's id is the composite case:component:metric key
    (r"SG\d{5,}", "SIG"), (r"CH\d{5,}", "CHG"), (r"INC\d{3,}", "INC"), (r"SHE\d{4,}", "SHE"), (r"CFG\d{4,}", "CFG"),
    (r"KA\d{2,}", "KB"), (r"CM\d{3}", "CMP"), (r"CS\d{4,}", "CASE"), (r"TM\d{2,}", "TEAM"),
    (r"IC\d{2}", "CAT"), (r"IS\d{3}", "SUB"), (r"RC\d{2}", "RCF"), (r"PE\d+", "ENT"), (r"C\d{5}", "CUST"), (r"P\d{3}", "PROD"), (r"A\d{3}", "AGT"),
]
ID_RE = re.compile(r"\b(" + "|".join(p for p, _ in ID_KINDS) + r")\b")
_KIND_RES = [(re.compile(rf"^{p}$"), k) for p, k in ID_KINDS]

EVIDENCE_KINDS = ("SIG", "CHG", "INC", "SHE", "CFG", "TEL", "KB", "CASE")  # kinds a tool returns as an `evidence_id`


def id_kind(canonical_id: str) -> Optional[str]:
    for rx, kind in _KIND_RES:
        if rx.match(str(canonical_id)):
            return kind
    return None


@dataclass
class Step:
    n: int
    clock: str
    tool: str
    args: dict
    hypotheses: list  # regular steps: [{"label", "confidence"}]; the submit step: the raw hypothesis dicts the agent wrote
    status: str  # ok | error | redundant
    redundant: bool
    result: Any
    evidence: list = field(default_factory=list)  # canonical evidence ids this step returned, in order
    error_kind: Optional[str] = None  # unknown_tool | validation_error | neo4j_error | other

    @property
    def is_submit(self) -> bool:
        return self.tool == "submit_diagnosis"


@dataclass
class Trace:
    run_id: str
    case_id: str
    stop_reason: str
    steps: list
    final: dict  # the persisted, contract-validated final diagnosis (what the harness and Phase 6 see)
    repair_events: list
    citation_violations: list
    token_usage: dict
    model_name: str
    variant: Optional[dict] = None  # set only on synthetic perturbation variants

    @property
    def diagnostic_steps(self) -> list:
        return [s for s in self.steps if not s.is_submit]

    @property
    def submit_step(self) -> Optional[Step]:
        return next((s for s in self.steps if s.is_submit), None)

    @property
    def retrieved_ids(self) -> list:
        """Evidence ids returned by any diagnostic step, in first-seen order."""
        seen, out = set(), []
        for s in self.diagnostic_steps:
            for e in s.evidence:
                if e not in seen:
                    seen.add(e)
                    out.append(e)
        return out

    def first_retrieval_step(self) -> dict:
        first = {}
        for s in self.diagnostic_steps:
            for e in s.evidence:
                first.setdefault(e, s.n)
        return first

    def to_run(self) -> dict:
        """Back to the persisted-run shape Phase 6's evaluate_run reads, so original and perturbed traces are scored by the same authoritative code."""
        steps = []
        for s in self.steps:
            hyp = s.hypotheses if s.is_submit else [f"{h.get('label', '')}:{h.get('confidence')}" if h.get("confidence") is not None else h.get("label", "") for h in s.hypotheses]
            steps.append({"step": s.n, "sim_clock": s.clock, "tool_name": s.tool, "args": dict(s.args), "hypotheses": hyp, "rationale": "", "result_summary": s.result,
                          "latency_ms": 0.0, "status": s.status, "redundant": s.redundant})
        return {"run_id": self.run_key, "case_id": self.case_id, "stop_reason": self.stop_reason, "trace_steps": steps, "final_diagnosis": self.final,
                "citation_violations": self.citation_violations, "evidence_ids_seen": self.retrieved_ids, "repair_events": self.repair_events,
                "num_tool_calls": len(self.steps), "num_llm_calls": None, "token_usage": self.token_usage, "model_name": self.model_name}

    @property
    def run_key(self) -> str:
        return self.run_id if not self.variant else f"{self.run_id}#{self.variant['perturbation']}:{self.variant['variant_id']}"
