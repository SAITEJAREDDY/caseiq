"""Plumbing check against the real graph with a deterministic stub model (no API call, no cost). It exercises the backend, alias exposure,
schemas and validators on real tool results; it says nothing about the model's behaviour and produces no diagnostic result.

    python3 -m agent.agent_v3.dry_run --n 3      # dev pool cases that are in neither cohort
"""
import argparse
import json
import random

from agent.agent_v3 import catalog as K
from agent.agent_v3.backend import Neo4jBackend
from agent.agent_v3.loop import run_case
from agent.agent_v3.llm import LLMResult
from agent.agent_v3.registry import leaked_ids

ORDER = ["get_customer_deployment", "get_technical_signals", "get_recent_changes", "get_deployment_history", "get_telemetry", "get_active_incidents",
         "get_component_topology", "get_configuration_history", "get_service_health"]


def _enum(schema, prop):
    p = schema["properties"][prop]
    p = p["anyOf"][0] if "anyOf" in p else p
    return p.get("enum", [])


class StubPolicy:
    def __init__(self, seed):
        self.rng, self.i = random.Random(seed), 0

    def complete(self, messages, schema, name, max_tokens):
        blob = "\n".join(m["content"] for m in messages) + json.dumps(schema)
        assert not leaked_ids({"x": blob}), f"canonical id in prompt: {leaked_ids({'x': blob})[:3]}"
        if name == "action":
            tools = _enum(schema, "tool")
            tool = ORDER[self.i] if self.i < len(ORDER) and ORDER[self.i] in tools else K.SUBMIT
            self.i += 1
            comps = _enum(schema, "component")
            spec = K.TOOLS_BY_NAME[tool]
            obj = {"hypotheses": [{"label": "stub", "confidence": 0.4, "status": "active", "supporting_evidence": [], "contradicting_evidence": []}], "tool": tool, "component": None, "metric_category": None, "keyword": None, "team": None}
            if "component" in spec.required or ("component" in spec.optional and comps and self.rng.random() < 0.5):
                obj["component"] = self.rng.choice(comps)
            if tool == "get_telemetry" and self.rng.random() < 0.5:
                obj["metric_category"] = self.rng.choice(list(K.METRIC_FAMILIES))
        else:
            cites = schema["properties"]["evidence_ids"].get("items", {}).get("enum", [])
            sup = cites[:1]
            obj = {"hypotheses": [{"label": "stub", "confidence": 0.5, "status": "active", "supporting_evidence": sup, "contradicting_evidence": []}],
                   "evidence_ids": sup, "issue_category": None, "category_confidence": None, "root_cause": None, "root_cause_confidence": None,
                   "affected_component": None, "component_confidence": None, "causal_change": None, "causal_change_confidence": None,
                   "owning_team": None, "routing_confidence": None, "confidence": 0.5, "evidence_sufficiency": "partial", "human_review_required": True,
                   "review_reason": "stub", "status": "HUMAN_REVIEW_REQUIRED", "recommended_next_action": "review", "unresolved_uncertainties": [],
                   "summary": "stub answer"}
        return LLMResult(json.dumps(obj), "stop", 0, 0, 1.0)


if __name__ == "__main__":
    from agent.agent_v3 import cohorts
    from agent.graph_v2.db import get_driver

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    n = ap.parse_args().n
    pool = json.loads(cohorts.POOL_PATH.read_text())["case_ids"]
    used = set(cohorts.load("iter50")["case_ids"]) | set(cohorts.load("verify100")["case_ids"])
    ids = [c for c in sorted(pool) if c not in used][:n]
    driver = get_driver()
    for cid in ids:
        with driver.session() as s:
            r = run_case(cid, Neo4jBackend(s, cid), StubPolicy(hash(cid) % 1000))
        print(cid, r["stop_reason"], r["final_status"], "steps", r["num_tool_calls"], "proposals", r["tool_proposals"],
              "tool_errors", len(r["tool_contract_errors"]), "final_ok", r["validation_result"]["final_ok"], "entities", r["registry_snapshots"][-1]["counts"])
        bad = [e for e in r["tool_contract_errors"]]
        for b in bad[:3]:
            print("   ", b["errors"])
    driver.close()
