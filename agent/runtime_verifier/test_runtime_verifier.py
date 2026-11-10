"""Offline tests for the Phase 9 runtime verifier (no API call, no graph call except the one boundary test that reads a stored dev run).
Run with: python3 -m unittest agent.runtime_verifier.test_runtime_verifier

The scripted agent and a fake Jev client stand in for the two network services, so the deterministic checks, the policy and the one-retry loop are tested exactly."""
import copy
import json
import unittest
from unittest import mock

from agent.agent_v3.catalog import SUBMIT
from agent.agent_v3.loop import run_case
from agent.agent_v3.test_agent_v3 import CASE, FakeBackend, ScriptedLLM, action, final_answer, good_final
from agent.runtime_verifier import deterministic_checks as D
from agent.runtime_verifier import jev_checks
from agent.runtime_verifier.models import ACCEPT, CONTINUE, HUMAN_REVIEW, PRIORITY_REVIEW, VerifierConfig
from agent.runtime_verifier.verifier import RuntimeVerifier


class FakeJev:
    """Stands in for the Jev HTTP client: typed answers only, configurable, and records how often it is called."""
    def __init__(self, missed=0.1, distractor=0.1, review=(0.8, 0.15, 0.05)):
        self.missed, self.distractor, self.review, self.calls = missed, distractor, review, []

    def judge(self, state, question, key):
        self.calls.append(key)
        if key == "missed_evidence":
            ans = {"noul": self.missed}
        elif key == "distractor_anchor":
            ans = {"noul": self.distractor}
        else:
            probs = dict(zip(("AUTO_CLOSE", "HUMAN_REVIEW", "PRIORITY_REVIEW"), self.review))
            ans = {"choice": max(probs, key=probs.get), "confidence": max(probs.values()), "probabilities": probs}
        return {"model": "jev-fake", "answers": {key: ans}, "usage": {"input_tokens": 1000}}


def verified_run(script, jev, cfg=None):
    """Runs the scripted agent under the real loop with the real RuntimeVerifier; only the packet build (graph) and Jev transport are faked."""
    cfg = cfg or VerifierConfig()
    v = RuntimeVerifier(session=None, case_id=CASE, jev_client=jev, config=cfg)
    llm = ScriptedLLM(script)
    with mock.patch.object(jev_checks, "build_packet", return_value={"packet_version": "test"}), mock.patch("agent.trace_eval_v2.guard.assert_request_clean"):
        return run_case(CASE, FakeBackend(), llm, verifier=v, extra_steps=cfg.extra_steps), llm


CLEAN = [action("get_customer_deployment"), action("get_technical_signals"), action("get_recent_changes"), action(SUBMIT), good_final]


def clean_final_with(**over):
    def f(schema):
        obj = good_final(schema)
        obj.update(over)
        return obj
    return f


class TestPolicyAndFlow(unittest.TestCase):
    def test_1_valid_agent_result_reaches_the_verifier(self):
        jev = FakeJev()
        run, _ = verified_run(CLEAN, jev)
        self.assertEqual(len(run["verification_rounds"]), 1)
        r = run["verification_rounds"][0]
        self.assertEqual(sorted(jev.calls), ["distractor_anchor", "human_review", "missed_evidence"])  # three Jev signals, on the same packet
        self.assertTrue(r["deterministic_checks"]["D1"]["passed"])
        self.assertIsNotNone(r["jev"]["missed_evidence_probability"])
        self.assertFalse(run["additional_investigation_performed"])

    def test_6_clean_result_is_accepted(self):
        run, _ = verified_run(CLEAN, FakeJev())
        r = run["verification_rounds"][0]
        self.assertEqual((r["decision"], r["triggers"]), (ACCEPT, []), r)
        self.assertTrue(r["deterministic_checks"]["all_passed"])

    def test_2_invalid_evidence_id_is_rejected_deterministically_and_jev_is_not_called(self):
        run, _ = verified_run(CLEAN, FakeJev())
        forged = copy.deepcopy(run)
        forged["final_alias_form"]["evidence_ids"] = forged["final_alias_form"]["evidence_ids"] + ["EVIDENCE_QQQ"]
        det = D.run_all(forged, VerifierConfig())
        self.assertFalse(det["D1"]["passed"])
        self.assertIn("EVIDENCE_QQQ", det["D1"]["detail"])
        jev = FakeJev()
        with mock.patch.object(jev_checks, "build_packet", return_value={}):
            verdict = RuntimeVerifier(None, CASE, jev)(forged, 1)
        self.assertEqual((verdict["decision"], verdict["triggers"]), (HUMAN_REVIEW, ["D1"]))
        self.assertEqual(jev.calls, [])  # a malformed answer is never sent to Jev
        # an alias observed only after the final answer is also "not retrieved before"
        late = copy.deepcopy(run)
        alias = late["final_alias_form"]["evidence_ids"][0]
        late["alias_mappings"][alias]["first_observed_step"] = 99
        self.assertFalse(D.d1_valid_contract(late)["passed"])

    def test_3_high_jev_missed_evidence_continues_and_the_agent_resumes(self):
        script = CLEAN + [action("get_active_incidents"), action(SUBMIT), good_final]
        run, llm = verified_run(script, FakeJev(missed=0.9))
        r1, r2 = run["verification_rounds"]
        self.assertEqual(r1["decision"], CONTINUE)
        self.assertIn("jev_missed_evidence", r1["triggers"])
        self.assertTrue(run["additional_investigation_performed"])
        self.assertIn("VERIFICATION FEEDBACK", llm.requests[5]["messages"][1]["content"])      # the resumed turn carried the verifier's message
        self.assertIn("possible missed evidence", llm.requests[5]["messages"][1]["content"])
        self.assertIn("get_incidents" if False else "get_active_incidents", r1["message"])   # names tools not yet used
        tools = [s["tool_name"] for s in run["trace_steps"]]
        self.assertIn("get_active_incidents", tools)                                            # the additional round really investigated
        self.assertEqual(tools.count(SUBMIT), 1)                                                # the round-1 submit step was replaced, not duplicated
        self.assertIsNotNone(run["initial_result"])
        self.assertEqual(r2["round"], 2)

    def test_4_high_jev_distractor_risk_continues(self):
        run, _ = verified_run(CLEAN + [action("get_active_incidents"), action(SUBMIT), good_final], FakeJev(distractor=0.8))
        r1 = run["verification_rounds"][0]
        self.assertEqual((r1["decision"], r1["triggers"]), (CONTINUE, ["jev_distractor_anchor"]))
        self.assertIn("anchoring", r1["message"])

    def test_5_low_agent_confidence_goes_to_human_review(self):
        run, _ = verified_run(CLEAN[:-1] + [clean_final_with(confidence=0.4)], FakeJev())
        r = run["verification_rounds"][0]
        self.assertEqual((r["decision"], r["triggers"]), (HUMAN_REVIEW, ["low_confidence"]))
        self.assertEqual(len(run["verification_rounds"]), 1)

    def test_7_second_verification_still_failing_ends_in_human_review(self):
        script = CLEAN + [action("get_active_incidents"), action(SUBMIT), good_final]
        run, _ = verified_run(script, FakeJev(missed=0.95))
        self.assertEqual([r["decision"] for r in run["verification_rounds"]], [CONTINUE, HUMAN_REVIEW])
        self.assertIn("still unresolved", run["verification_rounds"][1]["reason"])
        self.assertEqual(len(run["verification_rounds"]), 2)  # never more than two passes, never a third investigation round

    def test_priority_review_signal(self):
        run, _ = verified_run(CLEAN, FakeJev(review=(0.05, 0.25, 0.7)))
        self.assertEqual(run["verification_rounds"][0]["decision"], PRIORITY_REVIEW)

    def test_premature_finalization_continues_then_reviews(self):
        script = [action("get_customer_deployment"), action(SUBMIT), lambda s: final_answer(s)[0], action("get_technical_signals"), action(SUBMIT), lambda s: final_answer(s)[0]]
        run, _ = verified_run(script, FakeJev())
        r1, r2 = run["verification_rounds"]
        self.assertEqual((r1["decision"], "D4" in r1["triggers"]), (CONTINUE, True))          # no evidence + budget left: keep investigating
        self.assertEqual(r2["decision"], HUMAN_REVIEW)                                         # abstained again: a person looks

    def test_agent_that_abstains_after_using_its_budget_is_reviewed_not_accepted(self):
        script = ([action("get_customer_deployment"), action("get_technical_signals"), action("get_recent_changes"), action("get_active_incidents"), action("get_similar_cases"),
                   action("search_knowledge_base", keyword="tls"), action("get_telemetry"), action("get_telemetry", metric_category="Networking"),
                   action("get_telemetry", metric_category="Identity"), lambda s: final_answer(s)[0]])
        run, _ = verified_run(script, FakeJev())
        r = run["verification_rounds"][0]
        self.assertEqual(r["decision"], HUMAN_REVIEW)          # budget used: not premature; the agent itself asked for review
        self.assertIn("agent_requested_review", r["triggers"])

    def test_jev_unavailable_never_auto_accepts(self):
        class Down(FakeJev):
            def judge(self, state, question, key):
                raise RuntimeError("network down")
        run, _ = verified_run(CLEAN, Down())
        r = run["verification_rounds"][0]
        self.assertEqual((r["decision"], r["triggers"]), (HUMAN_REVIEW, ["jev_unavailable"]))
        cfg = VerifierConfig(require_jev_to_accept=False)
        run2, _ = verified_run(CLEAN, Down(), cfg)
        self.assertEqual(run2["verification_rounds"][0]["decision"], ACCEPT)   # configurable

    def test_no_verifier_means_the_unchanged_agent_loop(self):
        llm = ScriptedLLM(CLEAN)
        run = run_case(CASE, FakeBackend(), llm)
        self.assertEqual((run["verification_rounds"], run["initial_result"], run["additional_investigation_performed"]), ([], None, False))
        self.assertEqual(run["final_status"], "DIAGNOSIS_PROPOSED")

    def test_thresholds_are_configurable(self):
        run, _ = verified_run(CLEAN + [action("get_active_incidents"), action(SUBMIT), good_final], FakeJev(missed=0.6), VerifierConfig(missed_evidence_threshold=0.5))
        self.assertEqual(run["verification_rounds"][0]["decision"], ACCEPT if False else CONTINUE)   # 0.6 >= the configured 0.5
        run2, _ = verified_run(CLEAN, FakeJev(missed=0.6))                                             # the default 0.75 does not trigger
        self.assertEqual(run2["verification_rounds"][0]["decision"], ACCEPT)


class TestDeterministicChecks(unittest.TestCase):
    def setUp(self):
        self.run, _ = verified_run(CLEAN, FakeJev())

    def test_d2_and_d3_and_d4_on_a_clean_run(self):
        cfg = VerifierConfig()
        self.assertTrue(D.d2_evidence_support(self.run)["passed"])
        self.assertTrue(D.d3_final_consistency(self.run)["passed"])
        self.assertTrue(D.d4_premature_finalization(self.run, cfg)["passed"])

    def test_d2_fails_for_a_proposal_that_cites_nothing(self):
        r = copy.deepcopy(self.run)
        r["final_alias_form"]["evidence_ids"] = []
        r["final_alias_form"]["hypotheses"][0]["supporting_evidence"] = []
        self.assertFalse(D.d2_evidence_support(r)["passed"])

    def test_d3_flags_overconfidence_and_an_unfounded_top_hypothesis(self):
        r = copy.deepcopy(self.run)
        r["final_alias_form"]["confidence"] = 0.98
        r["final_alias_form"]["hypotheses"][0]["confidence"] = 0.5
        self.assertFalse(D.d3_final_consistency(r)["passed"])
        r = copy.deepcopy(self.run)
        r["final_alias_form"]["hypotheses"][0]["label"] = "quantum flux misalignment"
        self.assertFalse(D.d3_final_consistency(r)["passed"])
        r["final_alias_form"]["hypotheses"][0]["label"] = "certificate expiry"   # "certificate" appears in the retrieved change: a revision, not a contradiction
        self.assertTrue(D.d3_final_consistency(r)["passed"])

    def test_d4_no_evidence_is_premature_and_a_spent_budget_is_not(self):
        r = copy.deepcopy(self.run)
        r["evidence_ids_seen"] = []
        self.assertFalse(D.d4_premature_finalization(r, VerifierConfig())["passed"])
        r = copy.deepcopy(self.run)
        r["final_alias_form"]["hypotheses"][0]["supporting_evidence"] = []
        r["num_tool_calls"], r["tool_budget"] = 11, 10
        self.assertTrue(D.d4_premature_finalization(r, VerifierConfig())["passed"])
        r["num_tool_calls"] = 4
        self.assertFalse(D.d4_premature_finalization(r, VerifierConfig())["passed"])


class TestBoundaries(unittest.TestCase):
    """Test 8: no hidden truth enters the runtime verifier."""

    def test_8a_the_verifier_import_closure_holds_no_hidden_truth_or_scoring_module(self):
        from agent.agent_v3 import validate_boundaries as vb
        files = [vb.ROOT / "agent" / "runtime_verifier" / f"{m}.py" for m in ("verifier", "deterministic_checks", "jev_checks", "policy", "models", "run")]
        closure = {".".join(f.relative_to(vb.ROOT).with_suffix("").parts).replace(".__init__", "") for f in vb.import_closure(files)}
        # explicit allow-list for the three evaluation-adjacent packages; everything else (agent_v2/agent_v3/graph_v2/runtime_verifier) is agent-side
        allowed = {"agent.eval_v2", "agent.eval_v2.config", "agent.eval_v2.contract",                                           # a pure error-string classifier
                   "agent.trace_eval_v2", "agent.trace_eval_v2.config", "agent.trace_eval_v2.guard", "agent.trace_eval_v2.jev_evaluator", "agent.trace_eval_v2.models",
                   "agent.trace_eval_v2.questions", "agent.trace_eval_v2.trace_loader", "agent.trace_eval_v2.trace_projection",  # Phase 8's model-facing modules
                   "agent.jev_v2.client", "agent.jev_v2.config",                                                                   # the direct-HTTP Jev client
                   "agent.jev_v2.reference_data"}                                                                                  # observable taxonomy tables (early triage's option list)
        outside = sorted(m for m in closure if m.split(".")[1] in ("eval_v2", "trace_eval_v2", "jev_v2") and m not in allowed)
        self.assertEqual(outside, [], f"evaluation-side module in the verifier's import closure: {outside}")
        self.assertFalse([m for m in closure if m.startswith("data.eval")], "a data.eval module is in the closure")
        text = "".join(f.read_text() for f in files)
        for word in ("gt_", "get_hidden_truth", "eval_store", "evaluate_run", "outcome_label", "locked_benchmark", "case_splits"):
            self.assertFalse(word in text, word)

    def test_8b_a_real_packet_contains_no_hidden_field_and_passes_the_leakage_guard(self):
        import glob
        from agent.graph_v2.db import get_driver
        from agent.trace_eval_v2 import guard, questions
        from data.eval import eval_store

        run_path = sorted(glob.glob("data/agent_runs_v3/run_*.json"))[0]
        run = json.load(open(run_path))
        run["sim_clock_end"] = run["trace_steps"][-1]["sim_clock"]
        boom = mock.Mock(side_effect=AssertionError("hidden truth was read while building the verifier input"))
        drv = get_driver()
        try:
            with mock.patch.object(eval_store, "get_hidden_truth", boom, create=True), mock.patch("agent.eval_v2.ground_truth.get_hidden_truth", boom):
                with drv.session() as s:
                    packet = jev_checks.build_packet(s, run, run["case_id"])
        finally:
            drv.close()
        boom.assert_not_called()
        for judgment in ("missed_evidence", "distractor_anchor", "human_review"):
            guard.assert_request_clean(packet, questions.jev_question(judgment))          # raises LeakageError on any hidden field, marker or canonical id
        text = json.dumps(packet)
        for marker in ("gt_", "ground_truth", "critical_evidence_ids", "distractor_signal_ids", "irrelevant_change_ids", "causal_signal_ids", "expected_confidence_band",
                       "escalation_warranted", "actual_root_cause_name"):
            self.assertFalse(marker in text, f"hidden-field marker {marker!r} found in the packet")
        self.assertFalse(run["case_id"] in text, "the case id itself must be aliased away")


if __name__ == "__main__":
    unittest.main()
