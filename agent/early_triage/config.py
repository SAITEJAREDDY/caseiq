"""Early-triage configuration. Thresholds are hand-set MVP defaults (not tuned on any outcome); change them here."""
from dataclasses import asdict, dataclass

TRIAGE_VERSION = "early_triage_v1"
QUESTION_VERSION = "early_triage_category_v1"     # bump, never edit, once a run has used the wording
STATE_VERSION = "early_triage_state_v1"           # ticket text + customer tier/industry/size + product name; no signals, no graph read
ABSTAIN_KEY = "ABSTAIN"
ROLE = "triage_guidance"                          # early Jev = triage guidance; the Phase 9 verifier is the other role (answer verification)


@dataclass
class TriageConfig:
    min_probability: float = 0.30       # below this the plain-code policy drops the suggestion (fallback), even if Jev picked a category
    moderate_probability: float = 0.40  # uncertainty label: >= strong -> low, >= moderate -> moderate, else high
    strong_probability: float = 0.70
    top_alternatives: int = 3           # competing categories shown to the agent next to the suggestion
    timeout_s: float = 20.0             # wall-clock budget for the whole Jev call (retries included); a slow Jev must never stall the investigation

    def to_dict(self) -> dict:
        return asdict(self)
