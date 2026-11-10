"""The simulated investigation clock.

Owned entirely by the harness -- never exposed as an LLM-controllable tool
argument (the model could otherwise request an arbitrary future timestamp
and see evidence that "hadn't happened yet"). Starts at the case's own
observable created_date and advances by a fixed step after every tool call,
independent of any hidden/evaluation field (in particular, never reads
gt_resolution_duration_hours or any other *_ground_truth.csv value to decide
pacing -- that would itself be a boundary violation).
"""
from datetime import datetime, timedelta

from agent.agent_v2.config import SIM_CLOCK_STEP_MINUTES

# Matches the timestamp format used throughout Phase 2/3 (case_observable.csv
# created_date is a bare date; Phase 2/3 event timestamps are "YYYY-MM-DD HH:MM:SS").
_DATETIME_FMT = "%Y-%m-%d %H:%M:%S"
_DATE_FMT = "%Y-%m-%d"


def _parse_created_date(created_date: str) -> datetime:
    try:
        return datetime.strptime(created_date, _DATETIME_FMT)
    except ValueError:
        return datetime.strptime(created_date, _DATE_FMT)


class SimClock:
    """Monotonic, deterministic, fixed-step. `.as_of` is always a string in
    the same format Phase 2/3 timestamps use, so it can be passed directly
    into a Cypher string comparison."""

    def __init__(self, created_date: str, step_minutes: int = SIM_CLOCK_STEP_MINUTES):
        self._t = _parse_created_date(created_date)
        self._step = timedelta(minutes=step_minutes)

    @property
    def as_of(self) -> str:
        return self._t.strftime(_DATETIME_FMT)

    def advance(self) -> str:
        self._t = self._t + self._step
        return self.as_of
