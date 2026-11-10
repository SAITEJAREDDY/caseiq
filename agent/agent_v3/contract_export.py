"""Machine-readable contract (`agent/contracts/agent_contract_v1.json`), generated from the code that enforces it so the two cannot drift.
The JSON is an export, not a second source of truth: a test and the boundary validator recompute it and compare.

    python3 -m agent.agent_v3.contract_export --write
"""
import argparse
import hashlib
import json

from agent.agent_v3 import config as C
from agent.agent_v3.catalog import ACTION_FIELDS, ARG_FIELDS, HARNESS_TOOLS, HYPOTHESIS_STATUSES, METRIC_FAMILIES, export_contract_tools
from agent.agent_v3.final_contract import ALL_STATUSES, FINAL_FIELDS, MODEL_STATUSES, SELECTIONS, SUFFICIENCY
from agent.agent_v3.registry import CITABLE_KINDS, KINDS, _CONS


def build_contract() -> dict:
    return {
        "contract_version": C.CONTRACT_VERSION,
        "versions": {"agent": C.AGENT_VERSION, "prompt": C.PROMPT_VERSION, "tool_catalog": C.TOOL_CATALOG_VERSION, "action_schema": C.ACTION_SCHEMA_VERSION,
                     "final_schema": C.FINAL_SCHEMA_VERSION, "registry": C.REGISTRY_VERSION, "alias_scheme": C.ALIAS_SCHEME, "repair_policy": C.REPAIR_POLICY_VERSION},
        "model": {"provider": C.MODEL_PROVIDER, "name": C.MODEL_NAME, "temperature": C.TEMPERATURE, "note": "unchanged from the Phase 5 baseline"},
        "decoding": {"mode": C.DECODING, "note": "the provider enforces the schema at decode time; every output is nevertheless validated deterministically and never repaired silently"},
        "budgets": {"max_tool_calls": C.MAX_TOOL_CALLS, "note": "counts the harness-issued case-context step; the submit step is extra", "max_repeated_same_tool": C.MAX_REPEATED_SAME_TOOL},
        "tools": export_contract_tools(),
        "harness_only_tools": list(HARNESS_TOOLS),
        "action_schema": {"fields": list(ACTION_FIELDS), "argument_fields": list(ARG_FIELDS), "hypothesis_statuses": list(HYPOTHESIS_STATUSES),
                          "metric_categories": list(METRIC_FAMILIES), "min_hypotheses": 1, "max_hypotheses": C.MAX_HYPOTHESES, "unused_arguments": "must be null"},
        "final_schema": {
            "fields": list(FINAL_FIELDS), "statuses": {"model_selectable": list(MODEL_STATUSES), "harness_only": [s for s in ALL_STATUSES if s not in MODEL_STATUSES]},
            "evidence_sufficiency": list(SUFFICIENCY), "confidence_bounds": [0, 1],
            "selections": [{"field": v, "confidence_field": c, "alias_kinds": list(k), "nullable": True} for v, c, k in SELECTIONS],
            "nullable_fields": [v for v, _c, _k in SELECTIONS] + [c for _v, c, _k in SELECTIONS] + ["review_reason"],
            "status_rules": {
                "DIAGNOSIS_PROPOSED": "at least one non-rejected hypothesis with cited support; valid citations; evidence_sufficiency is not 'insufficient'",
                "INSUFFICIENT_EVIDENCE": "every selection may be null; evidence_sufficiency is not 'sufficient'",
                "HUMAN_REVIEW_REQUIRED": "human_review_required is true and review_reason is present",
                "CONTRACT_FAILURE": "assigned by the harness only; no diagnosis is pretended, human review required"},
            "grounding_rules": ["every cited alias is an evidence alias retrieved during the run, cited once", "a non-null selection needs a confidence; a null selection needs a null confidence",
                                "any selection needs at least one cited evidence item", "causal_change must also be cited in evidence_ids",
                                "every hypothesis citation is also listed in evidence_ids", "no internal id appears anywhere in the output"]},
        "alias_constraints": {"scheme": C.ALIAS_SCHEME, "kinds": list(KINDS), "citable_kinds": list(CITABLE_KINDS), "code_alphabet": _CONS, "code_length": 3,
                              "pattern": "^(" + "|".join(KINDS) + ")_[" + _CONS + "]{3}$", "keyed_on": "(scheme, case, kind, canonical id)",
                              "properties": "no order, recency, number or role is encoded; canonical ids are never shown to the model"},
        "repair_policy": {"max_tool_contract_repairs": C.MAX_TOOL_CONTRACT_REPAIRS, "max_final_contract_repairs": C.MAX_FINAL_CONTRACT_REPAIRS,
                          "on_exhaustion": "CONTRACT_FAILURE with human review required", "silent_rewriting": False,
                          "recorded_as": ["tool_contract_errors", "tool_contract_repairs", "final_contract_errors", "final_contract_repair"]},
    }


def digest(contract: dict) -> str:
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()


def write() -> str:
    c = build_contract()
    C.CONTRACT_JSON.parent.mkdir(parents=True, exist_ok=True)
    C.CONTRACT_JSON.write_text(json.dumps(c, indent=1, sort_keys=False) + "\n")
    return digest(c)


def matches_file() -> bool:
    return C.CONTRACT_JSON.exists() and json.loads(C.CONTRACT_JSON.read_text()) == json.loads(json.dumps(build_contract()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    if ap.parse_args().write:
        print("wrote", C.CONTRACT_JSON, "sha256", write())
    else:
        print("matches file:", matches_file())
