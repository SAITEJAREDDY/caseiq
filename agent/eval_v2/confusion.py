"""Confusion-matrix builders (spec section 37) for issue category, root
cause family, team, and severity. Root cause uses text_match.map_text_to_id
to bucket the agent's free text onto the fixed ~40-row taxonomy -- see that
function's docstring for the ambiguous/unmapped handling.
"""
from collections import defaultdict

from agent.eval_v2.ground_truth import all_root_causes
from agent.eval_v2.text_match import map_text_to_id

_SEV_ID_TO_LABEL = {1: "Sev1", 2: "Sev2", 3: "Sev3", 4: "Sev4"}


def _build(records, true_fn, pred_fn) -> dict:
    matrix = defaultdict(lambda: defaultdict(int))
    for r in records:
        true_label = true_fn(r) or "unknown_truth"
        pred_label = pred_fn(r) or "no_prediction"
        matrix[true_label][pred_label] += 1
    return {t: dict(preds) for t, preds in matrix.items()}


def category_confusion(records) -> dict:
    return _build(
        records,
        lambda r: r["stratification"]["issue_category_id"],
        lambda r: r["outcome"]["category"]["predicted"],
    )


def team_confusion(records) -> dict:
    def true_team(r):
        primaries = r["outcome"]["team"]["primary_teams"]
        return primaries[0] if primaries else "unknown_truth"

    return _build(records, true_team, lambda r: r["outcome"]["team"]["predicted"])


def severity_confusion(records) -> dict:
    def pred_sev(r):
        norm = r["outcome"]["severity"]["predicted_normalized"]
        return _SEV_ID_TO_LABEL.get(norm)

    return _build(records, lambda r: r["stratification"]["severity"], pred_sev)


def root_cause_confusion(records) -> dict:
    id_to_name = all_root_causes()

    def pred_rc_id(r):
        return map_text_to_id(r["predictions"].get("predicted_root_cause_family"), id_to_name)

    return _build(records, lambda r: r["stratification"]["root_cause_id"], pred_rc_id)


def all_confusion_matrices(records) -> dict:
    return {
        "issue_category": category_confusion(records),
        "root_cause": root_cause_confusion(records),
        "team": team_confusion(records),
        "severity": severity_confusion(records),
    }
