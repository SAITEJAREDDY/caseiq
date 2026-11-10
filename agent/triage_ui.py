"""Streamlit rendering for the demo app's third column, "With Graph + Jev" (see agent/triage_verifier.py). Kept out of app.py so it can be tested on its own."""
import streamlit as st

from agent import triage_verifier as T

_PCT = lambda x: "n/a" if x is None else f"{x * 100:.0f}%"


def chips(graph: bool, jev: bool, extra: str = "") -> str:
    return f"LLM ✓ · Graph {'✓' if graph else '✕'} · Jev {'✓' if jev else '✕'}" + (f" · {extra}" if extra else "")


def _details(result: dict, v: dict) -> None:
    with st.expander("Verification details"):
        for rd in v["rounds"]:
            st.markdown(f"**Pass {rd['round']} → {rd['decision']}** — {rd['reason']}")
            for c in rd["checks"]:
                st.markdown(f"{'✅' if c['passed'] else '❌'} **{c['id']} {c['name']}** — {c['detail']}")
            j = rd["jev"]
            if j.get("available"):
                probs = j.get("review_probabilities") or {}
                st.markdown(f"Jev · unsupported claims **{_PCT(j['unsupported_claims'])}** · missed evidence **{_PCT(j['missed_evidence'])}** · weak-option anchoring **{_PCT(j['weak_anchoring'])}** · "
                            f"review signal **{j['review']}**" + (f" ({', '.join(f'{k} {_PCT(x)}' for k, x in probs.items())})" if probs else ""))
            else:
                st.warning("Jev signals unavailable: " + "; ".join(j.get("errors") or ["no result"]))
            if rd.get("feedback"):
                st.markdown("Message sent back to the model for its one revision")
                st.code(rd["feedback"])
        if v["revised"]:
            st.markdown("**Original recommendation (before the revision)**")
            st.markdown(v["initial_response"])
        elif v.get("reverted"):
            st.markdown("**Revision that was not used** (it introduced a claim the retrieved data does not support, so the original answer is shown)")
            st.markdown(v["rounds"][1]["response"])
        st.caption("Jev is a signal, not the decision: plain code combines the grounding checks and the Jev signals. Thresholds are hand-set defaults and this check is a demonstration, "
                   "not a validated control; Jev was evaluated in this project on diagnostic traces, not on recommendations like this one.")


def render_jev_column(result: dict) -> None:
    st.markdown("**🔵 With Graph + Jev** — verified before you act")
    v = result.get("verified")
    if v is None or "error" in v:
        st.caption(chips(True, False, "verification not available"))
        if v:
            st.warning(f"Jev verification could not run: {v['error']}")
        else:
            st.info("Not run for this message. Turn on “Third column: verify with Jev” in the sidebar.")
        with st.container(border=True):
            st.markdown(result["with_graph"])
        return
    extra = f"+{result.get('latency_jev', v['latency_s']):.1f}s verification"
    if v["decision"] == T.ACCEPT:
        st.success("✅ Verified — accepted" + (" after one revision" if v["revised"] else ""))
    elif v["decision"] == T.PRIORITY_REVIEW:
        st.error(f"🔴 Priority review — {v['reason']}")
    else:
        st.warning(f"🟠 Needs human review — {v['reason']}")
    st.caption(chips(True, True, extra))
    with st.container(border=True):
        st.markdown(v["final_response"])
    _details(result, v)


# ── the COMPARISON panel: table rows and the answer cell for the Jev column ──────────────────────────

import html as _html


def table_html(css: str, headers: list, rows: list) -> str:
    """rows: (label, (value, css_class), ...). Values are escaped; classes are the app's cmp-good / cmp-med / cmp-bad."""
    head = "".join(f"<th>{_html.escape(h)}</th>" for h in headers)
    body = ""
    for label, *cells in rows:
        tds = "".join(f'<td class="{c}">{_html.escape(str(v))}</td>' if c else f"<td>{_html.escape(str(v))}</td>" for v, c in cells)
        body += f'<tr><td class="lbl">{_html.escape(label)}</td>{tds}</tr>'
    return css + f'<table class="cmp-tbl"><thead><tr><th>Metric</th>{head}</tr></thead><tbody>{body}</tbody></table>'


def first_pass_grounding(result: dict):
    """(text, all_passed, first_problem) for the With Graph answer itself: the first verification pass checks exactly that answer."""
    v = result.get("verified")
    if not v or "error" in v:
        return None, None, None
    checks = v["rounds"][0]["checks"]
    n = sum(1 for c in checks if c["passed"])
    bad = next((c for c in checks if not c["passed"]), None)
    return f"{n}/{len(checks)} checks pass", (n == len(checks)), (None if bad is None else bad["detail"][:110])


def assignment_rows(base: list, jv: dict, first_pass, sen_cls, esc_cls) -> list:
    if "error" in jv:
        return [r + (("unavailable", "cmp-med"),) for r in base]
    good = "cmp-good" if jv["decision"] == "ACCEPT" else "cmp-med"
    cells = [(jv["agent"], good), (jv["skill"], good), (jv["seniority"], sen_cls(jv["seniority"])), (jv["avg"], good),
             (jv["escalation"], esc_cls(jv["escalation"]) if jv["escalation"] != "n/a" else ""), (jv["confidence"], good)]
    rows = [r + (c,) for r, c in zip(base, cells)]
    dec = {"ACCEPT": "cmp-good", "HUMAN_REVIEW": "cmp-med", "PRIORITY_REVIEW": "cmp-bad"}.get(jv["decision"], "")
    fp_text, fp_ok = first_pass[0], first_pass[1]
    return rows + [("Verification (measured)", ("—", ""), ("—", ""), (jv["decision_text"], dec)),
                   ("Grounding checks (measured)", ("n/a: no graph data", ""), (fp_text, "cmp-good" if fp_ok else "cmp-bad"), (jv["grounding"], "cmp-good" if jv["grounding_ok"] else "cmp-bad")),
                   ("Jev risk (measured)", ("—", ""), ("—", ""), (jv["risks"], "")), ("Jev review signal", ("—", ""), ("—", ""), (jv["review"], ""))]


def observability_rows(base: list, jv: dict, latency_with: float, src_label: str, first_pass) -> list:
    """`base` rows are the app's own (some are typed-in estimates). With Graph's 'Hallucination Risk: None' is a fixed claim, so when verification ran it is replaced by the measured grounding result of that answer."""
    fp_text, fp_ok, fp_bad = first_pass
    rows = []
    for r in base:
        if r[0] == "Hallucination Risk" and fp_text is not None:
            r = (r[0], r[1], ("None: grounding checks pass" if fp_ok else f"Flagged: {fp_bad}", "cmp-good" if fp_ok else "cmp-bad"))
        rows.append(r)
    if "error" in jv:
        return [r + (("unavailable", "cmp-med"),) for r in rows]
    third = {"Latency": (f"{latency_with + (jv['verify_latency'] or 0):.1f}s (+{jv['verify_latency'] or 0:.1f}s verification)", "cmp-med"), "Data Sources": (src_label, "cmp-good"),
             "Input Tokens": (f"~800 + Jev {jv['jev_tokens']:,} (measured)", ""), "Output Tokens": ("~200" + (" + a revision" if jv["revision_called"] else ""), ""), "Traceable": ("Yes", "cmp-good"),
             "Hallucination Risk": (jv["hallucination"], "cmp-good" if jv["grounding_ok"] else "cmp-bad")}
    out = [r + (third.get(r[0], ("—", "")),) for r in rows]
    return out + [("Extra model calls", ("0", ""), ("0", ""), (f"{jv['extra_llm_calls']} revision + {jv['jev_calls']} Jev", ""))]


def render_jev_answer(result: dict) -> None:
    """The verified answer for the Response Quality tab: the verdict banner and the final text (details are in the main column)."""
    v = result.get("verified")
    if v is None or "error" in v:
        st.info("Jev verification did not run for this message." if v is None else f"Jev verification could not run: {v['error']}")
        return
    if v["decision"] == T.ACCEPT:
        st.success("✅ Verified — accepted" + (" after one revision" if v["revised"] else ""))
    elif v["decision"] == T.PRIORITY_REVIEW:
        st.error(f"🔴 Priority review — {v['reason']}")
    else:
        st.warning(f"🟠 Needs human review — {v['reason']}")
    with st.container(border=True):
        st.markdown(v["final_response"])
