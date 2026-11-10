"""Tests for Jev-assisted early triage (no API call, no paid service; two tests read the real graph and are skipped if it is unreachable).
Run with: python3 -m unittest agent.early_triage.test_early_triage

A fake Jev and the scripted agent stand in for the two network services, so the call order, the fallback paths, the prompts the agent is shown and the boundaries are tested
exactly. The central invariant: every fallback leaves the agent's prompts byte-identical to the unchanged workflow."""
import hashlib
import json
import time
import unittest
from unittest import mock

from agent.agent_v3 import loop, prompts
from agent.agent_v3 import validate_boundaries as vb
from agent.agent_v3.catalog import SUBMIT
from agent.agent_v3.registry import ObservedEntityRegistry
from agent.agent_v3.test_agent_v3 import CASE, FakeBackend, ScriptedLLM, action, enum_of, final_answer, good_final
from agent.compare import adapters, insights, orchestrator
from agent.compare.models import MODE_FULL, MODE_GRAPH, MODE_LLM
from agent.compare.test_compare import Ctx, fake_ticket, llm_only_answer, session_factory
from agent.early_triage import priorities
from agent.early_triage import triage as T
from agent.early_triage.config import ABSTAIN_KEY, TriageConfig
from agent.jev_v2.client import JevClient, LeakageGuardError, assert_no_leakage
from agent.jev_v2.reference_data import all_issue_categories
from agent.runtime_verifier import jev_checks
from agent.runtime_verifier.models import ACCEPT, CONTINUE, VerifierConfig
from agent.runtime_verifier.run import run_verified_case
from agent.runtime_verifier.test_runtime_verifier import CLEAN, FakeJev

# sha256 of a fixed step prompt + final prompt built by the code as it was BEFORE early triage existed (captured first, then the code was edited)
BASELINE_PROMPT_SHA256 = "47930ced2cad071e71af6e1da6ebb8b76b05cd019aaafd77bd1c4e6a537ba820"


def dist(top, p, second=None, q=0.0, abstain=0.02):
    """A probability table over the 18 categories + ABSTAIN that sums to 1 with `top` the strict maximum."""
    options = list(all_issue_categories()) + [ABSTAIN_KEY]
    probs = {top: p}
    if second:
        probs[second] = q
    if ABSTAIN_KEY not in probs:
        probs[ABSTAIN_KEY] = abstain
    rest = [o for o in options if o not in probs]
    each = (1 - sum(probs.values())) / len(rest)
    probs.update({o: each for o in rest})
    return probs


class FakeTriageJev:
    """Stands in for the Jev client's `system_one`. Records every request; can answer, fail or stall."""
    def __init__(self, probs=None, answer=None, exc=None, delay=0.0, backend=None):
        self.probs, self.answer, self.exc, self.delay, self.backend, self.calls = probs, answer, exc, delay, backend, []

    def system_one(self, state, questions, model=None):
        self.calls.append({"state": state, "questions": questions})
        if self.backend is not None:
            assert not self.backend.calls, f"a graph tool ran before early triage: {self.backend.calls}"
        if self.delay:
            time.sleep(self.delay)
        if self.exc:
            raise self.exc
        (key, q), = questions.items()
        ans = self.answer if self.answer is not None else {"choice": max(self.probs, key=self.probs.get), "confidence": max(self.probs.values()), "probabilities": self.probs}
        return {"model": "jev-fake", "answers": {key: ans}, "usage": {"input_tokens": 321}}


class FakeBoth:
    """Both Jev roles on one client, as in production (`TraceJevClient` has `judge` for the late verifier and inherits `system_one` for early triage). The two roles keep
    separate call logs: `calls_early` (system_one) and `calls_late` (judge)."""
    def __init__(self, probs=None, **kw):
        self.early, self.late = FakeTriageJev(probs, **kw), FakeJev()
        self.calls_early, self.calls_late = self.early.calls, self.late.calls

    missed = property(lambda self: self.late.missed, lambda self, v: setattr(self.late, "missed", v))
    distractor = property(lambda self: self.late.distractor, lambda self, v: setattr(self.late, "distractor", v))

    def system_one(self, state, questions, model=None):
        return self.early.system_one(state, questions, model)

    def judge(self, state, question, key):
        return self.late.judge(state, question, key)


class TaxonomyBackend(FakeBackend):
    """The fake graph, with a taxonomy that carries the real names for the ids the tests use (the graph loads the same CSV that Jev's option list is read from)."""
    def taxonomy(self):
        cats, causes = FakeBackend.taxonomy(self)
        return [("IC01", "Identity / Authentication"), ("IC02", "Authorization / Permissions"), ("IC03", "Networking / Connectivity")], causes


class PoisonedBackend(TaxonomyBackend):
    def case_context(self):
        return {**FakeBackend.case_context(self), "description": "note gt_root_cause_id RC07 appears in this text"}


def plain_run(script=None):
    llm = ScriptedLLM(script or CLEAN)
    return loop.run_case(CASE, TaxonomyBackend(), llm), llm


def triage_run(jev, script=None, cfg=None, backend=None, **kw):
    backend, llm = backend or TaxonomyBackend(), ScriptedLLM(script or CLEAN)
    if getattr(jev, "backend", 1) is None:
        jev.backend = backend
    return loop.run_case(CASE, backend, llm, triage=T.EarlyTriage(jev, cfg), **kw), llm


def user_messages(llm):
    return [[m["content"] for m in r["messages"]] for r in llm.requests]


def ctx_for(script, jev):
    c = Ctx(script, jev=jev)
    c.backend = TaxonomyBackend()
    return c


def final_picking(index):
    return lambda schema: {**good_final(schema), "issue_category": enum_of(schema, "issue_category")[index]}


NETWORKING = dist("IC03", 0.62, "IC01", 0.20)      # Networking / Connectivity, with Identity / Authentication as the runner-up


class TestIntegration(unittest.TestCase):
    def test_1_the_hint_reaches_every_prompt_as_provisional_guidance_with_source_and_uncertainty(self):
        run, llm = triage_run(FakeTriageJev(NETWORKING))
        self.assertGreaterEqual(len(llm.requests), 4)
        for req in llm.requests:
            text = req["messages"][1]["content"]
            for must in ("EARLY TRIAGE HINT (provisional and unverified)", "Source: Jev early triage", "no tool, log, telemetry or graph evidence", "Networking",
                         "probability 0.62", "moderate uncertainty", "It is not evidence and cannot be cited", "reject or replace it"):
                self.assertIn(must, text)
            self.assertIn("Identity / Authentication (0.20)", text)                       # a competing category is named
            self.assertNotIn("confirmed category", text.lower())
        self.assertEqual(run["early_triage"]["status"], "hint")
        self.assertTrue(all(run["triage_hint_text"] in r["messages"][1]["content"] for r in llm.requests))     # the stored text is exactly what the agent saw

    def test_1b_only_plausible_competitors_are_listed_but_all_are_recorded(self):
        run, llm = triage_run(FakeTriageJev(dist("IC03", 0.90, "IC01", 0.03)))
        text = llm.requests[0]["messages"][1]["content"]
        self.assertNotIn("Other categories Jev considered", text)          # 0.03 is below the 0.05 floor, so there is no competitor to name
        self.assertIn("probability 0.90, low uncertainty", text)
        self.assertEqual(run["early_triage"]["alternatives"][0]["category_id"], "IC01")      # the record keeps the top list regardless

    def test_2_triage_runs_after_the_case_report_and_before_any_graph_tool(self):
        backend = TaxonomyBackend()
        jev = FakeTriageJev(NETWORKING, backend=backend)      # asserts inside the call that no tool has run yet
        run, _ = triage_run(jev, backend=backend)
        self.assertEqual(len(jev.calls), 1)
        self.assertGreater(len(backend.calls), 0)             # the investigation did run, afterwards
        self.assertEqual(run["trace_steps"][0]["tool_name"], "get_case_context")

    def test_3_the_hint_never_narrows_the_tools_or_the_answer_space(self):
        base_run, base_llm = plain_run()
        _, llm = triage_run(FakeTriageJev(NETWORKING))
        self.assertEqual(len(base_llm.requests), len(llm.requests))
        for a, b in zip(base_llm.requests, llm.requests):     # every schema handed to the model is identical: same tools, same category aliases, same evidence aliases
            self.assertEqual(json.dumps(a["schema"], sort_keys=True), json.dumps(b["schema"], sort_keys=True))
        final_schema = llm.requests[-1]["schema"]
        self.assertEqual(len(enum_of(final_schema, "issue_category")), 3)          # every taxonomy category stays selectable
        self.assertEqual([r["messages"][0] for r in base_llm.requests], [r["messages"][0] for r in llm.requests])   # the system prompt is untouched
        self.assertIn("get_telemetry (metric_category Networking)", llm.requests[0]["messages"][1]["content"])      # advisory tools are shown, none are forced

    def test_4_the_baseline_prompts_are_byte_identical_to_before_early_triage_existed(self):
        reg = ObservedEntityRegistry("CS00001")
        reg.add("CATEGORY", "IC01", display_name="Identity / Authentication", source_tool="taxonomy", step=0, clock="t")
        reg.add("CAUSE", "RC01", display_name="expired certificate", source_tool="taxonomy", step=0, clock="t")
        cr = {"title": "Login fails", "description": "cannot sign in"}
        hyps = [{"label": "x", "confidence": 0.4, "status": "active", "supporting_evidence": [], "contradicting_evidence": []}]
        a = prompts.step_messages(cr, reg, ["1. get_case_context() -> ok (harness)"], hyps, {"step": 1, "tool": "t", "result": {"a": 1}}, 2, "", "", 10)
        b = prompts.final_messages(cr, reg, ["1. x"], hyps, forced=False, feedback="")
        self.assertEqual(hashlib.sha256(json.dumps([a, b], sort_keys=True).encode()).hexdigest(), BASELINE_PROMPT_SHA256)
        base_run, _ = plain_run()
        for key in ("early_triage", "triage_outcome", "triage_hint_text"):
            self.assertNotIn(key, base_run)                    # a baseline record keeps its exact shape

    def test_5_the_triage_record_captures_prediction_uncertainty_latency_and_fallback_status(self):
        run, _ = triage_run(FakeTriageJev(NETWORKING))
        e = run["early_triage"]
        self.assertEqual((e["status"], e["fallback"], e["category_id"], e["category_name"], e["uncertainty"]), ("hint", False, "IC03", "Networking / Connectivity", "moderate"))
        self.assertAlmostEqual(e["probability"], 0.62, places=2)
        self.assertEqual((e["jev_model"], e["input_tokens"], e["role"]), ("jev-fake", 321, "triage_guidance"))
        self.assertGreaterEqual(e["latency_ms"], 0)
        self.assertEqual([a["category_id"] for a in e["alternatives"]][0], "IC01")
        self.assertIn("get_telemetry (metric_category Networking)", e["suggested_tools"])
        self.assertIn("triage_outcome", run)


class TestFallbacks(unittest.TestCase):
    """Test 3: abstention, low probability, invalid answers and Jev failures all continue with the unchanged workflow."""

    def check_fallback(self, jev, status, cfg=None, taxonomy_note=None):
        _, base_llm = plain_run()
        run, llm = triage_run(jev, cfg=cfg)
        e = run["early_triage"]
        self.assertEqual((e["status"], e["fallback"]), (status, True))
        self.assertTrue(e["fallback_reason"])
        self.assertIsNone(run["triage_hint_text"])
        self.assertEqual(user_messages(llm), user_messages(base_llm), "a fallback must leave every prompt identical to the unchanged workflow")
        self.assertEqual(run["final_status"], "DIAGNOSIS_PROPOSED")           # the investigation completed normally
        self.assertEqual(run["triage_outcome"]["outcome"], "no_suggestion")
        self.assertFalse(run["triage_outcome"]["hint_shown"])
        return e

    def test_abstention_is_a_fallback(self):
        e = self.check_fallback(FakeTriageJev(dist(ABSTAIN_KEY, 0.5)), "abstained")
        self.assertIsNone(e["category_id"])
        self.assertAlmostEqual(e["abstain_probability"], 0.5, places=2)

    def test_a_low_probability_answer_is_dropped_by_plain_code(self):
        e = self.check_fallback(FakeTriageJev(dist("IC03", 0.20, "IC01", 0.18)), "low_probability")
        self.assertIn("below", e["fallback_reason"])
        self.assertEqual(e["distribution_top"][0]["category_id"], "IC03")     # the distribution is still recorded for analysis
        self.check_fallback(FakeTriageJev(dist("IC03", 0.55)), "low_probability", cfg=TriageConfig(min_probability=0.60))      # the threshold is configurable

    def test_invalid_answers_are_rejected_not_repaired(self):
        options = list(all_issue_categories()) + [ABSTAIN_KEY]
        good = dist("IC03", 0.62, "IC01", 0.2)
        for label, answer in {"unknown choice": {"choice": "IC99", "confidence": 0.9, "probabilities": good},
                              "no table": {"choice": "IC03", "confidence": 0.9},
                              "not a distribution": {"choice": "IC03", "confidence": 0.9, "probabilities": {o: 0.5 for o in options}},
                              "choice is not the maximum": {"choice": "IC01", "confidence": 0.2, "probabilities": good},
                              "probability out of range": {"choice": "IC03", "confidence": 1.4, "probabilities": {**good, "IC03": 1.4}},
                              "not an object": "IC03"}.items():
            with self.subTest(label):
                self.check_fallback(FakeTriageJev(answer=answer), "invalid")

    def test_a_suggestion_outside_the_graph_taxonomy_is_not_shown(self):
        run, llm = triage_run(FakeTriageJev(dist("IC05", 0.7)))              # IC05 is a real category, but not one of the fake graph's three
        self.assertEqual((run["early_triage"]["status"], run["early_triage"]["fallback"]), ("invalid", True))
        self.assertIsNone(run["triage_hint_text"])
        self.assertFalse(any("EARLY TRIAGE" in m for msgs in user_messages(llm) for m in msgs))

    def test_jev_failure_timeout_and_missing_configuration_do_not_stop_the_investigation(self):
        self.check_fallback(FakeTriageJev(exc=RuntimeError("TypeSafe API error 500")), "error")
        self.check_fallback(FakeTriageJev(NETWORKING, delay=0.4), "timeout", cfg=TriageConfig(timeout_s=0.05))
        with mock.patch("agent.trace_eval_v2.jev_evaluator.get_client", side_effect=RuntimeError("TYPESAFE_API_KEY is not set")):
            _, base_llm = plain_run()
            backend, llm = TaxonomyBackend(), ScriptedLLM(CLEAN)
            run = loop.run_case(CASE, backend, llm, triage=T.EarlyTriage(None))
        self.assertEqual((run["early_triage"]["status"], run["final_status"]), ("unavailable", "DIAGNOSIS_PROPOSED"))
        self.assertEqual(user_messages(llm), user_messages(base_llm))

    def test_a_failure_costs_nothing_but_is_recorded(self):
        run, _ = triage_run(FakeTriageJev(exc=RuntimeError("boom")))
        self.assertEqual(run["early_triage"]["input_tokens"], 0)
        self.assertIn("RuntimeError", run["early_triage"]["error"])


class TestAgentIsFreeToRejectTheSuggestion(unittest.TestCase):
    """Test 4: a wrong initial category can be discovered and revised; confirmation and dropping are recorded distinctly."""

    def test_wrong_initial_category_is_changed_after_investigation(self):
        run, _ = triage_run(FakeTriageJev(NETWORKING), script=CLEAN[:-1] + [final_picking(0)])       # Jev says Networking; the agent's evidence leads it to Authentication
        o = run["triage_outcome"]
        self.assertEqual((o["outcome"], o["suggested_category"], o["final_category"]), ("changed", "Networking / Connectivity", "Identity / Authentication"))
        self.assertTrue(o["final_in_alternatives"])
        self.assertEqual(run["final_diagnosis"]["predicted_category_id"], "IC01")
        self.assertTrue(run["validation_result"]["final_ok"])          # the change went through the ordinary final-answer contract

    def test_a_kept_suggestion_is_recorded_as_confirmed(self):
        run, _ = triage_run(FakeTriageJev(NETWORKING), script=CLEAN[:-1] + [final_picking(2)])
        self.assertEqual((run["triage_outcome"]["outcome"], run["final_diagnosis"]["predicted_category_id"]), ("confirmed", "IC03"))

    def test_selecting_no_category_is_recorded_as_dropped(self):
        script = [action("get_customer_deployment"), action(SUBMIT), lambda schema: final_answer(schema)[0]]
        run, _ = triage_run(FakeTriageJev(NETWORKING), script=script)
        self.assertEqual((run["triage_outcome"]["outcome"], run["final_status"]), ("dropped", "INSUFFICIENT_EVIDENCE"))

    def test_the_agent_still_investigates_the_graph_and_cites_only_retrieved_evidence(self):
        run, _ = triage_run(FakeTriageJev(NETWORKING))
        tools = [s["tool_name"] for s in run["trace_steps"] if s["proposed_by"] == "model"]
        self.assertGreaterEqual(len(tools) - 1, 3)                     # model-chosen retrieval steps happened after the hint
        self.assertEqual(run["citation_violations"], [])
        self.assertTrue(run["evidence_ids_seen"])


class TestRolesAndPolicy(unittest.TestCase):
    """Test 1/5: early Jev = guidance, late Jev = verification; the plain-code policy still decides."""

    def verified(self, jev, script=None, **kw):
        with mock.patch.object(jev_checks, "build_packet", return_value={"packet_version": "test"}), mock.patch("agent.trace_eval_v2.guard.assert_request_clean"):
            return run_verified_case(CASE, None, ScriptedLLM(script or CLEAN), jev, backend=TaxonomyBackend(), **kw)

    def test_the_full_workflow_makes_both_jev_calls_and_records_them_apart(self):
        jev = FakeBoth(NETWORKING)
        rec = self.verified(jev, early_triage=True)
        self.assertEqual(len(jev.calls_early), 1)
        self.assertEqual(sorted(jev.calls_late), ["distractor_anchor", "human_review", "missed_evidence"])
        self.assertEqual((rec["early_triage_used"], rec["early_triage"]["status"]), (True, "hint"))
        self.assertIn(rec["triage_outcome"]["outcome"], ("confirmed", "changed"))
        self.assertEqual(rec["policy_decision"], ACCEPT)
        self.assertEqual(rec["jev_input_tokens"], 321 + 3 * 1000)     # early tokens are counted with the late ones
        self.assertEqual(rec["triage_outcome_initial"], rec["triage_outcome"])

    def test_without_early_triage_the_phase9_workflow_is_unchanged(self):
        jev = FakeBoth(NETWORKING)
        rec = self.verified(jev)
        self.assertEqual(jev.calls_early, [])
        self.assertEqual((rec["early_triage_used"], rec["early_triage"], rec["triage_outcome"]), (False, None, None))
        self.assertNotIn("triage_hint_text", rec["agent_run"])

    def test_the_policy_decides_and_ignores_the_early_suggestion(self):
        jev = FakeBoth(NETWORKING)
        jev.missed = 0.9                                              # late Jev says evidence was missed -> the plain-code policy continues, regardless of any hint
        rec = self.verified(jev, script=CLEAN + [action("get_active_incidents"), action(SUBMIT), good_final], early_triage=True)
        self.assertEqual(rec["policy_decision"], CONTINUE)
        self.assertTrue(rec["additional_investigation_performed"])
        self.assertIsNotNone(rec["triage_outcome_initial"])           # the outcome of the FIRST answer is kept apart from the final one
        for fallback in (FakeBoth(dist(ABSTAIN_KEY, 0.5)), FakeBoth(exc=RuntimeError("down"))):
            self.assertEqual(self.verified(fallback, early_triage=True)["policy_decision"], ACCEPT)     # a triage fallback never blocks or alters the decision

    def test_the_late_verifier_packet_never_contains_the_early_hint(self):
        from agent.trace_eval_v2 import trace_projection
        seen = {}

        def real_packet(session, run, case_id):
            from agent.trace_eval_v2.trace_loader import load_trace
            ctx = {"ticket": {"title": "t"}, "inventory": [], "telemetry_categories_with_data": [], "as_of": run["sim_clock_end"]}
            state, _ = trace_projection.project(load_trace({**run, "run_id": "runtime_x", "model_name": "m"}), ctx, alias_salt="runtime")
            seen["packet"] = json.dumps(state)
            return state

        jev = FakeBoth(NETWORKING)
        with mock.patch.object(jev_checks, "build_packet", side_effect=real_packet), mock.patch("agent.trace_eval_v2.guard.assert_request_clean"):
            rec = run_verified_case(CASE, None, ScriptedLLM(CLEAN), jev, backend=TaxonomyBackend(), early_triage=True)
        self.assertEqual(rec["early_triage"]["status"], "hint")
        self.assertTrue(rec["agent_run"]["triage_hint_text"])
        for marker in ("EARLY TRIAGE", "Jev early triage", "triage_hint", "early_triage", "provisional and unverified", "Networking / Connectivity"):
            self.assertNotIn(marker, seen["packet"], marker)


class TestComparisonModes(unittest.TestCase):
    """Test 6: the mode boundaries. LLM Only touches neither Jev nor the graph; LLM + Graph is the unchanged baseline; LLM + Graph + Jev has both Jev roles."""

    def run_mode(self, mode, jev, script):
        return ctx_for(script, jev).run(mode)

    def test_llm_only_never_calls_jev_or_the_graph(self):
        jev = FakeBoth(NETWORKING)
        ctx = Ctx([llm_only_answer], jev=jev)
        r = ctx.run(MODE_LLM)
        self.assertEqual((jev.calls_early, jev.calls_late, ctx.backend.calls), ([], [], []))
        self.assertEqual((r.jev_used, r.graph_used, r.triage), (False, False, None))

    def test_llm_plus_graph_is_the_unchanged_baseline(self):
        jev = FakeBoth(NETWORKING)
        r = self.run_mode(MODE_GRAPH, jev, CLEAN)
        self.assertEqual((jev.calls_early, jev.calls_late), ([], []))
        self.assertEqual((r.jev_used, r.triage), (False, None))
        self.assertNotIn("early_triage", r.raw)
        self.assertNotIn("triage_hint_text", r.raw)

    def test_llm_plus_graph_plus_jev_has_early_triage_and_late_verification(self):
        jev = FakeBoth(NETWORKING)
        r = self.run_mode(MODE_FULL, jev, CLEAN)
        self.assertEqual((len(jev.calls_early), len(jev.calls_late)), (1, 3))
        self.assertTrue(r.jev_used and r.graph_used)
        self.assertEqual(r.triage["status"], "hint")
        self.assertEqual(r.verification["final_decision"], ACCEPT)
        self.assertGreaterEqual(r.latency_seconds, r.triage["latency_ms"] / 1000)


class TestHiddenTruthIsolation(unittest.TestCase):
    """Test 7: hidden ground truth cannot reach the early Jev call."""

    def test_the_import_closure_reads_no_hidden_truth_or_scoring_module(self):
        files = [vb.ROOT / "agent" / "early_triage" / f"{m}.py" for m in ("triage", "config", "priorities")] + [vb.ROOT / "agent" / "agent_v3" / "triage_hint.py"]
        closure = {".".join(f.relative_to(vb.ROOT).with_suffix("").parts).replace(".__init__", "") for f in vb.import_closure(files)}
        allowed = {"agent.eval_v2.config", "agent.jev_v2.client", "agent.jev_v2.config", "agent.jev_v2.reference_data", "agent.trace_eval_v2", "agent.trace_eval_v2.config",
                   "agent.trace_eval_v2.guard", "agent.trace_eval_v2.jev_evaluator", "agent.trace_eval_v2.models", "agent.trace_eval_v2.questions"}
        outside = sorted(m for m in closure if m.split(".")[1] in ("eval_v2", "trace_eval_v2", "jev_v2") and m not in allowed)
        self.assertEqual(outside, [], f"evaluation-side module in the early-triage closure: {outside}")
        self.assertFalse([m for m in closure if m.startswith("data.eval")])
        text = "".join(f.read_text() for f in files)
        for word in ("gt_", "get_hidden_truth", "eval_store", "ground_truth", "evaluate_run", "outcome_label", "locked_benchmark", "case_splits", "phase6"):
            self.assertNotIn(word, text, word)

    def test_only_allow_listed_ticket_fields_are_sent_even_if_the_context_is_poisoned(self):
        ctx = FakeBackend().case_context()
        poison = {"gt_root_cause_id": "ZQ-RC-42", "gt_issue_category_id": "ZQ-IC-17", "causal_change_id": "ZQ-CH-999", "escalation_warranted": "ZQ-yes", "critical_evidence_ids": "ZQ-SG-1",
                  "expected_confidence_band": "ZQ-high", "diagnosis_matches_truth": "ZQ-true"}
        jev = FakeTriageJev(NETWORKING)
        T.EarlyTriage(jev)({**ctx, **poison})
        sent = json.dumps(jev.calls[0])
        for k, v in poison.items():
            self.assertNotIn(k, sent)
            self.assertNotIn(str(v), sent)
        for private in (ctx["case_id"], ctx["customer_id"], ctx["created_date"], '"status"', "reported_product_id"):
            self.assertNotIn(private, sent)
        self.assertEqual(set(jev.calls[0]["state"]), {"ticket", "customer", "reported_product"})
        self.assertEqual(set(jev.calls[0]["state"]["ticket"]), set(T.TICKET_FIELDS))
        assert_no_leakage({"state": jev.calls[0]["state"], "questions": jev.calls[0]["questions"]})     # the existing Phase 7 guard accepts the real payload

    def test_the_leakage_guard_is_reused_and_a_trip_is_never_suppressed(self):
        ctx = PoisonedBackend().case_context()
        client = JevClient(api_key="test-key")
        with mock.patch.object(JevClient, "_post_with_retry", side_effect=AssertionError("the request must not leave the process")) as post:
            with self.assertRaises(LeakageGuardError):
                T.EarlyTriage(client)(ctx)
            post.assert_not_called()
            with self.assertRaises(LeakageGuardError):                    # and through the whole agent loop: the run stops, it does not degrade to a fallback
                loop.run_case(CASE, PoisonedBackend(), ScriptedLLM(CLEAN), triage=T.EarlyTriage(client))

    def test_no_hidden_truth_reader_is_called_during_a_full_run(self):
        boom = mock.Mock(side_effect=AssertionError("hidden truth was read during an early-triage run"))
        from data.eval import eval_store
        with mock.patch.object(eval_store, "get_hidden_truth", boom, create=True), mock.patch("agent.eval_v2.ground_truth.get_hidden_truth", boom):
            run, _ = triage_run(FakeTriageJev(NETWORKING))
        boom.assert_not_called()
        self.assertEqual(run["early_triage"]["status"], "hint")

    def test_the_question_wording_and_options_carry_no_label(self):
        q = T.build_question()
        self.assertEqual(set(q["criteria"]), set(all_issue_categories()) | {ABSTAIN_KEY})
        assert_no_leakage({"state": {}, "questions": {T.KEY: q}})
        blob = json.dumps(q).lower()
        for banned in ("ground truth", "correct answer", "label", "hidden"):
            self.assertNotIn(banned, blob)

    def test_the_suggested_tools_come_from_the_real_catalog_and_filter_nothing(self):
        for cat in all_issue_categories():
            for s in priorities.suggest(cat):
                self.assertIn(s.split(" ")[0], __import__("agent.agent_v3.catalog", fromlist=["TOOLS_BY_NAME"]).TOOLS_BY_NAME)
        self.assertEqual(priorities.suggest("IC18"), [])               # Unknown / Other: nothing to prioritise


class TestEvaluationIsOfflineAndArithmeticIsRight(unittest.TestCase):
    def test_no_runtime_module_can_import_the_evaluation_or_the_batch_runner(self):
        files = [vb.ROOT / "agent" / "runtime_verifier" / "run.py", vb.ROOT / "agent" / "compare" / "orchestrator.py", vb.ROOT / "agent" / "agent_v3" / "loop.py",
                 vb.ROOT / "agent" / "early_triage" / "triage.py"]
        closure = {".".join(f.relative_to(vb.ROOT).with_suffix("").parts).replace(".__init__", "") for f in vb.import_closure(files)}
        for banned in ("agent.early_triage.evaluation", "agent.early_triage.run_dev", "agent.compare.evaluation", "agent.eval_v2.ground_truth", "data.eval.eval_store"):
            self.assertNotIn(banned, closure, banned)

    @staticmethod
    def row(truth="IC03", hint=None, p=0.6, base="wrong", init="wrong", final="wrong", init_cat=None, base_cat=None, outcome="no_suggestion"):
        ev = {"total": 2, "retrieved": 1, "all": False, "seen": 5}
        return {"case_id": "X", "truth": truth, "jev_status": "hint" if hint else "abstained", "jev_hint": hint, "jev_top": hint, "jev_p": p if hint else None,
                "jev_hint_verdict": (None if not hint else "correct" if hint == truth else "wrong"), "jev_top_verdict": None if not hint else ("correct" if hint == truth else "wrong"),
                "jev_latency_s": 0.2, "jev_tokens": 900, "outcome": outcome, "base_cat": base_cat, "base": base, "init_cat": init_cat, "init": init, "final_cat": init_cat, "final": final,
                "ev_base": ev, "ev_init": ev, "ev_final": ev, "tools_base": 8, "tools_init": 8, "tools_final": 8, "tokens_base": 1000, "tokens_new": 1200, "jev_input_tokens_total": 3900,
                "model_s_base": 10.0, "model_s_new": 12.0, "verifier_s": 5.0, "cost_base": 0.02, "cost_new": 0.03, "extra_round": False, "first_decision": "ACCEPT", "final_decision": "ACCEPT",
                "base_status": "DIAGNOSIS_PROPOSED", "base_review_flag": False, "new_status": "DIAGNOSIS_PROPOSED", "contract_failure": False}

    def test_verdict_and_the_exact_mcnemar(self):
        from agent.early_triage import evaluation as E
        self.assertEqual([E.verdict(None, "IC01"), E.verdict("IC01", "IC01"), E.verdict("IC02", "IC01")], ["abstain", "correct", "wrong"])
        self.assertEqual(E.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(E.mcnemar_exact(5, 0), 0.0625)          # 2 * (1/32)
        self.assertAlmostEqual(E.mcnemar_exact(3, 3), 1.0)
        self.assertAlmostEqual(E.mcnemar_exact(10, 1), 2 * (1 + 11) / 2 ** 11)      # n = 11 discordant pairs, k = 1

    def test_hint_conditioned_counts(self):
        from agent.early_triage import evaluation as E
        R = self.row
        rows = [R(hint="IC03", init="correct", init_cat="IC03", outcome="confirmed", base="wrong"),                      # right hint, kept; baseline missed it
                R(hint="IC03", init="wrong", init_cat="IC01", outcome="changed", base="correct", base_cat="IC03"),       # right hint, agent moved away; baseline had it
                R(hint="IC01", init="wrong", init_cat="IC01", outcome="confirmed", base="wrong", base_cat="IC01"),       # wrong hint adopted (baseline made the same mistake)
                R(hint="IC01", init="correct", init_cat="IC03", outcome="changed", base="wrong", base_cat="IC02"),       # wrong hint corrected by the evidence
                R(hint=None)]                                                                                             # abstained: no hint
        a = E.aggregate(rows)
        self.assertEqual(a["jev_early"]["hint_coverage"], {"k": 4, "n": 5})
        self.assertEqual((a["jev_early"]["accuracy_when_hint_given"]["correct"], a["jev_early"]["accuracy_when_hint_given"]["n"]), (2, 4))
        h = a["what_the_agent_did_with_the_hint"]
        self.assertEqual((h["hint_correct"]["n"], h["hint_correct"]["confirmed"], h["hint_correct"]["changed_away"], h["hint_correct"]["baseline_correct_on_same_cases"]), (2, 1, 1, 1))
        self.assertEqual((h["hint_wrong"]["n"], h["hint_wrong"]["adopted_the_wrong_hint"], h["hint_wrong"]["changed_to_the_true_category"],
                          h["hint_wrong"]["baseline_also_chose_that_wrong_category"]), (2, 1, 1, 1))
        pr = a["paired_baseline_vs_early"]
        self.assertEqual((pr["only_early_correct"], pr["only_baseline_correct"], pr["both_correct"]), (2, 1, 0))
        self.assertEqual(sum(pr[k] for k in ("both_correct", "only_early_correct", "only_baseline_correct", "neither")), 5)      # the four cells partition the cases


class TestWithTheRealGraph(unittest.TestCase):
    """Reads one real dev case's context from Neo4j; skipped when the graph is unreachable."""

    @classmethod
    def setUpClass(cls):
        try:
            from agent.graph_v2.db import get_driver
            cls.driver = get_driver()
            cls.driver.verify_connectivity()
        except Exception as e:  # noqa: BLE001
            raise unittest.SkipTest(f"graph unreachable: {str(e)[:80]}")

    @classmethod
    def tearDownClass(cls):
        cls.driver.close()

    def test_a_real_case_context_projects_to_a_clean_request(self):
        import json as _json
        case_id = sorted(_json.loads((vb.ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"])[0]
        from agent.agent_v3.backend import Neo4jBackend
        from data.eval import eval_store
        boom = mock.Mock(side_effect=AssertionError("hidden truth was read"))
        jev = FakeTriageJev(NETWORKING)
        with self.driver.session() as s, mock.patch.object(eval_store, "get_hidden_truth", boom, create=True):
            ctx = Neo4jBackend(s, case_id).case_context()
            T.EarlyTriage(jev)(ctx)
        sent = json.dumps(jev.calls[0])
        self.assertNotIn(case_id, sent)
        self.assertNotIn("gt_", sent)
        assert_no_leakage({"state": jev.calls[0]["state"], "questions": jev.calls[0]["questions"]})
        boom.assert_not_called()


class TestPage(unittest.TestCase):
    """The Diagnostic Agent page shows the early suggestion as provisional guidance, apart from late verification, for a run with, without and before early triage."""

    def app(self, full_result, option="LLM + Graph + Jev"):
        from streamlit.testing.v1 import AppTest
        case = "CS00729"
        loader = lambda mode, cid: full_result if mode == MODE_FULL else None
        empty_aggregate = {"n": 0, "cases": [], "rows": [], "note": "stubbed"}
        with mock.patch.object(adapters, "load_stored", side_effect=loader), mock.patch.object(adapters, "available", return_value={MODE_LLM: False, MODE_GRAPH: False, MODE_FULL: True}), \
                mock.patch("agent.compare.aggregate.aggregate", return_value=empty_aggregate):
            at = AppTest.from_file("pages/1_Diagnostic_Agent.py", default_timeout=120).run()
            at.selectbox[0].select(case).run()
            at.radio[0].set_value(option).run()
        return at

    def texts(self, at):
        return " ".join([str(m.value) for m in at.markdown] + [str(c.value) for c in at.caption] + [str(m.value) for m in at.metric] + [str(c.value) for c in at.code])

    def test_hint_given_and_agent_changed_it(self):
        full = ctx_for(CLEAN[:-1] + [final_picking(0)], FakeBoth(NETWORKING)).run(MODE_FULL)
        at = self.app(full, "Compare All")
        self.assertEqual(list(at.exception), [])
        t = self.texts(at)
        for must in ("Early Jev (triage guidance)", "Provisional suggestion, not a diagnosis", "Networking / Connectivity", "Late Jev (verification)", "Early Jev — triage guidance",
                     "Late Jev — answer verification", "EARLY TRIAGE HINT (provisional and unverified)"):
            self.assertIn(must, t)
        early_line = next(str(m.value) for m in at.markdown if "Early Jev (triage guidance)" in str(m.value) and "💡" in str(m.value))
        self.assertNotIn("diagnosis", early_line.lower())              # the suggestion is labelled as guidance, never as a diagnosis or a verified result

    def test_fallback_and_pre_triage_runs_render_without_presenting_a_suggestion(self):
        fallback = ctx_for(CLEAN, FakeBoth(dist(ABSTAIN_KEY, 0.5))).run(MODE_FULL)
        t = self.texts(self.app(fallback))
        self.assertIn("no suggestion (Jev abstained)", t)
        self.assertIn("without a hint", t)
        old = ctx_for(CLEAN, FakeBoth(NETWORKING)).run(MODE_FULL)
        old.triage = None          # a stored run that predates early triage carries no triage record
        at = self.app(old)
        self.assertEqual(list(at.exception), [])
        self.assertIn("predates early triage", self.texts(at))

    def test_comparison_rows_and_labels_describe_the_actual_behaviour(self):
        from agent.compare.models import FLOW
        self.assertIn("Early Jev triage (guidance)", FLOW[MODE_FULL])
        self.assertIn("Late Jev verifier (verification)", FLOW[MODE_FULL])
        self.assertNotIn("Jev", FLOW[MODE_GRAPH])
        self.assertNotIn("Jev", FLOW[MODE_LLM])
        full = ctx_for(CLEAN, FakeBoth(NETWORKING)).run(MODE_FULL)
        rows = {r["Metric"]: r for r in insights.comparison_rows({MODE_FULL: full})}
        self.assertIn("Networking / Connectivity", rows["Early Jev suggestion (provisional)"]["LLM + Graph + Jev"])
        self.assertEqual(rows["Early Jev suggestion (provisional)"].get("LLM + Graph"), "not available")
        imp = insights.impact({MODE_FULL: full})
        self.assertTrue(imp["jev_early"] and imp["jev"])


if __name__ == "__main__":
    unittest.main()
