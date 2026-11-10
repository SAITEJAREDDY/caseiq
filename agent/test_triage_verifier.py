"""Offline tests for the demo app's third column (Jev verification of the graph-grounded recommendation). No API, no graph. Run: python3 -m unittest agent.test_triage_verifier"""
import copy
import unittest

from agent import triage_verifier as T

SIMILAR = [{"title": "Refund API returns 4023", "resolution_time_hours": 1.2}, {"title": "Refund failures on v2", "resolution_time_hours": 1.6}]
AGENTS = [{"name": "Jennifer Cooper", "seniority": "senior", "avg_resolution_time": 3.5}, {"name": "Michelle Mitchell", "seniority": "mid", "avg_resolution_time": 4.1}]
ARTICLES = [{"title": "Payment Gateway v2 integration checklist", "resolution_rate": 0.88, "times_used": 10},
            {"title": "Payment Gateway v2 performance optimization", "resolution_rate": 0.86, "times_used": 13},
            {"title": "Enterprise setup guide: Payment Gateway v2", "resolution_rate": 0.83, "times_used": 31}]
REC = {"customer": {"customer_tier": "gold", "customer_name": "Acme", "prior_cases_on_product": 4}, "avg_resolution_hours": 1.4}
CTX = T.context_from_graph(SIMILAR, AGENTS, ARTICLES, REC)
GOOD = """1. **2 Best Agents to Assign**
   - **Jennifer Cooper** (Senior) — resolves cases with an average of 3.5 hours, the fastest among the listed agents.
   - **Michelle Mitchell** (Mid) — averages 4.1 hours per case, the next-best performer.
2. **3 Most Relevant Resources**
   - **Payment Gateway v2 integration checklist** — 88% resolution rate, used in 10 past cases — addresses configuration errors.
   - **Payment Gateway v2 performance optimization** — 86% resolution rate, used in 13 past cases.
   - **Enterprise setup guide: Payment Gateway v2** — 83% resolution rate, used in 31 past cases.
3. **Estimated Resolution Time** The historical average for Payment Gateway v2 issues is 1.4 hours.
"""


class FakeJev:
    def __init__(self, unsupported=0.1, missed=0.1, anchoring=0.1, review=(0.8, 0.15, 0.05), fail=False):
        self.v, self.review, self.fail, self.calls = {"unsupported_claims": unsupported, "missed_evidence": missed, "weak_anchoring": anchoring}, review, fail, []

    def judge(self, state, question, key):
        self.calls.append(key)
        if self.fail:
            raise RuntimeError("network down")
        if key == "review":
            p = dict(zip(("NORMAL", "REVIEW", "PRIORITY_REVIEW"), self.review))
            ans = {"choice": max(p, key=p.get), "confidence": max(p.values()), "probabilities": p}
        else:
            ans = {"noul": self.v[key]}
        return {"model": "jev-fake", "answers": {key: ans}, "usage": {"input_tokens": 500}}


def verify(response=GOOD, jev=None, regenerate=None, ctx=CTX):
    return T.verify("Customer cannot process refunds on Payment Gateway v2.1", "Payment Gateway v2.1", ctx, response, regenerate or (lambda fb: GOOD), jev or FakeJev())


class TestGrounding(unittest.TestCase):
    def ids(self, response, ctx=CTX):
        g = T.grounding_checks(response, ctx)
        return {c["id"]: c["passed"] for c in g["checks"]}, g

    def test_a_faithful_recommendation_passes_every_check(self):
        ok, g = self.ids(GOOD)
        self.assertEqual(ok, {"G1": True, "G2": True, "G3": True, "G4": True})
        self.assertEqual((g["named_agents"], g["cited_articles"]), (2, 3))

    def test_an_invented_agent_or_article_fails_g1(self):
        ok, g = self.ids(GOOD + "   - **Bob Smith** (Senior) — averages 1.0 hours.\n")
        self.assertFalse(ok["G1"])
        self.assertIn("Bob Smith", g["problems"][0])
        ok, g = self.ids(GOOD + "   - **Payment Gateway secret manual** — 91% resolution rate.\n")
        self.assertFalse(ok["G1"])
        self.assertIn("secret manual", " ".join(g["problems"]))

    def test_a_wrong_figure_fails_g2(self):
        for bad in (GOOD.replace("88% resolution", "97% resolution"), GOOD.replace("average of 3.5 hours", "average of 1.2 hours"), GOOD.replace("used in 13 past", "used in 40 past")):
            ok, _ = self.ids(bad)
            self.assertFalse(ok["G2"], bad[:80])
        self.assertTrue(self.ids(GOOD.replace("3.5 hours", "3.6 hours"))[0]["G2"])   # within tolerance

    def test_ignoring_the_retrieved_data_fails_g3_and_thin_retrieval_fails_g4(self):
        ok, _ = self.ids("1. **Best agents** — a senior engineer would help.\n2. Resources — check the docs.\n")
        self.assertFalse(ok["G3"])
        thin = T.context_from_graph([], [], [], REC)
        self.assertFalse(self.ids(GOOD, thin)[0]["G4"])


class TestPolicy(unittest.TestCase):
    cfg = T.TriageVerifierConfig()

    def d(self, response=GOOD, jev=None, round_no=1, ctx=CTX):
        g = T.grounding_checks(response, ctx, self.cfg)
        j = T.jev_signals(T.build_packet("x", "p", ctx, response), jev or FakeJev())
        return T.decide(g, j, round_no, self.cfg)

    def test_clean_is_accepted(self):
        self.assertEqual(self.d()["decision"], T.ACCEPT)

    def test_grounding_failure_or_jev_risk_triggers_one_revision_then_review(self):
        for kw in ({"response": GOOD.replace("88% resolution", "97% resolution")}, {"jev": FakeJev(missed=0.9)}, {"jev": FakeJev(anchoring=0.8)}, {"jev": FakeJev(unsupported=0.8)}):
            self.assertEqual(self.d(**kw)["decision"], T.REVISE, kw.keys())
            self.assertEqual(self.d(round_no=2, **kw)["decision"], T.HUMAN_REVIEW)

    def test_priority_review_and_thin_evidence_and_jev_outage(self):
        self.assertEqual(self.d(jev=FakeJev(review=(0.05, 0.25, 0.7)))["decision"], T.PRIORITY_REVIEW)
        self.assertEqual(self.d(ctx=T.context_from_graph([], [], [], REC))["decision"], T.HUMAN_REVIEW)      # nothing to verify against: a person decides
        out = self.d(jev=FakeJev(fail=True))
        self.assertEqual((out["decision"], out["triggers"]), (T.HUMAN_REVIEW, ["jev_unavailable"]))          # never auto-accepted without Jev

    def test_thresholds_are_configurable(self):
        g = T.grounding_checks(GOOD, CTX)
        j = T.jev_signals(T.build_packet("x", "p", CTX, GOOD), FakeJev(missed=0.6))
        self.assertEqual(T.decide(g, j, 1, T.TriageVerifierConfig())["decision"], T.ACCEPT)
        self.assertEqual(T.decide(g, j, 1, T.TriageVerifierConfig(missed_threshold=0.5))["decision"], T.REVISE)


class TestVerifyFlow(unittest.TestCase):
    def test_accept_makes_no_revision(self):
        calls = []
        r = verify(regenerate=lambda fb: calls.append(fb) or GOOD)
        self.assertEqual((r["decision"], r["revised"], calls), (T.ACCEPT, False, []))
        self.assertEqual(r["final_response"], GOOD)

    def test_a_revision_happens_once_and_is_verified_again(self):
        bad, calls = GOOD.replace("88% resolution", "97% resolution"), []
        r = verify(response=bad, regenerate=lambda fb: calls.append(fb) or GOOD)
        self.assertEqual(len(calls), 1)
        self.assertEqual((r["decision"], r["revised"], r["final_response"], len(r["rounds"])), (T.ACCEPT, True, GOOD, 2))
        self.assertIn("VERIFICATION FEEDBACK", calls[0])
        self.assertIn("does not match", calls[0])
        self.assertIn("Rewrite the full recommendation", calls[0])

    def test_a_second_failure_ends_in_human_review_and_never_a_third_pass(self):
        bad, calls = GOOD.replace("88% resolution", "97% resolution"), []
        r = verify(response=bad, regenerate=lambda fb: calls.append(fb) or bad)
        self.assertEqual((r["decision"], len(calls), len(r["rounds"])), (T.HUMAN_REVIEW, 1, 2))
        self.assertIn("still unresolved", r["reason"])

    def test_a_revision_that_breaks_grounding_never_replaces_a_grounded_original(self):
        invented = GOOD + "   - **Payment Gateway secret manual** — 91% resolution rate.\n"
        r = verify(response=GOOD, jev=FakeJev(missed=0.9), regenerate=lambda fb: invented)      # Jev asks for a revision; the revision invents an article
        self.assertEqual((r["decision"], r["reverted"], r["revised"], r["final_response"]), (T.HUMAN_REVIEW, True, False, GOOD))
        self.assertIn("original answer is shown", r["reason"])
        self.assertFalse(all(c["passed"] for c in r["rounds"][1]["checks"]))                    # the rejected revision is kept for inspection

    def test_a_failed_revision_is_a_review_case_and_keeps_the_original(self):
        def boom(fb):
            raise RuntimeError("rate limited")
        r = verify(response=GOOD, jev=FakeJev(missed=0.9), regenerate=boom)
        self.assertEqual((r["decision"], r["final_response"], r["revised"]), (T.HUMAN_REVIEW, GOOD, False))

    def test_four_typed_jev_calls_per_pass(self):
        j = FakeJev()
        verify(jev=j)
        self.assertEqual(sorted(j.calls), ["missed_evidence", "review", "unsupported_claims", "weak_anchoring"])


class TestBoundaries(unittest.TestCase):
    def test_the_packet_is_id_free_and_passes_the_leakage_guard(self):
        from agent.trace_eval_v2 import guard
        packet = T.build_packet("Customer cannot process refunds on Payment Gateway v2.1 — error code 4023", "Payment Gateway v2.1", CTX, GOOD)
        for key, q in T.QUESTIONS.items():
            guard.assert_request_clean(packet, q)                      # raises on any hidden field name, marker or internal id
        self.assertNotIn("Acme", str(packet))                          # the customer's name is not sent

    def test_no_evaluation_or_ground_truth_code_is_reachable(self):
        from agent.agent_v3 import validate_boundaries as vb
        closure = {".".join(f.relative_to(vb.ROOT).with_suffix("").parts).replace(".__init__", "") for f in vb.import_closure([vb.ROOT / "agent" / "triage_verifier.py"])}
        allowed = {"agent.eval_v2", "agent.eval_v2.config", "agent.eval_v2.contract"}              # constants and a pure error-string classifier
        bad = [m for m in closure if (m.startswith("agent.eval_v2") and m not in allowed) or m.startswith(("data.eval", "agent.trace_eval_v2.labels", "agent.trace_eval_v2.scorer", "agent.trace_eval_v2.analysis"))]
        self.assertEqual(bad, [], "an evaluation or ground-truth module is reachable from the verifier")
        self.assertFalse(any(w in open(vb.ROOT / "agent" / "triage_verifier.py").read() for w in ("gt_", "get_hidden_truth", "eval_store")))


if __name__ == "__main__":
    unittest.main()


class TestComparisonColumn(unittest.TestCase):
    """The Jev column of the COMPARISON panel: derived from the verified result, never from fixed demo values."""

    def result(self, response=GOOD, jev=None, regen=None, agents=AGENTS):
        v = verify(response=response, jev=jev, regenerate=regen)
        top = dict(agents[0], skill_match_pct=94)
        return {"verified": v, "agents": [dict(a) for a in agents], "top_agent": top, "latency_jev": v["latency_s"]}

    def test_the_named_agent_seniority_and_resolution_time_are_the_real_ones(self):
        from agent import triage_compare as C
        view = C.jev_view(self.result(), 94)
        self.assertEqual((view["agent"], view["seniority"], view["avg"], view["skill"]), ("Jennifer Cooper", "Senior", "3.5 hrs", "94%"))
        self.assertEqual(view["grounding"], "4/4 checks pass")
        self.assertEqual((view["confidence"], view["decision"]), ("High (verified)", "ACCEPT"))

    def test_a_different_agent_gets_its_own_values_and_no_invented_skill_match(self):
        from agent import triage_compare as C
        first = "   - **Jennifer Cooper** (Senior) — resolves cases with an average of 3.5 hours, the fastest among the listed agents.\n"
        second = "   - **Michelle Mitchell** (Mid) — averages 4.1 hours per case, the next-best performer.\n"
        assert first in GOOD and second in GOOD
        swapped = GOOD.replace(first + second, second + first)          # same faithful answer, the other agent listed first
        view = C.jev_view(self.result(response=swapped), 94)
        self.assertEqual((view["agent"], view["seniority"], view["avg"]), ("Michelle Mitchell", "Mid", "4.1 hrs"))
        self.assertEqual(view["skill"], "n/a")                         # no stored skill match for that agent: never a made-up number

    def test_escalation_is_read_from_the_answer_and_confidence_follows_the_decision(self):
        from agent import triage_compare as C
        self.assertEqual(C.stated_escalation("4. **Escalation Risk Assessment** Risk level: High\n- x"), "High")
        self.assertEqual(C.stated_escalation("Escalation Risk Assessment\nMedium"), "Medium")
        self.assertEqual(C.stated_escalation("nothing here"), "n/a")
        review = C.jev_view(self.result(jev=FakeJev(review=(0.05, 0.25, 0.7))), 94)
        self.assertEqual((review["decision"], review["confidence"]), ("PRIORITY_REVIEW", "Low (priority review)"))
        revised = C.jev_view(self.result(response=GOOD.replace("88% resolution", "97% resolution")), 94)
        self.assertEqual((revised["revised"], revised["extra_llm_calls"], revised["jev_calls"], revised["confidence"]), (True, 1, 8, "High (verified after revision)"))

    def test_the_column_reports_the_answer_that_is_shown_after_a_reverted_revision(self):
        from agent import triage_compare as C
        invented = GOOD + "   - **Payment Gateway secret manual** — 91% resolution rate.\n"
        view = C.jev_view(self.result(jev=FakeJev(missed=0.9), regen=lambda fb: invented), 94)
        self.assertEqual((view["decision"], view["grounding"], view["grounding_ok"], view["revised"]), ("HUMAN_REVIEW", "4/4 checks pass", True, False))
        self.assertEqual((view["revision_called"], view["extra_llm_calls"]), (True, 1))          # the revision call happened even though its result was rejected
        self.assertIn("rejected", view["decision_text"])

    def test_states_without_a_verification(self):
        from agent import triage_compare as C
        self.assertIsNone(C.jev_view({"verified": None}, 94))
        self.assertEqual(C.jev_view({"verified": {"error": "boom"}}, 94), {"error": "boom"})

    def test_a_failed_grounding_check_is_reported_as_flagged(self):
        from agent import triage_compare as C
        bad = GOOD.replace("88% resolution", "97% resolution")
        view = C.jev_view(self.result(response=bad, regen=lambda fb: bad), 94)      # still wrong after the revision -> human review
        self.assertEqual(view["decision"], "HUMAN_REVIEW")
        self.assertFalse(view["grounding_ok"])
        self.assertTrue(view["hallucination"].startswith("Flagged"))


class TestComparisonPanelRendering(unittest.TestCase):
    """Renders the REAL render_comparison from app.py (its source is extracted with `ast`, since app.py itself binds a port and cannot be imported) under Streamlit's test runner."""

    @classmethod
    def setUpClass(cls):
        import ast
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
        wanted = {"_CMP_TABLE_CSS", "_esc_cls", "_conf_cls", "_sen_cls", "_compute_quality_scores", "render_comparison"}
        parts = []
        for n in ast.parse(src).body:
            name = n.name if isinstance(n, ast.FunctionDef) else next((t.id for t in getattr(n, "targets", []) if hasattr(t, "id")), None)
            if name in wanted:
                parts.append(ast.get_source_segment(src, n))
        cls.code = ("import streamlit as st, json\nfrom agent import triage_compare\n"
                    "from agent.triage_ui import assignment_rows, first_pass_grounding, observability_rows, render_jev_answer, table_html\n" + "\n\n".join(parts))

    def render(self, verified, agents=None):
        import json
        from streamlit.testing.v1 import AppTest
        agents = agents or [dict(a, skill_match_pct=94) for a in AGENTS]
        result = {"random_agent": {"name": "Brenda Perez", "seniority": "mid", "avg_resolution_time": 13.2}, "top_agent": dict(agents[0]), "similar": SIMILAR, "agents": agents, "articles": ARTICLES,
                  "without_graph": "generic answer", "with_graph": GOOD, "latency_no_graph": 2.1, "latency_with_graph": 6.0, "verified": verified,
                  "latency_jev": (verified or {}).get("latency_s", 0) if verified and "error" not in verified else None}
        script = self.code + "\nrender_comparison(json.loads(%r))\n" % json.dumps(result)
        return AppTest.from_string(script, default_timeout=60).run()

    def html(self, at):
        return " ".join(str(m.value) for m in at.markdown)

    def test_accepted_result_adds_a_third_column_to_every_tab(self):
        at = self.render(verify())
        self.assertEqual(list(at.exception), [])
        h = self.html(at)
        self.assertGreaterEqual(h.count("With Graph + Jev"), 3)                       # assignment table, observability table, scorecard
        for cell in ("Jennifer Cooper", "Senior", "3.5 hrs", "High (verified)", "4/4 checks pass", "Accepted"):
            self.assertIn(cell, h, cell)
        self.assertIn("None: grounding checks pass", h)                                 # With Graph's fixed 'None' replaced by the measured result
        self.assertIn("Baseline vs Graph Intelligence vs Graph + Jev", h)
        self.assertTrue(any("Verified" in str(x.value) for x in at.success))            # the verified answer in the Response Quality tab
        self.assertTrue(any("does not measure whether the answer is grounded" in str(i.value) for i in at.info))

    def test_a_flagged_graph_answer_is_reported_as_flagged_not_none(self):
        bad = GOOD.replace("88% resolution", "97% resolution")
        at = self.render(verify(response=bad))                                          # revised once, then accepted
        h = self.html(at)
        self.assertEqual(list(at.exception), [])
        self.assertIn("Flagged: 'Payment Gateway v2 integration checklist': quoted 97%, data says 88%", h.replace("&#x27;", "'"))   # With Graph's own answer failed G2
        self.assertIn("Accepted after one revision", h)
        self.assertIn("1 revision + 8 Jev", h)

    def test_human_review_and_error_and_off_states(self):
        bad = GOOD.replace("88% resolution", "97% resolution")
        at = self.render(verify(response=bad, regenerate=lambda fb: bad))
        self.assertEqual(list(at.exception), [])
        self.assertIn("Needs human review", self.html(at))
        at = self.render({"error": "RuntimeError: boom"})
        self.assertEqual(list(at.exception), [])
        self.assertIn("unavailable", self.html(at))
        at = self.render(None)                                                          # verification off: exactly the original two-column panel
        h = self.html(at)
        self.assertEqual(list(at.exception), [])
        self.assertNotIn("With Graph + Jev", h)
        self.assertIn("Graph Intelligence vs Baseline", h)
        self.assertEqual(len(at.tabs), 4)
