"""Phase 9A contract-hardened agent (`agent_v3`): versions, budgets and model.

The model, provider, temperature and investigation budget are read from the frozen Phase 5 config, not redefined: Phase 9A tests
whether protocol hardening alone fixes the contract layer, so the model must not change. Everything else here is new and additive.
"""
from pathlib import Path

from agent.agent_v2 import config as _p5

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

AGENT_VERSION = "agent_v3_contract_hardened"
CONTRACT_VERSION = "agent_contract_v1.1"
PROMPT_VERSION = "v3.1"
TOOL_CATALOG_VERSION = "tool_catalog_v3"
ACTION_SCHEMA_VERSION = "action_v3.1"
FINAL_SCHEMA_VERSION = "final_diagnosis_v3.1"
REGISTRY_VERSION = "observed_registry_v1"
ALIAS_SCHEME = "agent_alias_v1"
REPAIR_POLICY_VERSION = "repair_policy_v1"
DECODING = "json_schema_strict"  # provider-enforced response_format; the validators below never assume it held

# Same model as the historical baseline (spec section 30): read, never overridden here.
MODEL_PROVIDER = _p5.AGENT_MODEL_PROVIDER
MODEL_NAME = _p5.AGENT_MODEL_NAME
TEMPERATURE = _p5.AGENT_TEMPERATURE
MAX_TOOL_CALLS = _p5.MAX_TOOL_CALLS                  # 10, includes the harness-issued case-context step
MAX_REPEATED_SAME_TOOL = _p5.MAX_REPEATED_SAME_TOOL  # 2
SIM_CLOCK_STEP_MINUTES = _p5.SIM_CLOCK_STEP_MINUTES
GRAPH_VERSION_TAG = _p5.GRAPH_VERSION_TAG
STEP_MAX_TOKENS = 900
FINAL_MAX_TOKENS = 1500

# Repair budgets (spec sections 13 and 27). Exceeding either ends the run as CONTRACT_FAILURE with human review required.
MAX_TOOL_CONTRACT_REPAIRS = 2
MAX_FINAL_CONTRACT_REPAIRS = 1

MAX_HYPOTHESES = 4
LABEL_MAX = 60
KEYWORD_MAX = 60
SUMMARY_MAX = 500
LINE_MAX = 160

RUNS_DIR = PROJECT_ROOT / "data" / "agent_runs_v3"      # Phase 5's data/agent_runs is never written
COHORT_DIR = PROJECT_ROOT / "data" / "eval" / "agent_contract_9a"
CONTRACT_JSON = PROJECT_ROOT / "agent" / "contracts" / "agent_contract_v1.json"
