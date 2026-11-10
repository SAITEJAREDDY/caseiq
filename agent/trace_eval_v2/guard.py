"""The Phase 8 runtime leakage guard, applied to every request before it leaves the process (Jev and LLM judge alike).

Why not Phase 7's `assert_no_leakage`: its value scan blocks ordinary English words (`warranted`, `correct_`, `_missed`) that the *agent's own free text* can contain, so it
would refuse legitimate review packets. Phase 8 scans differently, with the same intent:

  * keys: every dict key in the packet and in the question bodies must not be an evaluation column name or contain a hidden-field marker;
  * values: every string must not contain a marker or name an evaluation column as a whole word (a value that names a hidden field is a leak), not English words;
  * ids: no canonical internal id may remain anywhere in the request (every id must have been replaced by an alias).

Nothing here reads hidden truth.
"""
import json
import re

from agent.trace_eval_v2.models import ID_RE

# Exact names of the evaluation-only columns of the Phase 1-3 truth files. A key equal to one of them, or a value that contains one as a whole word, is a leak.
# (Substring matching is deliberately not used for these: the agent's own public output field `predicted_causal_change_id` contains `causal_change_id`.)
HIDDEN_COLUMNS = [
    "causal_component_id", "origin_component_id", "causal_change_id", "contributing_change_ids", "irrelevant_change_ids", "causal_signal_ids", "distractor_signal_ids",
    "critical_evidence_ids", "critical_evidence_missed", "escalation_warranted", "escalation_occurred", "diagnosis_matches_truth", "expected_confidence_band",
    "investigation_efficiency_label", "required_evidence_types", "correct_hypothesis_root_cause", "reference_derived",
]
# Markers that no legitimate packet, question or agent output contains, matched as substrings in keys and in values.
MARKERS = ["gt_", "ground_truth", "evaluation_label", "ideal_path", "is_distractor", "review_policy", "reference_label", "outcome_label", "process_label"]
HIDDEN_FIELD_NAMES = HIDDEN_COLUMNS + MARKERS  # kept for tests and documentation


class LeakageError(RuntimeError):
    """A request that must not be sent. Never caught or downgraded to a warning."""


def _flatten(obj, keys: list, values: list) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(str(k))
            _flatten(v, keys, values)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _flatten(item, keys, values)
    elif obj is not None:
        values.append(str(obj))


def _word_regex(name: str):
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")


_COLUMN_RES = [(n, _word_regex(n)) for n in HIDDEN_COLUMNS]


def assert_request_clean(state: dict, question: dict) -> None:
    keys, values = [], []
    _flatten(state, keys, values)
    _flatten(question, keys, values)
    lowered_keys = [k.lower() for k in keys]
    for marker in MARKERS:
        if any(marker in k for k in lowered_keys):
            raise LeakageError(f"a key in the request contains the hidden-field marker {marker!r}")
    for name in HIDDEN_COLUMNS:
        if name in lowered_keys:
            raise LeakageError(f"a key in the request is the hidden evaluation column {name!r}")
    value_text = " ".join(values).lower()
    for marker in MARKERS:
        if marker in value_text:
            raise LeakageError(f"a value in the request names the hidden field {marker!r}")
    for name, rx in _COLUMN_RES:
        if rx.search(value_text):
            raise LeakageError(f"a value in the request names the hidden field {name!r}")
    blob = json.dumps({"state": state, "question": question}, default=str)
    m = ID_RE.search(blob)
    if m:
        raise LeakageError(f"a canonical internal id ({m.group(0)!r}) remained in the request; every id must be an alias")
