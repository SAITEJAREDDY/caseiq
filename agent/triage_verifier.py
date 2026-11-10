"""Jev verification of the demo app's graph-grounded triage recommendation: the third column, "With Graph + Jev".

The app's second column is an LLM recommendation (best agents, resources, resolution time, escalation risk) written from data retrieved from the knowledge graph. This module checks
that recommendation against the very data it was written from, then either accepts it, asks the model to revise it once, or flags it for a person:

  deterministic grounding checks   are the named agents and articles really in the retrieved data, do the quoted figures match it, was enough retrieved
  Jev signals (typed)              unsupported claims, missed evidence, anchoring on weak evidence, and a review signal (NORMAL / REVIEW / PRIORITY_REVIEW)
  policy (plain code)              ACCEPT, REVISE once (the model regenerates with the verifier's message), then ACCEPT or HUMAN_REVIEW / PRIORITY_REVIEW

Everything here is runtime-observable (the ticket, the retrieved graph data, the recommendation). There is no ground truth in this app and none is used. This is a different artifact from the
diagnostic traces Jev was evaluated on in Phase 8: those measurements do not carry over, the thresholds are hand-set defaults, and the column is a demonstration, not a validated control.
No Streamlit and no graph access here, so it is testable offline.
"""
import re
import time
from dataclasses import asdict, dataclass

from agent.jev_v2.client import choice_question, noul_question

QUESTION_VERSION = "triage_verify_v1"
ACCEPT, REVISE, HUMAN_REVIEW, PRIORITY_REVIEW = "ACCEPT", "REVISE", "HUMAN_REVIEW", "PRIORITY_REVIEW"
REVIEW_LABELS = {"AUTO_CLOSE": "NORMAL", "NORMAL": "NORMAL", "HUMAN_REVIEW": "REVIEW", "REVIEW": "REVIEW", "PRIORITY_REVIEW": "PRIORITY_REVIEW"}


@dataclass
class TriageVerifierConfig:
    unsupported_threshold: float = 0.75   # Jev P(the recommendation makes claims the retrieved data does not support)
    missed_threshold: float = 0.75        # Jev P(important retrieved information was ignored)
    anchoring_threshold: float = 0.75     # Jev P(anchored on weak options while stronger ones exist)
    priority_threshold: float = 0.50      # Jev P(PRIORITY_REVIEW) at or above this counts as a priority signal
    hours_tolerance: float = 0.15         # a quoted average resolution time may differ from the data by this many hours
    pct_tolerance: float = 1.5            # a quoted resolution rate may differ by this many percentage points

    def to_dict(self) -> dict:
        return asdict(self)


# ── the packet Jev sees ─────────────────────────────────────────────────────────────────────────────────

def context_from_graph(similar, agents, articles, recommendation) -> dict:
    """The retrieved graph data in plain, id-free form: exactly what the recommendation was written from."""
    rec = recommendation or {}
    cust = rec.get("customer") or {}
    return {
        "customer": {"account_tier": str(cust.get("customer_tier", "unknown")), "prior_cases_on_this_product": cust.get("prior_cases_on_product", 0)},
        "similar_resolved_cases": [{"title": c.get("title"), "resolution_hours": c.get("resolution_time_hours")} for c in similar or []],
        "historical_average_resolution_hours": rec.get("avg_resolution_hours"),
        "ranked_agents": [{"rank": i, "name": a.get("name"), "seniority": a.get("seniority"), "avg_resolution_hours": a.get("avg_resolution_time") or a.get("avg_resolution_hours")}
                          for i, a in enumerate(agents or [], 1)],
        "knowledge_base_articles": [{"title": a.get("title"), "resolution_rate": a.get("resolution_rate"), "times_used": a.get("times_used")} for a in articles or []],
    }


def build_packet(description: str, product: str, context: dict, response: str) -> dict:
    return {"packet_version": QUESTION_VERSION, "support_case": description, "product": product, "retrieved_graph_data": context, "recommendation_under_review": response}


# ── deterministic grounding checks ─────────────────────────────────────────────────────────────────

_PERSON = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)+)(?:\*\*)?[ \t]*\(\s*(?i:senior|mid|junior|lead|principal|staff)")
_ARTICLE = re.compile(r"\*\*([^*\n]{6,140})\*\*[ \t]*[—–-][ \t]*[^\n]*?\d+(?:\.\d+)?\s*%\s*resolution")   # same line only: a heading must never be read as an article


def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def grounding_checks(response: str, ctx: dict, cfg: TriageVerifierConfig = None) -> dict:
    """G1 named agents/articles exist in the retrieved data; G2 quoted figures match it; G3 the recommendation uses what was retrieved; G4 enough was retrieved.
    Returns {"checks": [...], "problems": [...]} where `problems` are the failures the model can be asked to fix."""
    cfg = cfg or TriageVerifierConfig()
    agents, arts, cases = ctx["ranked_agents"], ctx["knowledge_base_articles"], ctx["similar_resolved_cases"]
    low, lines = response.lower(), [l for l in response.splitlines() if l.strip()]
    agent_names = {a["name"] for a in agents if a["name"]}
    titles = [a["title"] for a in arts if a["title"]]

    invented_people = sorted({p for p in _PERSON.findall(response) if p not in agent_names})
    invented_articles = sorted({t.strip() for t in _ARTICLE.findall(response) if not any(t.strip().lower() in x.lower() or x.lower() in t.strip().lower() for x in titles)})
    g1_problems = ([f"agent(s) not in the retrieved data: {', '.join(invented_people)}"] if invented_people else []) + ([f"article(s) not in the retrieved data: {', '.join(invented_articles)}"] if invented_articles else [])

    mismatches = []
    for line in lines:
        ll = line.lower()
        for a in agents:
            avg = _num(a["avg_resolution_hours"])
            if a["name"] and a["name"].lower() in ll and avg is not None:
                hours = [float(h) for h in re.findall(r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|hr|h)\b", line, re.I)]
                if hours and not any(abs(h - avg) <= cfg.hours_tolerance for h in hours):
                    mismatches.append(f"{a['name']}: quoted {hours[0]:g} hours, data says {avg:g}")
        for t in arts:
            rate = _num(t["resolution_rate"])
            if t["title"] and t["title"].lower() in ll:
                pcts = [float(p) for p in re.findall(r"(\d+(?:\.\d+)?)\s*%", line)]
                if rate is not None and pcts and not any(abs(p - rate * 100) <= cfg.pct_tolerance for p in pcts):
                    mismatches.append(f"'{t['title'][:40]}': quoted {pcts[0]:g}%, data says {rate * 100:.0f}%")
                used = re.findall(r"used in (\d+)", ll)
                if used and _num(t["times_used"]) is not None and int(used[0]) != int(_num(t["times_used"])):
                    mismatches.append(f"'{t['title'][:40]}': quoted {used[0]} past cases, data says {int(_num(t['times_used']))}")

    named = [n for n in agent_names if n.lower() in low]
    cited = [t for t in titles if t.lower() in low]
    ignores = []
    if agents and not named:
        ignores.append("none of the retrieved agents is named")
    if arts and not cited:
        ignores.append("none of the retrieved articles is cited")
    enough = bool(agents) and (len(cases) + len(arts)) >= 1
    checks = [
        {"id": "G1", "name": "Named agents and articles come from the graph", "passed": not g1_problems, "detail": "; ".join(g1_problems) or f"{len(named)} retrieved agent(s) and {len(cited)} retrieved article(s) named, nothing invented"},
        {"id": "G2", "name": "Quoted figures match the graph data", "passed": not mismatches, "detail": "; ".join(mismatches[:3]) or "every quoted resolution time, rate and usage count matches"},
        {"id": "G3", "name": "Uses the retrieved evidence", "passed": not ignores, "detail": "; ".join(ignores) or "the recommendation draws on the retrieved agents and articles"},
        {"id": "G4", "name": "Enough evidence was retrieved", "passed": enough, "detail": f"{len(agents)} agents, {len(cases)} similar cases, {len(arts)} articles retrieved" + ("" if enough else " — too little to verify a recommendation")},
    ]
    return {"checks": checks, "problems": g1_problems + mismatches + ignores, "named_agents": len(named), "cited_articles": len(cited)}


# ── the Jev questions (typed; no explanations requested) ─────────────────────────────────────────────

_CONTEXT = ("You are reviewing a support-triage recommendation. The packet contains the support case, the data retrieved from the company's knowledge graph (customer profile, similar resolved "
            "cases, ranked support agents, knowledge-base articles) and the recommendation that was written from that data. ")
QUESTIONS = {
    "unsupported_claims": noul_question(
        _CONTEXT + "Does the recommendation state specific agents, articles, figures or reasons that the retrieved graph data does not support?",
        {"true": "The recommendation contains claims the retrieved data does not support.", "false": "Every specific claim is supported by the retrieved data."}),
    "missed_evidence": noul_question(
        _CONTEXT + "Does the retrieved data contain information that should materially change which agents or resources are recommended, or the resolution-time or escalation assessment, that the recommendation ignored?",
        {"true": "Important retrieved information was ignored.", "false": "The recommendation accounts for the important retrieved information."}),
    "weak_anchoring": noul_question(
        _CONTEXT + "Is the recommendation anchored on weak options (for example an agent with a slow average resolution time, or an article with a low resolution rate or few uses) while clearly stronger options in the retrieved data go unused?",
        {"true": "The recommendation leans on weak options while stronger ones exist.", "false": "The recommendation favors the strongest options in the retrieved data."}),
    "review": choice_question(
        _CONTEXT + "Should a person review this recommendation before it is acted on? Choose exactly one option.",
        {"NORMAL": "Safe to act on without a person reviewing it.", "REVIEW": "A person should review it before it is acted on.",
         "PRIORITY_REVIEW": "A person should review it urgently: it is likely wrong, unsupported or risky to act on."}),
}


def jev_signals(packet: dict, client=None) -> dict:
    """Four typed calls on one packet. A failed call is recorded as None and marks Jev unavailable; nothing is guessed. The client's leakage guard runs on every request."""
    if client is None:
        from agent.trace_eval_v2.jev_evaluator import get_client
        client = get_client()
    t0, out, errors, tokens = time.time(), {}, [], 0
    for key, question in QUESTIONS.items():
        try:
            resp = client.judge(packet, question, key)
            ans = resp["answers"][key]
            tokens += (resp.get("usage") or {}).get("input_tokens") or 0
            if question["type"] == "noul":
                out[key] = round(float(ans["noul"]), 4)
            else:
                probs = {REVIEW_LABELS.get(k, k): round(float(v), 4) for k, v in (ans.get("probabilities") or {}).items()}
                out["review"], out["review_probabilities"] = REVIEW_LABELS.get(ans.get("choice"), ans.get("choice")), probs
        except Exception as e:  # noqa: BLE001 - recorded, never hidden
            out.setdefault(key, None)
            errors.append(f"{key}: {type(e).__name__}: {str(e)[:120]}")
    out.setdefault("review", None)
    out.setdefault("review_probabilities", None)
    out.update(available=not errors, errors=errors, input_tokens=tokens, latency_s=round(time.time() - t0, 2), question_version=QUESTION_VERSION)
    return out


# ── policy ───────────────────────────────────────────────────────────────────────────────────────────

def decide(grounding: dict, jev: dict, round_no: int, cfg: TriageVerifierConfig) -> dict:
    checks = {c["id"]: c for c in grounding["checks"]}
    if not checks["G4"]["passed"]:
        return {"decision": HUMAN_REVIEW, "reason": f"the graph returned too little to verify a recommendation ({checks['G4']['detail']})", "triggers": ["G4"]}
    more = []
    if not checks["G1"]["passed"]:
        more.append(("G1", "it names an agent or article that is not in the retrieved data"))
    if not checks["G2"]["passed"]:
        more.append(("G2", "a quoted figure does not match the retrieved data"))
    if not checks["G3"]["passed"]:
        more.append(("G3", "it does not use the retrieved agents or articles"))
    have = bool(jev and jev.get("available"))
    if have and (jev["unsupported_claims"] or 0) >= cfg.unsupported_threshold:
        more.append(("jev_unsupported", "Jev sees claims the retrieved data does not support"))
    if have and (jev["missed_evidence"] or 0) >= cfg.missed_threshold:
        more.append(("jev_missed", "Jev sees important retrieved information that was ignored"))
    if have and (jev["weak_anchoring"] or 0) >= cfg.anchoring_threshold:
        more.append(("jev_anchoring", "Jev sees it leaning on weak options while stronger ones exist"))
    if more:
        triggers, reasons = [t for t, _ in more], [r for _, r in more]
        if round_no == 1:
            return {"decision": REVISE, "reason": "; ".join(reasons), "triggers": triggers, "reasons": reasons}
        return {"decision": HUMAN_REVIEW, "reason": "still unresolved after one revision: " + "; ".join(reasons), "triggers": triggers}
    if not have:
        return {"decision": HUMAN_REVIEW, "reason": "Jev could not be reached, so the recommendation cannot be accepted automatically (" + "; ".join((jev or {}).get("errors") or ["no result"]) + ")", "triggers": ["jev_unavailable"]}
    if jev.get("review") == "PRIORITY_REVIEW" or (jev.get("review_probabilities") or {}).get("PRIORITY_REVIEW", 0) >= cfg.priority_threshold:
        return {"decision": PRIORITY_REVIEW, "reason": "Jev flags this recommendation for priority review", "triggers": ["jev_priority_review"]}
    return {"decision": ACCEPT, "reason": "grounding checks passed and no Jev signal crossed a threshold", "triggers": []}


def build_feedback(reasons: list, grounding: dict, response: str, ctx: dict) -> str:
    low = response.lower()
    lines = ["VERIFICATION FEEDBACK (from the runtime verifier)", "Your previous recommendation needs one revision. Reasons:"] + [f"- {r}" for r in reasons]
    lines += [f"- {p}" for p in grounding["problems"][:4]]
    unused = [f"{a['name']} (average {a['avg_resolution_hours']} hours)" for a in ctx["ranked_agents"][:3] if a["name"] and a["name"].lower() not in low]
    if unused:
        lines.append("The retrieved data also ranks these agents, which you did not mention: " + "; ".join(unused) + ".")
    lines.append("Rewrite the full recommendation in the same format. Use only the agents, articles, cases and figures in the graph data above and state figures exactly as given. "
                 "If the data does not support a claim, leave it out.")
    return "\n".join(lines)


# ── the whole verification ─────────────────────────────────────────────────────────────────────────────

def verify(description: str, product: str, ctx: dict, response: str, regenerate, client=None, cfg: TriageVerifierConfig = None) -> dict:
    """At most two passes. `regenerate(feedback) -> new response text` is called once, only if the first pass says REVISE."""
    cfg, t0, rounds, current = cfg or TriageVerifierConfig(), time.time(), [], response
    final = None
    for round_no in (1, 2):
        grounding = grounding_checks(current, ctx, cfg)
        jev = jev_signals(build_packet(description, product, ctx, current), client)
        verdict = decide(grounding, jev, round_no, cfg)
        rec = {"round": round_no, "response": current, "checks": grounding["checks"], "jev": jev, "decision": verdict["decision"], "reason": verdict["reason"], "triggers": verdict["triggers"]}
        rounds.append(rec)
        if verdict["decision"] != REVISE:
            final = verdict
            break
        rec["feedback"] = build_feedback(verdict["reasons"], grounding, current, ctx)
        try:
            current = regenerate(rec["feedback"])
        except Exception as e:  # noqa: BLE001 - a failed revision is a review case, never silently accepted
            final = {"decision": HUMAN_REVIEW, "reason": f"the revision could not be generated ({type(e).__name__}: {str(e)[:100]})", "triggers": ["revision_failed"]}
            break
    # A revision must never replace a grounded answer with an ungrounded one: if it fails a grounding check (G1 / G2) that the original passed, the original is kept (and still flagged).
    def _grounded(rd):
        return all(c["passed"] for c in rd["checks"] if c["id"] in ("G1", "G2"))
    reverted = len(rounds) == 2 and final["decision"] != ACCEPT and _grounded(rounds[0]) and not _grounded(rounds[1])
    if reverted:
        final = {**final, "reason": "the revision introduced a claim the retrieved data does not support, so the original answer is shown; " + final["reason"]}
    shown_original = reverted or final["triggers"] == ["revision_failed"] or len(rounds) == 1
    return {"decision": final["decision"], "reason": final["reason"], "triggers": final["triggers"], "revised": (not shown_original) and rounds[-1]["response"] != response, "reverted": reverted,
            "initial_response": response, "final_response": response if shown_original else rounds[-1]["response"], "rounds": rounds, "jev_available": all(r["jev"].get("available") for r in rounds),
            "latency_s": round(time.time() - t0, 2), "config": cfg.to_dict()}
