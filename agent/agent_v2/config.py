"""Phase 5 baseline-agent configuration: model/budget/versioning constants.

Reads config.settings (the live app's GROQ_API_KEY/GROQ_MODEL) read-only --
this module is never imported back by config/settings.py or agent/llm_client.py,
so changing the baseline agent's model/temperature never affects the live app.
"""
import os

import config.settings as _live_settings

# ── Versioning (spec section 36) ────────────────────────────────────────────
PROMPT_VERSION = "v1"
TOOLSET_VERSION = "v1"
OUTPUT_SCHEMA_VERSION = "v1"
# Phase 6 addition: versions the loop's control flow and its repair layer
# separately from the tool/prompt/schema versions above, so a future change
# to either is distinguishable in a persisted run without conflating it with
# an unrelated prompt or schema change.
AGENT_LOOP_VERSION = "v1"
REPAIR_LAYER_VERSION = "v1"

# ── Model (spec section 38) ──────────────────────────────────────────────────
# Default is Together AI, not Groq, despite the live app using Groq: Groq's
# free/on-demand tier caps openai/gpt-oss-120b at 8000 tokens/minute, which a
# 15-tool agentic loop with growing conversation history burns through in a
# handful of steps (observed: single-request rejections, and once an 18-
# minute forced backoff). Together AI is already integrated in this project
# (data/generators/llm_client.py, paid usage) with no equivalent throttle.
# `AGENT_MODEL_PROVIDER=groq` still works if you want to compare later.
AGENT_MODEL_PROVIDER = os.getenv("AGENT_MODEL_PROVIDER", "together")
_DEFAULT_MODEL_BY_PROVIDER = {
    "groq": _live_settings.GROQ_MODEL,
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
}
AGENT_MODEL_NAME = os.getenv("AGENT_MODEL_NAME", _DEFAULT_MODEL_BY_PROVIDER.get(AGENT_MODEL_PROVIDER, ""))
AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.1"))
AGENT_MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "1300"))

# ── Investigation budgets (spec section 26) ─────────────────────────────────
MAX_TOOL_CALLS = int(os.getenv("AGENT_MAX_TOOL_CALLS", "10"))
MAX_REPEATED_SAME_TOOL = int(os.getenv("AGENT_MAX_REPEATED_SAME_TOOL", "2"))

# ── Simulated investigation clock (spec section 17) ─────────────────────────
# Deterministic, fixed-step -- never derived from any hidden/evaluation field
# (e.g. never from gt_resolution_duration_hours). Starts at the case's own
# created_date; advances this many simulated minutes after every tool call.
SIM_CLOCK_STEP_MINUTES = int(os.getenv("AGENT_SIM_CLOCK_STEP_MINUTES", "15"))

# ── Result bounding (spec section 44) ───────────────────────────────────────
DEFAULT_RESULT_LIMIT = 8

# ── Conversation-history bounding ───────────────────────────────────────────
# Groq's free tier is 8000 TPM; a growing multi-step tool-calling conversation
# can otherwise consume nearly the entire budget by step 8-10, leaving no
# room for the final structured answer. Only the most recent N tool results
# are kept verbatim in the prompt sent to the model; older ones are replaced
# with a one-line placeholder (the full detail still lives in the trace).
KEEP_LAST_N_FULL_TOOL_RESULTS = 4

# ── Graph version tag (Phase 4's measured, standing-graph scale) ───────────
GRAPH_VERSION_TAG = "phase4-2500case-2026-09-22"

# ── Approximate cost accounting (labeled estimate, not exact provider billing) ─
APPROX_USD_PER_1K_INPUT_TOKENS = float(os.getenv("AGENT_USD_PER_1K_INPUT", "0.0001"))
APPROX_USD_PER_1K_OUTPUT_TOKENS = float(os.getenv("AGENT_USD_PER_1K_OUTPUT", "0.0001"))

# ── Persistence ──────────────────────────────────────────────────────────────
from pathlib import Path  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_RUNS_DIR = PROJECT_ROOT / "data" / "agent_runs"
