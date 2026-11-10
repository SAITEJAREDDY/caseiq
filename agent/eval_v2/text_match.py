"""Deterministic free-text matching for the root-cause field. Spec section
56 bans an LLM judge for anything Phase 6 scores; `predicted_root_cause_family`
is free text from the agent, compared against `root_causes.csv` names and
`phase3_ground_truth.actual_root_cause_name`, both also free text. Rather
than fake precision with a fuzzy similarity score, this module implements
exactly two deterministic tiers and reports them separately -- see
docs/EVALUATION_METRICS.md for the documented limitation (this under-counts
true positives whenever the agent phrases a correct root cause differently
from the ground-truth string; it never over-counts).
"""
import re

_STOPWORDS = {"a", "an", "the", "of", "in", "on", "to", "and", "or", "issue", "error", "problem"}


def normalize(text) -> str:
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def exact_match(predicted, truth) -> bool:
    p, t = normalize(predicted), normalize(truth)
    return bool(p) and bool(t) and p == t


def containment_match(predicted, truth) -> bool:
    p, t = normalize(predicted), normalize(truth)
    if not p or not t:
        return False
    return p in t or t in p


def map_text_to_id(text, id_to_name: dict) -> str:
    """Maps free text onto a fixed small taxonomy (e.g. root_causes.csv's
    ~40 rows) for confusion-matrix bucketing ONLY -- deterministic, no LLM.
    Tier 1: exact normalized match against exactly one id -> that id.
    Tier 2: containment match; if exactly one id matches, use it; if more
    than one matches (e.g. "misconfiguration" containment-matching several
    rows), the mapping is genuinely ambiguous and is reported as such rather
    than guessing. Returns one of: a real id, 'no_prediction' (empty text),
    'ambiguous_text' (2+ containment matches), or 'unmapped_text' (0 matches).
    """
    if not text:
        return "no_prediction"
    p = normalize(text)
    exact = [rid for rid, name in id_to_name.items() if normalize(name) == p]
    if len(exact) == 1:
        return exact[0]
    contains = [rid for rid, name in id_to_name.items() if containment_match(text, name)]
    if len(contains) == 1:
        return contains[0]
    if len(contains) > 1:
        return "ambiguous_text"
    return "unmapped_text"
