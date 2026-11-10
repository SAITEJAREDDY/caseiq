"""The observed-entity registry and evidence ledger (Phase 9A sections 6, 7, 15, 22, 23).

Everything the model may name is registered here with a model-facing alias (`COMPONENT_KZT`, `CHANGE_BQD`, ...). The alias <-> canonical
mapping stays outside the model: tool results are rewritten to aliases before the model sees them, and the final answer is mapped back
to canonical ids deterministically after validation.

Aliases are hash-keyed on (scheme, case, kind, canonical id): sparse three-consonant codes that encode no order, recency, number or
role (Phase 7 found that identifier structure can influence a model), and sparse enough that an invented alias almost never collides
with a real one, so a fabricated reference is detectable rather than silently valid.

Entities come only from (a) the standing taxonomy read from the runtime graph and (b) tool results the agent actually received. No
hidden truth, no Phase 6 score and no evaluation store is read here.
"""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent.agent_v3.config import ALIAS_SCHEME, LINE_MAX

KINDS = ("PRODUCT", "COMPONENT", "CATEGORY", "CAUSE", "CHANGE", "INCIDENT", "TEAM", "EVIDENCE", "REF")
CITABLE_KINDS = ("EVIDENCE", "CHANGE", "INCIDENT")   # kinds that may appear in `evidence_ids` / hypothesis citations
_CONS = "BCDFGHJKLMNPQRSTVWXZ"                       # no vowels: a code can never spell a word

# Canonical id shapes in the Phase 4 graph. Used only to detect an id that leaked into free text or model output.
ID_RE = re.compile(
    r"\b(CS\d{4,}:CM\d{3}:[A-Za-z0-9_]+|SG\d{5,}|CH\d{5,}|INC\d{3,}|SHE\d{4,}|CFG\d{4,}|KA\d{2,}|CM\d{3}|CS\d{4,}|TM\d{2,}"
    r"|IC\d{2}|IS\d{3}|RC\d{2}|PE\d+|C\d{5}|P\d{3}|A\d{3})\b"
)
ALIAS_RE = re.compile(r"\b(" + "|".join(KINDS) + r")_[BCDFGHJKLMNPQRSTVWXZ]{3}\b")

# tool -> (alias kind of the rows' `evidence_id`, evidence type shown in the ledger)
EVIDENCE_TYPES = {
    "get_technical_signals": ("EVIDENCE", "signal"),
    "get_telemetry": ("EVIDENCE", "telemetry"),
    "get_recent_changes": ("CHANGE", "change"),
    "get_deployment_history": ("CHANGE", "deployment"),
    "get_configuration_history": ("EVIDENCE", "config_snapshot"),
    "get_service_health": ("EVIDENCE", "health_event"),
    "get_active_incidents": ("INCIDENT", "incident"),
    "get_similar_cases": ("EVIDENCE", "similar_case"),
    "search_knowledge_base": ("EVIDENCE", "kb_article"),
}
_DROP_KEYS = {"case_id", "customer_id", "agent_id", "skill_id"}  # canonical ids the model has no use for and must not see
_SCALAR_KEYS = {"component_id": "COMPONENT", "product_id": "PRODUCT", "reported_product_id": "PRODUCT", "team_id": "TEAM"}
_LIST_KEYS = {"product_components": "COMPONENT", "affected_components": "COMPONENT"}
_PAIR_KEYS = {"upstream_dependencies": "COMPONENT", "downstream_dependents": "COMPONENT", "owning_teams": "TEAM"}


@dataclass
class Entity:
    alias: str
    canonical_id: str
    kind: str
    type: str
    display_name: str
    source_tool: str
    first_observed_step: int
    first_observed_clock: str
    summary: str = ""

    def to_dict(self) -> dict:
        return {"alias": self.alias, "canonical_id": self.canonical_id, "kind": self.kind, "type": self.type,
                "display_name": self.display_name, "source_tool": self.source_tool,
                "first_observed_step": self.first_observed_step, "first_observed_clock": self.first_observed_clock, "summary": self.summary}


def _code(case_id: str, kind: str, canonical: str, probe: int) -> str:
    n = int.from_bytes(hashlib.sha256(f"{ALIAS_SCHEME}|{case_id}|{kind}|{canonical}|{probe}".encode()).digest()[:4], "big")
    return "".join(_CONS[(n // len(_CONS) ** i) % len(_CONS)] for i in range(3))


@dataclass
class ObservedEntityRegistry:
    case_id: str
    _by_alias: dict = field(default_factory=dict)
    _by_canonical: dict = field(default_factory=dict)
    _refs: dict = field(default_factory=dict)  # canonical id -> REF alias: ids that appeared only in prose; never selectable, never citable

    # ── registration ────────────────────────────────────────────────────────
    def add(self, kind: str, canonical_id: str, *, type: str = "", display_name: str = "", source_tool: str, step: int, clock: str,
            summary: str = "") -> Entity:
        if kind not in KINDS:
            raise ValueError(f"unknown entity kind {kind!r}")
        existing = self._by_canonical.get(canonical_id)
        if existing is not None:
            if existing.kind != kind:
                raise ValueError(f"{canonical_id} already registered as {existing.kind}, not {kind}")
            if display_name and not existing.display_name:
                existing.display_name = display_name
            if summary and not existing.summary:
                existing.summary = summary
            return existing
        probe = 0
        while True:
            alias = f"{kind}_{_code(self.case_id, kind, canonical_id, probe)}"
            if alias not in self._by_alias:
                break
            probe += 1
        ent = Entity(alias, canonical_id, kind, type or kind.lower(), display_name, source_tool, step, clock, summary)
        self._by_alias[alias] = ent
        self._by_canonical[canonical_id] = ent
        return ent

    # ── lookup ──────────────────────────────────────────────────────────────
    def get(self, alias) -> Optional[Entity]:
        return self._by_alias.get(alias) if isinstance(alias, str) else None

    def canonical(self, alias: str) -> str:
        return self._by_alias[alias].canonical_id

    def by_kind(self, *kinds: str) -> list:
        return [e for e in self._by_alias.values() if e.kind in kinds]

    def aliases(self, *kinds: str) -> list:
        return [e.alias for e in self.by_kind(*kinds)]

    def has_canonical(self, canonical_id: str) -> bool:
        return canonical_id in self._by_canonical

    def mapping(self) -> dict:
        out = {a: e.to_dict() for a, e in self._by_alias.items()}
        for cid, alias in self._refs.items():
            out[alias] = {"alias": alias, "canonical_id": cid, "kind": "REF", "type": "text_reference", "display_name": "", "source_tool": "prose",
                          "first_observed_step": None, "first_observed_clock": None, "summary": ""}
        return out

    def ref_alias(self, canonical_id: str) -> str:
        if canonical_id not in self._refs:
            probe = 0
            while True:
                alias = f"REF_{_code(self.case_id, 'REF', canonical_id, probe)}"
                if alias not in self._by_alias and alias not in self._refs.values():
                    break
                probe += 1
            self._refs[canonical_id] = alias
        return self._refs[canonical_id]

    def counts(self) -> dict:
        out = {}
        for e in self._by_alias.values():
            out[e.kind] = out.get(e.kind, 0) + 1
        return out

    def snapshot(self, step: int) -> dict:
        digest = hashlib.sha256("|".join(sorted(self._by_alias)).encode()).hexdigest()[:16]
        return {"step": step, "n_entities": len(self._by_alias), "counts": self.counts(), "aliases_sha256_16": digest}

    # ── text scrubbing ──────────────────────────────────────────────────────
    def scrub(self, text: str, *, source_tool: str = "", step: int = 0, clock: str = "") -> str:
        """Replaces every canonical id in free text. A registered id becomes its alias; an id the agent has not been shown as a
        structured entity becomes a stateless REF alias (not in the entity table), so mentioning an entity in prose never makes it selectable
        or citable. Re-scrubbing after the entity is later observed yields its real alias."""
        def repl(m):
            cid = m.group(0)
            ent = self._by_canonical.get(cid)
            if ent is not None:
                return ent.alias
            if cid == self.case_id:
                return "THIS_CASE"
            return self.ref_alias(cid)
        return ID_RE.sub(repl, text)


# ── tool result -> model-facing result ───────────────────────────────────────

def _summarize(tool: str, row: dict) -> str:
    """One deterministic line per ledger entry, built from the already-aliased row: enough for the model to recall what an item says
    without re-reading the raw result. Never labels an item relevant, causal or misleading."""
    g = lambda k: row.get(k) if row.get(k) is not None else ""
    if tool == "get_technical_signals":
        s = f"{g('signal_type')}: {g('message')} on {g('component_id')} @ {g('timestamp')}"
    elif tool == "get_telemetry":
        s = (f"{g('metric_code')} on {g('component_id')}: status {g('status')}, direction {g('direction')}, baseline {g('baseline')}, "
             f"observed {g('observed_min')}..{g('observed_max')}")
    elif tool == "get_recent_changes":
        s = f"{g('change_type')} on {g('component_id')} started {g('started_at')}, status {g('status')}, {g('time_proximity_hours')}h before case"
    elif tool == "get_deployment_history":
        s = (f"deployment {g('version_from')} -> {g('version_to')} on {g('component_id')} started {g('started_at')}, "
             f"{g('rollout_strategy')}, status {g('status')}")
    elif tool == "get_configuration_history":
        s = f"{g('config_key')} = {g('config_value')} on {g('component_id')} @ {g('snapshot_at')}. {g('note')}"
    elif tool == "get_service_health":
        s = f"health event severity {g('severity')} {g('started_at')}..{g('ended_at')}: {g('description')}"
    elif tool == "get_active_incidents":
        s = f"incident severity {g('severity')}, status {g('status')}, {g('started_at')}..{g('ended_at')}, affects {g('affected_components')}: {g('summary')}"
    elif tool == "get_similar_cases":
        s = f"similar case (score {g('similarity_score')}) titled '{g('title')}', historical diagnosis: {g('historical_diagnosis')}"
    elif tool == "search_knowledge_base":
        s = f"article '{g('title')}' (resolution rate {g('resolution_rate')}, outdated {g('outdated')}): {g('summary')}"
    else:
        s = str(row)
    s = " ".join(str(s).split())
    return s if len(s) <= LINE_MAX * 2 else s[: LINE_MAX * 2 - 1] + "…"


def expose_result(registry: ObservedEntityRegistry, tool: str, result, *, step: int, clock: str,
                  name_lookup: Optional[Callable] = None):
    """Rewrites one canonical tool result into its model-facing form and registers every entity it names. Returns the new result.
    `name_lookup(canonical_ids) -> {id: name}` is an optional read-only taxonomy lookup used to give components a display name."""
    ev_kind, ev_type = EVIDENCE_TYPES.get(tool, (None, None))
    ctx = dict(source_tool=tool, step=step, clock=clock)

    def reg(kind, cid, name="", **kw):
        return registry.add(kind, cid, display_name=name, **ctx, **kw).alias

    def walk(o, parent=""):
        if isinstance(o, dict):
            out, name_hint = {}, o.get("name") or o.get("product_name") or o.get("reported_product_name") or o.get("team_name") or o.get("component_name") or ""
            for k, v in o.items():
                if k in _DROP_KEYS:
                    continue
                if k == "id" and parent in _PAIR_KEYS and isinstance(v, str):
                    out[k] = reg(_PAIR_KEYS[parent], v, o.get("name") or "")
                elif k == "evidence_id" and isinstance(v, str) and ev_kind:
                    out[k] = v  # placeholder; aliased below once the row's other ids are aliased so the summary reads in aliases
                elif k in _SCALAR_KEYS and isinstance(v, str):
                    out[k] = reg(_SCALAR_KEYS[k], v, name_hint if _SCALAR_KEYS[k] != "COMPONENT" else "")
                elif k in _LIST_KEYS and isinstance(v, list):
                    out[k] = [reg(_LIST_KEYS[k], x) if isinstance(x, str) else walk(x, k) for x in v]
                elif k in _PAIR_KEYS and isinstance(v, list):
                    out[k] = [walk(x, k) for x in v]
                else:
                    out[k] = walk(v, k)
            if isinstance(o.get("evidence_id"), str) and ev_kind:
                canonical = o["evidence_id"]
                out.pop("evidence_id", None)
                alias = reg(ev_kind, canonical, type=ev_type, summary=_summarize(tool, out))
                out = {"evidence_id": alias, **out}
            return out
        if isinstance(o, list):
            return [walk(x, parent) for x in o]
        if isinstance(o, str):
            return registry.scrub(o, source_tool=tool, step=step, clock=clock)
        return o

    exposed = walk(result)
    if name_lookup is not None:
        missing = [e.canonical_id for e in registry.by_kind("COMPONENT") if not e.display_name]
        if missing:
            for cid, name in (name_lookup(missing) or {}).items():
                registry.add("COMPONENT", cid, display_name=name, **ctx)
    return exposed


def leaked_ids(payload) -> list:
    """Every canonical-id-shaped string still present in a model-facing payload (must be empty)."""
    import json
    text = json.dumps(payload, default=str)
    return sorted({m.group(0) for m in ID_RE.finditer(ALIAS_RE.sub(" ", text))})
