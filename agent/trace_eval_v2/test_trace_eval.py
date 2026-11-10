"""Offline tests for Phase 8 (no API call, no graph call). Run with: python3 -m unittest agent.trace_eval_v2.test_trace_eval"""
import copy
import json
import re
import unittest
from unittest import mock

from agent.trace_eval_v2 import guard, labels as L, metrics as M, perturbations as P, questions, scorer
from agent.trace_eval_v2.config import JUDGMENTS
from agent.trace_eval_v2.models import ID_RE, Step, Trace, id_kind
from agent.trace_eval_v2.trace_projection import Aliaser, project, state_json


# ── builders ──────────────────────────────────────────────────────────────────────────
def step(n, tool, evidence=(), hyps=(), status="ok", result=None, args=None, error_kind=None, redundant=False):
    rows = [{"evidence_id": e, **({"signal_type": "API_VERSION_MISMATCH", "message": "API version mismatch detected on Webhook Dispatch Service"} if e.startswith("SG") else
                                  {"change_type": "credential_rotation"} if e == "CH000002" else {"change_type": "api_contract_change"})} for e in evidence]
    return Step(n=n, clock=f"2026-01-01 00:{15 * (n - 1):02d}:00", tool=tool, args=args or {}, hypotheses=[{"label": l, "confidence": c} for l, c in hyps], status=status,
                redundant=redundant, result=result if result is not None else {"signals": rows, "count": len(rows)}, evidence=list(evidence), error_kind=error_kind)


def final(top="api_contract_change", conf=0.8, cited=(), review=False, suff="partial", extra=None, overall=None):
    f = {"hypotheses": [{"label": top, "description": "", "confidence": conf, "status": "confirmed", "supporting_evidence": list(cited), "contradicting_evidence": []},
                        {"label": "other_issue", "description": "", "confidence": 0.1, "status": "rejected", "supporting_evidence": [], "contradicting_evidence": []}],
         "predicted_causal_change_id": None, "predicted_component_id": None, "component_confidence": None, "overall_confidence": conf if overall is None else overall,
         "evidence_sufficiency": suff, "human_review_required": review, "human_review_reason": None, "recommended_next_action": "inspect the API contract",
         "evidence_summary": "API version mismatch on Webhook Dispatch Service", "unresolved_uncertainties": []}
    f.update(extra or {})
    return f


def make_trace(steps=None, fin=None, stop="model_submitted", case="CS00001", run="run_test"):
    steps = steps if steps is not None else [
        step(1, "get_case_context", result={"case_id": case, "title": "API errors"}),
        step(2, "get_recent_changes", evidence=["CH000001"], hyps=[("internal_issue", 0.5), ("api_contract_change", 0.3)], result={"recent_changes": [{"evidence_id": "CH000001", "change_type": "api_contract_change", "component_id": "CM032"}], "count": 1}),
        step(3, "get_technical_signals", evidence=["SG0000001", "SG0000002"], hyps=[("internal_issue", 0.5), ("api_contract_change", 0.4)]),
    ]
    fin = fin if fin is not None else final()
    steps = steps + [Step(n=len(steps) + 1, clock=f"2026-01-01 01:{15 * (len(steps)):02d}:00", tool="submit_diagnosis", args={}, hypotheses=fin["hypotheses"], status="ok", redundant=False, result="submitted")]
    return Trace(run_id=run, case_id=case, stop_reason=stop, steps=steps, final=fin, repair_events=[], citation_violations=[], token_usage={}, model_name="m")


INVENTORY = [
    {"id": "SG0000001", "kind": "signal", "type": "API_VERSION_MISMATCH", "component": "CM032", "time": "2025-12-31 20:00:00", "text": "API version mismatch detected on Webhook Dispatch Service"},
    {"id": "SG0000002", "kind": "signal", "type": "API_VERSION_MISMATCH", "component": "CM032", "time": "2025-12-31 21:00:00", "text": "API version mismatch detected on Webhook Dispatch Service"},
    {"id": "SG0000003", "kind": "signal", "type": "HTTP_500", "component": "CM040", "time": "2025-12-31 22:00:00", "text": "HTTP 500 spike on Authentication Service"},
    {"id": "CH000001", "kind": "change", "type": "api_contract_change", "component": "CM032", "time": "2025-12-31 19:00:00"},
    {"id": "CH000002", "kind": "change", "type": "credential_rotation", "component": "CM040", "time": "2025-12-31 18:00:00"},
]
CONTEXT = {"ticket": {"title": "API errors and webhook retries", "description": "Customer CS00001 (C00412) sees errors on CM032", "reported_symptoms": ["errors"]},
           "inventory": INVENTORY, "telemetry_categories_with_data": ["Application"], "as_of": "2026-01-01 01:00:00"}
TRUTH = {"phase2_ground_truth": {"causal_change_id": "CH000001", "causal_signal_ids": "SG0000001;SG0000002", "distractor_signal_ids": "SG0000003", "irrelevant_change_ids": "CH000002",
                                 "evidence_sufficiency": "sufficient"},
         "phase3_ground_truth": {"critical_evidence_ids": "CH000001;SG0000001;SG0000002", "escalation_warranted": "false"}}
INV_IDS = {i["id"] for i in INVENTORY}


class AliasTests(unittest.TestCase):
    def test_deterministic_injective_and_kind_prefixed(self):
        a, b = Aliaser("s"), Aliaser("s")
        ids = ["SG0000001", "SG0000002", "CH000001", "CM032", "CS00001", "TM07", "C00412", "CS00001:CM032:HTTP_5XX_RATE"]
        self.assertEqual([a.alias(i) for i in ids], [b.alias(i) for i in ids])
        self.assertEqual(len({a.alias(i) for i in ids}), len(ids))
        self.assertTrue(a.alias("SG0000001").startswith("SIG_") and a.alias("CH000001").startswith("CHG_") and a.alias("CM032").startswith("CMP_") and a.alias("CS00001:CM032:HTTP_5XX_RATE").startswith("TEL_"))
        self.assertEqual(a.reverse[a.alias("CH000001")], "CH000001")

    def test_aliases_do_not_encode_id_order_or_number(self):
        al = Aliaser("s")
        aliases = [al.alias(f"SG{n:07d}") for n in range(1, 40)]
        self.assertNotEqual(aliases, sorted(aliases))
        self.assertFalse(any(re.search(r"\d{4}", a) for a in aliases))

    def test_text_and_composite_ids_are_replaced(self):
        al = Aliaser("s")
        out = al.text("see SG0000001 on CM032 for CS00001:CM032:HTTP_5XX_RATE, customer C00412")
        self.assertIsNone(ID_RE.search(out))
        self.assertEqual(al.text("HTTP502 CIRCUIT_BREAKER_OPEN version 1.2"), "HTTP502 CIRCUIT_BREAKER_OPEN version 1.2")

    def test_no_canonical_id_survives_projection_and_content_is_kept(self):
        state, al = project(make_trace(), CONTEXT)
        blob = state_json(state)
        self.assertIsNone(ID_RE.search(blob), ID_RE.search(blob))
        self.assertIn("API version mismatch detected on Webhook Dispatch Service", blob)  # semantic content is preserved
        self.assertIn("2025-12-31 20:00:00", blob)  # timestamps are preserved
        self.assertIn("api_contract_change", blob)

    def test_a_different_salt_changes_every_alias_but_not_the_content(self):
        t = make_trace()
        s0, a0 = project(t, CONTEXT, "0")
        s1, a1 = project(t, CONTEXT, "p6")
        self.assertNotEqual(state_json(s0), state_json(s1))

        def restore(state, aliaser):
            text = state_json(state)
            for alias, canonical in aliaser.reverse.items():
                text = text.replace(alias, canonical)
            return text

        self.assertEqual(restore(s0, a0), restore(s1, a1))
        self.assertTrue(set(a0.reverse) .isdisjoint(a1.reverse))

    def test_the_packet_carries_no_free_text_rationale_and_no_hidden_field(self):
        t = make_trace()
        t.final = dict(final(), rationale="PRIVATE REASONING TEXT")
        state, _ = project(t, CONTEXT)
        blob = state_json(state)
        self.assertNotIn("PRIVATE REASONING TEXT", blob)
        self.assertNotIn("rationale", json.dumps(list(state["final_output"].keys())))
        lowered = blob.lower()
        for marker in guard.MARKERS:
            self.assertNotIn(marker, lowered)
        for name in guard.HIDDEN_COLUMNS:
            self.assertIsNone(guard._word_regex(name).search(lowered), name)  # the agent's own field predicted_causal_change_id is fine: it is a different word

    def test_inventory_retrieved_flags_follow_the_trace(self):
        state, al = project(make_trace(), CONTEXT)
        items = {i["id"]: i for i in state["available_evidence_inventory"]["items"]}
        self.assertTrue(items[al.alias("SG0000001")]["retrieved_by_agent"])
        self.assertFalse(items[al.alias("SG0000003")]["retrieved_by_agent"])
        self.assertEqual(items[al.alias("SG0000001")]["first_retrieved_at_step"], 3)
        kinds = [i["kind"] for i in state["available_evidence_inventory"]["items"]]
        self.assertEqual(kinds, sorted(kinds, key=lambda k: P_ORDER.get(k, 9)))  # ordered by kind then time, never by canonical id


P_ORDER = {"signal": 0, "change": 1, "deployment": 2, "incident": 3, "configuration_snapshot": 4}


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.state, _ = project(make_trace(), CONTEXT)
        self.q = questions.jev_question("support")

    def test_a_clean_packet_passes_and_agent_free_text_with_ordinary_words_is_allowed(self):
        guard.assert_request_clean(self.state, self.q)
        s = copy.deepcopy(self.state)
        s["final_output"]["evidence_summary"] = "Further investigation is warranted; the diagnosis is not correct_ly ruled out."
        guard.assert_request_clean(s, self.q)  # Phase 7's value scan would refuse this; the Phase 8 guard scans hidden field NAMES, not English words

    def test_hidden_field_names_ids_and_banned_keys_are_refused(self):
        for mutate, expect in ((lambda s: s.update({"note": "critical_evidence_ids: SG1"}), "hidden field"), (lambda s: s.update({"gt_root_cause": "x"}), "marker"),
                               (lambda s: s["case_as_reported"].update({"title": "look at SG0000123"}), "canonical internal id"),
                               (lambda s: s.update({"is_distractor": True}), "marker"), (lambda s: s.update({"causal_change_id": "x"}), "evaluation column")):
            s = copy.deepcopy(self.state)
            mutate(s)
            with self.assertRaises(guard.LeakageError) as cm:
                guard.assert_request_clean(s, self.q)
            self.assertIn(expect, str(cm.exception))

    def test_every_question_passes_the_guard_with_a_clean_packet(self):
        for j in JUDGMENTS:
            guard.assert_request_clean(self.state, questions.jev_question(j))


class LabelTests(unittest.TestCase):
    def facts(self, trace, truth=TRUTH):
        return L.trace_facts(trace, INV_IDS, truth)

    def test_full_retrieval_and_matching_conclusion_is_supported_consistent_not_missed_not_premature(self):
        t = make_trace()
        f = self.facts(t)
        self.assertEqual(L.label_support(f)["label"], "SUPPORTED")
        self.assertFalse(L.label_missed(f)["label"])
        self.assertFalse(L.label_anchor(f)["label"])
        self.assertFalse(L.label_premature(f)["label"])
        self.assertTrue(L.label_consistency(t, f)["label"])

    def test_missed_evidence_counts_only_accessible_critical_items(self):
        t = make_trace(steps=[step(1, "get_case_context"), step(2, "get_recent_changes", evidence=["CH000001"], hyps=[("api_contract_change", 0.5)])])
        f = self.facts(t)
        m = L.label_missed(f)
        self.assertTrue(m["label"])
        self.assertEqual(m["n_missed"], 2)
        # critical evidence that is not in the accessible inventory can never be "missed"
        f2 = L.trace_facts(t, {"CH000001", "CH000002", "SG0000003"}, TRUTH)
        self.assertFalse(L.label_missed(f2)["label"])

    def test_anchoring_needs_a_distractor_tie_stronger_than_any_critical_tie(self):
        steps = [step(1, "get_case_context"), step(2, "get_recent_changes", evidence=["CH000002"], hyps=[("credential_rotation_issue", 0.5)],
                                                  result={"recent_changes": [{"evidence_id": "CH000002", "change_type": "credential_rotation"}], "count": 1})]
        t = make_trace(steps=steps, fin=final(top="credential_rotation_issue"))
        self.assertTrue(L.label_anchor(self.facts(t))["label"])
        self.assertFalse(L.label_anchor(self.facts(make_trace()))["label"])

    def test_premature_needs_a_commitment_and_a_gap_and_a_forced_submit_is_not_a_choice(self):
        steps = [step(1, "get_case_context"), step(2, "get_recent_changes", evidence=["CH000001"], hyps=[("api_contract_change", 0.5)])]
        self.assertTrue(L.label_premature(self.facts(make_trace(steps=steps)))["label"])
        flagged = make_trace(steps=steps, fin=final(review=True))
        self.assertFalse(L.label_premature(self.facts(flagged))["label"])
        forced = make_trace(steps=steps, stop="tool_budget_exhausted")
        self.assertFalse(L.label_premature(self.facts(forced))["label"])

    def test_consistency_violations(self):
        bad_cite = make_trace(fin=final(cited=["SG0000099"]))
        self.assertIn("V1", " ".join(L.label_consistency(bad_cite, self.facts(bad_cite))["violations"]))
        no_basis = make_trace(fin=final(top="idp_unreachable_issue"))
        self.assertIn("V2", " ".join(L.label_consistency(no_basis, self.facts(no_basis))["violations"]))
        contradictory = make_trace(fin=final(overall=0.95, conf=0.5))
        self.assertIn("V3", " ".join(L.label_consistency(contradictory, self.facts(contradictory))["violations"]))
        insufficient = make_trace(fin=final(suff="insufficient", review=False))
        self.assertIn("V3", " ".join(L.label_consistency(insufficient, self.facts(insufficient))["violations"]))
        populated = make_trace(fin=final(extra={"predicted_component_id": "CM032"}))
        self.assertIn("V4", " ".join(L.label_consistency(populated, self.facts(populated))["violations"]))

    def test_a_late_revision_tied_to_retrieved_evidence_is_not_inconsistent(self):
        t = make_trace()  # top hypothesis api_contract_change was stated before submit and is tied to retrieved evidence
        self.assertTrue(L.label_consistency(t, self.facts(t))["label"])

    def test_support_bands(self):
        no_tie = make_trace(fin=final(top="quantum_flux_issue"))
        self.assertEqual(L.label_support(self.facts(no_tie))["label"], "UNSUPPORTED")
        self.assertEqual(L.label_support(self.facts(make_trace(fin={**final(), "hypotheses": []})))["label"], "UNSUPPORTED")
        cited_missing = make_trace(fin=final(cited=["SG0000099"]))
        self.assertEqual(L.label_support(self.facts(cited_missing))["label"], "PARTIALLY_SUPPORTED")

    def test_review_policy_tiers_and_the_process_only_variant(self):
        t = make_trace()
        f = self.facts(t)
        labels = {"support": L.label_support(f), "missed_evidence": L.label_missed(f), "distractor_anchor": L.label_anchor(f), "premature_close": L.label_premature(f),
                  "final_consistency": L.label_consistency(t, f)}
        correct = {"label": "CORRECT"}
        self.assertEqual(L.review_policy(t, f, labels, correct, TRUTH)["label"], "AUTO_CLOSE")
        wrong = {"label": "WRONG"}
        hedged = make_trace(fin=final(conf=0.6))
        fh = self.facts(hedged)
        lab_h = dict(labels, final_consistency=L.label_consistency(hedged, fh))
        r = L.review_policy(hedged, fh, lab_h, wrong, TRUTH)
        self.assertEqual(r["label"], "HUMAN_REVIEW")
        confident = make_trace(fin=final(conf=0.9))
        self.assertEqual(L.review_policy(t, f, labels, wrong, TRUTH)["label"], "PRIORITY_REVIEW")  # the default final is 0.8 confident with no review flag: false-confident wrong
        fc = self.facts(confident)
        lab2 = dict(labels, final_consistency=L.label_consistency(confident, fc))
        self.assertEqual(L.review_policy(confident, fc, lab2, wrong, TRUTH)["label"], "PRIORITY_REVIEW")  # false-confident wrong result
        self.assertEqual(L.review_policy(confident, fc, lab2, wrong, TRUTH, include_hidden_outcome=False)["label"], "AUTO_CLOSE")  # process-only ignores the hidden outcome
        escalate = {"phase2_ground_truth": TRUTH["phase2_ground_truth"], "phase3_ground_truth": {**TRUTH["phase3_ground_truth"], "escalation_warranted": "true"}}
        self.assertEqual(L.review_policy(t, f, labels, correct, escalate)["label"], "HUMAN_REVIEW")

    def test_the_universal_final_diagnosis_repair_is_not_a_review_trigger(self):
        t = make_trace()
        t.repair_events = [{"step": 4, "kind": "final_diagnosis_repair", "detail": "x"}]
        f = self.facts(t)
        labels = {"support": L.label_support(f), "missed_evidence": L.label_missed(f), "distractor_anchor": L.label_anchor(f), "premature_close": L.label_premature(f),
                  "final_consistency": L.label_consistency(t, f)}
        self.assertEqual(L.review_policy(t, f, labels, {"label": "CORRECT"}, TRUTH)["label"], "AUTO_CLOSE")
        t.repair_events = [{"step": 4, "kind": "final_diagnosis_fallback", "detail": "x"}]
        self.assertIn("contract_or_consistency_problem", L.review_policy(t, f, labels, {"label": "CORRECT"}, TRUTH)["triggers"])

    def test_outcome_and_process_labels(self):
        p6 = {"outcome": {"root_cause": {"containment_match": None}, "component": {"correct": None}, "category": {"correct": None}, "causal_change": {"false_positive": False, "correct": None}},
              "process": {"hypothesis_recovery": {"final_hypothesis_correct": True}}, "predictions": {"hypotheses": [1]}}
        self.assertEqual(L.outcome_label(p6)["label"], "CORRECT")
        p6["process"]["hypothesis_recovery"]["final_hypothesis_correct"] = False
        self.assertEqual(L.outcome_label(p6)["label"], "WRONG")
        p6["predictions"] = {"hypotheses": []}
        self.assertEqual(L.outcome_label(p6)["label"], "UNANSWERED")
        p6["outcome"]["component"]["correct"] = True
        self.assertEqual(L.outcome_label(p6)["label"], "CORRECT")
        p6["outcome"]["category"]["correct"] = False
        self.assertEqual(L.outcome_label(p6)["label"], "WRONG")


class PerturbationTests(unittest.TestCase):
    def base(self):
        t = make_trace()
        f = L.trace_facts(t, INV_IDS, TRUTH)
        lab = {"support": L.label_support(f), "missed_evidence": L.label_missed(f), "distractor_anchor": L.label_anchor(f), "premature_close": L.label_premature(f),
               "final_consistency": L.label_consistency(t, f)}
        return t, f, lab

    def test_p1_removes_one_critical_item_from_results_and_leaves_the_original_untouched(self):
        t, f, _ = self.base()
        before = json.dumps(t.steps[2].result, default=str)
        v = P.p1_remove_critical(t, f)
        vt = v["trace"]
        removed = v["params"]["removed_evidence"]
        self.assertIn(removed, f["critical"])
        self.assertNotIn(removed, vt.retrieved_ids)
        self.assertNotIn(removed, json.dumps([s.result for s in vt.diagnostic_steps], default=str))
        self.assertEqual(json.dumps(t.steps[2].result, default=str), before)
        self.assertIn(removed, t.retrieved_ids)
        self.assertTrue(vt.variant["synthetic"] and vt.variant["perturbation"] == "P1")

    def test_p1_keeps_the_tools_own_count_consistent(self):
        t, f, _ = self.base()
        vt = P.p1_remove_critical(t, f)["trace"]
        for s in vt.diagnostic_steps:
            if isinstance(s.result, dict) and "count" in s.result:
                lists = [v for v in s.result.values() if isinstance(v, list)]
                self.assertEqual(s.result["count"], len(lists[0]))

    def test_p2_moves_the_distractor_step_late_and_repeats_it_without_new_evidence(self):
        steps = [step(1, "get_case_context"),
                 step(2, "get_recent_changes", evidence=["CH000002"], hyps=[("a_issue", 0.5)], result={"recent_changes": [{"evidence_id": "CH000002", "change_type": "credential_rotation"}], "count": 1}),
                 step(3, "get_technical_signals", evidence=["SG0000001"], hyps=[("a_issue", 0.5)]), step(4, "get_telemetry", hyps=[("a_issue", 0.5)], result={"telemetry_findings": [], "count": 0})]
        t = make_trace(steps=steps)
        f = L.trace_facts(t, INV_IDS, TRUTH)
        v = P.p2_distractor_prominence(t, f)
        vt = v["trace"]
        diag = vt.diagnostic_steps
        self.assertEqual(diag[-1].tool, "get_recent_changes")
        self.assertEqual(diag[-2].tool, "get_recent_changes")  # the moved step and its repeat are adjacent, just before the conclusion
        self.assertEqual(set(vt.retrieved_ids), set(t.retrieved_ids))  # no new evidence
        self.assertEqual([s.n for s in vt.steps], list(range(1, len(vt.steps) + 1)))
        clocks = [s.clock for s in vt.steps]
        self.assertEqual(clocks, sorted(clocks))

    def test_p3_truncates_before_the_first_critical_retrieval_and_keeps_the_final_answer(self):
        t, f, lab = self.base()
        v = P.p3_truncate(t, f, lab)
        vt = v["trace"]
        self.assertEqual(vt.final, t.final)
        self.assertFalse(set(vt.retrieved_ids) & f["critical"])
        self.assertEqual(vt.steps[-1].tool, "submit_diagnosis")
        vf = L.trace_facts(vt, INV_IDS, TRUTH)
        self.assertTrue(L.label_premature(vf)["label"])

    def test_p4_swaps_in_an_alternative_from_unretrieved_evidence_and_the_variant_is_inconsistent(self):
        steps = [step(1, "get_case_context"), step(2, "get_recent_changes", evidence=["CH000001"], hyps=[("api_contract_change", 0.5)],
                                                  result={"recent_changes": [{"evidence_id": "CH000001", "change_type": "api_contract_change"}], "count": 1})]
        t = make_trace(steps=steps)
        f = L.trace_facts(t, INV_IDS, TRUTH)
        lab = {"final_consistency": L.label_consistency(t, f)}
        self.assertTrue(lab["final_consistency"]["label"])
        v = P.p4_inconsistent_final(t, f, lab, INVENTORY)
        vt = v["trace"]
        vf = L.trace_facts(vt, INV_IDS, TRUTH)
        self.assertFalse(L.label_consistency(vt, vf)["label"])
        self.assertEqual(t.final["hypotheses"][0]["confidence"], 0.8)  # original untouched
        self.assertEqual(vt.steps[:-1][1].evidence, t.steps[:-1][1].evidence)  # the investigation itself is unchanged

    def test_p5_keeps_the_unique_evidence(self):
        t, f, _ = self.base()
        v = P.p5_duplicate_call(t, f)
        self.assertEqual(v["params"]["mode"], "insert")
        self.assertEqual(set(v["trace"].retrieved_ids), set(t.retrieved_ids))
        self.assertEqual(len(v["trace"].diagnostic_steps), len(t.diagnostic_steps) + 1)
        dup = make_trace(steps=[step(1, "get_case_context"), step(2, "get_recent_changes", evidence=["CH000001"]), step(3, "get_recent_changes", evidence=["CH000001"])])
        removed = P.p5_duplicate_call(dup, L.trace_facts(dup, INV_IDS, TRUTH))
        self.assertEqual(removed["params"]["mode"], "remove")
        self.assertEqual(len(removed["trace"].diagnostic_steps), len(dup.diagnostic_steps) - 1)

    def test_p6_changes_only_the_alias_mapping(self):
        t, _, _ = self.base()
        v = P.p6_realias(t)
        s0, _ = project(t, CONTEXT, "0")
        s1, _ = project(v["trace"], CONTEXT, v["alias_salt"])
        self.assertNotEqual(state_json(s0), state_json(s1))
        self.assertEqual(v["trace"].steps[2].evidence, t.steps[2].evidence)

    def test_every_perturbation_has_expectations_and_a_description(self):
        self.assertEqual(set(P.EXPECTED), {"P1", "P2", "P3", "P4", "P5", "P6"})
        self.assertEqual(set(P.DESCRIPTIONS), set(P.EXPECTED))
        for expect in P.EXPECTED.values():
            self.assertTrue(set(expect) <= set(JUDGMENTS))

    def test_variants_are_deterministic_for_a_seed(self):
        t, f, lab = self.base()
        bases = [(t, f, lab, INVENTORY)]
        a = [v["trace"].run_key for v in P.build_variants(bases, seed=1)]
        b = [v["trace"].run_key for v in P.build_variants(bases, seed=1)]
        self.assertEqual(a, b)
        self.assertTrue(all(v["trace"].variant["synthetic"] for v in P.build_variants(bases, seed=1)))


class ParityTests(unittest.TestCase):
    """Jev and the LLM judge must see the same packet, the same question and the same allowed answers."""

    def test_the_two_judges_receive_identical_state_and_question(self):
        from agent.trace_eval_v2 import jev_evaluator, llm_evaluator

        state, _ = project(make_trace(), CONTEXT)
        seen = {}

        class FakeClient(jev_evaluator.TraceJevClient):
            def __init__(self):
                self.model = "jev-test"

            def _post_with_retry(self, payload):
                seen["jev"] = payload
                q = payload["questions"]
                key = next(iter(q))
                ans = {"type": "noul", "noul": 0.6} if q[key]["type"] == "noul" else {"type": "choice", "choice": "HUMAN_REVIEW", "confidence": 0.7, "probabilities": {"AUTO_CLOSE": 0.1, "HUMAN_REVIEW": 0.7, "PRIORITY_REVIEW": 0.2}}
                return {"model": "jev-test", "answers": {key: ans}, "usage": {"input_tokens": 10, "output_tokens": 1}}

        def fake_llm(messages):
            seen.setdefault("llm", []).append(messages)
            user = messages[-1]["content"]
            return ('{"probability": 0.4}' if "probability" in user else '{"selected": "HUMAN_REVIEW", "confidence": 0.6}'), {"prompt_tokens": 20, "completion_tokens": 3}

        for j in JUDGMENTS:
            seen.clear()
            jev_evaluator.ask(j, state, FakeClient())
            with mock.patch.object(llm_evaluator, "_call_together", side_effect=lambda m, **k: fake_llm(m)):
                llm_evaluator.ask(j, state)
            self.assertEqual(seen["jev"]["state"], state)
            packet_text = re.search(r"REVIEW PACKET:\n(.*)\n\nQUESTION:", seen["llm"][0][-1]["content"], re.S).group(1)
            self.assertEqual(json.loads(packet_text), json.loads(json.dumps(state, default=str)))
            spec = questions.QUESTIONS[j]
            self.assertEqual(seen["jev"]["questions"][j]["instructions"], spec["instructions"])
            self.assertIn(spec["instructions"], seen["llm"][0][-1]["content"])
            if spec["primitive"] == "noul":
                self.assertEqual(seen["jev"]["questions"][j]["criteria"], {"true": spec["yes"], "false": spec["no"]})
                self.assertIn(spec["yes"], seen["llm"][0][-1]["content"])
                self.assertIn(spec["no"], seen["llm"][0][-1]["content"])
            else:
                self.assertEqual(seen["jev"]["questions"][j]["criteria"], spec["options"])
                for key, desc in spec["options"].items():
                    self.assertIn(key, seen["llm"][0][-1]["content"])
                    self.assertIn(desc, seen["llm"][0][-1]["content"])

    def test_a_leak_stops_both_judges_before_any_call(self):
        from agent.trace_eval_v2 import jev_evaluator, llm_evaluator

        state, _ = project(make_trace(), CONTEXT)
        state["gt_note"] = "x"
        with mock.patch.object(llm_evaluator, "_call_together") as call:
            with self.assertRaises(guard.LeakageError):
                llm_evaluator.ask("support", state)
            call.assert_not_called()
        client = jev_evaluator.TraceJevClient(api_key="k", model="jev-test")
        with mock.patch.object(client, "_post_with_retry") as post:
            with self.assertRaises(guard.LeakageError):
                jev_evaluator.ask("support", state, client)
            post.assert_not_called()

    def test_llm_contract_failures_are_recorded_not_hidden(self):
        from agent.trace_eval_v2 import llm_evaluator

        state, _ = project(make_trace(), CONTEXT)
        replies = iter([("not json", {"prompt_tokens": 5, "completion_tokens": 2}), ('{"probability": 0.9}', {"prompt_tokens": 6, "completion_tokens": 3})])
        with mock.patch.object(llm_evaluator, "_call_together", side_effect=lambda m, **k: next(replies)):
            rec = llm_evaluator.ask("missed_evidence", state)
        self.assertFalse(rec["first_attempt_valid"])
        self.assertTrue(rec["repair_required"] and rec["repair_succeeded"])
        self.assertEqual(rec["first_attempt_failure"], "malformed_json")
        self.assertEqual(rec["answer"]["noul"], 0.9)
        self.assertEqual(rec["usage"]["input_tokens"], 11)


class MetricTests(unittest.TestCase):
    def rows(self, pairs):
        return [{"p": p, "y": y} for p, y in pairs]

    def test_auc_average_precision_brier_and_ece_on_known_values(self):
        perfect = self.rows([(0.9, 1), (0.8, 1), (0.2, 0), (0.1, 0)])
        self.assertEqual(M.roc_auc(perfect), 1.0)
        self.assertEqual(M.average_precision(perfect), 1.0)
        self.assertAlmostEqual(M.brier(perfect), (0.01 + 0.04 + 0.04 + 0.01) / 4)
        inverted = self.rows([(0.1, 1), (0.9, 0)])
        self.assertEqual(M.roc_auc(inverted), 0.0)
        tie = self.rows([(0.5, 1), (0.5, 0)])
        self.assertEqual(M.roc_auc(tie), 0.5)
        self.assertIsNone(M.roc_auc(self.rows([(0.5, 1)])))
        calibrated = self.rows([(0.7, 1)] * 7 + [(0.7, 0)] * 3)
        self.assertAlmostEqual(M.ece(calibrated), 0.0)
        overconfident = self.rows([(0.95, 1)] * 5 + [(0.95, 0)] * 5)
        self.assertAlmostEqual(M.ece(overconfident), 0.45)

    def test_binary_report_and_false_confident(self):
        rows = self.rows([(0.95, 0), (0.95, 1), (0.05, 1), (0.05, 0), (0.6, 1), (0.4, 0)])
        r = M.binary_report(rows, with_ci=False)
        self.assertEqual((r["tp"], r["fp"], r["fn"], r["tn"]), (2, 1, 1, 2))
        self.assertEqual(r["false_confident"]["n_confident"], 4)
        self.assertEqual(r["false_confident"]["n_false_confident"], 2)

    def test_directional_consistency(self):
        up = M.directional([(0.2, 0.5), (0.2, 0.22), (0.5, 0.3), (0.4, 0.4)], "up")
        self.assertEqual((up["moved_up"], up["moved_down"], up["flat"]), (2, 1, 1))
        self.assertEqual(up["consistent"], 2)
        self.assertEqual(up["material"], 1)
        down = M.directional([(0.9, 0.2), (0.9, 0.95)], "down")
        self.assertEqual(down["consistent"], 1)
        stable = M.directional([(0.5, 0.52), (0.4, 0.6), (0.2, 0.25)], "stable")
        self.assertEqual(stable["consistent"], 2)
        self.assertEqual(stable["decision_flips"], 1)

    def test_review_simulation_counts_unsafe_auto_close(self):
        rows = [{"p_auto": 0.95, "ref": "AUTO_CLOSE"}, {"p_auto": 0.92, "ref": "HUMAN_REVIEW"}, {"p_auto": 0.6, "ref": "HUMAN_REVIEW"}, {"p_auto": 0.1, "ref": "PRIORITY_REVIEW"}]
        sim = {r["threshold"]: r for r in M.review_simulation(rows)}
        self.assertEqual(sim[0.9]["auto_close"], 2)
        self.assertEqual(sim[0.9]["unsafe_auto_close"], 1)
        self.assertEqual(sim[0.95]["auto_close"], 1)
        self.assertEqual(sim[0.95]["unsafe_auto_close"], 0)
        self.assertEqual(sim[0.7]["review_rate"], 0.5)

    def test_review_report_operational_metrics(self):
        rows = [{"ref": "AUTO_CLOSE", "pred": "AUTO_CLOSE"}, {"ref": "HUMAN_REVIEW", "pred": "AUTO_CLOSE"}, {"ref": "PRIORITY_REVIEW", "pred": "HUMAN_REVIEW"}, {"ref": "PRIORITY_REVIEW", "pred": "PRIORITY_REVIEW"}]
        r = M.review_report(rows)
        self.assertEqual(r["unsafe_auto_close_count"], 1)
        self.assertEqual(r["auto_close_precision"], 0.5)
        self.assertEqual(r["priority_review_recall"], 0.5)
        self.assertEqual(r["review_recall_on_problematic"], 2 / 3)


class ScorerTests(unittest.TestCase):
    def test_binary_targets_and_rows(self):
        t = make_trace()
        f = L.trace_facts(t, INV_IDS, TRUTH)
        labels = {"labels": {"support": L.label_support(f), "missed_evidence": L.label_missed(f), "distractor_anchor": L.label_anchor(f), "premature_close": L.label_premature(f),
                              "final_consistency": L.label_consistency(t, f), "human_review": {"label": "AUTO_CLOSE"}, "human_review_process_only": {"label": "AUTO_CLOSE"}}}
        self.assertEqual(scorer.binary_target("support", labels), 1)
        self.assertEqual(scorer.binary_target("missed_evidence", labels), 0)
        self.assertEqual(scorer.binary_target("human_review", labels), 0)
        raw = {"judge": "jev", "judgment": "support", "status": "ok", "answer": {"noul": 0.83}, "usage": {"input_tokens": 1000, "output_tokens": 1}, "jev_model": "j", "latency_ms": 12.0}
        row = scorer.score_row(raw, {"trace_key": "k", "run_id": "r", "case_id": "c"}, labels)
        self.assertEqual((row["p"], row["y"]), (0.83, 1))
        self.assertTrue(row["valid"])
        raw6 = {"judge": "jev", "judgment": "human_review", "status": "ok", "answer": {"choice": "HUMAN_REVIEW", "confidence": 0.5, "probabilities": {"AUTO_CLOSE": 0.2, "HUMAN_REVIEW": 0.5, "PRIORITY_REVIEW": 0.3}},
                "usage": {"input_tokens": 1000, "output_tokens": 1}, "jev_model": "j", "latency_ms": 1.0}
        r6 = scorer.score_row(raw6, {"trace_key": "k", "run_id": "r", "case_id": "c"}, labels)
        self.assertAlmostEqual(r6["p"], 0.8)
        self.assertEqual(r6["ref"], "AUTO_CLOSE")
        self.assertAlmostEqual(r6["p_level"], (0.5 + 2 * 0.3) / 2)
        llm6 = {"judge": "llm", "judgment": "human_review", "status": "ok", "answer": {"choice": "AUTO_CLOSE", "confidence": 0.9, "probabilities": None}, "usage": {"input_tokens": 1, "output_tokens": 1}, "latency_ms": 1.0}
        self.assertEqual(scorer.score_row(llm6, {"trace_key": "k", "run_id": "r", "case_id": "c"}, labels)["p"], 0.0)

    def test_observable_baselines_use_no_hidden_truth(self):
        t = make_trace()
        b = scorer.observable_baselines(t, INVENTORY)
        self.assertEqual(set(b), {"support", "missed_evidence", "distractor_anchor", "premature_close", "final_consistency", "human_review_agent_flag", "human_review_defect_rule"})
        self.assertEqual(b["human_review_agent_flag"], 0)
        self.assertEqual(b["missed_evidence"], 1)  # an unretrieved signal exists in the inventory


class QuestionTests(unittest.TestCase):
    def test_the_corrected_consistency_question_is_versioned_and_the_old_wording_is_kept_on_record(self):
        self.assertEqual(questions.question_version("final_consistency"), "final_consistency_v2")
        self.assertIn("final_consistency_v1", questions.SUPERSEDED_WORDING)
        self.assertNotEqual(questions.SUPERSEDED_WORDING["final_consistency_v1"], questions.QUESTIONS["final_consistency"]["instructions"])
        for j in ("support", "missed_evidence", "distractor_anchor", "premature_close", "human_review"):
            self.assertTrue(questions.question_version(j).endswith("_v1"))  # only J5 was corrected

    def test_versions_primitives_and_no_explanation_requests(self):
        self.assertEqual(set(questions.QUESTIONS), set(JUDGMENTS))
        for j, spec in questions.QUESTIONS.items():
            self.assertRegex(spec["version"], r"_v[12]$")
            self.assertEqual(spec["primitive"], "choice" if j == "human_review" else "noul")
            text = spec["instructions"].lower()
            for banned in ("explain", "rationale", "reasoning", "chain of thought", "overall quality"):
                self.assertNotIn(banned, text)
        self.assertEqual(set(questions.REVIEW_OPTIONS), {"AUTO_CLOSE", "HUMAN_REVIEW", "PRIORITY_REVIEW"})


class StoredRunFidelityTests(unittest.TestCase):
    def test_the_trace_round_trips_through_phase6_scoring(self):
        """Phase 6's evaluate_run gives the same outcome, evidence and process scores for a persisted run and for the run rebuilt from the Trace."""
        import glob

        from agent.eval_v2.metrics import evaluate_run
        from agent.trace_eval_v2.trace_loader import load_trace
        from agent.trace_eval_v2.config import AGENT_RUNS_DIR

        paths = sorted(glob.glob(str(AGENT_RUNS_DIR / "run_*.json")))[-6:]
        if not paths:
            self.skipTest("no stored runs")
        for p in paths:
            run = json.load(open(p))
            if "repair_events" not in run:
                continue
            a, b = evaluate_run(run), evaluate_run(load_trace(run).to_run())
            for key in ("outcome", "evidence", "process", "predictions", "failure_tags", "stratification"):
                self.assertEqual(json.dumps(a[key], sort_keys=True, default=str), json.dumps(b[key], sort_keys=True, default=str), f"{p}: {key}")


class CorpusTests(unittest.TestCase):
    def test_pool_is_dev_only_and_deterministic(self):
        from agent.trace_eval_v2 import corpus
        from agent.eval_v2.splits import case_ids_for_split

        pool = corpus.build_pool()
        self.assertEqual(pool["case_ids"], corpus.build_pool()["case_ids"])
        self.assertTrue(set(pool["case_ids"]) <= set(case_ids_for_split("dev")))
        corpus.assert_dev_only(pool["case_ids"])
        with self.assertRaises(SystemExit):
            corpus.assert_dev_only(case_ids_for_split("validation")[:1])

    def test_the_stored_pool_matches_the_deterministic_build(self):
        from agent.trace_eval_v2 import corpus

        if not corpus.POOL_PATH.exists():
            self.skipTest("pool not written")
        self.assertEqual(corpus.load_pool()["case_ids_sha256"], corpus.build_pool()["case_ids_sha256"])

    def test_the_stored_corpus_is_a_subset_of_the_pool_and_reproducible(self):
        from agent.trace_eval_v2 import corpus

        if not corpus.CORPUS_PATH.exists():
            self.skipTest("corpus not selected")
        stored = json.loads(corpus.CORPUS_PATH.read_text())
        again = corpus.select_corpus(corpus.load_labels())
        self.assertEqual(stored["run_ids"], again["run_ids"])
        self.assertTrue(set(stored["case_ids"]) <= set(corpus.load_pool()["case_ids"]))


if __name__ == "__main__":
    unittest.main()
