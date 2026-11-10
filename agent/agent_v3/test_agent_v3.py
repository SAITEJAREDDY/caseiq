"""Offline tests for the Phase 9A contract-hardened agent (no API call, no graph call).
Run with: python3 -m unittest agent.agent_v3.test_agent_v3

The scripted model chooses values from the schema it is handed (as the schema-constrained provider would), or emits deliberately bad output to
exercise the deterministic validators, the repair budgets and the failure states."""
import ast
import copy
import json
import unittest
from pathlib import Path

from agent.agent_v3 import catalog as K
from agent.agent_v3 import final_contract as F
from agent.agent_v3 import loop, prompts
from agent.agent_v3.llm import LLMResult
from agent.agent_v3.registry import ID_RE, ObservedEntityRegistry, expose_result, leaked_ids

CASE = "CS00001"
CANONICAL_IDS = ["CM100", "CM101", "SG0000001", "CH000001", "RC01", "RC02", "RC40", "IC01", "IC02", "P001", "C00001", "TM01", "INC001"]


class FakeBackend:
    """Canned tool results with canonical ids, as the Phase 5 query functions return them."""
    def __init__(self):
        self.calls = []

    def case_context(self):
        return {"case_id": CASE, "title": "Login fails for SSO users", "description": "Users cannot sign in; error mentions CM100 handshake.",
                "environment": "prod", "region": "us", "reported_business_impact": "high", "reported_affected_users": 40, "priority": "P2",
                "created_date": "2026-03-01", "status": "open", "customer_id": "C00001", "customer_tier": "gold", "customer_industry": "retail",
                "customer_company_size": "large", "reported_product_id": "P001", "reported_product_name": "Auth Suite", "reported_symptoms": ["login failure"]}

    def taxonomy(self):
        return [("IC01", "Authentication"), ("IC02", "Networking")], [("RC01", "expired certificate"), ("RC02", "misconfiguration"),
                                                                       ("RC40", "insufficient information to determine root cause")]

    def component_names(self, ids):
        return {i: {"CM100": "Auth Gateway", "CM101": "Token Service"}.get(i, i) for i in ids}

    def execute(self, tool, a, as_of):
        self.calls.append((tool, dict(a), as_of))
        if tool == "get_customer_deployment":
            return {"deployments": [{"product_id": "P001", "product_name": "Auth Suite", "version": "1.2", "environment": "prod", "region": "us",
                                     "status": "active", "deployed_at": "2026-01-01", "product_components": ["CM100", "CM101"]}]}
        if tool == "get_technical_signals":
            return {"signals": [{"evidence_id": "SG0000001", "signal_type": "TLS_FAILURE", "message": "handshake failed on CM100",
                                 "timestamp": "2026-03-01 00:10:00", "component_id": "CM100"}], "count": 1}
        if tool == "get_recent_changes":
            return {"recent_changes": [{"evidence_id": "CH000001", "change_type": "certificate", "component_id": "CM100", "started_at": "2026-02-28 20:00:00",
                                        "status": "completed", "initiated_by": "ops", "time_proximity_hours": 4.0, "scope_match": True}], "count": 1}
        if tool == "get_component_topology":
            return {"component_id": a["component_id"], "component_name": "Auth Gateway", "upstream_dependencies": [{"id": "CM101", "name": "Token Service"}],
                    "downstream_dependents": [], "external_dependencies": [], "owning_teams": [{"id": "TM01", "name": "Identity"}]}
        if tool == "get_active_incidents":
            return {"incidents": [{"evidence_id": "INC001", "region": "us", "started_at": "2026-03-01 00:00:00", "severity": "high", "status": "active",
                                   "summary": "Regional auth slowdown", "affected_components": ["CM100"]}], "count": 1}
        return {"note": "no data"}


class ScriptedLLM:
    """Each script item is a dict/str, or a callable(schema) -> dict/str. Records every request so tests can inspect what the model was shown."""
    def __init__(self, script):
        self.script, self.requests = list(script), []

    def complete(self, messages, schema, name, max_tokens):
        self.requests.append({"messages": messages, "schema": schema, "name": name})
        if not self.script:
            raise AssertionError("scripted model ran out of outputs")
        item = self.script.pop(0)
        item = item(schema) if callable(item) else item
        return LLMResult(item if isinstance(item, str) else json.dumps(item), "stop", 100, 50, 5.0)


def enum_of(schema, prop):
    p = schema["properties"][prop]
    p = p["anyOf"][0] if "anyOf" in p else p
    return p.get("enum", [])


H0 = {"label": "initial hypothesis", "confidence": 0.4, "status": "active", "supporting_evidence": [], "contradicting_evidence": []}


def action(tool, hyps=None, **args):
    base = {"hypotheses": list(hyps) if hyps else [dict(H0)], "tool": tool, "component": None, "metric_category": None, "keyword": None, "team": None}
    base.update(args)
    return base


def pick_component(tool, idx=0, hyps=()):
    return lambda schema: action(tool, hyps, component=enum_of(schema, "component")[idx])


def final_answer(schema, **over):
    cites = enum_of(schema["properties"]["evidence_ids"], "items") if False else schema["properties"]["evidence_ids"].get("items", {}).get("enum", [])
    obj = {"hypotheses": [dict(H0)], "evidence_ids": [], "issue_category": None, "category_confidence": None, "root_cause": None, "root_cause_confidence": None,
           "affected_component": None, "component_confidence": None, "causal_change": None, "causal_change_confidence": None, "owning_team": None,
           "routing_confidence": None, "confidence": 0.3, "evidence_sufficiency": "insufficient", "human_review_required": True, "review_reason": "evidence is thin",
           "status": "INSUFFICIENT_EVIDENCE", "recommended_next_action": "request customer confirmation", "unresolved_uncertainties": ["cause unknown"],
           "summary": "Not enough evidence to name a cause."}
    obj.update(over)
    return obj, cites


def good_final(schema):
    """A valid DIAGNOSIS_PROPOSED built from whatever the schema offers."""
    cites = schema["properties"]["evidence_ids"]["items"]["enum"]
    change = [c for c in cites if c.startswith("CHANGE_")][0]
    sig = [c for c in cites if c.startswith("EVIDENCE_")][0]
    obj, _ = final_answer(schema, hypotheses=[{"label": "certificate expiry", "confidence": 0.7, "status": "active", "supporting_evidence": [sig, change],
                                                "contradicting_evidence": []}], evidence_ids=[sig, change],
                          issue_category=enum_of(schema, "issue_category")[0], category_confidence=0.6,
                          root_cause=enum_of(schema, "root_cause")[0], root_cause_confidence=0.6,
                          affected_component=enum_of(schema, "affected_component")[0], component_confidence=0.7,
                          causal_change=change, causal_change_confidence=0.65, confidence=0.7, evidence_sufficiency="partial",
                          human_review_required=False, review_reason=None, status="DIAGNOSIS_PROPOSED")
    return obj


def run(script, backend=None):
    llm = ScriptedLLM(script)
    backend = backend or FakeBackend()
    return loop.run_case(CASE, backend, llm), llm, backend


def registry_with_evidence():
    reg = ObservedEntityRegistry(CASE)
    for cid, name in [("IC01", "Authentication")]:
        reg.add("CATEGORY", cid, display_name=name, source_tool="taxonomy", step=0, clock="t")
    for cid, name in [("RC01", "expired certificate"), ("RC40", "insufficient information")]:
        reg.add("CAUSE", cid, display_name=name, source_tool="taxonomy", step=0, clock="t")
    expose_result(reg, "get_customer_deployment", FakeBackend().execute("get_customer_deployment", {}, "t"), step=2, clock="t")
    expose_result(reg, "get_technical_signals", FakeBackend().execute("get_technical_signals", {}, "t"), step=3, clock="t")
    expose_result(reg, "get_recent_changes", FakeBackend().execute("get_recent_changes", {}, "t"), step=4, clock="t")
    return reg


def valid_final_for(reg):
    sig = reg.aliases("EVIDENCE")[0]
    chg = reg.aliases("CHANGE")[0]
    obj, _ = final_answer({"properties": {"evidence_ids": {}}}, hypotheses=[{"label": "cert", "confidence": 0.7, "status": "active", "supporting_evidence": [sig],
                                                                            "contradicting_evidence": []}], evidence_ids=[sig, chg],
                          causal_change=chg, causal_change_confidence=0.5, confidence=0.6, evidence_sufficiency="partial", human_review_required=False,
                          review_reason=None, status="DIAGNOSIS_PROPOSED")
    return obj


class TestRegressionFromPhase5(unittest.TestCase):
    """The nine regression tests required by the Phase 9A spec (section 43)."""

    def test_1_phantom_tool_name_is_rejected(self):
        reg = registry_with_evidence()
        _, errors = K.validate_action(action("get_system_logs"), reg)
        self.assertEqual([e["code"] for e in errors], ["unknown_tool"])
        result, llm, backend = run([action("get_system_logs"), action("get_customer_deployment"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        self.assertEqual(result["tool_contract_errors"][0]["errors"][0]["code"], "unknown_tool")
        self.assertNotIn("get_system_logs", [c[0] for c in backend.calls])  # rejected before anything executed
        self.assertEqual(result["tool_contract_repairs"][0]["outcome"], "accepted")
        self.assertEqual(result["repair_events"][0]["kind"], "tool_contract_repair")

    def test_2_unknown_tool_argument_alias_is_rejected(self):
        reg = registry_with_evidence()
        cases = {"COMPONENT_ZZZ": "unknown_alias", "CM100": "canonical_id_used", reg.aliases("CHANGE")[0]: "alias_wrong_kind", 7: "bad_type"}
        for value, code in cases.items():
            _, errors = K.validate_action(action("get_component_topology", component=value), reg)
            self.assertIn(code, [e["code"] for e in errors], (value, errors))
        _, errors = K.validate_action(action("get_component_topology"), reg)  # a required argument left null
        self.assertIn("argument_required", [e["code"] for e in errors])
        _, errors = K.validate_action(action("get_active_incidents", component=reg.aliases("COMPONENT")[0]), reg)
        self.assertIn("argument_not_allowed", [e["code"] for e in errors])

    def test_3_invented_root_cause_id_cannot_enter_the_final_output(self):
        reg = registry_with_evidence()
        for bad, code in (("RC17", "canonical_id_used"), ("CAUSE_QQQ", "unknown_alias"), (reg.aliases("CATEGORY")[0], "alias_wrong_kind")):
            obj = valid_final_for(reg)
            obj.update(root_cause=bad, root_cause_confidence=0.5)
            final, errors = F.validate_final(obj, reg)
            self.assertIsNone(final)
            self.assertIn(code, [e["code"] for e in errors], (bad, errors))
        text = valid_final_for(reg)
        text["summary"] = "Likely RC17."
        self.assertIn("canonical_id_used", [e["code"] for e in F.validate_final(text, reg)[1]])

    def test_4_unretrieved_evidence_cannot_be_cited(self):
        reg = registry_with_evidence()
        obj = valid_final_for(reg)
        obj["evidence_ids"] = obj["evidence_ids"] + ["EVIDENCE_QQQ"]
        codes = [e["code"] for e in F.validate_final(obj, reg)[1]]
        self.assertIn("evidence_not_retrieved", codes)
        obj = valid_final_for(reg)
        obj["hypotheses"][0]["supporting_evidence"] = ["CHANGE_QQQ"]
        self.assertIn("evidence_not_retrieved", [e["code"] for e in F.validate_final(obj, reg)[1]])
        obj = valid_final_for(reg)
        obj["evidence_ids"] = [obj["evidence_ids"][0]] * 2
        self.assertIn("duplicate_evidence", [e["code"] for e in F.validate_final(obj, reg)[1]])
        obj = valid_final_for(reg)
        obj["evidence_ids"] = [reg.aliases("COMPONENT")[0]]  # an entity that is not evidence
        self.assertIn("alias_wrong_kind", [e["code"] for e in F.validate_final(obj, reg)[1]])

    def test_5_valid_abstention_passes(self):
        reg = ObservedEntityRegistry(CASE)
        obj, _ = final_answer({"properties": {"evidence_ids": {}}})
        final, errors = F.validate_final(obj, reg)
        self.assertEqual(errors, [])
        mapped = F.to_phase5_final(final, reg)
        self.assertIsNone(mapped["predicted_root_cause_family"])
        self.assertEqual(mapped["status"], "INSUFFICIENT_EVIDENCE")
        human = copy.deepcopy(obj)
        human.update(status="HUMAN_REVIEW_REQUIRED", human_review_required=True, review_reason="conflicting signals")
        self.assertEqual(F.validate_final(human, reg)[1], [])

    def test_6_malformed_final_triggers_exactly_one_repair(self):
        bad = lambda s: {"status": "DIAGNOSIS_PROPOSED"}
        result, llm, _ = run([action(K.SUBMIT), bad, lambda s: final_answer(s)[0]])
        v = result["validation_result"]
        self.assertFalse(v["first_pass_ok"])
        self.assertTrue(v["repair_used"])
        self.assertTrue(v["final_ok"])
        self.assertEqual(result["final_contract_repair"]["outcome"], "accepted")
        self.assertEqual([r["name"] for r in llm.requests].count("final"), 2)
        self.assertEqual(result["stop_reason"], "model_submitted")
        self.assertEqual(result["final_status"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("CONTRACT ERROR", llm.requests[-1]["messages"][1]["content"])  # the correction carried the validation errors

    def test_7_second_malformed_final_is_a_contract_failure(self):
        bad = lambda s: {"status": "DIAGNOSIS_PROPOSED"}
        result, llm, _ = run([action(K.SUBMIT), bad, bad])
        self.assertEqual(result["final_status"], "CONTRACT_FAILURE")
        self.assertEqual(result["stop_reason"], "final_contract_failure")
        self.assertTrue(result["final_diagnosis"]["human_review_required"])
        self.assertEqual(result["final_diagnosis"]["hypotheses"], [])
        self.assertFalse(result["validation_result"]["final_ok"])
        self.assertEqual([r["name"] for r in llm.requests].count("final"), 2)  # never a third attempt

    def test_8_alias_maps_deterministically_to_canonical_id(self):
        a, b = registry_with_evidence(), registry_with_evidence()
        self.assertEqual({k: v["canonical_id"] for k, v in a.mapping().items()}, {k: v["canonical_id"] for k, v in b.mapping().items()})
        for alias, ent in a.mapping().items():
            self.assertEqual(a.canonical(alias), ent["canonical_id"])
        self.assertNotEqual(ObservedEntityRegistry("CS00002").add("COMPONENT", "CM100", source_tool="x", step=1, clock="t").alias,
                            ObservedEntityRegistry(CASE).add("COMPONENT", "CM100", source_tool="x", step=1, clock="t").alias)
        reg = registry_with_evidence()
        mapped = F.to_phase5_final(F.validate_final(valid_final_for(reg), reg)[0], reg)
        self.assertEqual(mapped["predicted_causal_change_id"], "CH000001")
        self.assertEqual(mapped["evidence_ids"], ["SG0000001", "CH000001"])

    def test_9_no_hidden_truth_populates_the_registry(self):
        result, llm, backend = run([action("get_customer_deployment"), action("get_technical_signals"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        sources = {e["source_tool"] for e in result["alias_mappings"].values()}
        self.assertLessEqual(sources, {"taxonomy", "get_case_context", "get_customer_deployment", "get_technical_signals", "prose"})
        for e in result["alias_mappings"].values():
            self.assertNotRegex(e["alias"], r"\d")  # no number, order or id structure in an alias
        for mod in ("registry", "catalog", "final_contract", "loop", "prompts", "llm", "backend", "config"):
            tree = ast.parse((Path(loop.__file__).parent / f"{mod}.py").read_text())
            names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
            for n in names:
                self.assertNotRegex(n, r"eval_store|eval_v2|ground_truth|trace_eval_v2|jev_v2", f"{mod} imports {n}")


class TestLoopBehaviour(unittest.TestCase):
    def test_happy_path_first_pass(self):
        result, llm, backend = run([action("get_customer_deployment"), action("get_technical_signals"), action("get_recent_changes"), action(K.SUBMIT), good_final])
        self.assertEqual(result["stop_reason"], "model_submitted")
        self.assertEqual(result["final_status"], "DIAGNOSIS_PROPOSED")
        self.assertEqual(result["tool_contract_errors"], [])
        self.assertTrue(result["validation_result"]["first_pass_ok"])
        self.assertEqual(result["repair_events"], [])
        fd = result["final_diagnosis"]
        self.assertEqual(fd["predicted_causal_change_id"], "CH000001")
        self.assertEqual(fd["predicted_component_id"], "CM100")
        self.assertEqual(fd["predicted_category_id"], "IC01")
        self.assertEqual(fd["predicted_root_cause_family"], "expired certificate")  # the Phase 6 field holds the root-cause name
        self.assertEqual(result["citation_violations"], [])
        self.assertEqual(result["trace_steps"][0]["proposed_by"], "harness")
        self.assertEqual(result["trace_steps"][-1]["tool_name"], K.SUBMIT)

    def test_no_canonical_id_ever_reaches_the_model(self):
        result, llm, _ = run([action("get_customer_deployment"), pick_component("get_component_topology"), action("get_technical_signals"),
                              action("get_active_incidents"), action(K.SUBMIT), good_final if False else (lambda s: final_answer(s)[0])])
        for req in llm.requests:
            text = "\n".join(m["content"] for m in req["messages"]) + json.dumps(req["schema"])
            for cid in CANONICAL_IDS:
                self.assertNotIn(cid, text, f"{cid} was shown to the model")
            self.assertEqual(leaked_ids({"t": text}), [])

    def test_component_tools_are_not_offered_before_a_component_is_seen(self):
        result, llm, _ = run([action("get_customer_deployment"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        first = llm.requests[0]["schema"]
        self.assertNotIn("get_component_topology", enum_of(first, "tool"))
        self.assertNotIn("get_service_health", enum_of(first, "tool"))
        self.assertNotIn("get_agent_availability", enum_of(first, "tool"))
        self.assertIn("get_technical_signals", enum_of(first, "tool"))
        second = llm.requests[1]["schema"]
        self.assertIn("get_component_topology", enum_of(second, "tool"))
        _, errors = K.validate_action(action("get_component_topology", component=None), ObservedEntityRegistry(CASE))
        self.assertIn("tool_unavailable", [e["code"] for e in errors])

    def test_tool_repair_budget_is_two_then_contract_failure(self):
        bad = action("get_system_logs")
        result, llm, backend = run([bad, bad, bad])
        self.assertEqual(result["stop_reason"], "tool_contract_repair_budget_exhausted")
        self.assertEqual(result["final_status"], "CONTRACT_FAILURE")
        self.assertEqual(len(result["tool_contract_repairs"]), 2)
        self.assertEqual(len(result["tool_contract_errors"]), 3)
        self.assertTrue(result["final_diagnosis"]["human_review_required"])
        self.assertEqual([r["name"] for r in llm.requests].count("final"), 0)  # the investigation stopped; no final call
        self.assertEqual(backend.calls, [])

    def test_repairs_are_budgeted_per_run_not_per_step(self):
        bad = action("get_system_logs")
        result, _, _ = run([bad, action("get_customer_deployment"), bad, action("get_technical_signals"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        self.assertEqual(result["stop_reason"], "model_submitted")
        self.assertEqual([r["outcome"] for r in result["tool_contract_repairs"]], ["accepted", "accepted"])
        result2, _, _ = run([bad, action("get_customer_deployment"), bad, action("get_technical_signals"), bad, action(K.SUBMIT)])
        self.assertEqual(result2["stop_reason"], "tool_contract_repair_budget_exhausted")

    def test_invalid_json_and_extra_fields_are_rejected(self):
        reg = registry_with_evidence()
        self.assertEqual(K.validate_action("not json", reg)[1][0]["code"], "not_json")
        self.assertEqual(K.validate_action("[1]", reg)[1][0]["code"], "not_json")
        extra = action("get_customer_deployment")
        extra["case_id"] = CASE
        self.assertIn("unknown_field", [e["code"] for e in K.validate_action(extra, reg)[1]])
        missing = action("get_customer_deployment")
        del missing["team"]
        self.assertIn("missing_field", [e["code"] for e in K.validate_action(missing, reg)[1]])

    def test_hypothesis_state_is_validated_on_every_step(self):
        reg = registry_with_evidence()
        sig = reg.aliases("EVIDENCE")[0]
        good = [{"label": "cert", "confidence": 0.5, "status": "active", "supporting_evidence": [sig], "contradicting_evidence": []}]
        self.assertEqual(K.validate_action(action("get_customer_deployment", good), reg)[1], [])
        for patch, code in (({"status": "open"}, "bad_enum"), ({"confidence": 1.4}, "confidence_range"), ({"supporting_evidence": ["EVIDENCE_QQQ"]}, "evidence_not_retrieved"),
                            ({"supporting_evidence": [sig, sig]}, "duplicate_evidence"), ({"label": ""}, "bad_value"), ({"extra": 1}, "unknown_field")):
            h = [dict(good[0], **patch)]
            self.assertIn(code, [e["code"] for e in K.validate_action(action("get_customer_deployment", h), reg)[1]], patch)
        five = good * 5
        self.assertIn("too_many_hypotheses", [e["code"] for e in K.validate_action(action("get_customer_deployment", five), reg)[1]])

    def test_redundant_identical_call_is_not_reexecuted(self):
        result, _, backend = run([action("get_customer_deployment")] * 3 + [action(K.SUBMIT), lambda s: final_answer(s)[0]])
        self.assertEqual([c[0] for c in backend.calls].count("get_customer_deployment"), 2)  # the 3rd identical call is redundant (limit 2, as in Phase 5)
        self.assertEqual([s["status"] for s in result["trace_steps"] if s["tool_name"] == "get_customer_deployment"], ["ok", "ok", "redundant"])

    def test_tool_budget_forces_finalization_and_counts_like_phase5(self):
        script = [action("get_customer_deployment"), action("get_technical_signals"), action("get_recent_changes"), action("get_active_incidents"),
                  action("get_similar_cases"), action("get_customer_deployment", keyword=None) if False else action("search_knowledge_base", keyword="tls"),
                  action("get_telemetry"), action("get_telemetry", metric_category="Networking"), action("get_telemetry", metric_category="Identity"),
                  lambda s: final_answer(s)[0]]
        result, llm, _ = run(script)
        self.assertEqual(result["stop_reason"], "tool_budget_exhausted")
        self.assertEqual(result["num_tool_calls"], 11)  # 10 diagnostic steps (incl. the harness case-context step) + the submit
        self.assertEqual(result["trace_steps"][-1]["result_summary"], "submitted (forced)")
        self.assertIn("budget is exhausted", llm.requests[-1]["messages"][1]["content"])

    def test_forced_final_contract_failure_is_a_failure(self):
        # a run that reaches finalization with an unrecoverable answer is CONTRACT_FAILURE, never a repaired-looking diagnosis
        result, _, _ = run([action(K.SUBMIT), "not json", "still not json"])
        self.assertEqual(result["final_status"], "CONTRACT_FAILURE")
        self.assertEqual(result["validation_result"]["errors_first"][0]["code"], "not_json")

    def test_contract_fields_are_recorded(self):
        result, _, _ = run([action("get_system_logs"), action("get_customer_deployment"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        for key in ("tool_contract_errors", "tool_contract_repairs", "final_contract_errors", "final_contract_repair", "registry_snapshots", "alias_mappings",
                    "validation_result", "tool_proposals", "llm_calls", "final_alias_form"):
            self.assertIn(key, result)
        self.assertEqual(result["tool_proposals"], 3)  # bad, deployment, submit (the final answer is not a tool proposal)
        self.assertGreaterEqual(len(result["registry_snapshots"]), 2)
        self.assertTrue(all(c["phase"] in ("action", "final") for c in result["llm_calls"]))


class TestFinalContract(unittest.TestCase):
    def setUp(self):
        self.reg = registry_with_evidence()

    def errors(self, **over):
        obj = valid_final_for(self.reg)
        obj.update(over)
        return [e["code"] for e in F.validate_final(obj, self.reg)[1]]

    def test_valid_proposal(self):
        self.assertEqual(self.errors(), [])

    def test_status_requirements(self):
        self.assertIn("proposed_without_supported_hypothesis", self.errors(hypotheses=[]))
        rejected = valid_final_for(self.reg)["hypotheses"]
        rejected[0]["status"] = "rejected"
        self.assertIn("proposed_without_supported_hypothesis", self.errors(hypotheses=rejected))
        self.assertIn("status_sufficiency_conflict", self.errors(evidence_sufficiency="insufficient"))
        self.assertIn("status_sufficiency_conflict", self.errors(status="INSUFFICIENT_EVIDENCE", evidence_sufficiency="sufficient"))
        self.assertIn("review_flag_missing", self.errors(status="HUMAN_REVIEW_REQUIRED", human_review_required=False, review_reason="x"))
        self.assertIn("review_reason_missing", self.errors(status="HUMAN_REVIEW_REQUIRED", human_review_required=True, review_reason=None))
        self.assertIn("bad_enum", self.errors(status="CONTRACT_FAILURE"))  # never model-selectable

    def test_nullability_and_confidence(self):
        self.assertIn("confidence_required", self.errors(root_cause=self.reg.aliases("CAUSE")[0], root_cause_confidence=None))
        self.assertIn("confidence_without_selection", self.errors(root_cause=None, root_cause_confidence=0.4))
        self.assertIn("confidence_range", self.errors(confidence=1.2))
        self.assertIn("confidence_required", self.errors(root_cause=self.reg.aliases("CAUSE")[0], root_cause_confidence=-0.1))
        self.assertIn("confidence_range", self.errors(confidence=True))

    def test_grounding_rules(self):
        self.assertIn("selection_without_citation", self.errors(evidence_ids=[], causal_change=None, causal_change_confidence=None,
                                                                affected_component=self.reg.aliases("COMPONENT")[0], component_confidence=0.5,
                                                                hypotheses=[dict(valid_final_for(self.reg)["hypotheses"][0], supporting_evidence=[])]))
        self.assertIn("causal_change_not_cited", self.errors(evidence_ids=[self.reg.aliases("EVIDENCE")[0]]))
        h = valid_final_for(self.reg)["hypotheses"]
        h[0]["supporting_evidence"] = self.reg.aliases("EVIDENCE") + self.reg.aliases("CHANGE")
        self.assertEqual(self.errors(hypotheses=h), [])
        self.assertIn("hypothesis_citation_not_in_evidence_ids", self.errors(evidence_ids=[self.reg.aliases("CHANGE")[0]]))

    def test_structure(self):
        obj = valid_final_for(self.reg)
        del obj["summary"]
        self.assertEqual(F.validate_final(obj, self.reg)[1][0]["code"], "missing_field")
        obj = valid_final_for(self.reg)
        obj["rationale"] = "free text"
        self.assertIn("unknown_field", [e["code"] for e in F.validate_final(obj, self.reg)[1]])
        self.assertEqual(F.validate_final("nope", self.reg)[1][0]["code"], "not_json")

    def test_text_fields_may_mention_real_aliases_only(self):
        self.assertEqual(self.errors(summary=f"See {self.reg.aliases('CHANGE')[0]}."), [])
        self.assertIn("unknown_alias", self.errors(summary="See CHANGE_QQQ."))

    def test_contract_failure_final_pretends_nothing(self):
        cf = F.contract_failure_final("x")
        self.assertEqual(cf["status"], "CONTRACT_FAILURE")
        self.assertEqual(cf["hypotheses"], [])
        self.assertTrue(cf["human_review_required"])
        self.assertIsNone(cf["predicted_root_cause_family"])


class TestRegistryAndSchemas(unittest.TestCase):
    def test_result_exposure_hides_canonical_ids_and_registers_entities(self):
        reg = ObservedEntityRegistry(CASE)
        out = expose_result(reg, "get_technical_signals", FakeBackend().execute("get_technical_signals", {}, "t"), step=2, clock="t",
                            name_lookup=FakeBackend().component_names)
        self.assertEqual(leaked_ids(out), [])
        row = out["signals"][0]
        self.assertTrue(row["evidence_id"].startswith("EVIDENCE_"))
        self.assertTrue(row["component_id"].startswith("COMPONENT_"))
        self.assertNotIn("CM100", row["message"])
        self.assertEqual(reg.get(row["component_id"]).display_name, "Auth Gateway")
        self.assertEqual(reg.canonical(row["evidence_id"]), "SG0000001")

    def test_case_report_drops_ids_and_aliases_the_product(self):
        reg = ObservedEntityRegistry(CASE)
        out = expose_result(reg, "get_case_context", FakeBackend().case_context(), step=1, clock="t")
        self.assertNotIn("case_id", out)
        self.assertNotIn("customer_id", out)
        self.assertTrue(out["reported_product_id"].startswith("PRODUCT_"))
        self.assertEqual(reg.get(out["reported_product_id"]).display_name, "Auth Suite")
        self.assertEqual(leaked_ids(out), [])

    def test_id_mentioned_only_in_text_is_not_citable(self):
        reg = ObservedEntityRegistry(CASE)
        out = reg.scrub("failure also seen near CM555 and CH999999 in CS00001", source_tool="t", step=1, clock="t")
        self.assertEqual(leaked_ids(out), [])
        self.assertIn("THIS_CASE", out)
        self.assertEqual(reg.aliases("EVIDENCE", "CHANGE", "INCIDENT", "COMPONENT"), [])  # REF aliases are never citable or selectable
        ref = [a for a in reg.mapping() if a.startswith("REF_")][0]
        self.assertIsNone(reg.get(ref))
        self.assertEqual(K.check_alias(ref, ("COMPONENT",), reg, "component")["code"], "unknown_alias")
        reg.add("COMPONENT", "CM555", source_tool="t", step=2, clock="t")  # observed later: prose now scrubs to the real alias
        self.assertIn(reg._by_canonical["CM555"].alias, reg.scrub("near CM555"))

    def test_schema_offers_only_registered_values(self):
        reg = registry_with_evidence()
        s = K.action_schema(reg)
        self.assertEqual(set(s["required"]), set(K.ACTION_FIELDS))
        self.assertEqual(set(enum_of(s, "tool")), set(K.available_tools(reg)))
        self.assertEqual(set(enum_of(s, "component")), set(reg.aliases("COMPONENT")))
        self.assertEqual(s["properties"]["team"], {"type": "null"})  # no team observed yet: nothing to choose
        f = F.final_schema(reg)
        self.assertEqual(set(f["required"]), set(F.FINAL_FIELDS))
        self.assertEqual(set(enum_of(f, "causal_change")), set(reg.aliases("CHANGE")))
        self.assertEqual(set(enum_of(f, "root_cause")), set(reg.aliases("CAUSE")))
        self.assertEqual(set(f["properties"]["evidence_ids"]["items"]["enum"]), set(reg.aliases("EVIDENCE", "CHANGE", "INCIDENT")))
        empty = F.final_schema(ObservedEntityRegistry(CASE))
        self.assertEqual(empty["properties"]["evidence_ids"], {"type": "array", "maxItems": 0})
        self.assertEqual(empty["properties"]["root_cause"], {"type": "null"})

    def test_anything_the_schema_allows_for_an_action_passes_the_validator(self):
        reg = registry_with_evidence()
        s = K.action_schema(reg)
        for tool in enum_of(s, "tool"):
            spec = K.TOOLS_BY_NAME[tool]
            args = {}
            for a in spec.required:
                args[a] = {"component": reg.aliases("COMPONENT")[0], "team": None, "metric_category": "Networking", "keyword": "tls"}[a]
            if tool == "get_agent_availability":
                continue  # needs a team, which this registry has none of; the schema (correctly) does not offer it
            self.assertEqual(K.validate_action(action(tool, **args), reg)[1], [], tool)

    def test_catalog_is_single_source(self):
        self.assertEqual(len(K.TOOL_NAMES), len(set(K.TOOL_NAMES)))
        for t in K.TOOLS:
            self.assertIn(t.name, prompts.system_prompt())
        self.assertNotIn("get_system_logs", prompts.system_prompt().replace("There is no raw-log search", ""))
        contract = json.loads(Path(loop.__file__).parent.parent.joinpath("contracts", "agent_contract_v1.json").read_text()) if Path(loop.__file__).parent.parent.joinpath("contracts", "agent_contract_v1.json").exists() else None
        if contract:
            self.assertEqual([t["name"] for t in contract["tools"] if t["available_when"] != "harness only"], list(K.TOOL_NAMES))

    def test_id_pattern_matches_real_id_shapes(self):
        for cid in ("CM230", "SG0000943", "CH030460", "CS00166:CM230:error_rate_pct", "KA0012", "TM04", "RC17", "IC03"):
            self.assertTrue(ID_RE.fullmatch(cid), cid)
        for alias in ("COMPONENT_KZT", "EVIDENCE_QZM", "THIS_CASE"):
            self.assertFalse(ID_RE.search(alias), alias)


class TestProviderClient(unittest.TestCase):
    def _resp(self, code, body=None):
        from unittest import mock
        m = mock.Mock(status_code=code, headers={}, text=json.dumps(body or {}))
        m.json.return_value = body or {}
        return m

    def test_402_is_retried_then_succeeds_and_persistent_402_stops_the_batch(self):
        from unittest import mock
        from agent.agent_v3 import llm as L
        ok = self._resp(200, {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 1}})
        c = L.TogetherJSONClient("k")
        with mock.patch.object(L.time, "sleep"), mock.patch.object(L.requests, "post", side_effect=[self._resp(402), self._resp(402), ok]) as post:
            res = c.complete([{"role": "user", "content": "x"}], {"type": "object"}, "n", 10)
        self.assertEqual((res.content, post.call_count, res.http_retries), ("{}", 3, 2))
        with mock.patch.object(L.time, "sleep"), mock.patch.object(L.requests, "post", side_effect=[self._resp(402)] * 20):
            with self.assertRaises(L.ProviderCreditError):
                c.complete([{"role": "user", "content": "x"}], {"type": "object"}, "n", 10)

    def test_schema_rejection_is_a_harness_error_not_a_model_failure(self):
        from unittest import mock
        from agent.agent_v3 import llm as L
        with mock.patch.object(L.requests, "post", return_value=self._resp(400, {"error": "bad schema"})):
            with self.assertRaises(L.ProviderSchemaError):
                L.TogetherJSONClient("k").complete([{"role": "user", "content": "x"}], {"type": "object"}, "n", 10)


if __name__ == "__main__":
    unittest.main()


class TestEvaluatorMechanics(unittest.TestCase):
    """The protocol metrics are recounted from run records, independently of the validator."""

    def test_recount_flags_invented_and_unobserved_references(self):
        from agent.agent_v3 import evaluate as E
        good, _, _ = run([action("get_customer_deployment"), action("get_technical_signals"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        c = E.recount_references(good)
        self.assertEqual(c["invented_canonical_ids"], 0)
        self.assertEqual(c["evidence_invalid"], 0)
        # a forged run record: the model output cites a canonical id, an unknown alias and an alias observed only later
        forged = copy.deepcopy(good)
        sig = [a for a, e in forged["alias_mappings"].items() if e["kind"] == "EVIDENCE"][0]
        forged["alias_mappings"][sig]["first_observed_step"] = 99
        forged["llm_calls"][-1]["raw_output"] = json.dumps({"evidence_ids": ["SG0000001", "EVIDENCE_QQQ", sig], "hypotheses": [], "root_cause": "RC17"})
        c = E.recount_references(forged)
        self.assertEqual((c["invented_canonical_ids"], c["aliases_outside_registry"], c["cited_before_observed"]), (2, 1, 1))

    def test_protocol_metrics_and_targets_on_scripted_runs(self):
        from agent.agent_v3 import evaluate as E
        bad_tool = action("get_system_logs")
        r1, _, _ = run([action("get_customer_deployment"), action(K.SUBMIT), good_final if False else (lambda s: final_answer(s)[0])])
        r2, _, _ = run([bad_tool, action("get_customer_deployment"), action(K.SUBMIT), lambda s: {"status": "x"}, lambda s: final_answer(s)[0]])
        r3, _, _ = run([bad_tool, bad_tool, bad_tool])
        pm = E.protocol_metrics({"a": r1, "b": r2, "c": r3})
        self.assertEqual(pm["tool_contract"]["hallucinated_tool_name_rate"]["k"], 4)
        self.assertEqual(pm["tool_contract"]["rejected_proposals"], 4)
        self.assertEqual(pm["final_contract"]["runs_reaching_finalization"], 2)
        self.assertEqual(pm["final_contract"]["first_pass_final_valid_rate"]["k"], 1)
        self.assertEqual(pm["final_contract"]["final_valid_after_one_repair_rate"]["k"], 2)
        self.assertEqual(pm["final_contract"]["unrecoverable_by_kind"]["tool_contract_repair_budget_exhausted"], 1)
        self.assertEqual(pm["final_contract"]["unrecoverable_contract_failure_rate"]["k"], 1)
        tc = E.targets_check(pm)
        self.assertFalse(tc["valid_registered_tool_name_rate"]["met"])
        self.assertFalse(tc["unrecoverable_contract_failure_rate"]["met"])
        self.assertTrue(tc["invented_canonical_ids"]["met"])

    def test_every_generated_schema_is_valid_json_schema(self):
        import jsonschema
        reg = registry_with_evidence()
        for schema in (K.action_schema(reg), F.final_schema(reg), K.action_schema(ObservedEntityRegistry(CASE)), F.final_schema(ObservedEntityRegistry(CASE))):
            jsonschema.Draft202012Validator.check_schema(schema)
        # a scripted run's own outputs conform to the schema the provider was given, and the validator agrees with the schema
        llm = ScriptedLLM([action("get_customer_deployment"), action("get_technical_signals"), action("get_recent_changes"), action(K.SUBMIT), good_final])
        result = loop.run_case(CASE, FakeBackend(), llm)
        for req, call in zip(llm.requests, result["llm_calls"]):
            jsonschema.validate(json.loads(call["raw_output"]), req["schema"], cls=jsonschema.Draft202012Validator)


class TestHypothesisStateNonEmpty(unittest.TestCase):
    """The single correction after the 50-case run: 365 of 409 model steps had stated NO hypothesis (the shortest valid completion), which made
    the Phase 5 hypothesis-state mechanism vacuous and forced abstention. An empty hypothesis state is now a contract error and the schema forbids it."""

    def test_empty_hypothesis_state_is_rejected_for_actions_and_finals(self):
        reg = registry_with_evidence()
        empty = action("get_customer_deployment")
        empty["hypotheses"] = []
        self.assertIn("hypotheses_empty", [e["code"] for e in K.validate_action(empty, reg)[1]])
        obj = valid_final_for(reg)
        obj["hypotheses"] = []
        self.assertIn("hypotheses_empty", [e["code"] for e in F.validate_final(obj, reg)[1]])
        self.assertEqual(K.action_schema(reg)["properties"]["hypotheses"]["minItems"], 1)
        self.assertEqual(F.final_schema(reg)["properties"]["hypotheses"]["minItems"], 1)

    def test_a_low_confidence_uncited_hypothesis_satisfies_the_rule(self):
        reg = ObservedEntityRegistry(CASE)
        self.assertEqual(K.validate_action(action("get_customer_deployment"), reg)[1], [])  # first turn, no evidence yet
        obj, _ = final_answer({"properties": {"evidence_ids": {}}})
        self.assertEqual(F.validate_final(obj, reg)[1], [])  # abstention with a stated, uncited hypothesis

    def test_an_empty_state_in_a_run_uses_a_tool_repair(self):
        empty = action("get_customer_deployment")
        empty["hypotheses"] = []
        result, _, _ = run([empty, action("get_customer_deployment"), action(K.SUBMIT), lambda s: final_answer(s)[0]])
        self.assertEqual(result["tool_contract_errors"][0]["errors"][0]["code"], "hypotheses_empty")
        self.assertEqual(result["tool_contract_repairs"][0]["outcome"], "accepted")
