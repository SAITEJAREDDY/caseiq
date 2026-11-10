"""The Jev column of the main page's COMPARISON panel: every value derived from the verified result, no fixed demo numbers.

The app's Without Graph / With Graph columns contain some fixed demo values (skill match 23% / 94%, escalation risk, confidence, typed-in token estimates). This module never invents such a value for Jev:
it reads the agent named in the verified answer, that agent's real seniority and resolution time, the escalation level the answer itself states, the measured grounding checks and Jev signals, the real latency
and call counts. Where a value cannot be derived it is "n/a". Pure functions; no Streamlit.
"""
import re

_ESC = re.compile(r"escalation risk(?: assessment)?[\s*:—–-]*(?:risk level[\s*:—–-]*)?(low|medium|high)", re.I)
_DECISION_TEXT = {"ACCEPT": "Accepted", "HUMAN_REVIEW": "Needs human review", "PRIORITY_REVIEW": "Priority review"}


def first_named_agent(text: str, agents: list) -> dict:
    """The retrieved agent named earliest in the answer ({} if none is named). Agents come from the graph, so this can only be a real agent."""
    low, best = text.lower(), None
    for a in agents or []:
        i = low.find((a.get("name") or "\0").lower())
        if i >= 0 and (best is None or i < best[0]):
            best = (i, a)
    return best[1] if best else {}


def stated_escalation(text: str) -> str:
    m = _ESC.search(text or "")
    return m.group(1).title() if m else "n/a"


def confidence_from_decision(v: dict) -> str:
    d = v["decision"]
    if d == "ACCEPT":
        return "High (verified after revision)" if v["revised"] else "High (verified)"
    return "Low (priority review)" if d == "PRIORITY_REVIEW" else "Low (needs review)"


def jev_view(result: dict, graph_skill_pct: int) -> dict:
    """None if verification was not run; {"error": ...} if it could not run; else the column's values. `graph_skill_pct` is the value the app shows for the graph's top agent, reused only when Jev's
    answer names that same agent (any other agent shows its own stored skill match, or n/a)."""
    v = result.get("verified")
    if v is None:
        return None
    if "error" in v:
        return {"error": v["error"]}
    agents, top = result.get("agents") or [], result.get("top_agent") or {}
    final = v["final_response"]
    agent = first_named_agent(final, agents)
    last = v["rounds"][0] if v.get("reverted") else v["rounds"][-1]      # the answer that is actually shown
    checks = last["checks"]
    passed = sum(1 for c in checks if c["passed"])
    bad = next((c for c in checks if not c["passed"]), None)
    if agent and agent.get("name") == top.get("name"):
        skill = f"{graph_skill_pct}%"
    else:
        s = agent.get("skill_match_pct") if agent else None
        skill = f"{int(s)}%" if s is not None else "n/a"
    avg = agent.get("avg_resolution_time") or agent.get("avg_resolution_hours") if agent else None
    jev_rounds = [r["jev"] for r in v["rounds"]]
    j = last["jev"]                                                        # signals for the answer that is shown
    called = len(v["rounds"]) > 1                                          # a revision was requested, whether or not it was kept
    return {
        "decision": v["decision"], "decision_text": _DECISION_TEXT.get(v["decision"], v["decision"]) + (" after one revision" if v["revised"] and v["decision"] == "ACCEPT" else "")
        + (" (a revision was tried and rejected)" if v.get("reverted") else ""), "revised": v["revised"], "revision_called": called, "agent": agent.get("name") or "n/a", "skill": skill, "seniority": (agent.get("seniority") or "n/a").title() if agent else "n/a",
        "avg": f"{avg} hrs" if avg else "n/a", "escalation": stated_escalation(final), "confidence": confidence_from_decision(v),
        "grounding": f"{passed}/{len(checks)} checks pass", "grounding_ok": passed == len(checks), "hallucination": ("Checked: every named agent, article and figure matches the graph data" if passed == len(checks)
                                                                                                                       else f"Flagged: {bad['detail'][:110]}" if bad else "n/a"),
        "risks": (f"unsupported {j['unsupported_claims'] * 100:.0f}% · missed {j['missed_evidence'] * 100:.0f}% · anchoring {j['weak_anchoring'] * 100:.0f}%" if j.get("available") else "Jev unavailable"),
        "review": j.get("review") or "n/a", "jev_calls": 4 * len(v["rounds"]), "jev_tokens": sum(x.get("input_tokens") or 0 for x in jev_rounds), "extra_llm_calls": 1 if called else 0,
        "verify_latency": result.get("latency_jev") if result.get("latency_jev") is not None else v["latency_s"], "final_response": final, "reason": v["reason"],
    }
