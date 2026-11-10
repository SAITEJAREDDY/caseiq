"""CaseIQ Diagnostic Agent page: run or open a dev case in one of three architectures, or compare all three side by side.

  LLM Only          Ticket -> LLM -> Diagnosis                                     (no Neo4j, no tools, no Jev)
  LLM + Graph       Ticket -> Agent -> Neo4j -> Diagnosis                           (the unchanged baseline: graph tools, no triage, no verification, no Jev)
  LLM + Graph + Jev Ticket -> early Jev triage -> Agent -> Neo4j -> Diagnosis -> late Jev verifier -> Final Action
                    Jev has two roles: early = triage guidance (a provisional category hint from the ticket text, never a diagnosis); late = verification of the finished answer.

Everything is normalized into one ComparisonResult (agent/compare) so the rendering has a single code path. Ground truth is shown only on request, for dev cases, after the
runs have finished (agent/compare/evaluation.py); it never reaches any runtime input. Dev cases only.
"""
import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(page_title="CaseIQ Diagnostic Agent", page_icon="🩺", layout="wide")

from agent.compare import adapters, insights  # noqa: E402
from agent.db_status_ui import render_sidebar_status  # noqa: E402
from agent.compare import orchestrator as orch  # noqa: E402
from agent.compare.models import BADGES, FIELD_LABELS, FLOW, LABELS, MODE_FULL, MODE_GRAPH, MODE_LLM, MODES, NAMES, SELECTION_FIELDS  # noqa: E402

POOL_PATH = ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json"   # the 300 dev cases (plain JSON, no evaluation code)
OPTIONS = ["LLM Only", "LLM + Graph", "LLM + Graph + Jev", "Compare All"]
OPTION_MODE = {"LLM Only": MODE_LLM, "LLM + Graph": MODE_GRAPH, "LLM + Graph + Jev": MODE_FULL}
PROGRESS = {MODE_LLM: "Running LLM Only", MODE_GRAPH: "Running Graph Agent", MODE_FULL: "Running early Jev triage + agent + late Jev verifier"}
RUN_WHAT = {MODE_LLM: "1 direct LLM call", MODE_GRAPH: "1 graph-agent investigation", MODE_FULL: "1 graph-agent + early Jev triage + late Jev verifier workflow"}

STATUS_STYLE = {"DIAGNOSIS_PROPOSED": ("🟢", "Diagnosis proposed"), "INSUFFICIENT_EVIDENCE": ("🟡", "Insufficient evidence"),
                "HUMAN_REVIEW_REQUIRED": ("🟠", "Human review required"), "CONTRACT_FAILURE": ("🔴", "Contract failure")}


SELECTIONS = (("issue_category", "category_confidence", "Issue category"), ("root_cause", "root_cause_confidence", "Root cause"),
              ("affected_component", "component_confidence", "Affected component"), ("causal_change", "causal_change_confidence", "Causal change"),
              ("owning_team", "routing_confidence", "Owning team"))


DECISION_STYLE = {"ACCEPT": ("✅", "ACCEPT"), "CONTINUE_INVESTIGATION": ("🔁", "CONTINUE INVESTIGATION"), "HUMAN_REVIEW": ("🟠", "HUMAN REVIEW"),
                  "PRIORITY_REVIEW": ("🔴", "PRIORITY REVIEW")}


def label(mapping: dict, alias) -> str:
    """Human-readable form of a model-facing alias: the entity's name or its ledger summary."""
    if not alias:
        return "—"
    e = mapping.get(alias) or {}
    text = e.get("display_name") or e.get("summary") or ""
    return f"{text[:110]} · {alias}" if text else alias


def render_run(run: dict) -> None:
    mp, fa, fd = run["alias_mappings"], run.get("final_alias_form"), run["final_diagnosis"]
    status = run["final_status"]
    icon, status_text = STATUS_STYLE.get(status, ("⚪", status))
    ctx = next((s["result_summary"] for s in run["trace_steps"] if s["tool_name"] == "get_case_context"), {}) or {}

    st.subheader(f"{run['case_id']} — {ctx.get('title', '')}")
    if ctx.get("description"):
        st.caption(ctx["description"])
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Outcome", f"{icon} {status_text}")
    c2.metric("Confidence", f"{fd['overall_confidence']:.2f}")
    c3.metric("Evidence", fd["evidence_sufficiency"])
    c4.metric("Human review", "required" if fd["human_review_required"] else "not flagged")
    c5.metric("Steps · LLM calls", f"{run['num_tool_calls']} · {run['num_llm_calls']}")

    v = run["validation_result"]
    n_tool_repairs = len(run["tool_contract_repairs"])
    if run["contract_failure"]:
        st.error(f"Contract failure: {run['contract_failure']}. No diagnosis was produced; a person should investigate.")
    elif v["first_pass_ok"] and not n_tool_repairs:
        st.success("Contract: every tool call and the final answer were valid on the first attempt (no repairs).")
    else:
        st.warning(f"Contract: valid after repair (tool repairs: {n_tool_repairs}, final repair: {'yes' if v['repair_used'] else 'no'}). The errors are listed under Contract.")
    if fd.get("human_review_reason"):
        st.info(f"Review reason: {fd['human_review_reason']}")

    tabs = st.tabs(["Diagnosis", "Hypotheses", "Investigation", "Evidence ledger", "Contract", "Raw"])

    with tabs[0]:
        if fa:
            rows = [{"Field": name, "Selection": label(mp, fa[v_]), "Confidence": fa[c_]} for v_, c_, name in SELECTIONS]
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.markdown(f"**Summary.** {fa['summary']}")
            st.markdown(f"**Recommended next action.** {fa['recommended_next_action']}")
            if fa["unresolved_uncertainties"]:
                st.markdown("**Unresolved uncertainties**\n" + "\n".join(f"- {u}" for u in fa["unresolved_uncertainties"]))
            st.caption("A blank selection means the agent abstained: it did not have evidence to justify one.")
        else:
            st.write(fd["evidence_summary"])

    with tabs[1]:
        hyps = (fa or {}).get("hypotheses") or []
        if hyps:
            st.dataframe([{"Hypothesis": h["label"], "Confidence": h["confidence"], "Status": h["status"],
                           "Supporting evidence": "; ".join(label(mp, a) for a in h["supporting_evidence"]) or "—",
                           "Contradicting evidence": "; ".join(label(mp, a) for a in h["contradicting_evidence"]) or "—"} for h in hyps],
                         use_container_width=True, hide_index=True)
        else:
            st.write("No final hypotheses.")

    with tabs[2]:
        for s in run["trace_steps"]:
            who = "harness" if s.get("proposed_by") == "harness" else "agent"
            args = ", ".join(f"{k}={label(mp, v)}" if isinstance(v, str) and v in mp else f"{k}={v}" for k, v in (s.get("args_alias") or {}).items())
            with st.expander(f"Step {s['step']} · {s['tool_name']}({args}) · {s['status']} · {who} · clock {s['sim_clock']}"):
                if s.get("hypothesis_state"):
                    st.markdown("**Hypotheses at this step**")
                    for h in s["hypothesis_state"]:
                        st.markdown(f"- {h['label']} ({h['confidence']}, {h['status']})")
                if s["tool_name"] != "submit_diagnosis":
                    st.markdown("**Tool result** (as returned by the graph)")
                    st.json(s["result_summary"], expanded=False)

    with tabs[3]:
        cited = set((fa or {}).get("evidence_ids") or [])
        ledger = sorted((e for e in mp.values() if e["kind"] in ("EVIDENCE", "CHANGE", "INCIDENT")), key=lambda e: (e["first_observed_step"] or 0, e["alias"]))
        if ledger:
            st.dataframe([{"Alias": e["alias"], "Type": e["type"], "Step": e["first_observed_step"], "Summary": e["summary"],
                           "Source id": e["canonical_id"], "Cited in answer": "yes" if e["alias"] in cited else ""} for e in ledger],
                         use_container_width=True, hide_index=True)
        else:
            st.write("No evidence was retrieved.")

    with tabs[4]:
        st.markdown(f"**Stop reason:** `{run['stop_reason']}` · **Tool proposals:** {run['tool_proposals']} · **Rejected:** {len(run['tool_contract_errors'])} · "
                    f"**First-pass final valid:** {v['first_pass_ok']} · **Final repair used:** {v['repair_used']}")
        if run["tool_contract_errors"]:
            st.markdown("**Rejected tool proposals** (nothing was executed for these)")
            st.json(run["tool_contract_errors"], expanded=False)
        if run["final_contract_errors"]:
            st.markdown("**Final-answer validation errors**")
            st.json(run["final_contract_errors"], expanded=False)
        st.markdown("**Versions**")
        st.dataframe([{"Item": k, "Value": str(run.get(k))[:16] if k == "code_digest" else run.get(k)} for k in
                      ("model_name", "agent_version", "prompt_version", "tool_catalog_version", "final_schema_version", "registry_version", "repair_policy_version", "code_digest")],
                     use_container_width=True, hide_index=True)

    with tabs[5]:
        st.json(run, expanded=False)


def pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def render_verification(rec: dict) -> None:
    """The runtime-verification section: status, evidence check, Jev risks, review signal, and what happened across the (at most two) passes."""
    rounds = rec["verification_rounds"]
    final = rec["final_policy_decision"]
    icon, text = DECISION_STYLE.get(final, ("⚪", final))
    last = rounds[-1] if rounds else {}
    checks = last.get("deterministic_checks") or {}
    review = (last.get("jev_review") or {})
    st.markdown(f"### Late Jev — runtime verification: {icon} {text}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evidence check", "PASS" if checks.get("D1", {}).get("passed") else "FAIL")
    c2.metric("Missed-evidence risk", pct(last.get("jev_missed_evidence")))
    c3.metric("Distractor risk", pct(last.get("jev_distractor_anchor")))
    c4.metric("Jev review signal", review.get("label") or "n/a")
    st.write(f"**Why:** {rec['final_reason']}")
    if rec["additional_investigation_performed"]:
        first_icon, first_text = DECISION_STYLE.get(rec["policy_decision"], ("⚪", rec["policy_decision"]))
        st.info(f"The first verification said {first_icon} {first_text}, so the agent was sent back for one more investigation round; the result above is after that round.")
    st.caption(f"{rec['latency_s']}s · about ${rec['cost_usd_estimate']} (estimate) · {len(rounds)} verification pass(es)")
    with st.expander("Verification details (per pass)"):
        for rd in rounds:
            st.markdown(f"**Pass {rd['round']} → {rd['policy_decision']}**  ·  {rd['reason']}")
            st.dataframe([{"Check": c["id"] + " " + c["name"], "Result": ("PASS" if c["passed"] else "FAIL") + ("" if c["applicable"] else " (n/a)"), "Detail": c["detail"]}
                          for k, c in rd["deterministic_checks"].items() if k != "all_passed"], use_container_width=True, hide_index=True)
            probs = (rd.get("jev_review") or {}).get("probabilities") or {}
            st.write(f"Jev: missed evidence {pct(rd.get('jev_missed_evidence'))} · distractor anchoring {pct(rd.get('jev_distractor_anchor'))} · review "
                     + (", ".join(f"{k} {pct(v)}" for k, v in probs.items()) or "n/a"))
            if rd.get("message_to_agent"):
                st.markdown("**Message sent back to the agent**")
                st.code(rd["message_to_agent"])
    if rec.get("review_packet"):
        with st.expander("Human-review packet", expanded=True):
            st.json(rec["review_packet"], expanded=False)
    if rec["additional_investigation_performed"]:
        with st.expander("Agent's initial diagnosis (before the additional round)"):
            st.json(rec["agent_initial_result"], expanded=False)
    st.markdown("---")
    st.markdown("### Agent diagnosis")


# ── data access ──────────────────────────────────────────────────────────────

@st.cache_data
def dev_cases() -> list:
    return sorted(json.loads(POOL_PATH.read_text())["case_ids"])


@st.cache_resource
def graph_driver():
    from agent.graph_v2.db import get_driver
    driver = get_driver()
    driver.verify_connectivity()
    return driver


@st.cache_data(ttl=300)
def cached_cost(modes: tuple) -> dict:
    return orch.cost_estimate(modes)


@st.cache_data
def cached_aggregate(include_truth: bool, n_llm: int, n_graph: int, n_full: int) -> dict:
    from agent.compare import aggregate
    return aggregate.aggregate(include_truth)


def run_live(modes, case_id: str) -> dict:
    """Runs the given architectures (in parallel) with visible progress. Each finished run is stored, so it survives a page interruption."""
    from agent.agent_v3.llm import TogetherJSONClient

    key = os.environ.get("TOGETHER_API_KEY", "")
    if not key:
        raise RuntimeError("TOGETHER_API_KEY is not set in .env")
    llm = TogetherJSONClient(key)
    with st.status(f"Running {', '.join(NAMES[m] for m in modes)} on {case_id}…", expanded=True) as status:
        slots = {m: st.empty() for m in modes}

        def on_update(mode, state, payload):
            if state == "started":
                slots[mode].write(f"⏳ {PROGRESS[mode]}… running")
            elif state == "done":
                slots[mode].write(f"✅ {PROGRESS[mode]}… done in {payload.latency_seconds:.0f}s (model + verifier time)")
            else:
                slots[mode].write(f"❌ {NAMES[mode]} failed: {type(payload).__name__}: {str(payload)[:140]}")

        out = orch.run_modes(modes, case_id, session_factory=graph_driver().session, llm=llm, on_update=on_update)
        failed = [m for m, r in out.items() if isinstance(r, Exception)]
        status.update(label="Finished" if not failed else f"Finished with {len(failed)} error(s)", state="complete" if not failed else "error")
    return out


# ── rendering: badges, cards ─────────────────────────────────────────────────

def badges_html(mode: str) -> str:
    def chip(name, on):
        bg, fg = ("#dcfce7", "#166534") if on else ("#f1f5f9", "#64748b")
        return f"<span style='background:{bg};color:{fg};padding:2px 10px;border-radius:12px;font-size:0.82rem;margin-right:6px'>{name} {'✓' if on else '✕'}</span>"
    llm, graph, jev = BADGES[mode]
    return chip("LLM", llm) + chip("Graph", graph) + chip("Jev", jev)


def sel_line(name: str, value) -> str:
    return f"**{name}** &nbsp; {value}" if value else f"**{name}** &nbsp; <span style='color:#94a3b8'>ABSTAIN</span>"


def render_early_line(result) -> None:
    """One line for early Jev on a card. Always labelled provisional guidance: the suggestion is a prior from the ticket text, not a diagnosis."""
    e = insights.early_triage_added(result)
    if e is None:
        st.caption("Early Jev (triage guidance): not used — this stored run predates early triage.")
    elif e["given"]:
        st.markdown(f"**Early Jev (triage guidance)** &nbsp; 💡 {e['category']} · p={e['probability']:.2f} · {e['uncertainty']} uncertainty")
        st.caption(f"Provisional suggestion, not a diagnosis — {e['outcome_text']}" + (f": {e['final_category']}" if e.get("outcome") == "changed" and e.get("final_category") else "") + ".")
    else:
        st.markdown(f"**Early Jev (triage guidance)** &nbsp; ⚪ no suggestion ({e['status_text']})")
        st.caption("The agent investigated without a hint (the unchanged graph workflow).")


def render_card(mode: str, result, case_id: str, compact: bool = True) -> None:
    with st.container(border=True):
        st.markdown(f"### {LABELS[mode]}")
        st.markdown(badges_html(mode), unsafe_allow_html=True)
        if result is None:
            st.info("Not available for this case yet.")
            if st.button(f"Run {NAMES[mode]}", key=f"run_one_{mode}_{case_id}"):
                st.session_state["pending_run"] = [mode]
                st.rerun()
            return
        for f in ("root_cause", "affected_component", "issue_category"):
            st.markdown(sel_line(FIELD_LABELS[f], getattr(result, f)), unsafe_allow_html=True)
        st.markdown(f"**Confidence** &nbsp; {'—' if result.confidence is None else f'{result.confidence:.2f}'} &nbsp;·&nbsp; **Status** &nbsp; {result.status.replace('_', ' ').title()}")
        st.caption((result.summary[:300] + "…") if len(result.summary) > 300 else result.summary)
        st.markdown(f"Tools: **{result.tool_calls}** &nbsp;·&nbsp; Evidence: **{result.evidence_count}** &nbsp;·&nbsp; Graph: **{'Yes' if result.graph_used else 'No'}** &nbsp;·&nbsp; "
                    f"Jev: **{'Yes' if result.jev_used else 'No'}**", unsafe_allow_html=True)
        if result.jev_used:
            render_early_line(result)
        if result.jev_used and result.verification:
            v = result.verification
            first = v["passes"][0] if v["passes"] else {}
            icon, text = DECISION_STYLE.get(v["final_decision"], ("⚪", v["final_decision"]))
            st.markdown(f"**Late Jev (verification)** &nbsp; {icon} {text}")
            st.markdown(f"Missed evidence: **{pct(first.get('missed'))}** &nbsp;·&nbsp; Distractor risk: **{pct(first.get('distractor'))}** &nbsp;·&nbsp; Review signal: **{first.get('review') or 'n/a'}**")
            if v["additional_investigation"]:
                st.caption(f"Extra investigation: +{result.extra_tool_calls} tool calls; the answer above is the one after it.")
        st.caption(f"{result.latency_seconds:.0f}s model + verifier time · about ${result.estimated_cost:.3f} · {result.source}")


# ── rendering: comparison sections ───────────────────────────────────────────

def render_differences(results: dict) -> None:
    for kind, text in insights.differences(results):
        (st.warning if kind == "diff" else st.success if kind == "same" else st.caption)(("🔀 " if kind == "diff" else "") + text)


def render_graph_added(results: dict) -> None:
    st.markdown("## What the Graph Added")
    llm, graph = results.get(MODE_LLM), results.get(MODE_GRAPH)
    if not (llm and graph):
        st.info("Needs both LLM Only and LLM + Graph results.")
        return
    g = insights.graph_added(llm, graph)
    c = st.columns(5)
    c[0].metric("Evidence retrieved", f"+{g['evidence_added']}")
    c[1].metric("Tool calls", g["tool_calls"])
    c[2].metric("Changes discovered", g["changes"])
    c[3].metric("Incidents discovered", g["incidents"])
    c[4].metric("Similar cases", g["similar_cases"])
    st.markdown(f"Components queried: **{g['components_queried']}** · components with evidence: **{g['components_with_evidence']}** · signals: **{g['signals']}** · telemetry findings: **{g['telemetry']}**")
    st.markdown(f"**Diagnosis changed:** {'YES — ' + ', '.join(FIELD_LABELS[f].lower() for f in g['changed_fields']) if g['diagnosis_changed'] else 'NO'}")
    if g["confidence"]:
        st.markdown(f"**Confidence:** {g['confidence'][0]:.2f} → {g['confidence'][1]:.2f}")
    if g["component_wording"]:
        st.markdown(f"**Component:** LLM Only said “{g['component_wording'][0]}” (free text); LLM + Graph selected “{g['component_wording'][1]}” (an observed component).")
    st.caption("Diagnosis changed is judged on issue category and root cause only (the fields both architectures choose from the same list). Descriptive only: this shows what retrieval added and whether the answer changed, not whether it is more accurate (see the evaluation panel for that).")


def render_jev_added(results: dict) -> None:
    st.markdown("## What Jev Added")
    full = results.get(MODE_FULL)
    if not full:
        st.info("Needs an LLM + Graph + Jev result.")
        return
    st.markdown("### Early Jev — triage guidance")
    e = insights.early_triage_added(full)
    if e is None:
        st.info("This stored run predates early triage (it has late verification only). Re-run LLM + Graph + Jev to see early triage.")
    else:
        c = st.columns(4)
        c[0].metric("Suggested category", e["category"] or "none")
        c[1].metric("Probability", "—" if e["probability"] is None else f"{e['probability']:.2f}")
        c[2].metric("Uncertainty", (e["uncertainty"] or "—").title())
        c[3].metric("Agent", (e.get("outcome") or "—").replace("_", " ").title())
        st.markdown(f"**Result:** {e['summary']}" + (f"  \n**Competing categories Jev listed:** " + "; ".join(f"{a['name']} ({a['probability']:.2f})" for a in e["alternatives"]) if e["alternatives"] else ""))
        st.caption("Provisional guidance from the ticket text alone, before any graph evidence. It is never presented as a verified diagnosis: the agent was free to reject it, and the late verifier below never saw it.")
    st.markdown("### Late Jev — answer verification")
    j = insights.jev_added(full)
    st.markdown(f"**Initial agent diagnosis:** {j['initial']}")
    c = st.columns(4)
    c[0].metric("Missed-evidence risk", pct(j["missed"]))
    c[1].metric("Distractor anchoring risk", pct(j["distractor"]))
    c[2].metric("Review signal", j["review"] or "n/a")
    c[3].metric("Verifier decision", j["first_decision"].replace("_", " ").title())
    st.markdown(f"**Extra tool calls:** {j['extra_tool_calls']}" + ("" if j["additional_investigation"] else " (none: verification did not ask for more investigation)"))
    st.markdown(f"**Final diagnosis:** {j['final']}  \n**Final disposition:** {j['final_decision'].replace('_', ' ')}")
    st.markdown(f"**Diagnosis changed after verification:** {'YES — ' + (', '.join(FIELD_LABELS[f].lower() for f in j['changed_fields']) or 'status: ' + str(j['initial_status']) + ' → ' + str(j['final_status'])) if (j['diagnosis_changed'] or j['status_changed']) else 'NO'}")


def render_impact(results: dict) -> None:
    st.markdown("## Architecture Impact")
    imp = insights.impact(results)
    a, b = st.columns(2)
    with a:
        st.markdown("**Graph impact**")
        st.markdown("\n".join(f"- {x}" for x in imp["graph"]) or "- needs LLM Only and LLM + Graph")
    with b:
        st.markdown("**Jev impact**")
        if imp["jev"]:
            st.markdown("*Early Jev — triage guidance*\n" + "\n".join(f"- {x}" for x in imp["jev_early"]) + "\n\n*Late Jev — verification*\n" + "\n".join(f"- {x}" for x in imp["jev"]))
        else:
            st.markdown("- needs LLM + Graph + Jev")


def render_tool_trace(run: dict, title: str) -> None:
    mp = run["alias_mappings"]
    rows = []
    for s in run["trace_steps"]:
        if s["tool_name"] == "submit_diagnosis":
            continue
        ev = [e for e in mp.values() if e["kind"] in ("EVIDENCE", "CHANGE", "INCIDENT") and e["first_observed_step"] == s["step"]]
        args = ", ".join(f"{k}={label(mp, v) if isinstance(v, str) and v in mp else v}" for k, v in (s.get("args_alias") or {}).items())
        rows.append({"Step": s["step"], "Tool": s["tool_name"] + (" (ticket, harness)" if s.get("proposed_by") == "harness" else ""), "Arguments": args or "—", "Result": s["status"],
                     "Evidence returned": (f"{len(ev)}: " + " | ".join(e["summary"][:70] for e in ev[:2]) + (" …" if len(ev) > 2 else "")) if ev else "—"})
    with st.expander(f"Tool trace — {title} ({len([r for r in rows if 'harness' not in r['Tool']])} tool calls)"):
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("Structured hypothesis state and tool results only; no free-text reasoning is stored or shown.")


def render_early_triage_detail(result) -> None:
    """The early-triage record: what Jev saw and answered, the fallback reason if any, and exactly what the agent was shown."""
    e = insights.early_triage_added(result)
    if e is None:
        return
    with st.expander("Early Jev triage — guidance before investigation", expanded=False):
        st.markdown(f"**Status:** {e['status_text']}" + (f" — {e['fallback_reason']}" if e["fallback_reason"] else "") + f"  \n**Latency:** {e['latency_ms']:.0f} ms · **Jev input tokens:** {e['input_tokens']} · "
                    f"**Jev model:** {e['jev_model'] or 'n/a'} · **Question:** {e['question_version']}")
        if e["distribution_top"]:
            st.dataframe([{"Category": d["name"], "Jev probability": d["probability"]} for d in e["distribution_top"]] +
                         [{"Category": "(abstain option)", "Jev probability": e["abstain_probability"]}], use_container_width=True, hide_index=True)
        if e["suggested_tools"]:
            st.markdown("**Advisory starting tools shown to the agent:** " + "; ".join(e["suggested_tools"]) + "  \n(Advisory only: every tool stayed available and no category or evidence was filtered.)")
        hint = (result.raw.get("agent_run") or {}).get("triage_hint_text")
        if hint:
            st.markdown("**Exactly what the agent was shown**")
            st.code(hint)
        st.markdown(f"**Agent result:** {e['outcome_text']}" + (f" (final category: {e['final_category']})" if e.get("final_category") else ""))
        st.caption("Guidance only. The early suggestion comes from the ticket text before any graph investigation; it is not verified and is not a diagnosis. Early Jev and late Jev are separate calls; the late verifier never receives this suggestion.")


def render_verification_trace(result) -> None:
    v = result.verification
    with st.expander("Late Jev — answer verification (runtime verifier)", expanded=False):
        for p in v["passes"]:
            st.markdown(f"**PASS {p['round']}**")
            names = {"D1": "Valid Final Contract", "D2": "Evidence Support", "D3": "Final Consistency", "D4": "Premature Finalization"}
            st.dataframe([{"Check": names.get(k, k), "Result": ("PASS" if c["passed"] else "FAIL") + ("" if c["applicable"] else " (n/a)"), "Detail": c["detail"]} for k, c in p["checks"].items()],
                         use_container_width=True, hide_index=True)
            probs = p.get("review_probabilities") or {}
            st.markdown(f"Missed Evidence **{p['missed'] if p['missed'] is not None else 'n/a'}** · Distractor Risk **{p['distractor'] if p['distractor'] is not None else 'n/a'}** · "
                        f"Review Signal **{p['review'] or 'n/a'}**" + (f" ({', '.join(f'{k} {x:.2f}' for k, x in probs.items())})" if probs else ""))
            st.markdown(f"Decision: **{p['decision']}** — {p['reason']}")
            if p.get("message"):
                st.markdown("Message sent back to the agent")
                st.code(p["message"])
        if v.get("contract_failure"):
            st.error(f"Contract failure: {v['contract_failure']}")


def render_ground_truth(case_id: str, results: dict) -> None:
    """Optional, dev cases only. Imported and run only after all architectures have finished; it never feeds back into any run."""
    from agent.compare import evaluation

    st.markdown("## Evaluation against dev ground truth")
    st.caption("Offline and separate from the runs above. Correct = matches the dev ground truth (root cause by exact/containment match, others by name); ABSTAIN = the architecture selected nothing.")
    try:
        ev = evaluation.score_all(case_id, results)
    except Exception as e:  # noqa: BLE001
        st.error(f"Evaluation unavailable: {e}")
        return
    icon = {"correct": "✓", "wrong": "✕", "abstain": "ABSTAIN"}
    st.dataframe([{"Architecture": NAMES[m], "Correct root cause": icon[s["root_cause"]], "Correct category": icon[s["issue_category"]], "Correct component": icon[s["affected_component"]],
                   "Correct team": icon[s["owning_team"]]} for m, s in ev["scores"].items()], use_container_width=True, hide_index=True)
    t = ev["truth"]
    with st.expander("Ground truth for this case (dev)"):
        st.markdown(f"Root cause: **{t['root_cause']}** · Category: **{t['issue_category']}** · Component: **{t['affected_component']}** · Acceptable teams: **{', '.join(t['owning_team'])}**")


def render_debug(results: dict) -> None:
    with st.expander("Advanced / debug"):
        rows = []
        for m, r in results.items():
            raw = r.raw.get("agent_run", r.raw) if m != MODE_LLM else r.raw
            rows.append({"Architecture": NAMES[m], "Run id": r.run_id, "Source": r.source, "Model": raw.get("model_name"), "Prompt": raw.get("prompt_version"),
                         "Agent version": raw.get("agent_version") or "—", "Code digest": (raw.get("code_digest") or "")[:12] or "—"})
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_compare(results: dict, case_id: str, show_truth: bool) -> None:
    st.markdown("**How the three architectures differ**")
    st.markdown("  \n".join(f"**{NAMES[m]}** — {FLOW[m]}" for m in MODES))
    cols = st.columns(3)
    for col, m in zip(cols, MODES):
        with col:
            render_card(m, results.get(m), case_id)
    if not results:
        return
    render_differences(results)
    st.markdown("### Comparison")
    st.dataframe(insights.comparison_rows(results), use_container_width=True, hide_index=True)
    render_graph_added(results)
    render_jev_added(results)
    render_impact(results)
    for m in (MODE_GRAPH, MODE_FULL):
        if results.get(m):
            render_tool_trace(results[m].raw.get("agent_run", results[m].raw), NAMES[m])
    if results.get(MODE_FULL):
        render_early_triage_detail(results[MODE_FULL])
        render_verification_trace(results[MODE_FULL])
    if show_truth:
        render_ground_truth(case_id, results)
    render_debug(results)


def render_single(mode: str, result, case_id: str, show_truth: bool) -> None:
    render_card(mode, result, case_id)
    if result is None:
        return
    if mode == MODE_LLM:
        with st.expander("What the model saw (the ticket) and its raw answer"):
            st.json(result.raw["ticket_shown_to_model"], expanded=False)
            st.json(result.raw["parsed"], expanded=False)
            st.caption(f"{result.raw['n_categories_offered']} issue categories and {result.raw['n_root_causes_offered']} root causes were offered as the answer vocabulary. No tools, no graph, no Jev.")
    elif mode == MODE_GRAPH:
        render_run(result.raw)
    else:
        render_early_triage_detail(result)
        render_verification(result.raw)
        render_run(result.raw["agent_run"])
    if show_truth:
        render_ground_truth(case_id, {mode: result})
    render_debug({mode: result})


def render_architecture_results() -> None:
    st.markdown("### Architecture results (stored dev runs)")
    include = st.checkbox("Include accuracy against dev ground truth (offline, over stored runs)", value=True, key="agg_truth")
    agg = cached_aggregate(include, len(adapters.llm_index()), len(adapters.graph_index()), len(adapters.full_index()))
    st.markdown(f"**Cases compared: {agg['n']}**")
    if not agg["n"]:
        st.info(agg["note"])
        return
    st.dataframe(agg["rows"], use_container_width=True, hide_index=True)
    st.caption(agg["note"])
    with st.expander("Cases included"):
        st.write(", ".join(agg["cases"]))


# ── page ─────────────────────────────────────────────────────────────────────

render_sidebar_status()
st.title("🩺 Diagnostic agent")
st.caption("Compare what a plain LLM, an LLM with the graph (the unchanged baseline), and an LLM with the graph plus Jev do on the same dev case. Jev has two roles: early triage (a provisional category hint from the ticket text) and late verification of the finished answer. Dev cases only.")

choice = st.radio("Execution mode", OPTIONS, index=2, horizontal=True)
compare_all = choice == "Compare All"
selected = list(MODES) if compare_all else [OPTION_MODE[choice]]
cases = dev_cases()
case_id = st.selectbox("Dev case", cases, format_func=lambda c: c)

avail = adapters.available(case_id)
if st.session_state.get("cmp_case") != case_id:
    st.session_state["cmp_case"] = case_id
    st.session_state["cmp_results"] = {m: adapters.load_stored(m, case_id) for m in MODES if avail[m]}
    st.session_state.pop("cmp_errors", None)
results = st.session_state["cmp_results"]

chips = st.columns(3)
for col, m in zip(chips, MODES):
    live = m in results and results[m] is not None and results[m].source == "live"
    col.markdown(f"**{NAMES[m]}** &nbsp; " + ("🟢 Live ✓" if live else "🟦 Stored ✓" if avail[m] else "⚪ Stored ✕"))
show_truth = st.checkbox("Show evaluation / ground truth (dev cases only, after the runs)", value=False)

missing = [m for m in selected if m not in results or results[m] is None]
to_run = None
if compare_all:
    cost_missing = cached_cost(tuple(missing)) if missing else {"total": 0}
    cost_all = cached_cost(tuple(MODES))
    st.info("Live runs execute in parallel.  \n" + "  \n".join(f"• {RUN_WHAT[m]} ({NAMES[m]})" for m in MODES) +
            f"  \nRe-running all three: about ${cost_all['total']:.2f}, several minutes." + (f"  \nRunning only the missing modes ({', '.join(NAMES[m] for m in missing)}): about ${cost_missing['total']:.2f}." if missing else "  \nNo mode is missing."))
    b1, b2, b3 = st.columns(3)
    if b1.button("Load available stored results", use_container_width=True):
        st.session_state["cmp_results"] = {m: adapters.load_stored(m, case_id) for m in MODES if adapters.available(case_id)[m]}
        st.rerun()
    if b2.button("Run missing modes", type="primary", disabled=not missing, use_container_width=True):
        to_run = missing
    if b3.button("Re-run all three live", use_container_width=True):
        to_run = list(MODES)
else:
    m = selected[0]
    b1, b2 = st.columns(2)
    if b1.button("Show stored result", disabled=not avail[m], use_container_width=True):
        st.session_state["cmp_results"][m] = adapters.load_stored(m, case_id)
        st.rerun()
    if b2.button("Run live", type="primary", use_container_width=True):
        to_run = [m]
if st.session_state.get("pending_run"):
    to_run, st.session_state["pending_run"] = st.session_state["pending_run"], None

if to_run:
    try:
        out = run_live(to_run, case_id)
        st.session_state["cmp_results"].update({m: r for m, r in out.items() if not isinstance(r, Exception)})
        st.session_state["cmp_errors"] = {m: f"{type(r).__name__}: {str(r)[:300]}" for m, r in out.items() if isinstance(r, Exception)}
    except Exception as e:  # noqa: BLE001
        st.session_state["cmp_errors"] = {"run": f"{type(e).__name__}: {str(e)[:300]}"}
    results = st.session_state["cmp_results"]
for m, msg in (st.session_state.get("cmp_errors") or {}).items():
    st.error(f"{NAMES.get(m, 'Run')} could not complete: {msg}")

tab_case, tab_agg = st.tabs(["Case", "Architecture Results"])
with tab_case:
    if compare_all:
        render_compare({m: results[m] for m in MODES if m in results and results[m] is not None}, case_id, show_truth)
    else:
        render_single(selected[0], results.get(selected[0]), case_id, show_truth)
with tab_agg:
    render_architecture_results()
