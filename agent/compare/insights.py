"""Deterministic comparison text and tables from the results alone: no LLM call, no ground truth. The language is descriptive (changed, added, retrieved, discovered), never
"better" or "more accurate": whether an answer is correct is only shown by the separate, optional evaluation panel."""
from agent.compare.models import FIELD_LABELS, MODE_FULL, MODE_GRAPH, MODE_LLM, MODES, NAMES, PRIMARY_FIELDS, SELECTION_FIELDS, SHARED_FIELDS, ComparisonResult

NA = "—"


def _n(x) -> str:
    return " ".join(str(x).lower().split()) if x else ""


def changed_fields(a: dict, b: dict, fields=PRIMARY_FIELDS) -> list:
    return [f for f in fields if _n(a.get(f)) != _n(b.get(f))]


def _pick(r: ComparisonResult, fields=SELECTION_FIELDS) -> dict:
    return {f: getattr(r, f) for f in fields}


def diagnosis_text(d: dict, confidence=None) -> str:
    parts = [d.get("root_cause") or "no root cause selected", d.get("affected_component") or "no component"]
    return " · ".join(parts) + (f" · confidence {confidence:.2f}" if confidence is not None else "")


# ── the comparison table ──────────────────────────────────────────────────────────────────

def comparison_rows(results: dict) -> list:
    def cell(mode, fn, jev_only=False):
        r = results.get(mode)
        if r is None:
            return "not available"
        if jev_only and not r.jev_used:
            return NA
        return fn(r)
    rows = [("Root cause", lambda r: r.root_cause or "ABSTAIN"), ("Issue category", lambda r: r.issue_category or "ABSTAIN"), ("Component", lambda r: r.affected_component or "ABSTAIN"),
            ("Confidence", lambda r: NA if r.confidence is None else f"{r.confidence:.2f}"), ("Tool calls", lambda r: str(r.tool_calls)), ("Evidence", lambda r: str(r.evidence_count)),
            ("Status", lambda r: r.status.replace("_", " ").title())]
    out = [{"Metric": name, **{NAMES[m]: cell(m, fn) for m in MODES}} for name, fn in rows]
    out.append({"Metric": "Early Jev suggestion (provisional)", **{NAMES[m]: cell(m, lambda r: (early_triage_added(r) or {"summary": "not used (this run predates early triage)"})["summary"], True) for m in MODES}})
    out.append({"Metric": "Extra investigation", **{NAMES[m]: cell(m, lambda r: f"Yes (+{r.extra_tool_calls} tool calls)" if r.verification["additional_investigation"] else "No", True) for m in MODES}})
    out.append({"Metric": "Final policy", **{NAMES[m]: cell(m, lambda r: r.verification["final_decision"].replace("_", " "), True) for m in MODES}})
    out.append({"Metric": "Latency (model + verifier)", **{NAMES[m]: cell(m, lambda r: f"{r.latency_seconds:.0f}s") for m in MODES}})
    out.append({"Metric": "Est. cost", **{NAMES[m]: cell(m, lambda r: f"${r.estimated_cost:.3f}") for m in MODES}})
    return out


# ── what the graph added (LLM Only vs LLM + Graph) ───────────────────────────────────────────

def graph_added(llm: ComparisonResult, graph: ComparisonResult) -> dict:
    e = graph.entities
    changed = changed_fields(_pick(llm), _pick(graph), SHARED_FIELDS)
    conf = None if llm.confidence is None or graph.confidence is None else (llm.confidence, graph.confidence)
    return {"evidence_added": graph.evidence_count - llm.evidence_count, "tool_calls": graph.tool_calls, "components_with_evidence": e.get("components_with_evidence", 0),
            "components_queried": e.get("components_queried", 0), "changes": e.get("changes", 0), "incidents": e.get("incidents", 0), "similar_cases": e.get("similar_cases", 0),
            "signals": e.get("signals", 0), "telemetry": e.get("telemetry", 0), "diagnosis_changed": bool(changed), "changed_fields": changed, "confidence": conf,
            "component_wording": (llm.affected_component, graph.affected_component) if (llm.affected_component and graph.affected_component
                                                                                          and _n(llm.affected_component) != _n(graph.affected_component)) else None,
            "llm": diagnosis_text(_pick(llm), llm.confidence), "graph": diagnosis_text(_pick(graph), graph.confidence)}


# ── what Jev added (LLM + Graph + Jev, before vs after verification) ──────────────────────────────────

def jev_added(full: ComparisonResult) -> dict:
    v = full.verification
    first = v["passes"][0] if v["passes"] else {}
    initial = full.initial or _pick(full) | {"confidence": full.confidence}
    final = _pick(full)
    changed = changed_fields(initial, final)
    return {"initial": diagnosis_text(initial, initial.get("confidence")), "missed": first.get("missed"), "distractor": first.get("distractor"), "review": first.get("review"),
            "first_decision": v["first_decision"], "final_decision": v["final_decision"], "additional_investigation": v["additional_investigation"], "extra_tool_calls": full.extra_tool_calls,
            "final": diagnosis_text(final, full.confidence), "diagnosis_changed": bool(changed), "changed_fields": changed, "triggers": first.get("triggers", []),
            "status_changed": (initial.get("status") or "") != full.status, "initial_status": initial.get("status"), "final_status": full.status}


# ── what early Jev added (guidance before investigation) ──────────────────────────────────────────────

OUTCOME_TEXT = {"confirmed": "the agent kept the suggestion after investigating", "changed": "the agent changed the category after investigating",
                "dropped": "the agent selected no category", "no_suggestion": "no suggestion reached the agent", "no_final_answer": "the run ended without a valid final answer"}
STATUS_TEXT = {"hint": "suggestion given", "abstained": "Jev abstained", "low_probability": "too uncertain to suggest", "invalid": "Jev's answer was invalid", "error": "Jev call failed",
               "timeout": "Jev call timed out", "unavailable": "Jev not configured"}


def early_triage_added(full: ComparisonResult):
    """The early-Jev panel data, or None when this run predates early triage. Guidance only: nothing here says the suggestion, or the agent, is correct."""
    t = full.triage
    if t is None:
        return None
    given = t["status"] == "hint"
    return {**t, "given": given, "status_text": STATUS_TEXT.get(t["status"], t["status"]), "outcome_text": OUTCOME_TEXT.get(t.get("outcome"), "—"),
            "summary": ((f"{t['category']} (probability {t['probability']:.2f}, {t['uncertainty']} uncertainty)" if given else f"none: {STATUS_TEXT.get(t['status'], t['status'])}")
                        + (f" — {OUTCOME_TEXT[t['outcome']]}" + (f": {t['final_category']}" if t.get("outcome") == "changed" and t.get("final_category") else "") if given and t.get("outcome") in OUTCOME_TEXT else ""))}


# ── highlights and impact ───────────────────────────────────────────────────────────────────────────

def differences(results: dict) -> list:
    """(kind, text) lines: 'diff' where two architectures disagree, 'same' where they agree, 'note' for caveats. Never says which is correct."""
    out, llm, graph, full = [], results.get(MODE_LLM), results.get(MODE_GRAPH), results.get(MODE_FULL)
    if llm and graph:
        ch = changed_fields(_pick(llm), _pick(graph), SHARED_FIELDS)
        for f in ch:
            out.append(("diff", f"{FIELD_LABELS[f]} changed — LLM: {llm.selections()[f] or 'ABSTAIN'} → Graph: {graph.selections()[f] or 'ABSTAIN'}"))
        if not ch:
            out.append(("same", "LLM Only and LLM + Graph reached the same issue category and root cause."))
        cw = graph_added(llm, graph)["component_wording"]
        if cw:
            out.append(("note", f"Component: LLM Only named \"{cw[0]}\" (free text); LLM + Graph selected \"{cw[1]}\" from the components it observed. Not counted as a changed diagnosis: the two are not in the same vocabulary."))
    if full:
        e = early_triage_added(full)
        if e and e["given"] and e.get("outcome") == "changed":
            out.append(("diff", f"Early Jev suggested {e['category']} (provisional); the agent changed the category to {e.get('final_category') or 'none'} after investigating."))
        elif e and e["given"] and e.get("outcome") == "confirmed":
            out.append(("same", f"The agent kept the early Jev category suggestion ({e['category']}) after investigating."))
        elif e and not e["given"]:
            out.append(("note", f"Early Jev triage gave no suggestion ({e['status_text']}); the agent investigated without a hint."))
        j = jev_added(full)
        if j["additional_investigation"]:
            out.append(("diff", "Jev verification caused additional investigation and changed the final diagnosis." if j["diagnosis_changed"] or j["status_changed"]
                        else "Jev verification caused additional investigation; the diagnosis was unchanged."))
        else:
            out.append(("same", f"Graph diagnosis retained after Jev verification (decision: {j['final_decision'].replace('_', ' ')})."))
        if graph:
            ch = changed_fields(_pick(graph), full.initial or _pick(full))
            if ch:
                out.append(("note", "The LLM + Graph and LLM + Graph + Jev columns are separate agent runs (the model is not deterministic), so their investigations differ: "
                                    + ", ".join(FIELD_LABELS[f].lower() for f in ch) + " differ before verification."))
    return out


def impact(results: dict) -> dict:
    llm, graph, full = results.get(MODE_LLM), results.get(MODE_GRAPH), results.get(MODE_FULL)
    out = {"graph": [], "jev_early": [], "jev": []}          # jev_early = triage guidance; jev = late verification
    if llm and graph:
        g = graph_added(llm, graph)
        derived = g["changes"] + g["incidents"] + g["similar_cases"] + g["components_with_evidence"]
        which = ", ".join(FIELD_LABELS[f].lower() for f in g["changed_fields"])
        out["graph"] = [f"{g['evidence_added']:+d} evidence items retrieved", f"{derived} tool-derived entities (changes {g['changes']}, incidents {g['incidents']}, similar cases {g['similar_cases']}, "
                        f"components with evidence {g['components_with_evidence']})", f"diagnosis changed ({which})" if g["diagnosis_changed"] else "diagnosis unchanged"]
        if g["confidence"]:
            out["graph"].append(f"confidence {g['confidence'][0]:.2f} → {g['confidence'][1]:.2f} ({g['confidence'][1] - g['confidence'][0]:+.2f})")
    if full:
        j = jev_added(full)
        t = j["triggers"]
        e = early_triage_added(full)
        out["jev_early"] = [f"suggestion: {e['summary']}" + (f"; latency {e['latency_ms'] / 1000:.1f}s" if e["latency_ms"] else "")] if e else ["not used in this run (it predates early triage)"]
        out["jev"] = [("flagged missed evidence" if "jev_missed_evidence" in t else "did not flag missed evidence") + (f" ({j['missed'] * 100:.0f}%)" if j["missed"] is not None else ""),
                      ("flagged distractor anchoring" if "jev_distractor_anchor" in t else "did not flag distractor anchoring") + (f" ({j['distractor'] * 100:.0f}%)" if j["distractor"] is not None else ""),
                      f"triggered one additional investigation (+{j['extra_tool_calls']} tool calls)" if j["additional_investigation"] else "no additional investigation",
                      "diagnosis changed after verification" if (j["diagnosis_changed"] or j["status_changed"]) else "diagnosis unchanged by verification",
                      f"final disposition: {j['final_decision'].replace('_', ' ')}"]
    return out
