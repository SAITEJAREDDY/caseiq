"""Offline regression checks for Phase 7 Stage B v2 changes, Stage C analysis helpers and the locked-benchmark guards."""
import json
import unittest
from unittest import mock

from agent.jev_v2 import candidates as candidates_mod
from agent.jev_v2 import config as jev_config
from agent.jev_v2 import frozen_config, llm_baseline
from agent.jev_v2.aggregate import causal_change_recency_categories, contract_summary, strict_first_attempt_accuracy
from agent.jev_v2.candidates import owning_team_candidates, root_cause_candidates
from agent.jev_v2.questions import question_version
from agent.jev_v2.scoring import score_evidence_sufficiency
from agent.jev_v2 import locked_benchmark, locked_report, opaque_control, stage_c_posthoc, stage_c_report, threshold_policy


class CandidateGenerationV2Tests(unittest.TestCase):
    def test_team_candidates_consider_components_after_the_old_eighth_item(self):
        state = {
            "ticket": {"reported_symptoms": []},
            "reported_product": {"id": "P002"},
            # CM045 (Commerce) is deliberately ninth. v1 never queried it.
            "deployed_components": ["CM001", "CM002", "CM003", "CM004", "CM005", "CM006", "CM007", "CM008", "CM045"],
            "evidence_summary": {"signals": []},
        }
        candidates, meta = owning_team_candidates(state)
        self.assertIn("TM08", candidates)
        self.assertEqual(meta["team_cutoff"], 12)
        self.assertLessEqual(len(candidates), 12)

    def test_root_cause_candidates_are_bounded_and_keep_canonical_abstention(self):
        state = {
            "ticket": {"reported_symptoms": ["login failure"]},
            "reported_product": {"id": "P002"},
            "technical_evidence": {"signals": [{"component_id": "CM011"}]},
        }
        candidates, meta = root_cause_candidates(state)
        self.assertIn("RC40", candidates)
        self.assertLessEqual(len(candidates), 16)
        self.assertEqual(meta["root_cause_cutoff_excluding_rc40"], 15)


class EvidenceSufficiencyV2Tests(unittest.TestCase):
    def test_partial_label_is_scored_without_normalization_or_inversion(self):
        record = {"answer": {"choice": "partially_sufficient", "confidence": 0.7, "probabilities": {}}}
        scored = score_evidence_sufficiency(record, {"evidence_sufficiency": "partially_sufficient"})
        self.assertTrue(scored["correct"])
        self.assertEqual(scored["ground_truth_value"], "partially_sufficient")

    def test_evidence_question_is_explicitly_versioned(self):
        self.assertEqual(question_version("evidence_sufficiency"), "evidence_sufficiency_v2")


CHANGE = {"evidence_id": "CH017279", "change_type": "config_change", "component_id": "CM001", "started_at": "2025-08-05 10:00:00", "time_proximity_hours": 5.0}
DEPLOY = {"evidence_id": "CH030400", "component_id": "CM011", "version_from": "1.8", "version_to": "2.2", "rollout_strategy": "rolling",
          "deploy_duration_minutes": 20, "started_at": "2025-08-05 23:14:00", "status": "rolled_back"}


def _candidates(changes, deployments, version="v3", key_mode="canonical", as_of="2025-08-06"):
    with mock.patch.object(candidates_mod, "q_recent_changes", return_value={"recent_changes": changes}), \
         mock.patch.object(candidates_mod, "q_deployment_history", return_value={"deployments": deployments}):
        return candidates_mod.causal_change_candidates(None, "CS0", as_of, version=version, key_mode=key_mode)


class CausalChangeCandidateGenerationV3Tests(unittest.TestCase):
    def test_v3_offers_deployments_and_the_none_option_newest_first(self):
        cands, meta = _candidates([CHANGE], [DEPLOY])
        self.assertEqual(list(cands), ["CH030400", "CH017279", "none"])
        self.assertIn("version 1.8 -> 2.2", cands["CH030400"])
        self.assertEqual(meta["num_deployment_candidates"], 1)
        self.assertEqual(meta["newest_change_id"], "CH030400")
        self.assertEqual(meta["candidate_generation_version"], "v3")
        self.assertEqual(meta["candidate_events"]["CH030400"]["deployment"]["rollout_strategy"], "rolling")

    def test_v3_never_exposes_a_status_that_could_postdate_the_decision(self):
        cands, meta = _candidates([], [DEPLOY])
        self.assertNotIn("rolled_back", json.dumps(cands) + json.dumps(meta))

    def test_v2_is_unchanged_and_still_omits_deployments(self):
        cands, meta = _candidates([CHANGE], [DEPLOY], version="v2")
        self.assertEqual(list(cands), ["CH017279", "none"])
        self.assertEqual(meta["candidate_generation_version"], "v2")
        self.assertEqual(meta["strategy"], "recent_changes_plus_none_option")

    def test_same_event_from_both_projections_is_offered_once(self):
        duplicate_as_change = {**CHANGE, "evidence_id": "CH030400", "change_type": "deployment", "component_id": "CM011", "started_at": "2025-08-05 23:14:00"}
        cands, meta = _candidates([duplicate_as_change], [DEPLOY])
        self.assertEqual(list(cands), ["CH030400", "none"])
        self.assertEqual(meta["duplicates_suppressed"], 1)
        self.assertEqual(meta["candidate_events"]["CH030400"]["sources"], ["recent_changes", "deployment_history"])
        self.assertIsNotNone(meta["candidate_events"]["CH030400"]["deployment"])

    def test_events_after_the_decision_time_are_dropped(self):
        future = {**DEPLOY, "evidence_id": "CH030999", "started_at": "2025-08-07 01:00:00"}
        cands, meta = _candidates([CHANGE], [DEPLOY, future])
        self.assertNotIn("CH030999", cands)
        self.assertEqual(meta["future_events_dropped"], 1)

    def test_no_visible_events_leaves_only_the_none_option(self):
        cands, meta = _candidates([], [])
        self.assertEqual(list(cands), ["none"])
        self.assertIsNone(meta["newest_change_id"])
        self.assertEqual(meta["num_real_change_candidates"], 0)

    def test_ordering_is_deterministic_for_equal_timestamps(self):
        a = {**CHANGE, "evidence_id": "CH000002", "started_at": "2025-08-05 10:00:00"}
        b = {**CHANGE, "evidence_id": "CH000001", "started_at": "2025-08-05 10:00:00"}
        first, _ = _candidates([a, b], [])
        second, _ = _candidates([b, a], [])
        self.assertEqual(list(first), list(second))

    def test_opaque_keys_hide_ids_and_map_back_to_canonical(self):
        cands, meta = _candidates([CHANGE], [DEPLOY], key_mode="opaque")
        facing = candidates_mod.model_facing_candidates(cands, meta)
        self.assertEqual(list(facing), ["option_1", "option_2", "none"])
        self.assertNotIn("CH0", json.dumps(facing.keys().__repr__()))
        self.assertEqual(list(cands), ["CH030400", "CH017279", "none"])  # scoring still sees canonical ids
        answer = {"choice": "option_1", "confidence": 0.7, "probabilities": {"option_1": 0.7, "option_2": 0.2, "none": 0.1}}
        mapped = candidates_mod.to_canonical_answer(answer, meta)
        self.assertEqual(mapped["choice"], "CH030400")
        self.assertEqual(mapped["choice_alias"], "option_1")
        self.assertEqual(mapped["probabilities"]["CH030400"], 0.7)

    def test_opaque_mode_is_not_defined_for_v2(self):
        with self.assertRaises(ValueError):
            _candidates([CHANGE], [], version="v2", key_mode="opaque")

    def test_default_version_is_the_configured_one(self):
        self.assertEqual(jev_config.CANDIDATE_GENERATION_VERSIONS["causal_change"], "v3")


def _scored(truth, candidate_starts, predicted):
    return {"candidates": {**{cid: "" for cid in candidate_starts}, "none": ""},
            "candidate_meta": {"change_started_ats": candidate_starts, "num_real_change_candidates": len(candidate_starts), "newest_change_id": (max(candidate_starts, key=candidate_starts.get) if candidate_starts else None)},
            "scoring": {"ground_truth_value": truth, "predicted_value": predicted, "correct": predicted == truth,
                        "selected_is_newest_change": bool(candidate_starts) and predicted == max(candidate_starts, key=candidate_starts.get)}}


class RecencyCategoryTests(unittest.TestCase):
    def test_groups_a_b_c_d_and_e(self):
        records = [
            _scored("N1", {"N1": "2025-02", "O1": "2025-01"}, "N1"),   # A (newest is causal), also D (two candidates)
            _scored("O2", {"N2": "2025-03", "O2": "2025-01"}, "N2"),   # B (older than a distractor), also D, distractor selected
            _scored("none", {"X": "2025-01"}, "none"),                  # C
            _scored("MISSING", {"X": "2025-01"}, "none"),               # E (true change never offered)
            _scored("T", {"T": "2025-01", "U": "2025-01"}, "T"),        # equal timestamps -> A, not B
        ]
        out = causal_change_recency_categories(records)
        self.assertEqual((out["A"]["n"], out["B"]["n"], out["C"]["n"], out["E"]["n"]), (2, 1, 1, 1))
        self.assertEqual(out["B"]["accuracy"], 0.0)
        self.assertEqual(out["D_multiple_recent_changes"]["n"], 3)
        self.assertEqual(out["E"]["accuracy"], 0.0)  # reported separately so it is never read as a model failure
        self.assertAlmostEqual(out["distractor_selection_rate_all_decisions"], 1 / 5)


class FakeTogether:
    def __init__(self, texts):
        self.texts, self.calls = list(texts), 0

    def __call__(self, messages, max_retries=5):
        self.calls += 1
        return self.texts.pop(0), {"prompt_tokens": 100, "completion_tokens": 10}


CANDS = {"A": "first", "B": "second"}
QUESTION = {"type": "choice", "instructions": "pick one", "criteria": CANDS}


def _run_llm(fake):
    with mock.patch.object(llm_baseline, "_call_together", fake):
        return llm_baseline.run_llm_decision("issue_category", "CS0", {"ticket": {"title": "t"}}, dict(QUESTION), CANDS, {}, "2025-01-01", "v3_technical")


class LlmContractTrackingTests(unittest.TestCase):
    def test_valid_first_attempt(self):
        rec = _run_llm(FakeTogether(['{"selected": "A", "confidence": 0.8}']))
        self.assertTrue(rec["first_attempt_valid"])
        self.assertFalse(rec["repair_required"])
        self.assertIsNone(rec["repair_succeeded"])
        self.assertEqual(rec["answer"]["choice"], "A")

    def test_invalid_option_then_successful_repair_is_not_hidden(self):
        fake = FakeTogether(['{"selected": "Z", "confidence": 0.8}', '{"selected": "B", "confidence": 0.6}'])
        rec = _run_llm(fake)
        self.assertFalse(rec["first_attempt_valid"])
        self.assertEqual(rec["first_attempt_failure"], "invalid_option")
        self.assertTrue(rec["repair_required"] and rec["repair_succeeded"])
        self.assertFalse(rec["unrecoverable_failure"])
        self.assertEqual(rec["answer"]["choice"], "B")
        self.assertEqual(rec["usage"], {"input_tokens": 200, "output_tokens": 20})  # both attempts are billed
        self.assertEqual([a["purpose"] for a in rec["attempts"]], ["initial", "repair"])
        # the strict view still counts it as a failure even though the repaired answer is right
        scored = {**rec, "scoring": {"correct": True}}
        self.assertEqual(strict_first_attempt_accuracy([scored]), 0.0)

    def test_unrecoverable_after_one_repair(self):
        fake = FakeTogether(["not json at all", '{"selected": "Z", "confidence": 0.5}'])
        rec = _run_llm(fake)
        self.assertEqual(fake.calls, 1 + jev_config.LLM_REPAIR_MAX_ATTEMPTS)
        self.assertEqual(rec["first_attempt_failure"], "malformed_json")
        self.assertTrue(rec["repair_required"])
        self.assertFalse(rec["repair_succeeded"])
        self.assertTrue(rec["unrecoverable_failure"])
        self.assertEqual(rec["contract_failure"], "invalid_option")
        self.assertNotIn("answer", rec)

    def test_missing_answer_and_bad_confidence_are_distinct_kinds(self):
        self.assertEqual(llm_baseline._classify_response("choice", '{"confidence": 0.5}', CANDS)[1], "missing_answer")
        self.assertEqual(llm_baseline._classify_response("choice", '{"selected": "A", "confidence": 85}', CANDS)[1], "invalid_confidence")
        self.assertEqual(llm_baseline._classify_response("noul", '{"probability": 1.5}', None)[1], "invalid_probability")

    def test_contract_summary_counts_each_stage(self):
        recs = [
            {"status": "ok", "first_attempt_valid": True, "repair_required": False, "repair_succeeded": None, "unrecoverable_failure": False, "first_attempt_failure": None},
            {"status": "ok", "first_attempt_valid": False, "repair_required": True, "repair_succeeded": True, "unrecoverable_failure": False, "first_attempt_failure": "invalid_option"},
            {"status": "ok", "first_attempt_valid": False, "repair_required": True, "repair_succeeded": False, "unrecoverable_failure": True, "first_attempt_failure": "malformed_json"},
        ]
        out = contract_summary(recs)
        self.assertEqual((out["first_attempt_valid"], out["repair_required"], out["repair_succeeded"], out["unrecoverable_failures"]), (1, 2, 1, 1))
        self.assertEqual(out["first_attempt_failure_kinds"], {"invalid_option": 1, "malformed_json": 1})


class FrozenConfigVersionTests(unittest.TestCase):
    def _cfg(self):
        return {
            "decisions": {dt: {"question_version": jev_config.QUESTION_VERSIONS[dt], "candidate_generation_version": jev_config.CANDIDATE_GENERATION_VERSIONS[dt]} for dt in jev_config.QUESTION_VERSIONS},
            "evaluator_version": jev_config.EVALUATOR_VERSION, "question_set_version": jev_config.QUESTION_SET_VERSION,
            "candidate_strategy_bundle": jev_config.CANDIDATE_STRATEGY_VERSION, "pricing_version": jev_config.PRICING_VERSION,
            "llm_baseline": {"model": jev_config.LLM_BASELINE_MODEL, "temperature": jev_config.LLM_BASELINE_TEMPERATURE,
                             "max_tokens": jev_config.LLM_BASELINE_MAX_TOKENS, "repair_max_attempts": jev_config.LLM_REPAIR_MAX_ATTEMPTS},
            "jev": {"api_endpoint": jev_config.TYPESAFE_SYSTEM_ONE_PATH},
        }

    def test_matching_config_has_no_problems(self):
        self.assertEqual(frozen_config.verify_versions(self._cfg()), [])

    def test_drifted_versions_are_reported(self):
        cfg = self._cfg()
        cfg["decisions"]["causal_change"]["candidate_generation_version"] = "v2"
        cfg["decisions"]["root_cause"]["question_version"] = "root_cause_v0"
        problems = frozen_config.verify_versions(cfg)
        self.assertEqual(len(problems), 2)
        self.assertTrue(any("causal_change" in p for p in problems))


def _causal_record(truth, predicted, offered, confidence=0.9, newest=None):
    """A minimal stored causal-change decision record (already scored), for analysis-helper tests."""
    cands = {c: "x" for c in offered}
    cands["none"] = "none"
    return {"decision_type": "causal_change", "case_id": "CS0", "candidates": cands,
            "candidate_meta": {"num_real_change_candidates": len(offered), "newest_change_id": newest or (offered[0] if offered else None)},
            "scoring": {"ground_truth_value": truth, "predicted_value": predicted, "predicted_confidence": confidence,
                        "correct": truth == predicted, "candidate_answer_present": truth in cands}}


class StageCAnalysisHelperTests(unittest.TestCase):
    def test_lower_is_better_labels_are_inverted(self):
        below = {"diff": -0.05, "ci_low": -0.10, "ci_high": -0.01}
        self.assertEqual(stage_c_report.delta_label(below, 100, 750), "material degradation")
        self.assertEqual(stage_c_report.delta_label(below, 100, 750, lower_is_better=True), "improvement")
        above = {"diff": 0.05, "ci_low": 0.01, "ci_high": 0.10}
        self.assertEqual(stage_c_report.delta_label(above, 100, 750), "improvement")
        self.assertEqual(stage_c_report.delta_label(above, 100, 750, lower_is_better=True), "material degradation")
        self.assertEqual(stage_c_report.delta_label(below, 10, 750), "insufficient sample")

    def test_size_bins_drop_empty_terciles_and_note_a_dominant_size(self):
        recs = [{"candidates": {str(i): "x" for i in range(12)}, "scoring": {"correct": True, "candidate_answer_present": True}} for _ in range(90)]
        recs += [{"candidates": {str(i): "x" for i in range(size)}, "scoring": {"correct": False, "candidate_answer_present": True}} for size in (5, 6, 7, 8, 9, 10, 11) for _ in range(2)]
        out = stage_c_report.size_bins(recs)
        self.assertTrue(all(b["n"] > 0 for b in out["bins"].values()))
        self.assertFalse(any(label.startswith("13-") for label in out["bins"]))

    def test_mcnemar_exact_matches_a_hand_computed_case(self):
        self.assertAlmostEqual(stage_c_posthoc.mcnemar_exact(5, 0), 0.0625)
        self.assertEqual(stage_c_posthoc.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(stage_c_posthoc.mcnemar_exact(3, 3), 1.0)

    def test_causal_nontrivial_excludes_none_only_decisions(self):
        recs = [_causal_record("none", "none", []) for _ in range(6)]                          # only `none` offered
        recs += [_causal_record("CH2", "CH2", ["CH2", "CH1"], newest="CH2")]                    # newest is true, found
        recs += [_causal_record("CH2", "none", ["CH2"], confidence=0.3, newest="CH2")]         # true change missed
        recs += [_causal_record("none", "CH1", ["CH1"], newest="CH1")]                          # false positive
        out = stage_c_posthoc.causal_nontrivial(recs)
        self.assertEqual((out["n_all"], out["n_only_none_offered"], out["n_nontrivial"]), (9, 6, 3))
        self.assertEqual(out["correct_nontrivial"], 1)
        self.assertAlmostEqual(out["baseline_newest_change_nontrivial"], 2 / 3)  # newest == true in the two true-change cases
        self.assertEqual(out["confidence_ge_0.90"]["only_none_offered"], 6)

    def test_causal_split_by_whether_a_change_exists(self):
        recs = [_causal_record("CH2", "CH2", ["CH2"]), _causal_record("CH2", "none", ["CH2"]), _causal_record("none", "none", ["CH1"]), _causal_record("none", "CH1", ["CH1"])]
        out = stage_c_posthoc.causal_split(recs)
        self.assertEqual((out["change_exists"]["n"], out["change_exists"]["correct"], out["change_exists"]["answered_none"]), (2, 1, 1))
        self.assertEqual((out["no_change"]["n"], out["no_change"]["false_positive"]), (2, 1))


def _conf_record(conf, correct, real=1, dt="issue_category"):
    return {"decision_type": dt, "candidate_meta": {"num_real_change_candidates": real},
            "scoring": {"predicted_confidence": conf, "correct": correct}}


class ThresholdPolicyTests(unittest.TestCase):
    def test_selects_the_lowest_grid_threshold_that_meets_each_tier(self):
        recs = [_conf_record(0.96, i >= 3) for i in range(300)] + [_conf_record(0.72, i >= 60) for i in range(300)]
        out = threshold_policy.select(recs, "issue_category")
        # 0.70 automates everything (10.5% error) and fails; 0.80 keeps only the 300 confident decisions (1% error, upper bound < 4%)
        self.assertEqual(out["tiers"]["standard"]["selected_threshold"], 0.80)
        self.assertEqual(out["tiers"]["strict"]["selected_threshold"], 0.80)

    def test_no_threshold_is_forced_when_none_qualifies(self):
        recs = [_conf_record(0.99, i >= 90) for i in range(300)]  # 30% wrong at every confidence
        out = threshold_policy.select(recs, "issue_category")
        self.assertIsNone(out["tiers"]["standard"]["selected_threshold"])
        self.assertIn("reason", out["tiers"]["standard"])

    def test_minimum_automated_decisions_is_enforced(self):
        recs = [_conf_record(0.99, True) for _ in range(40)]  # perfect but only 40 decisions
        out = threshold_policy.select(recs, "issue_category")
        self.assertIsNone(out["tiers"]["standard"]["selected_threshold"])

    def test_trivial_causal_decisions_are_excluded_from_the_population(self):
        recs = [_conf_record(0.99, True, real=0, dt="causal_change") for _ in range(500)] + [_conf_record(0.99, i % 2 == 0, real=1, dt="causal_change") for i in range(100)]
        out = threshold_policy.select(recs, "causal_change")
        self.assertEqual(out["population"], 100)
        self.assertIsNone(out["tiers"]["standard"]["selected_threshold"])  # the 500 trivial decisions must not rescue it


class LockedBenchmarkGuardTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / "state.json"
        self.registry = self.tmp / "registry.jsonl"

    def test_first_run_is_allowed_then_only_resume_of_the_same_run(self):
        locked_benchmark.check_run_allowed("locked_benchmark_run", False, "abc", self.state, self.registry)  # nothing started yet
        locked_benchmark.record_run_start("locked_benchmark_run", "abc", "m1", False, self.state)
        with self.assertRaises(SystemExit):
            locked_benchmark.check_run_allowed("locked_benchmark_run", False, "abc", self.state, self.registry)   # a second run
        with self.assertRaises(SystemExit):
            locked_benchmark.check_run_allowed("another_name", True, "abc", self.state, self.registry)           # resume under another name
        locked_benchmark.check_run_allowed("locked_benchmark_run", True, "abc", self.state, self.registry)       # resume of the same run

    def test_resume_without_a_started_run_is_refused(self):
        with self.assertRaises(SystemExit):
            locked_benchmark.check_run_allowed("locked_benchmark_run", True, "abc", self.state, self.registry)

    def test_config_change_after_start_is_refused_as_invalidating(self):
        locked_benchmark.record_run_start("locked_benchmark_run", "abc", "m1", False, self.state)
        with self.assertRaises(SystemExit) as ctx:
            locked_benchmark.check_run_allowed("locked_benchmark_run", True, "CHANGED", self.state, self.registry)
        self.assertIn("no longer a valid holdout", str(ctx.exception))

    def test_a_registered_locked_run_without_a_marker_is_refused(self):
        self.registry.write_text(json.dumps({"experiment_id": "exp_x", "kind": "locked_benchmark"}) + "\n")
        with self.assertRaises(SystemExit):
            locked_benchmark.check_run_allowed("locked_benchmark_run", False, "abc", self.state, self.registry)

    def test_explicit_case_ids_outside_dev_and_validation_are_refused(self):
        fake = lambda: {"CS1": "dev", "CS2": "validation", "CS3": "test"}
        locked_benchmark.assert_not_locked_ids(["CS1", "CS2"], load_splits=fake)
        with self.assertRaises(SystemExit):
            locked_benchmark.assert_not_locked_ids(["CS1", "CS3"], load_splits=fake)
        with self.assertRaises(SystemExit):
            locked_benchmark.assert_not_locked_ids(["NOT_A_CASE"], load_splits=fake)

    def test_pinned_closure_covers_run_scoring_and_analysis_code(self):
        files = locked_benchmark.pinned_source_files()
        for expected in ("agent/jev_v2/run_experiment.py", "agent/jev_v2/scoring.py", "agent/jev_v2/candidates.py", "agent/jev_v2/stage_c_report.py",
                         "agent/jev_v2/threshold_policy.py", "agent/jev_v2/locked_report.py", "agent/agent_v2/tools.py", "agent/eval_v2/splits.py"):
            self.assertIn(expected, files)
        self.assertFalse(any(f.startswith("agent/graph_v2/loaders/") for f in files))

    def test_environment_check_flags_forbidden_and_drifted_packages(self):
        from importlib import metadata

        real = metadata.version
        def fake(pkg):
            return {"tenacity": "9.1.4", "typesafe-sdk": "1.0"}.get(pkg) or real(pkg)
        with mock.patch.object(locked_benchmark.metadata, "version", side_effect=fake):
            problems = locked_benchmark.verify_environment()
        self.assertTrue(any("tenacity" in p for p in problems))
        self.assertTrue(any("typesafe-sdk" in p for p in problems))

    def test_reading_of_a_direction_neutral_metric(self):
        out = locked_report._reading("share", (100, 500), (400, 500), neutral=True)
        self.assertEqual(out["reading"], "differs from validation (higher)")
        self.assertEqual(locked_report._reading("share", (100, 500), (101, 500), neutral=True)["reading"], "plausible sampling variation")


class LockedPreflightTests(unittest.TestCase):
    def _args(self, **kw):
        from types import SimpleNamespace
        base = dict(split="test", kind="locked_benchmark", compare_llm=True, name="locked_benchmark_run", n=None, decision_types=None, context_version=None,
                    candidate_version=None, causal_key_mode=None, jev_model=None, baseline_experiment_id=None, protocol=None, workers=None, pre_freeze=False,
                    frozen_config="locked_benchmark_frozen_v1", resume=False)
        base.update(kw)
        return SimpleNamespace(**base)

    def _refused(self, args, cfg):
        import argparse
        import contextlib
        import io
        from agent.jev_v2 import run_experiment

        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run_experiment._locked_preflight(argparse.ArgumentParser(), args, cfg)

    def test_locked_split_without_a_locked_configuration_is_refused(self):
        self._refused(self._args(frozen_config=None), None)

    def test_wrong_split_or_kind_is_refused(self):
        cfg = {"run": {"name": "locked_benchmark_run"}}
        self._refused(self._args(split="validation"), cfg)
        self._refused(self._args(kind="engineering"), cfg)

    def test_missing_compare_llm_wrong_name_and_every_override_are_refused(self):
        cfg = {"run": {"name": "locked_benchmark_run"}}
        self._refused(self._args(compare_llm=False), cfg)
        self._refused(self._args(name="something_else"), cfg)
        for override in ({"n": 10}, {"decision_types": ["causal_change"]}, {"workers": 2}, {"pre_freeze": True}, {"protocol": "x.md"}, {"jev_model": "jev-latest"},
                         {"causal_key_mode": "opaque"}, {"context_version": "v5_graph"}, {"candidate_version": ["causal_change=v2"]}):
            self._refused(self._args(**override), cfg)


class SealedLockedFreezeTests(unittest.TestCase):
    """Against the real sealed locked_benchmark_frozen_v1 (reads no test-case id)."""

    def test_sealed_freeze_verifies_clean_and_the_holdout_is_unused(self):
        self.assertEqual(locked_benchmark.verify(), [])
        self.assertIsNone(locked_benchmark.read_run_state())

    def test_frozen_settings_match_the_code_and_the_inclusion_decisions(self):
        cfg = frozen_config.load(locked_benchmark.NAME)
        self.assertEqual(frozen_config.verify_versions(cfg), [])
        self.assertEqual(locked_benchmark.included_decisions(cfg), ["issue_category", "root_cause", "causal_change", "owning_team"])
        settings = locked_benchmark.run_settings(cfg)
        self.assertEqual((settings["context_version"], settings["causal_key_mode"], settings["jev_model"], settings["workers"]), ("v4_operational", "canonical", "jev-1.13.0", 8))
        self.assertEqual(settings["expected_case_count"], 751)
        for dt, d in cfg["decisions"].items():
            self.assertIn("primary_metric", d)
            self.assertEqual(bool(d.get("threshold_selection")), d["include_in_locked_test"])

    def test_frozen_thresholds_are_the_policy_output_on_validation(self):
        from agent.jev_v2.registry import load_decisions

        cfg = frozen_config.load(locked_benchmark.NAME)
        validation = load_decisions(cfg["stage_c"]["jev_experiment"])
        for dt in locked_benchmark.included_decisions(cfg):
            recomputed = threshold_policy.select([r for r in validation if r["decision_type"] == dt], dt)
            frozen = cfg["decisions"][dt]["threshold_selection"]["tiers"]
            for tier in ("standard", "strict"):
                self.assertEqual(recomputed["tiers"][tier].get("selected_threshold"), frozen[tier].get("selected_threshold"), f"{dt} {tier}")

    def test_editing_the_config_or_a_pinned_file_is_detected(self):
        from pathlib import Path

        real = locked_benchmark.sha256_file
        targets = {frozen_config.config_path(locked_benchmark.NAME): "configuration file content changed",
                   locked_benchmark.PROJECT_ROOT / "agent/jev_v2/scoring.py": "pinned source file changed: agent/jev_v2/scoring.py",
                   locked_benchmark.PROJECT_ROOT / "agent/jev_v2/locked_report.py": "pinned source file changed: agent/jev_v2/locked_report.py",
                   locked_benchmark.PROJECT_ROOT / "docs/JEV_LOCKED_BENCHMARK_PROTOCOL.md": "pinned file changed: protocol",
                   locked_benchmark.SPLIT_FILE if hasattr(locked_benchmark, "SPLIT_FILE") else frozen_config.SPLIT_FILE: "split file content changed"}
        for path, expected in targets.items():
            with mock.patch.object(locked_benchmark, "sha256_file", side_effect=lambda p, path=path: "0" * 64 if Path(p) == Path(path) else real(p)):
                problems = locked_benchmark.verify()
            self.assertTrue(any(expected in p for p in problems), f"{expected!r} not reported: {problems[:3]}")

    def test_a_config_edit_after_the_run_started_invalidates_it(self):
        import tempfile
        from pathlib import Path

        state_file = Path(tempfile.mkdtemp()) / "state.json"
        locked_benchmark.record_run_start("locked_benchmark_run", "digest-at-start", "m", False, state_file)
        problems = locked_benchmark.verify(run_state_file=state_file)
        self.assertTrue(any("no longer a valid holdout" in p for p in problems))


def _control_inputs():
    """A small synthetic decision: three real candidates (newest first) plus the none option."""
    cands = {"CH030402": "api_contract_change on CM120 started 2026-01-13 22:07:00",
             "CH013876": "policy_change on CM114 started 2026-01-13 02:09:00",
             "CH027929": "deployment on CM229 started 2026-01-11 20:30:00 (version 1.1 -> 1.2, rolling rollout)",
             "none": "No recent change is causally related to this incident"}
    cmeta = {"candidate_generation_version": "v3", "key_mode": "canonical", "num_real_change_candidates": 3}
    state = {"ticket": {"reported_symptoms": ["login failure"]}, "deployed_components": ["CM120"], "technical_evidence": {"signals": []}}
    return state, cands, cmeta


class OpaqueKeyControlTests(unittest.TestCase):
    def test_keys_are_deterministic_distinct_and_well_formed(self):
        ids = ["CH030402", "CH013876", "CH027929"]
        first, again = opaque_control.opaque_keys("CS00005", ids), opaque_control.opaque_keys("CS00005", list(reversed(ids)))
        self.assertEqual(first, again)  # independent of the order the ids are presented in
        self.assertEqual(len(set(first.values())), 3)
        self.assertTrue(all(opaque_control.KEY_PATTERN.match(k) and k != "none" for k in first.values()))
        self.assertNotEqual(first, opaque_control.opaque_keys("CS00006", ids))  # a key does not carry over between cases

    def test_a_key_depends_only_on_case_and_id_not_on_position_or_neighbours(self):
        alone = opaque_control.opaque_keys("CS00005", ["CH013876"])["CH013876"]
        crowded = opaque_control.opaque_keys("CS00005", ["CH030402", "CH013876", "CH027929"])["CH013876"]
        self.assertEqual(alone, crowded)

    def test_keys_encode_neither_id_order_nor_id_shape(self):
        keys = [opaque_control.opaque_keys("CS00001", [f"CH{n:06d}"])[f"CH{n:06d}"] for n in range(30000, 30040)]
        self.assertNotEqual(keys, sorted(keys))  # not monotone in the id number
        self.assertTrue(all(len(k) == len(keys[0]) and k.startswith("opt_") for k in keys))
        self.assertEqual(len(set(keys)), len(keys))  # distinct ids give distinct keys

    def test_a_faithful_opaque_arm_passes_every_equivalence_check(self):
        state, cands, cmeta = _control_inputs()
        opaque_meta = opaque_control.apply_key_scheme("CS00005", cands, cmeta, True)
        self.assertEqual(opaque_control.equivalence_problems("CS00005", state, cands, cmeta, opaque_meta), [])
        self.assertEqual(list(opaque_meta["alias_to_id"].values()), ["CH030402", "CH013876", "CH027929"])  # candidate order kept

    def test_the_model_facing_request_carries_no_canonical_id_but_maps_back_exactly(self):
        state, cands, cmeta = _control_inputs()
        opaque_meta = opaque_control.apply_key_scheme("CS00005", cands, cmeta, True)
        requests = opaque_control.build_requests(state, cands, opaque_meta)
        for label in ("jev", "llm"):
            text = json.dumps(requests[label])
            self.assertFalse(any(cid in text for cid in ("CH030402", "CH013876", "CH027929")), label)
        self.assertEqual(list(requests["model_cands"])[-1], "none")
        answer = {"choice": next(iter(opaque_meta["alias_to_id"])), "confidence": 0.9, "probabilities": {"none": 0.1, next(iter(opaque_meta["alias_to_id"])): 0.9}}
        mapped = candidates_mod.to_canonical_answer(answer, opaque_meta)
        self.assertEqual(mapped["choice"], "CH030402")
        self.assertEqual(set(mapped["probabilities"]), {"none", "CH030402"})

    def test_a_canonical_id_left_in_the_state_is_caught(self):
        state, cands, cmeta = _control_inputs()
        state["technical_evidence"]["note"] = "see CH030402"
        opaque_meta = opaque_control.apply_key_scheme("CS00005", cands, cmeta, True)
        problems = opaque_control.equivalence_problems("CS00005", state, cands, cmeta, opaque_meta)
        self.assertTrue(any("still contains canonical id CH030402" in p for p in problems), problems)

    def test_reordered_or_altered_options_are_caught(self):
        state, cands, cmeta = _control_inputs()
        opaque_meta = opaque_control.apply_key_scheme("CS00005", cands, cmeta, True)
        items = list(opaque_meta["alias_to_id"].items())
        swapped = {**opaque_meta, "alias_to_id": dict([items[1], items[0], items[2]])}
        self.assertTrue(opaque_control.equivalence_problems("CS00005", state, cands, cmeta, swapped))
        dropped = {**opaque_meta, "alias_to_id": dict(items[:2])}
        self.assertTrue(any("alias map" in p for p in opaque_control.equivalence_problems("CS00005", state, cands, cmeta, dropped)))
        malformed = {**opaque_meta, "alias_to_id": {"CH999999": "CH030402", **dict(items[1:])}}
        self.assertTrue(any("malformed" in p for p in opaque_control.equivalence_problems("CS00005", state, cands, cmeta, malformed)))

    def test_reference_check_rejects_inputs_that_differ_from_stage_c(self):
        state, cands, cmeta = _control_inputs()
        stored = {"state": json.loads(json.dumps(state)), "candidates": dict(cands), "candidate_meta": dict(cmeta), "as_of": "2026-01-14"}
        self.assertEqual(opaque_control.reference_problems("CS00005", "2026-01-14", state, cands, cmeta, stored, stored), [])
        changed = {**stored, "candidates": {**cands, "CH030402": "something else"}}
        self.assertTrue(opaque_control.reference_problems("CS00005", "2026-01-14", state, cands, cmeta, changed, stored))
        reordered = {**stored, "candidates": dict(reversed(list(cands.items())))}
        self.assertTrue(opaque_control.reference_problems("CS00005", "2026-01-14", state, cands, cmeta, stored, reordered))
        self.assertTrue(opaque_control.reference_problems("CS00005", "2026-01-15", state, cands, cmeta, stored, stored))
        self.assertTrue(opaque_control.reference_problems("CS00005", "2026-01-14", state, cands, cmeta, None, stored))

    def test_a_none_only_decision_is_byte_identical_in_both_arms(self):
        state, _, cmeta = _control_inputs()
        cands = {"none": "No recent change is causally related to this incident"}
        opaque_meta = opaque_control.apply_key_scheme("CS00007", cands, cmeta, True)
        self.assertEqual(opaque_meta["alias_to_id"], {})
        self.assertEqual(json.dumps(opaque_control.build_requests(state, cands, cmeta)), json.dumps(opaque_control.build_requests(state, cands, opaque_meta)))
        self.assertFalse(opaque_control.is_nontrivial(cands))

    def test_the_control_module_is_not_part_of_the_sealed_locked_source_list(self):
        pinned = set(frozen_config.load_manifest(locked_benchmark.NAME)["source_file_sha256"])
        self.assertNotIn("agent/jev_v2/opaque_control.py", pinned)
        self.assertNotIn("agent/jev_v2/opaque_control_report.py", pinned)
        self.assertEqual(locked_benchmark.verify(), [])  # adding the control changed no sealed file


class SupersessionRecordTests(unittest.TestCase):
    """The v1 locked freeze is recorded as superseded before use (JEV-036); the record must describe the sealed artifacts exactly."""

    def setUp(self):
        self.path = locked_benchmark.FROZEN_DIR / f"{locked_benchmark.NAME}_superseded.json"
        if not self.path.exists():
            self.skipTest("the freeze has not been superseded")
        self.record = json.loads(self.path.read_text())

    def test_the_record_matches_the_sealed_configuration_and_manifest_byte_for_byte(self):
        manifest = frozen_config.load_manifest(locked_benchmark.NAME)
        self.assertEqual(self.record["preserved"]["config_sha256"], frozen_config.sha256_file(frozen_config.config_path(locked_benchmark.NAME)))
        self.assertEqual(self.record["preserved"]["config_sha256"], manifest["config_sha256"])
        self.assertEqual(self.record["preserved"]["manifest_sha256"], frozen_config.sha256_file(locked_benchmark.manifest_path(locked_benchmark.NAME)))

    def test_the_record_states_that_the_locked_split_was_not_opened_and_that_it_is_not_machine_enforced(self):
        self.assertEqual(self.record["status"], "superseded_before_use")
        self.assertFalse(self.record["locked_split"]["opened"])
        self.assertIsNone(locked_benchmark.read_run_state())
        self.assertFalse(self.record["enforcement"]["machine_enforced"])  # the sealed runner does not read this file

    def test_the_record_cites_the_pre_registered_protocol_by_digest(self):
        self.assertEqual(self.record["evidence"]["protocol_sha256"], frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / self.record["evidence"]["protocol"]))


if __name__ == "__main__":
    unittest.main()
