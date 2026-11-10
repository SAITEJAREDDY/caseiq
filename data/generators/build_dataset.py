"""
Phase 1 dataset orchestrator.

Usage:
    python build_dataset.py --pilot 50       # small LLM pilot (sanity-check narrative quality)
    python build_dataset.py --skip-narratives  # structural + ground truth only, no API calls
    python build_dataset.py --full           # full 25,000-case / 900-article run (writes CSVs)

Order: build the ontology + structural tables (deterministic) -> generate case
ground truth (deterministic) -> fill narrative text via Together AI (only stage
that calls an LLM, cached/resumable) -> compute customer/agent historical
aggregates -> write every CSV to ../raw_v2/.
"""
import argparse
import random
import sys
import time
from collections import Counter, defaultdict

import generate_cases as gc
import generate_structural as gs
import narratives as nar
from csv_io import write_csv
import llm_client
from llm_client import TogetherAuthError

random.seed(42)


def _bool(v):
    return "true" if v else "false"


def compute_customer_aggregates(customers, briefs):
    counts, escalations = Counter(), Counter()
    for b in briefs:
        counts[b["customer_id"]] += 1
        if b["gt_escalated"]:
            escalations[b["customer_id"]] += 1
    for c in customers:
        total = counts.get(c["id"], 0)
        c["historical_case_volume"] = total
        c["historical_escalation_rate"] = round(escalations.get(c["id"], 0) / total, 3) if total else 0.0


def compute_agent_aggregates(agents, briefs):
    counts = Counter(b["gt_assigned_agent_id"] for b in briefs)
    for a in agents:
        a["historical_case_volume"] = counts.get(a["id"], 0)


def build_agent_category_experience(briefs):
    counts = Counter((b["gt_assigned_agent_id"], b["gt_issue_category_id"]) for b in briefs)
    return [{"agent_id": aid, "category_id": cid, "case_count": n} for (aid, cid), n in counts.items()]


def write_case_tables(briefs):
    cases, observable, ground_truth = [], [], []
    customer_cases, case_products, case_components = [], [], []
    case_symptoms, case_required_skills, case_team_ownership, agent_cases = [], [], [], []

    for b in briefs:
        cases.append({
            "id": b["id"], "title": b["title"], "description": b["description"],
            "customer_id": b["customer_id"], "product_reported_id": b["product_reported_id"],
            "environment": b["environment"], "region": b["region"],
            "reported_business_impact": b["reported_business_impact"],
            "reported_affected_users": b["reported_affected_users"],
            "priority": b["priority"], "status": b["status"],
            "created_date": b["created_date"].strftime("%Y-%m-%d"),
            "gt_product_id": b["gt_product_id"], "gt_component_id": b["gt_component_id"],
            "gt_issue_category_id": b["gt_issue_category_id"],
            "gt_issue_subcategory_id": b["gt_issue_subcategory_id"],
            "gt_root_cause_id": b["gt_root_cause_id"], "gt_resolution_type_id": b["gt_resolution_type_id"],
            "gt_primary_team_id": b["gt_primary_team_id"], "gt_secondary_team_id": b["gt_secondary_team_id"],
            "gt_severity": b["gt_severity"], "gt_true_business_impact": b["gt_true_business_impact"],
            "gt_true_affected_users": b["gt_true_affected_users"],
            "gt_resolution_duration_hours": b["gt_resolution_duration_hours"],
            "gt_resolved_date": b["gt_resolved_date"].strftime("%Y-%m-%d") if b["gt_resolved_date"] else "",
            "gt_escalated": _bool(b["gt_escalated"]), "gt_reopened": _bool(b["gt_reopened"]),
            "gt_csat_score": b["gt_csat_score"], "gt_assigned_agent_id": b["gt_assigned_agent_id"],
            "gt_difficulty_archetype": b["difficulty_archetype"],
        })

        observable.append({k: cases[-1][k] for k in
                            ["id", "title", "description", "customer_id", "product_reported_id",
                             "environment", "region", "reported_business_impact",
                             "reported_affected_users", "priority", "status", "created_date"]})
        ground_truth.append({k: v for k, v in cases[-1].items()
                              if k == "id" or k.startswith("gt_")})

        customer_cases.append({"customer_id": b["customer_id"], "case_id": b["id"]})
        case_products.append({"case_id": b["id"], "product_id": b["product_reported_id"], "relation": "reported"})
        case_products.append({"case_id": b["id"], "product_id": b["gt_product_id"], "relation": "confirmed"})

        case_components.append({"case_id": b["id"], "component_id": b["gt_component_id"], "relation": "confirmed"})
        if b["extra_component_id"]:
            case_components.append({"case_id": b["id"], "component_id": b["extra_component_id"], "relation": "candidate"})

        for sid in b["gt_confirmed_symptom_ids"]:
            case_symptoms.append({"case_id": b["id"], "symptom_id": sid})
        for skid in b["gt_required_skill_ids"]:
            case_required_skills.append({"case_id": b["id"], "skill_id": skid})

        case_team_ownership.append({"case_id": b["id"], "team_id": b["gt_primary_team_id"], "role": "primary"})
        if b["gt_secondary_team_id"]:
            case_team_ownership.append({"case_id": b["id"], "team_id": b["gt_secondary_team_id"], "role": "secondary"})

        if b["status"] == "resolved":
            role = "resolved"
        elif b["status"] == "escalated":
            role = "resolved_escalated"
        else:
            role = "assigned"
        agent_cases.append({"agent_id": b["gt_assigned_agent_id"], "case_id": b["id"], "role": role})

    write_csv("cases.csv", cases, list(cases[0].keys()))
    write_csv("case_observable.csv", observable, list(observable[0].keys()))
    write_csv("case_ground_truth.csv", ground_truth, list(ground_truth[0].keys()))
    write_csv("customer_cases.csv", customer_cases, ["customer_id", "case_id"])
    write_csv("case_products.csv", case_products, ["case_id", "product_id", "relation"])
    write_csv("case_components.csv", case_components, ["case_id", "component_id", "relation"])
    write_csv("case_symptoms.csv", case_symptoms, ["case_id", "symptom_id"])
    write_csv("case_required_skills.csv", case_required_skills, ["case_id", "skill_id"])
    write_csv("case_team_ownership.csv", case_team_ownership, ["case_id", "team_id", "role"])
    write_csv("agent_cases.csv", agent_cases, ["agent_id", "case_id", "role"])
    return cases


def build_similar_cases(briefs, max_pairs=12000):
    by_subcat = defaultdict(list)
    for b in briefs:
        by_subcat[b["gt_issue_subcategory_id"]].append(b["id"])

    rows, seen = [], set()
    for subcat, ids in by_subcat.items():
        if len(ids) < 2:
            continue
        n_pairs = min(len(ids) // 2, 120)
        added, attempts = 0, 0
        while added < n_pairs and attempts < n_pairs * 10:
            a, b = random.sample(ids, 2)
            key = tuple(sorted([a, b]))
            if key not in seen:
                rows.append({"case_id_a": a, "case_id_b": b, "similarity_score": round(random.uniform(0.55, 0.99), 2)})
                seen.add(key)
                added += 1
            attempts += 1

    random.shuffle(rows)
    rows = rows[:max_pairs]
    write_csv("similar_cases.csv", rows, ["case_id_a", "case_id_b", "similarity_score"])


def build_case_articles(briefs, kb_briefs):
    by_subcat = defaultdict(list)
    for a in kb_briefs:
        for sid in a["_subcategory_ids"]:
            by_subcat[sid].append(a)
    by_category = defaultdict(list)
    for a in kb_briefs:
        by_category[a["_category_id"]].append(a)

    rows = []
    for b in briefs:
        if b["status"] not in ("resolved", "escalated"):
            continue
        if random.random() > 0.85:
            continue
        candidates = by_subcat.get(b["gt_issue_subcategory_id"], []) or by_category.get(b["gt_issue_category_id"], [])
        if not candidates:
            continue
        n = random.choices([1, 2], weights=[0.7, 0.3])[0]
        picked = random.sample(candidates, k=min(n, len(candidates)))
        for a in picked:
            rows.append({"case_id": b["id"], "article_id": a["id"]})
    write_csv("case_articles.csv", rows, ["case_id", "article_id"])


def write_kb_tables(kb_briefs):
    articles = [{
        "id": a["id"], "title": a["title"], "content_summary": a["content_summary"],
        "content_body": a["content_body"], "specificity": a["specificity"],
        "resolution_rate": a["resolution_rate"], "views": a["views"],
        "created_date": a["created_date"], "outdated": _bool(a["outdated"]),
    } for a in kb_briefs]
    write_csv("knowledge_articles.csv", articles, list(articles[0].keys()))

    def rel(field, out_name, col):
        rows = [{"article_id": a["id"], col: v} for a in kb_briefs for v in a[field]]
        write_csv(out_name, rows, ["article_id", col])

    rel("_product_ids", "article_products.csv", "product_id")
    rel("_component_ids", "article_components.csv", "component_id")
    rel("_subcategory_ids", "article_issue_subcategories.csv", "subcategory_id")
    rel("_symptom_ids", "article_symptoms.csv", "symptom_id")
    rel("_root_cause_ids", "article_root_causes.csv", "root_cause_id")
    rel("_resolution_ids", "article_resolutions.csv", "resolution_type_id")
    write_csv("article_issue_categories.csv",
              [{"article_id": a["id"], "category_id": a["_category_id"]} for a in kb_briefs],
              ["article_id", "category_id"])


def run(n_customers, n_agents, n_articles, n_cases, do_narratives, seed=42):
    t0 = time.time()
    print("Building ontology + structural tables...")
    structural = gs.build_all(n_customers=n_customers, n_agents=n_agents, n_articles=n_articles)
    gs.write_static_tables(structural)
    print(f"  done in {time.time() - t0:.1f}s\n")

    print(f"Generating {n_cases:,} case ground-truth briefs...")
    t1 = time.time()
    briefs = gc.generate_case_briefs(n_cases, structural)
    print(f"  done in {time.time() - t1:.1f}s\n")

    if do_narratives:
        print(f"Generating case narratives via Together AI ({len(briefs):,} cases)...")
        t2 = time.time()
        try:
            nar.fill_case_narratives(briefs, seed=seed)
        except TogetherAuthError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        llm_client.print_usage_summary()
        print(f"  done in {time.time() - t2:.1f}s\n")

        print(f"Generating KB article narratives via Together AI ({len(structural['kb_briefs']):,} articles)...")
        t3 = time.time()
        name_lookup = {
            "category": {c["id"]: c["name"] for c in structural["categories"]},
            "subcategory": {s["id"]: s["name"] for s in structural["subcategories"]},
            "symptom": {s["id"]: s["name"] for s in structural["symptoms"]},
            "root_cause": {r["id"]: r["name"] for r in structural["root_causes"]},
            "resolution": {r["id"]: r["name"] for r in structural["resolution_types"]},
            "product": {p["id"]: p["name"] for p in structural["products"]},
        }
        try:
            nar.fill_article_narratives(structural["kb_briefs"], name_lookup, seed=seed)
        except TogetherAuthError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        llm_client.print_usage_summary()
        print(f"  done in {time.time() - t3:.1f}s\n")
    else:
        print("Skipping narrative generation (--skip-narratives); using template placeholders.\n")
        for b in briefs:
            nar._template_fallback_case(b)
        for a in structural["kb_briefs"]:
            nar._template_fallback_article(a)

    print("Computing customer/agent historical aggregates...")
    compute_customer_aggregates(structural["customers"], briefs)
    compute_agent_aggregates(structural["agents"], briefs)
    write_csv("customers.csv", structural["customers"],
              ["id", "name", "tier", "region", "industry", "company_size", "num_products_deployed",
               "deployment_complexity", "technical_maturity", "tenure_months",
               "historical_case_volume", "historical_escalation_rate"])
    write_csv("agents.csv", structural["agents"],
              ["id", "name", "seniority", "primary_team_id", "avg_resolution_time_hours",
               "historical_case_volume"])
    write_csv("agent_issue_category_experience.csv", build_agent_category_experience(briefs),
              ["agent_id", "category_id", "case_count"])
    print()

    print("Writing case tables...")
    write_case_tables(briefs)
    build_similar_cases(briefs)
    print()

    print("Writing KB article tables...")
    write_kb_tables(structural["kb_briefs"])
    build_case_articles(briefs, structural["kb_briefs"])

    print(f"\nTotal build time: {time.time() - t0:.1f}s")
    return structural, briefs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=int, default=0, help="Run a small pilot of N cases through the LLM stage")
    parser.add_argument("--skip-narratives", action="store_true", help="Skip LLM calls, use template placeholders")
    parser.add_argument("--full", action="store_true", help="Run the full target-scale build")
    args = parser.parse_args()

    if args.pilot:
        run(n_customers=200, n_agents=20, n_articles=15, n_cases=args.pilot, do_narratives=True)
    elif args.full:
        run(n_customers=5000, n_agents=180, n_articles=900, n_cases=25000, do_narratives=True)
    elif args.skip_narratives:
        run(n_customers=5000, n_agents=180, n_articles=900, n_cases=25000, do_narratives=False)
    else:
        parser.print_help()
