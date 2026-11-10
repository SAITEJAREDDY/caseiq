"""
Central configuration — all values loaded from environment variables.
Copy .env.example to .env and fill in your credentials before running.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Groq (LLM) ────────────────────────────────────────────────────────────────
GROQ_API_KEY    = os.environ["GROQ_API_KEY"]
GROQ_MODEL            = "openai/gpt-oss-120b"
GROQ_TEMP             = 0.1
GROQ_MAX_TOKENS       = 4000   # TPM cap is 8000; largest input ~1200 t → 1200+4000=5200 < 8000.
                               # reasoning_effort=high uses ~2k internally → ~2k left for text output.
GROQ_REASONING_EFFORT = "low"    # graph context supplies facts; low effort leaves ~3.8k tokens for text

# ── LangSmith (observability + experiments) ───────────────────────────────────
LANGCHAIN_API_KEY      = os.environ["LANGCHAIN_API_KEY"]
LANGCHAIN_TRACING_V2   = os.getenv("LANGCHAIN_TRACING_V2", "true")
LANGCHAIN_PROJECT      = os.getenv("LANGCHAIN_PROJECT", "support-intelligence-poc")
LANGSMITH_DATASET_NAME = os.getenv("LANGSMITH_DATASET_NAME", "support-intelligence-evals")

# Force these into the process env so LangChain picks them up automatically
os.environ["LANGCHAIN_API_KEY"]    = LANGCHAIN_API_KEY
os.environ["LANGCHAIN_TRACING_V2"] = LANGCHAIN_TRACING_V2
os.environ["LANGCHAIN_PROJECT"]    = LANGCHAIN_PROJECT

# ── Neo4j AuraDB ──────────────────────────────────────────────────────────────
NEO4J_URI      = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

# ── Agent memory ──────────────────────────────────────────────────────────────
MEMORY_WINDOW_SIZE = 5   # last N conversation exchanges to retain

# ── Case extraction confidence thresholds (configurable) ──────────────────────
CONF_HIGH   = 0.80   # ≥ this → auto-assign, no confirmation needed
CONF_MEDIUM = 0.60   # ≥ this → show confirmation to user
CONF_LOW    = 0.50   # ≥ this → LOW semantic match (still shows confirmation)
                     # < CONF_LOW → INSUFFICIENT, trigger manual product picker

# ── Agent ranking & selection ──────────────────────────────────────────────────
# Penalty applied per hour of avg_resolution_time in the match_score Cypher formula.
# Higher = resolution time matters more vs skill coverage.
RESOLUTION_TIME_WEIGHT = 0.2

# GOLD tier seniority preference: if the best senior agent's resolution time is
# within this many hours of the overall fastest agent, prefer the senior.
# Exceeding this threshold means the time cost is too high → fall back to fastest.
SENIORITY_TIME_TOLERANCE_HOURS = 3.0

# ── Demo scenarios (used by main.py and app.py) ───────────────────────────────
SCENARIOS = {
    "A": {
        "label": "Payment Gateway Refund Failure",
        "description": (
            "Customer cannot process refunds on Payment Gateway v2.1 — "
            "error code 4023, affecting 3 enterprise accounts"
        ),
        "product_id":      "P001",
        "customer_id":     "C0009",
        "required_skills": ["SK001", "SK002"],
    },
    "B": {
        "label": "SSO Onboarding Blocked — Gold Tier",
        "description": (
            "New customer onboarding blocked — SSO integration failing "
            "with Azure AD, customer is Gold tier"
        ),
        "product_id":      "P002",
        "customer_id":     "C0028",
        "required_skills": ["SK007", "SK009"],
    },
    "C": {
        "label": "Analytics Data Export Corruption",
        "description": (
            "Data export corrupted for Analytics Module — "
            "customer reports missing rows in CSV output since last update"
        ),
        "product_id":      "P003",
        "customer_id":     "C0030",
        "required_skills": ["SK014", "SK013"],
    },
}
