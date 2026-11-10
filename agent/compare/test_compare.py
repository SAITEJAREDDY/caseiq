"""Tests for the three-architecture comparison (no API call, no paid service; the page tests read stored dev runs and the reference CSVs).
Run with: python3 -m unittest agent.compare.test_compare

The scripted agent, a fake backend and a fake Jev stand in for Together, Neo4j and Jev, so the execution boundaries between the modes are tested exactly."""
import contextlib
import sys
import unittest
from unittest import mock

import requests

from agent.agent_v3 import validate_boundaries as vb
from agent.agent_v3.catalog import SUBMIT
from agent.agent_v3.test_agent_v3 import FakeBackend, ScriptedLLM, action, good_final
from agent.compare import adapters, insights, llm_only, orchestrator
from agent.compare.models import MODE_FULL, MODE_GRAPH, MODE_LLM, MODES, ComparisonResult
from agent.runtime_verifier import jev_checks
from agent.runtime_verifier.test_runtime_verifier import CLEAN, FakeJev

CASE = "CS00729"          # a real dev case id (the runs below use fakes, so nothing is read from the graph)
STORED_CASE = "CS00729"   # has a stored result for all three architectures (checked by the tests that need it)
def _first_unstored_dev_case() -> str:
    """A dev case with no stored result for any architecture (chosen at run time: people use the page, so any fixed case can gain stored runs)."""
    import json
    pool = sorted(json.loads((vb.ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"])
    return next((c for c in pool if not any(adapters.available(c).values())), pool[-1])


MISSING_CASE = _first_unstored_dev_case()


def session_factory():
    return contextlib.nullcontext(None)


def fake_ticket(session, case_id):
    return {"title": "Login fails for SSO users", "description": "Users cannot sign in.", "reported_symptoms": ["login failure"]}


def llm_only_answer(schema):
    return {"issue_category": schema["properties"]["issue_category"]["anyOf"][0]["enum"][0], "root_cause": schema["properties"]["root_cause"]["anyOf"][0]["enum"][0],
            "affected_component": "SSO Broker", "causal_change": None, "owning_team": None, "confidence": 0.6, "status": "DIAGNOSIS_PROPOSED", "summary": "Likely a permissions problem."}


def boom(*a, **k):
    raise AssertionError("this must not be called in this mode")


class Ctx:
    """Runs a mode with every collaborator faked and records what was touched."""
    def __init__(self, script=None, jev=None):
        self.backend, self.jev, self.llm = FakeBackend(), jev or FakeJev(), ScriptedLLM(script or [])

    def run(self, mode):
        with mock.patch.object(jev_checks, "build_packet", return_value={"packet_version": "test"}), mock.patch("agent.trace_eval_v2.guard.assert_request_clean"):
            return orchestrator.run_mode(mode, CASE, session_factory=session_factory, llm=self.llm, jev_client=self.jev, backend_factory=lambda s, c: self.backend,
                                         ticket_loader=fake_ticket, save=False)


def stored_all_three(case_id=STORED_CASE) -> bool:
    return all(adapters.available(case_id).values())


class TestExecutionBoundaries(unittest.TestCase):
    """Tests 1-4: the modes genuinely differ."""

    def test_1_llm_only_never_calls_graph_tools(self):
        files = [vb.ROOT / "agent" / "compare" / "llm_only.py"]
        closure = {".".join(f.relative_to(vb.ROOT).with_suffix("").parts).replace(".__init__", "") for f in vb.import_closure(files)}
        forbidden = [m for m in closure if m.startswith(("agent.agent_v2.tools", "agent.agent_v3.backend", "agent.agent_v3.loop", "agent.agent_v3.registry", "agent.agent_v3.catalog", "agent.graph_v2",
                                                         "agent.runtime_verifier", "agent.jev_v2", "agent.trace_eval_v2", "agent.eval_v2", "data.eval", "agent.compare.evaluation"))]
        self.assertEqual(forbidden, [], f"LLM Only can reach: {forbidden}")
        ctx = Ctx([llm_only_answer])
        with mock.patch.object(orchestrator, "run_case", boom), mock.patch.object(orchestrator, "run_verified_case", boom):
            r = orchestrator.run_mode(MODE_LLM, CASE, session_factory=session_factory, llm=ctx.llm, jev_client=boom, backend_factory=boom, ticket_loader=fake_ticket, save=False)
        self.assertEqual((r.tool_calls, r.evidence_count, r.graph_used, r.jev_used), (0, 0, False, False))
        self.assertEqual(ctx.backend.calls, [])
        self.assertIsNone(r.verification)

    def test_2_llm_only_never_calls_jev(self):
        ctx = Ctx([llm_only_answer])
        with mock.patch.object(jev_checks, "signals", boom):
            r = ctx.run(MODE_LLM)
        self.assertEqual(ctx.jev.calls, [])
        self.assertFalse(r.jev_used)
        self.assertEqual(len(ctx.llm.requests), 1)          # exactly one direct model call
        self.assertIn("no tools", ctx.llm.requests[0]["messages"][0]["content"])             # the prompt tells the model it has no tools

    def test_3_graph_mode_calls_graph_tools_but_never_jev(self):
        ctx = Ctx(CLEAN)
        with mock.patch.object(jev_checks, "signals", boom):
            r = ctx.run(MODE_GRAPH)
        self.assertGreater(len(ctx.backend.calls), 0)
        self.assertEqual(ctx.jev.calls, [])
        self.assertEqual((r.graph_used, r.jev_used, r.verification), (True, False, None))
        self.assertGreater(r.tool_calls, 0)
        self.assertGreater(r.evidence_count, 0)

    def test_4_full_mode_executes_the_verifier(self):
        ctx = Ctx(CLEAN)
        r = ctx.run(MODE_FULL)
        self.assertEqual(sorted(ctx.jev.calls), ["distractor_anchor", "human_review", "missed_evidence"])
        self.assertTrue(r.graph_used and r.jev_used)
        self.assertEqual(r.verification["final_decision"], "ACCEPT")
        self.assertEqual(len(r.verification["passes"]), 1)
        self.assertIn("D1", r.verification["passes"][0]["checks"])

    def test_the_three_modes_share_one_result_schema(self):
        rs = {MODE_LLM: Ctx([llm_only_answer]).run(MODE_LLM), MODE_GRAPH: Ctx(CLEAN).run(MODE_GRAPH), MODE_FULL: Ctx(CLEAN).run(MODE_FULL)}
        for m, r in rs.items():
            self.assertIsInstance(r, ComparisonResult)
            self.assertEqual(r.mode, m)
            self.assertEqual(set(r.selections()), {"issue_category", "root_cause", "affected_component", "causal_change", "owning_team"})
        self.assertEqual([rs[m].jev_used for m in MODES], [False, False, True])
        self.assertEqual([rs[m].graph_used for m in MODES], [False, True, True])

    def test_only_dev_cases_can_be_run(self):
        with self.assertRaises(ValueError):
            orchestrator.run_mode(MODE_LLM, "CS99999", session_factory=session_factory, llm=ScriptedLLM([]), ticket_loader=fake_ticket, save=False)

    def test_run_modes_reports_progress_and_isolates_failures(self):
        ctx, events = Ctx([llm_only_answer]), []
        with mock.patch.object(jev_checks, "build_packet", return_value={}), mock.patch("agent.trace_eval_v2.guard.assert_request_clean"):
            out = orchestrator.run_modes([MODE_LLM, MODE_GRAPH], CASE, session_factory=session_factory, llm=ctx.llm, jev_client=ctx.jev, parallel=False,
                                         on_update=lambda m, s, p: events.append((m, s)), backend_factory=lambda s, c: ctx.backend, ticket_loader=fake_ticket, save=False)
        self.assertEqual(events[:2], [(MODE_LLM, "started"), (MODE_GRAPH, "started")])
        self.assertIsInstance(out[MODE_LLM], ComparisonResult)
        self.assertIsInstance(out[MODE_GRAPH], Exception)                   # the scripted model ran out of outputs: reported per mode, not raised
        self.assertIn((MODE_GRAPH, "error"), events)


class TestGroundTruthBoundary(unittest.TestCase):
    """Test 6: ground truth is loaded only after runtime execution."""

    def test_6_ground_truth_is_read_only_after_all_runs(self):
        from agent.compare import evaluation
        static_closure = {".".join(f.relative_to(vb.ROOT).with_suffix("").parts).replace(".__init__", "") for f in vb.import_closure(
            [vb.ROOT / "agent" / "compare" / f"{m}.py" for m in ("llm_only", "orchestrator", "adapters", "insights", "models", "ticket")])}
        leaks = [m for m in static_closure if m in ("agent.compare.evaluation", "agent.compare.aggregate") or m.startswith(("agent.eval_v2.ground_truth", "agent.eval_v2.metrics", "data.eval"))]
        self.assertEqual(leaks, [], f"a runtime module can reach evaluation code: {leaks}")
        trip = mock.Mock(return_value={"case_ground_truth": {"gt_root_cause_id": "RC01", "gt_issue_category_id": "IC01", "gt_component_id": "CM001"}, "case_team_ownership": []})
        with mock.patch.object(evaluation, "get_hidden_truth", trip):
            results = {MODE_LLM: Ctx([llm_only_answer]).run(MODE_LLM), MODE_GRAPH: Ctx(CLEAN).run(MODE_GRAPH), MODE_FULL: Ctx(CLEAN).run(MODE_FULL)}
            self.assertEqual(trip.call_count, 0, "hidden truth was read while the architectures were running")
            evaluation.score_all(CASE, results)
            self.assertGreaterEqual(trip.call_count, 1)                    # ...and only now

    def test_evaluation_scores_abstain_correct_and_wrong(self):
        from agent.compare import evaluation
        r = Ctx([llm_only_answer]).run(MODE_LLM)
        names = {"root_cause": "product defect", "issue_category": "Identity / Authentication", "affected_component": "SSO Broker", "owning_team": ["Identity"]}
        s = evaluation.score(CASE, r, names)
        self.assertEqual(s["affected_component"], "correct")               # free text contained in the true name
        self.assertEqual(s["owning_team"], "abstain")                      # null prediction is ABSTAIN, never wrong
        self.assertIn(s["root_cause"], ("correct", "wrong"))
        r.root_cause = None
        self.assertEqual(evaluation.score(CASE, r, names)["root_cause"], "abstain")


class TestInsightsAreDeterministic(unittest.TestCase):
    def setUp(self):
        self.llm, self.graph, self.full = Ctx([llm_only_answer]).run(MODE_LLM), Ctx(CLEAN).run(MODE_GRAPH), Ctx(CLEAN).run(MODE_FULL)
        self.results = {MODE_LLM: self.llm, MODE_GRAPH: self.graph, MODE_FULL: self.full}

    def test_table_shows_dashes_for_jev_fields_of_non_jev_modes(self):
        rows = {r["Metric"]: r for r in insights.comparison_rows(self.results)}
        self.assertEqual((rows["Final policy"]["LLM Only"], rows["Final policy"]["LLM + Graph"]), ("—", "—"))
        self.assertEqual(rows["Final policy"]["LLM + Graph + Jev"], "ACCEPT")
        self.assertEqual(rows["Tool calls"]["LLM Only"], "0")
        partial = {r["Metric"]: r for r in insights.comparison_rows({MODE_LLM: self.llm})}
        self.assertEqual(partial["Tool calls"]["LLM + Graph"], "not available")

    def test_graph_and_jev_sections_use_descriptive_language_and_are_repeatable(self):
        a, b = insights.graph_added(self.llm, self.graph), insights.graph_added(self.llm, self.graph)
        self.assertEqual(a, b)
        self.assertEqual(a["evidence_added"], self.graph.evidence_count)
        j = insights.jev_added(self.full)
        self.assertFalse(j["additional_investigation"])
        text = " ".join(t for _, t in insights.differences(self.results)) + " ".join(insights.impact(self.results)["graph"] + insights.impact(self.results)["jev"])
        for banned in ("better", "more accurate", "improved", "worse"):
            self.assertNotIn(banned, text.lower())

    def test_component_wording_alone_is_not_a_changed_diagnosis(self):
        llm = ComparisonResult(**{**self.llm.__dict__, "issue_category": self.graph.issue_category, "root_cause": self.graph.root_cause, "affected_component": "Some free text"})
        g = insights.graph_added(llm, self.graph)
        self.assertFalse(g["diagnosis_changed"])
        self.assertEqual(g["component_wording"], ("Some free text", self.graph.affected_component))
        lines = insights.differences({MODE_LLM: llm, MODE_GRAPH: self.graph})
        self.assertFalse(any(k == "diff" for k, _ in lines))
        self.assertTrue(any(k == "note" and "Component" in t for k, t in lines))

    def test_disagreement_is_called_out_without_saying_who_is_right(self):
        other = ComparisonResult(**{**self.llm.__dict__, "root_cause": "a different root cause"})
        lines = insights.differences({MODE_LLM: other, MODE_GRAPH: self.graph})
        self.assertTrue(any(k == "diff" and "Root cause changed" in t for k, t in lines))


@unittest.skipUnless(stored_all_three(), f"needs stored results for all three architectures on {STORED_CASE}")
class TestPageWithStoredResults(unittest.TestCase):
    """Tests 5, 7, 8 on the real page (Streamlit AppTest). Network and live execution are patched to fail: stored views must need neither."""

    def app(self, case_id, option="Compare All", truth=False):
        from streamlit.testing.v1 import AppTest
        with mock.patch.object(requests, "post", side_effect=AssertionError("an API call was made")), mock.patch.object(orchestrator, "run_modes", boom):
            at = AppTest.from_file("pages/1_Diagnostic_Agent.py", default_timeout=120).run()
            at.selectbox[0].select(case_id).run()
            at.radio[0].set_value(option).run()
            if truth:
                [c for c in at.checkbox if c.label.startswith("Show evaluation")][0].check().run()
        return at

    def test_5_and_7_compare_all_renders_every_stored_result_without_api_calls(self):
        at = self.app(STORED_CASE)
        self.assertEqual(list(at.exception), [])
        heads = [str(m.value) for m in at.markdown]
        for h in ("### LLM ONLY", "### LLM + GRAPH", "### LLM + GRAPH + JEV", "## What the Graph Added", "## What Jev Added", "## Architecture Impact"):
            self.assertTrue(any(x.startswith(h) for x in heads), h)
        self.assertTrue(any("LLM ✓" in str(m.value) and "Jev ✕" in str(m.value) for m in at.markdown))     # the badges
        self.assertTrue([b for b in at.button if b.label == "Run missing modes"][0].disabled)          # nothing is missing

    def test_default_mode_is_the_full_architecture(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file("pages/1_Diagnostic_Agent.py", default_timeout=120).run()
        self.assertEqual(at.radio[0].value, "LLM + Graph + Jev")

    def test_each_single_mode_renders(self):
        for option in ("LLM Only", "LLM + Graph", "LLM + Graph + Jev"):
            at = self.app(STORED_CASE, option)
            self.assertEqual(list(at.exception), [], option)
            self.assertTrue(any(str(m.value).startswith("### " + option.upper()) for m in at.markdown), option)

    def test_8_missing_modes_are_handled_gracefully(self):
        self.assertFalse(any(adapters.available(MISSING_CASE).values()), f"{MISSING_CASE} unexpectedly has stored results")
        at = self.app(MISSING_CASE)
        self.assertEqual(list(at.exception), [])
        self.assertGreaterEqual(sum("Not available" in str(i.value) for i in at.info), 3)
        run_missing = [b for b in at.button if b.label == "Run missing modes"][0]
        self.assertFalse(run_missing.disabled)
        self.assertTrue([b for b in at.button if b.label == "Load available stored results"])

    def test_ground_truth_panel_is_off_by_default_and_runs_only_when_asked(self):
        from agent.compare import evaluation
        with mock.patch.object(evaluation, "score_all", wraps=evaluation.score_all) as spy:
            self.app(STORED_CASE)
            self.assertEqual(spy.call_count, 0)
            at = self.app(STORED_CASE, truth=True)
            self.assertGreaterEqual(spy.call_count, 1)
        self.assertEqual(list(at.exception), [])
        self.assertTrue(any("Evaluation against dev ground truth" in str(m.value) for m in at.markdown))

    def test_aggregate_tab_shows_n_and_only_common_cases(self):
        from agent.compare import aggregate
        cases = aggregate.comparable_cases()
        self.assertIn(STORED_CASE, cases)
        agg = aggregate.aggregate(include_truth=False)
        self.assertEqual(agg["n"], len(cases))
        self.assertTrue(all(all(adapters.available(c).values()) for c in cases))
        self.assertTrue(any(r["Metric"] == "Human-review rate" and r["LLM Only"] == "—" and r["LLM + Graph"] == "—" for r in agg["rows"]))


if __name__ == "__main__":
    unittest.main()
