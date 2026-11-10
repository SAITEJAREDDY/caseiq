"""Observable-only reference/taxonomy table reads for candidate generation.

Deliberately separate from agent/eval_v2/ground_truth.py: that module also
exposes hidden-truth accessors, and candidates.py/state_builder.py must
never import anything that COULD reach hidden truth, not just avoid calling
the hidden-truth functions -- keeping the import graph itself clean is what
makes agent/jev_v2/validate_boundaries.py's static check unambiguous. Every
table read here (issue_categories.csv, root_causes.csv,
issue_subcategory_root_causes.csv, issue_subcategory_components.csv,
product_components.csv, teams.csv) is loaded into the Phase 4 graph
unconditionally by agent/graph_v2/loaders/taxonomy.py -- i.e. it is
observable, the same fact already established in Phase 6's own
agent/eval_v2/ground_truth.py.
"""
import csv
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_V2 = PROJECT_ROOT / "data" / "raw_v2"

_cache: dict = {}


def _rows(filename: str) -> list:
    if filename not in _cache:
        with open(DATA_RAW_V2 / filename, newline="", encoding="utf-8") as f:
            _cache[filename] = list(csv.DictReader(f))
    return _cache[filename]


def all_issue_categories() -> dict:
    """{category_id: name} for all canonical Phase 1 issue categories."""
    return {r["id"]: r["name"] for r in _rows("issue_categories.csv")}


def all_root_causes() -> dict:
    """{root_cause_id: name} for the ~40-row canonical root-cause taxonomy.
    RC40 ('insufficient information to determine root cause') is a REAL
    existing taxonomy entry -- not invented -- used as the built-in
    abstention/'none of these' option for root-cause Choice questions
    (spec section 42)."""
    return {r["id"]: r["name"] for r in _rows("root_causes.csv")}


NO_ROOT_CAUSE_ID = "RC40"


def team_name_lookup() -> dict:
    return {r["id"]: r["name"] for r in _rows("teams.csv")}


def component_team_links() -> dict:
    """Observable ``component -> [(team, support weight)]`` relationships."""
    out = defaultdict(list)
    for r in _rows("component_teams.csv"):
        out[r["component_id"]].append((r["team_id"], float(r["weight"])))
    return out


def product_team_links() -> dict:
    """Observable ``product -> [(team, support weight)]`` relationships."""
    out = defaultdict(list)
    for r in _rows("product_teams.csv"):
        out[r["product_id"]].append((r["team_id"], float(r["weight"])))
    return out


def symptom_subcategory_links() -> dict:
    """Observable ``symptom name -> [(subcategory, association weight)]``."""
    symptom_names = {r["id"]: r["name"] for r in _rows("symptoms.csv")}
    out = defaultdict(list)
    for r in _rows("issue_subcategory_symptoms.csv"):
        name = symptom_names.get(r["symptom_id"])
        if name:
            out[name].append((r["subcategory_id"], float(r["weight"])))
    return out


def subcategory_team_links() -> dict:
    out = defaultdict(list)
    for r in _rows("issue_subcategory_teams.csv"):
        out[r["subcategory_id"]].append((r["team_id"], float(r["weight"])))
    return out


def component_root_cause_links() -> dict:
    """Observable component/topology path to root-cause families.

    Each score is the product of the public component-to-subcategory and
    subcategory-to-root-cause association weights.  This is taxonomy support,
    not a case-level truth label.
    """
    subcats_by_component = defaultdict(list)
    for r in _rows("issue_subcategory_components.csv"):
        subcats_by_component[r["component_id"]].append((r["subcategory_id"], float(r["weight"])))
    roots_by_subcat = defaultdict(list)
    for r in _rows("issue_subcategory_root_causes.csv"):
        roots_by_subcat[r["subcategory_id"]].append((r["root_cause_id"], float(r["weight"])))

    out = defaultdict(list)
    for component_id, subcats in subcats_by_component.items():
        for subcategory_id, subcategory_weight in subcats:
            for root_cause_id, root_cause_weight in roots_by_subcat[subcategory_id]:
                out[component_id].append((root_cause_id, subcategory_weight * root_cause_weight))
    return out


def subcategory_root_cause_links() -> dict:
    out = defaultdict(list)
    for r in _rows("issue_subcategory_root_causes.csv"):
        out[r["subcategory_id"]].append((r["root_cause_id"], float(r["weight"])))
    return out


def components_for_product(product_id: str) -> list:
    return [r["component_id"] for r in _rows("product_components.csv") if r["product_id"] == product_id]


def root_cause_candidates_for_product(product_id: str, max_candidates: int) -> dict:
    """Fully observable chain, no hidden truth or category input needed:
    product -> its components (product_components.csv) -> subcategories
    whose typical components overlap (issue_subcategory_components.csv,
    reversed) -> root causes typically linked to those subcategories
    (issue_subcategory_root_causes.csv), weighted and deduped. Always
    includes RC40 as the abstention option (spec section 42)."""
    component_ids = set(components_for_product(product_id))
    if not component_ids:
        candidate_subcats = set()
    else:
        candidate_subcats = {
            r["subcategory_id"] for r in _rows("issue_subcategory_components.csv") if r["component_id"] in component_ids
        }

    weights = defaultdict(float)
    for r in _rows("issue_subcategory_root_causes.csv"):
        if r["subcategory_id"] in candidate_subcats:
            weights[r["root_cause_id"]] += float(r["weight"])

    names = all_root_causes()
    ranked = sorted(weights.items(), key=lambda kv: -kv[1])[: max(0, max_candidates - 1)]
    candidates = {rc_id: names.get(rc_id, rc_id) for rc_id, _ in ranked}
    candidates[NO_ROOT_CAUSE_ID] = names.get(NO_ROOT_CAUSE_ID, "insufficient information to determine root cause")
    return candidates
