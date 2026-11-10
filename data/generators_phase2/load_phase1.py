"""
Read-only loaders for the frozen Phase 1 dataset (data/raw_v2/*.csv).

Nothing in this module ever opens a Phase 1 file in write mode, and nothing in
generators_phase2/ imports data/generators/ (which would re-run Phase 1's own
random-seeded assembly). Phase 2 treats data/raw_v2/ purely as an immutable
input to read from.
"""
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta

RAW_V1 = os.path.join(os.path.dirname(__file__), "..", "raw_v2")


def _read(filename):
    path = os.path.join(RAW_V1, filename)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_date(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d")


def load_all():
    """Returns a dict of Phase 1 tables needed by Phase 2, plus a few derived
    lookups (component -> issue-category flavor weights, category key <-> id)."""
    cases = _read("cases.csv")
    for c in cases:
        c["created_date"] = _parse_date(c["created_date"])
        c["gt_resolved_date"] = _parse_date(c["gt_resolved_date"])
        c["reported_affected_users"] = int(c["reported_affected_users"])
        c["gt_true_affected_users"] = int(c["gt_true_affected_users"])

    # Fixed reference point for all of Phase 2's "recent activity" timestamps
    # (background changes, health events, capacity snapshots, etc.), derived
    # from Phase 1's OWN frozen data rather than datetime.now() at Phase 2
    # build time. Phase 1 anchors case dates to whenever *it* was built (see
    # generate_cases._rand_created_date), so reusing wall-clock "now" here
    # would make Phase 2 non-reproducible across separate runs even with a
    # fixed seed (the same rng draws would land on different calendar
    # timestamps run to run). Anchoring to Phase 1's own latest case date
    # instead makes every Phase 2 timestamp reproducible as long as Phase 1
    # stays frozen.
    phase2_now = max(c["created_date"] for c in cases) + timedelta(days=14)

    customers = _read("customers.csv")
    agents = _read("agents.csv")
    products = _read("products.csv")
    components = _read("components.csv")
    teams = _read("teams.csv")
    skills = _read("skills.csv")
    issue_categories = _read("issue_categories.csv")
    issue_subcategories = _read("issue_subcategories.csv")
    root_causes = _read("root_causes.csv")
    resolution_types = _read("resolution_types.csv")
    product_components = _read("product_components.csv")
    component_teams = _read("component_teams.csv")
    issue_subcategory_components = _read("issue_subcategory_components.csv")
    case_components = _read("case_components.csv")

    cat_id_to_name = {c["id"]: c["name"] for c in issue_categories}
    cat_name_to_id = {v: k for k, v in cat_id_to_name.items()}
    subcat_id_to_cat_id = {s["id"]: s["category_id"] for s in issue_subcategories}
    root_cause_id_to_name = {r["id"]: r["name"] for r in root_causes}
    root_cause_name_to_id = {v: k for k, v in root_cause_id_to_name.items()}
    component_id_to_name = {c["id"]: c["name"] for c in components}
    product_id_to_name = {p["id"]: p["name"] for p in products}

    # component_id -> {category_id: total weight} inferred from
    # issue_subcategory_components.csv (subcategory -> parent category).
    component_category_weights = defaultdict(lambda: defaultdict(int))
    for row in issue_subcategory_components:
        cat_id = subcat_id_to_cat_id.get(row["subcategory_id"])
        if cat_id:
            component_category_weights[row["component_id"]][cat_id] += int(row["weight"])

    product_id_to_component_ids = defaultdict(list)
    for row in product_components:
        product_id_to_component_ids[row["product_id"]].append(row["component_id"])

    component_id_to_product_ids = defaultdict(list)
    for row in product_components:
        component_id_to_product_ids[row["component_id"]].append(row["product_id"])

    case_id_to_components = defaultdict(list)
    for row in case_components:
        case_id_to_components[row["case_id"]].append(row["component_id"])

    return {
        "phase2_now": phase2_now,
        "cases": cases,
        "customers": customers,
        "agents": agents,
        "products": products,
        "components": components,
        "teams": teams,
        "skills": skills,
        "issue_categories": issue_categories,
        "issue_subcategories": issue_subcategories,
        "root_causes": root_causes,
        "resolution_types": resolution_types,
        "product_components": product_components,
        "component_teams": component_teams,
        "cat_id_to_name": cat_id_to_name,
        "cat_name_to_id": cat_name_to_id,
        "subcat_id_to_cat_id": subcat_id_to_cat_id,
        "root_cause_id_to_name": root_cause_id_to_name,
        "root_cause_name_to_id": root_cause_name_to_id,
        "component_id_to_name": component_id_to_name,
        "product_id_to_name": product_id_to_name,
        "component_category_weights": component_category_weights,
        "product_id_to_component_ids": product_id_to_component_ids,
        "component_id_to_product_ids": component_id_to_product_ids,
        "case_id_to_components": case_id_to_components,
    }
