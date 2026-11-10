"""
Phase 1 dataset consistency validator. Run after build_dataset.py:

    python validate.py

Checks foreign-key integrity across every relationship table, date ordering,
and that each case's root cause / resolution / team / required skills are
actually drawn from that case's own issue-subcategory's plausible sets (i.e.
no cross-wired ground truth). Prints a PASS/FAIL report; exits non-zero on
any failure.
"""
import sys
from collections import defaultdict
from datetime import datetime

from csv_io import read_csv

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


def ids(rows, key="id"):
    return {r[key] for r in rows}


def main():
    customers = read_csv("customers.csv")
    products = read_csv("products.csv")
    components = read_csv("components.csv")
    categories = read_csv("issue_categories.csv")
    subcategories = read_csv("issue_subcategories.csv")
    symptoms = read_csv("symptoms.csv")
    root_causes = read_csv("root_causes.csv")
    resolutions = read_csv("resolution_types.csv")
    teams = read_csv("teams.csv")
    skills = read_csv("skills.csv")
    agents = read_csv("agents.csv")
    cases = read_csv("cases.csv")
    articles = read_csv("knowledge_articles.csv")

    sub_root_causes = read_csv("issue_subcategory_root_causes.csv")
    sub_skills = read_csv("issue_subcategory_skills.csv")
    sub_teams = read_csv("issue_subcategory_teams.csv")
    rc_resolutions = read_csv("root_cause_resolutions.csv")
    case_required_skills = read_csv("case_required_skills.csv")
    case_team_ownership = read_csv("case_team_ownership.csv")

    id_sets = {
        "customer": ids(customers), "product": ids(products), "component": ids(components),
        "category": ids(categories), "subcategory": ids(subcategories), "symptom": ids(symptoms),
        "root_cause": ids(root_causes), "resolution": ids(resolutions), "team": ids(teams),
        "skill": ids(skills), "agent": ids(agents), "case": ids(cases), "article": ids(articles),
    }

    print("Checking foreign keys on cases.csv...")
    for c in cases:
        check(c["customer_id"] in id_sets["customer"], f"case {c['id']}: unknown customer {c['customer_id']}")
        check(c["product_reported_id"] in id_sets["product"], f"case {c['id']}: unknown reported product")
        check(c["gt_product_id"] in id_sets["product"], f"case {c['id']}: unknown gt product")
        check(c["gt_component_id"] in id_sets["component"], f"case {c['id']}: unknown gt component")
        check(c["gt_issue_category_id"] in id_sets["category"], f"case {c['id']}: unknown gt category")
        check(c["gt_issue_subcategory_id"] in id_sets["subcategory"], f"case {c['id']}: unknown gt subcategory")
        check(c["gt_root_cause_id"] in id_sets["root_cause"], f"case {c['id']}: unknown gt root cause")
        check(c["gt_primary_team_id"] in id_sets["team"], f"case {c['id']}: unknown gt primary team")
        check(c["gt_assigned_agent_id"] in id_sets["agent"], f"case {c['id']}: unknown assigned agent")
        if c["gt_resolution_type_id"]:
            check(c["gt_resolution_type_id"] in id_sets["resolution"], f"case {c['id']}: unknown gt resolution")
        if c["gt_secondary_team_id"]:
            check(c["gt_secondary_team_id"] in id_sets["team"], f"case {c['id']}: unknown gt secondary team")

    print("Checking date ordering and status/resolution consistency...")
    for c in cases:
        created = datetime.strptime(c["created_date"], "%Y-%m-%d")
        if c["gt_resolved_date"]:
            resolved = datetime.strptime(c["gt_resolved_date"], "%Y-%m-%d")
            check(resolved >= created, f"case {c['id']}: resolved_date before created_date")
        if c["status"] == "open":
            check(c["gt_resolved_date"] == "", f"case {c['id']}: status=open but has resolved_date")
            check(c["gt_resolution_type_id"] == "", f"case {c['id']}: status=open but has resolution_type")
        else:
            check(c["gt_resolved_date"] != "", f"case {c['id']}: status={c['status']} but missing resolved_date")

    print("Checking subcategory-scoped ground truth (root cause / resolution / team / skills)...")
    valid_rc_by_sub = defaultdict(set)
    for r in sub_root_causes:
        valid_rc_by_sub[r["subcategory_id"]].add(r["root_cause_id"])
    valid_skills_by_sub = defaultdict(set)
    for r in sub_skills:
        valid_skills_by_sub[r["subcategory_id"]].add(r["skill_id"])
    valid_teams_by_sub = defaultdict(set)
    for r in sub_teams:
        valid_teams_by_sub[r["subcategory_id"]].add(r["team_id"])
    valid_resolutions_by_rc = defaultdict(set)
    for r in rc_resolutions:
        valid_resolutions_by_rc[r["root_cause_id"]].add(r["resolution_type_id"])

    for c in cases:
        sub = c["gt_issue_subcategory_id"]
        check(c["gt_root_cause_id"] in valid_rc_by_sub[sub],
              f"case {c['id']}: root cause not in subcategory {sub}'s plausible set")
        check(c["gt_primary_team_id"] in valid_teams_by_sub[sub],
              f"case {c['id']}: primary team not in subcategory {sub}'s team pool")
        if c["gt_resolution_type_id"]:
            check(c["gt_resolution_type_id"] in valid_resolutions_by_rc[c["gt_root_cause_id"]],
                  f"case {c['id']}: resolution not in root cause {c['gt_root_cause_id']}'s pool")

    required_skills_by_case = defaultdict(set)
    for r in case_required_skills:
        required_skills_by_case[r["case_id"]].add(r["skill_id"])
    for c in cases:
        sub = c["gt_issue_subcategory_id"]
        bad = required_skills_by_case[c["id"]] - valid_skills_by_sub[sub]
        check(not bad, f"case {c['id']}: required skill(s) {bad} not in subcategory {sub}'s skill pool")

    team_roles_by_case = defaultdict(set)
    for r in case_team_ownership:
        team_roles_by_case[r["case_id"]].add(r["team_id"])
    for c in cases:
        check(c["gt_primary_team_id"] in team_roles_by_case[c["id"]],
              f"case {c['id']}: primary team missing from case_team_ownership")

    print("Checking every component belongs to >=1 product...")
    pc = read_csv("product_components.csv")
    comp_with_product = {r["component_id"] for r in pc}
    orphan_components = id_sets["component"] - comp_with_product
    check(not orphan_components, f"components with no product: {orphan_components}")

    print("Checking severity is not a deterministic function of customer tier...")
    tier_by_customer = {c["id"]: c["tier"] for c in customers}
    from collections import Counter
    sev_by_tier = defaultdict(Counter)
    for c in cases:
        sev_by_tier[tier_by_customer[c["customer_id"]]][c["gt_severity"]] += 1
    for tier, counts in sev_by_tier.items():
        total = sum(counts.values())
        dist = {k: round(v / total, 2) for k, v in counts.items()}
        print(f"    {tier:8s} severity distribution: {dist}")
        check(len(counts) > 1, f"tier {tier} maps to a single severity value — looks deterministic")

    print()
    if failures:
        print(f"FAILED — {len(failures)} issue(s):")
        for f in failures[:50]:
            print("  -", f)
        if len(failures) > 50:
            print(f"  ... and {len(failures) - 50} more")
        sys.exit(1)
    else:
        print("PASSED — all consistency checks OK.")


if __name__ == "__main__":
    main()
