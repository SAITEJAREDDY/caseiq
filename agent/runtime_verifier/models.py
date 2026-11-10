"""Decisions and configuration for the Phase 9 runtime verifier. Thresholds are MVP defaults (chosen by hand, not tuned); change them here."""
from dataclasses import asdict, dataclass

ACCEPT = "ACCEPT"
CONTINUE = "CONTINUE_INVESTIGATION"
HUMAN_REVIEW = "HUMAN_REVIEW"
PRIORITY_REVIEW = "PRIORITY_REVIEW"
DECISIONS = (ACCEPT, CONTINUE, HUMAN_REVIEW, PRIORITY_REVIEW)

# Phase 8's review question answers AUTO_CLOSE / HUMAN_REVIEW / PRIORITY_REVIEW; shown to users as NORMAL / REVIEW / PRIORITY_REVIEW.
REVIEW_LABELS = {"AUTO_CLOSE": "NORMAL", "HUMAN_REVIEW": "REVIEW", "PRIORITY_REVIEW": "PRIORITY_REVIEW"}


@dataclass
class VerifierConfig:
    missed_evidence_threshold: float = 0.75   # Jev P(important evidence was missed) at or above this -> CONTINUE
    distractor_threshold: float = 0.75        # Jev P(anchored on weak evidence) at or above this -> CONTINUE
    priority_review_threshold: float = 0.50   # Jev P(PRIORITY_REVIEW) at or above this counts as a priority-review signal
    min_confidence: float = 0.55              # agent's own confidence below this -> HUMAN_REVIEW
    extra_steps: int = 4                      # tool calls granted in the one additional investigation round
    premature_min_steps_left: int = 2         # "no supported hypothesis" only counts as premature if this many tool calls were still available
    require_jev_to_accept: bool = True        # if Jev could not be reached, never ACCEPT: send to HUMAN_REVIEW

    def to_dict(self) -> dict:
        return asdict(self)
