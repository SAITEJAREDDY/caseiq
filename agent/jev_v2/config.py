"""Phase 7 configuration: Jev/TypeSafe API settings, question/context/
candidate-strategy versioning, LLM-baseline model config, paths.

Reads config.settings (the live app's TOGETHER_API_KEY, read-only) and a
new TYPESAFE_API_KEY -- neither is imported back by the live app or by
agent/agent_v2/, so nothing here can affect either.
"""
import os
from pathlib import Path

import config.settings as _live_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ── Jev / TypeSafe API (verified against docs.typesafe.ai -- see
# docs/JEV_PRIMITIVE_ARCHITECTURE.md for how this was confirmed) ────────────
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY", "")
TYPESAFE_BASE_URL = os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
TYPESAFE_SYSTEM_ONE_PATH = "/v1/systemone"
JEV_MODEL = os.getenv("JEV_MODEL", "jev-latest")  # response's own `model` field records the resolved id actually used

# ── LLM primitive baseline (spec section 28) -- same model Phase 5 defaults to ─
LLM_BASELINE_PROVIDER = "together"
LLM_BASELINE_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
LLM_BASELINE_TEMPERATURE = 0.1
LLM_BASELINE_MAX_TOKENS = 400

# ── Versioning (spec section 6) ──────────────────────────────────────────────
# v2.1: additive REPORTING changes only -- per-decision scoring.py semantics are
# unchanged from v2. (a) causal_change `recency_analysis` no longer counts a
# candidate MISS as an "older than a distractor" case (JEV-024); (b) new
# `recency_categories`, LLM contract/repair metrics, strict first-attempt
# accuracy, latency percentiles and cost. Stored v2 experiment.json files keep
# their original "v2" label and values; they are never rewritten.
EVALUATOR_VERSION = "v2.1"
QUESTION_SET_VERSION = "v2"
# Bundle label recorded on experiments. It only names the combination below;
# the per-decision map that follows is authoritative. Versioned experiment
# records retain their own value, so advancing this default never mutates or
# reinterprets Stage A / Stage B v1 / Stage B v2 artifacts.
#   "v2" = Stage B v2 bundle (root_cause v2, owning_team v2, causal_change v2)
#   "v3" = "v2" + causal_change candidate_generation_v3 (JEV-013)
CANDIDATE_STRATEGY_VERSION = "v3"

# Per-decision candidate-generation versions (authoritative). Older versions
# stay callable so Stage B v1/v2 remain reproducible.
#   issue_category        v1  all 18 canonical categories (unchanged since Stage A)
#   root_cause            v2  weighted product/signal/symptom topology, top 15 + RC40
#   causal_change         v3  visible changes + visible deployments + "none"
#                         v2  visible changes only (misses deployment-type causes)
#   owning_team           v2  weighted deployment/product/signal/symptom support, top 12
#   evidence_sufficiency  v1  fixed three-way label set
#   incident_relationship v1  active incidents overlapping the case (one Noul each)
CANDIDATE_GENERATION_VERSIONS = {
    "issue_category": "v1",
    "root_cause": "v2",
    "causal_change": "v3",
    "owning_team": "v2",
    "evidence_sufficiency": "v1",
    "incident_relationship": "v1",
}

# Per-decision question versions -- bump the specific one when its wording changes,
# never silently overwrite (spec section 6's "do not overwrite question definitions").
QUESTION_VERSIONS = {
    "issue_category": "issue_category_v1",
    "root_cause": "root_cause_v1",
    "causal_change": "causal_change_v1",
    "owning_team": "owning_team_v1",
    "evidence_sufficiency": "evidence_sufficiency_v2",
    "incident_relationship": "incident_relationship_v1",
}

# Context-ablation versions for root cause (spec section 24)
CONTEXT_VERSIONS = ["v1_narrative", "v2_domain", "v3_technical", "v4_operational", "v5_graph"]
DEFAULT_CONTEXT_VERSION = "v3_technical"  # used for decisions other than root cause, and root cause's own default

# ── Thresholds / buckets -- reuse Phase 6's exact values, don't redefine them ──
from agent.eval_v2.config import (  # noqa: E402
    AUTOMATION_THRESHOLDS,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CONFIDENCE_BUCKETS,
    FALSE_CONFIDENT_THRESHOLD,
)

TARGET_ERROR_RATES = [0.05, 0.02, 0.01]

# ── Candidate-set sizing ──────────────────────────────────────────────────────
# v2 candidate sets are deliberately bounded after aggregating all relevant
# observable support, rather than truncating their input component lists.
MAX_ROOT_CAUSE_CANDIDATES = 16  # top 15 ranked causes plus RC40 abstention
MAX_TEAM_CANDIDATES = 12
DEFAULT_RESULT_LIMIT = 8  # mirrors agent.agent_v2.config's own bound

# ── Cost accounting (versioned assumptions -- token COUNTS are always actual
# provider-returned usage; only the per-token price is an assumption) ──────────
PRICING_VERSION = "2026-09-23"
# Jev: $0.042 per 1M input tokens, output tokens free (docs.typesafe.ai pricing,
# verified during the Phase 7 API verification).
JEV_PRICE_PER_M_INPUT_USD = 0.042
JEV_PRICE_PER_M_OUTPUT_USD = 0.0
# Together "Llama 3.3 70B" serverless: $1.04 / $1.04 per 1M input/output tokens,
# read from together.ai/pricing on 2026-09-23. That page lists no separate
# "Turbo" row, so applying it to the Turbo model id is an ASSUMPTION.
LLM_PRICE_PER_M_INPUT_USD = 1.04
LLM_PRICE_PER_M_OUTPUT_USD = 1.04

# LLM baseline contract handling: at most this many repair re-prompts after an
# invalid first attempt (JEV-018). 0 disables repair.
LLM_REPAIR_MAX_ATTEMPTS = 1

# ── Retry ──────────────────────────────────────────────────────────────────
MAX_RETRIES = 5
BASE_RETRY_DELAY_SECONDS = 2.0

# ── Persistence -- same directory Phase 6 already uses (spec section 52) ────
from agent.eval_v2.config import EXPERIMENTS_DIR  # noqa: E402

TOGETHER_API_KEY = getattr(_live_settings, "TOGETHER_API_KEY", None) or os.getenv("TOGETHER_API_KEY", "")
