"""Phase 8 configuration: versions, seeds, sizes. Every version string is recorded on every experiment.

Nothing here is tuned against Jev's outputs: reference labels, the review policy, the perturbation set and the questions are
versioned and frozen before the first Jev call (see docs/TRACE_EVAL_REFERENCE_LABELS.md)."""
import json
from pathlib import Path

from agent.eval_v2.config import AUTOMATION_THRESHOLDS, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, EXPERIMENTS_DIR, FALSE_CONFIDENT_THRESHOLD  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRACE_EVAL_DIR = PROJECT_ROOT / "data" / "eval" / "trace_eval"
AGENT_RUNS_DIR = PROJECT_ROOT / "data" / "agent_runs"

# ── versions ─────────────────────────────────────────────────────────────────────────
PROJECTION_VERSION = "trace_projection_v1"
ALIAS_SCHEME = "trace_alias_v1"
REFERENCE_LABEL_VERSION = "reference_labels_v1"
REVIEW_POLICY_VERSION = "review_policy_v1"
PERTURBATION_VERSION = "perturbations_v1"
POOL_VERSION = "trace_pool_v1"
CORPUS_VERSION = "trace_corpus_v1"
QUESTION_VERSIONS = {
    "support": "trace_support_v1",
    "missed_evidence": "missed_evidence_v1",
    "distractor_anchor": "distractor_anchor_v1",
    "premature_close": "premature_close_v1",
    "final_consistency": "final_consistency_v2",
    "human_review": "human_review_v1",
}
JUDGMENTS = ["support", "missed_evidence", "distractor_anchor", "premature_close", "final_consistency", "human_review"]
JUDGMENT_IDS = {"support": "J1", "missed_evidence": "J2", "distractor_anchor": "J3", "premature_close": "J4", "final_consistency": "J5", "human_review": "J6"}

# ── the trace pool and corpus ────────────────────────────────────────────────────────
POOL_SEED = 20260924
POOL_SIZE = 300  # all insufficient and partially-sufficient dev cases, the rest sampled from the sufficient strata
CORPUS_TARGET = 150
PERTURBATION_SEED = 20260924
RUN_WORKERS = 6

# ── judges ───────────────────────────────────────────────────────────────────────────
def jev_model() -> str:
    """The Jev model id the repository froze in Phase 7 (read-only)."""
    return json.loads((PROJECT_ROOT / "data" / "eval" / "jev" / "stage_b_frozen_v1.json").read_text())["jev"]["model_requested"]


JUDGE_WORKERS = 8
