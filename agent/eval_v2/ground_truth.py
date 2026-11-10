"""Phase 6's read side: wraps data.eval.eval_store (the sanctioned hidden-
truth accessor -- see that module's own docstring naming this package as its
intended caller) plus lookups against OBSERVABLE reference/taxonomy tables
(products/components/issue_categories/issue_subcategories/root_causes/teams
-- all loaded into the Phase 4 graph unconditionally by
agent/graph_v2/loaders/taxonomy.py, so reading them directly here is not a
boundary crossing; it's the same data the agent's own tools already expose).

This module is imported ONLY by agent/eval_v2/*.py -- never by
agent/agent_v2/*.py (the runtime agent). Enforced by validate_boundaries.py.
"""
import csv
from pathlib import Path

from data.eval import eval_store

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_V2 = PROJECT_ROOT / "data" / "raw_v2"

_ref_cache: dict = {}


def _id_name_lookup(filename: str, id_col: str, name_col: str = "name") -> dict:
    if filename not in _ref_cache:
        path = DATA_RAW_V2 / filename
        with open(path, newline="", encoding="utf-8") as f:
            _ref_cache[filename] = {row[id_col]: row[name_col] for row in csv.DictReader(f)}
    return _ref_cache[filename]


def product_name(product_id):
    return _id_name_lookup("products.csv", "id").get(product_id) if product_id else None


def component_name(component_id):
    return _id_name_lookup("components.csv", "id").get(component_id) if component_id else None


def team_name(team_id):
    return _id_name_lookup("teams.csv", "id").get(team_id) if team_id else None


def issue_category_name(category_id):
    return _id_name_lookup("issue_categories.csv", "id").get(category_id) if category_id else None


def issue_subcategory_name(subcategory_id):
    return _id_name_lookup("issue_subcategories.csv", "id").get(subcategory_id) if subcategory_id else None


def root_cause_name(root_cause_id):
    return _id_name_lookup("root_causes.csv", "id").get(root_cause_id) if root_cause_id else None


def all_root_causes() -> dict:
    """{root_cause_id: name} for all ~40 canonical root causes -- used to map
    the agent's free-text predicted_root_cause_family back onto the fixed
    taxonomy for confusion-matrix purposes (agent/eval_v2/confusion.py)."""
    return dict(_id_name_lookup("root_causes.csv", "id"))


def get_hidden_truth(case_id: str) -> dict:
    """Bundles every hidden fact this evaluator needs for one case. Never
    call this from anything under agent/agent_v2/."""
    return {
        "case_ground_truth": eval_store.get_case_ground_truth(case_id),
        "phase2_ground_truth": eval_store.get_phase2_ground_truth(case_id),
        "phase3_ground_truth": eval_store.get_phase3_ground_truth(case_id),
        "ideal_investigation_requirements": eval_store.get_ideal_investigation_requirements(case_id),
        "case_team_ownership": eval_store.get_case_team_ownership(case_id),
        "incident_relationship_rows": eval_store.get_incident_relationship(case_id),
    }
