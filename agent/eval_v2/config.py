"""Phase 6 deterministic-evaluator configuration: versioning, split
proportions/seed, confidence buckets, thresholds. No LLM calls happen in
this package's own scoring code -- only run_experiment.py's optional
"run_and_evaluate" mode drives agent.agent_v2.loop, and that is clearly
separated from the pure-function scoring path (metrics.py/aggregate.py).
"""
from pathlib import Path

EVAL_HARNESS_VERSION = "v1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_EVAL_DIR = PROJECT_ROOT / "data" / "eval"
SPLITS_DIR = DATA_EVAL_DIR / "splits"
EXPERIMENTS_DIR = PROJECT_ROOT / "data" / "experiments"
AGENT_RUNS_DIR = PROJECT_ROOT / "data" / "agent_runs"

# ── Dataset splits (spec section 2) ─────────────────────────────────────────
SPLIT_VERSION = "v1"
SPLIT_SEED = 20260923
SPLIT_PROPORTIONS = {"dev": 0.40, "validation": 0.30, "test": 0.30}

# ── Confidence calibration buckets (spec section 16) ────────────────────────
CONFIDENCE_BUCKETS = [
    (0.0, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.0001),
]

# ── False-confident-decision threshold (spec section 18) ────────────────────
FALSE_CONFIDENT_THRESHOLD = 0.90

# ── Automation-coverage simulation thresholds (spec section 19) ─────────────
AUTOMATION_THRESHOLDS = [0.70, 0.80, 0.85, 0.90, 0.95]

# ── Bootstrap confidence intervals (spec section 53) ─────────────────────────
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20260923

# ── Severity ordinal mapping (Sev1 = most severe) ───────────────────────────
SEVERITY_ORDER = {"Sev1": 1, "Sev2": 2, "Sev3": 3, "Sev4": 4}
