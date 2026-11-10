"""Read-only loaders for the frozen Phase 1 (data/raw_v2/) and Phase 2
(data/phase2/) datasets, indexed for Phase 3's per-case investigation
simulation. Nothing here ever opens a Phase 1 or Phase 2 file in write mode.

Phase 3 has no need for a wall-clock-free "now" anchor the way Phase 2 did:
every new timestamp it generates is an offset from a case's own already-fixed
`created_date`/`gt_resolved_date`, so there is no ambient/background
generation step to anchor.
"""
import csv
import os
from collections import defaultdict
from datetime import datetime

RAW_V1 = os.path.join(os.path.dirname(__file__), "..", "raw_v2")
PHASE2 = os.path.join(os.path.dirname(__file__), "..", "phase2")

PROFICIENCY_RANK = {"basic": 1, "intermediate": 2, "advanced": 3, "expert": 4}


def _read1(filename):
    with open(os.path.join(RAW_V1, filename), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read2(filename):
    with open(os.path.join(PHASE2, filename), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_date(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d")


def _parse_dt(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def load_all():
    # ── Phase 1 core ──────────────────────────────────────────────────────────
    cases = _read1("cases.csv")
    for c in cases:
        # status in {resolved, escalated, open}. Only "open" cases (~25%,
        # verified to still carry every gt_* diagnostic field except the
        # resolution-outcome ones) have these four fields blank — Phase 3
        # simulates their investigation identically but truncates the
        # observable trajectory before any resolution is reached.
        c["created_date"] = _parse_date(c["created_date"])
        c["gt_resolved_date"] = _parse_date(c["gt_resolved_date"]) if c["gt_resolved_date"] else None
        c["gt_resolution_duration_hours"] = float(c["gt_resolution_duration_hours"]) if c["gt_resolution_duration_hours"] else None
        c["gt_csat_score"] = float(c["gt_csat_score"]) if c["gt_csat_score"] else None
        c["is_open"] = c["status"] == "open"
        c["gt_escalated"] = c["gt_escalated"] == "true"
        c["gt_reopened"] = c["gt_reopened"] == "true"
        c["reported_affected_users"] = int(c["reported_affected_users"])
        c["gt_true_affected_users"] = int(c["gt_true_affected_users"])

    customers = _read1("customers.csv")
    agents = _read1("agents.csv")
    products = _read1("products.csv")
    components = _read1("components.csv")
    teams = _read1("teams.csv")
    skills = _read1("skills.csv")
    symptoms = _read1("symptoms.csv")
    issue_categories = _read1("issue_categories.csv")
    issue_subcategories = _read1("issue_subcategories.csv")
    root_causes = _read1("root_causes.csv")
    resolution_types = _read1("resolution_types.csv")
    knowledge_articles = _read1("knowledge_articles.csv")

    component_teams = _read1("component_teams.csv")
    product_teams = _read1("product_teams.csv")
    issue_subcategory_teams = _read1("issue_subcategory_teams.csv")
    issue_subcategory_symptoms = _read1("issue_subcategory_symptoms.csv")
    issue_subcategory_skills = _read1("issue_subcategory_skills.csv")
    issue_subcategory_root_causes = _read1("issue_subcategory_root_causes.csv")
    root_cause_resolutions = _read1("root_cause_resolutions.csv")
    product_components = _read1("product_components.csv")
    issue_subcategory_components = _read1("issue_subcategory_components.csv")

    case_symptoms = _read1("case_symptoms.csv")
    case_components = _read1("case_components.csv")
    case_required_skills = _read1("case_required_skills.csv")
    similar_cases = _read1("similar_cases.csv")

    agent_skills = _read1("agent_skills.csv")
    agent_teams = _read1("agent_teams.csv")
    agent_components = _read1("agent_components.csv")
    agent_products = _read1("agent_products.csv")
    agent_issue_category_experience = _read1("agent_issue_category_experience.csv")

    article_root_causes = _read1("article_root_causes.csv")
    article_issue_categories = _read1("article_issue_categories.csv")
    article_issue_subcategories = _read1("article_issue_subcategories.csv")
    article_components = _read1("article_components.csv")
    article_symptoms = _read1("article_symptoms.csv")

    # ── Phase 2 evidence ──────────────────────────────────────────────────────
    change_events = _read2("change_events.csv")
    change_by_id = {c["id"]: c for c in change_events}
    for c in change_events:
        c["started_at"] = _parse_dt(c["started_at"])
        c["completed_at"] = _parse_dt(c["completed_at"])
    case_change_links = _read2("case_change_links.csv")
    case_telemetry = _read2("case_telemetry.csv")
    for t in case_telemetry:
        t["timestamp"] = _parse_dt(t["timestamp"])
    case_signals = _read2("case_signals.csv")
    signal_by_id = {s["id"]: s for s in case_signals}
    for s in case_signals:
        s["timestamp"] = _parse_dt(s["timestamp"])
    configuration_snapshots = _read2("configuration_snapshots.csv")
    for cs in configuration_snapshots:
        cs["snapshot_at"] = _parse_dt(cs["snapshot_at"])
    incidents = _read2("incidents.csv")
    incident_by_id = {i["id"]: i for i in incidents}
    for i in incidents:
        i["started_at"] = _parse_dt(i["started_at"])
        i["ended_at"] = _parse_dt(i["ended_at"])
    incident_cases = _read2("incident_cases.csv")
    component_dependencies = _read2("component_dependencies.csv")
    agent_capacity = _read2("agent_capacity.csv")
    phase2_ground_truth = _read2("phase2_ground_truth.csv")
    phase2_observable = _read2("phase2_observable.csv")
    customer_entitlements = _read2("customer_entitlements.csv")
    sla_policies = _read2("sla_policies.csv")

    # ── Simple id -> name / id -> row lookups ────────────────────────────────
    cat_id_to_name = {c["id"]: c["name"] for c in issue_categories}
    subcat_id_to_name = {s["id"]: s["name"] for s in issue_subcategories}
    subcat_id_to_cat_id = {s["id"]: s["category_id"] for s in issue_subcategories}
    root_cause_id_to_name = {r["id"]: r["name"] for r in root_causes}
    root_cause_name_to_id = {v: k for k, v in root_cause_id_to_name.items()}
    resolution_type_id_to_name = {r["id"]: r["name"] for r in resolution_types}
    component_id_to_name = {c["id"]: c["name"] for c in components}
    product_id_to_name = {p["id"]: p["name"] for p in products}
    team_id_to_name = {t["id"]: t["name"] for t in teams}
    skill_id_to_name = {s["id"]: s["name"] for s in skills}
    agent_by_id = {a["id"]: a for a in agents}
    case_by_id = {c["id"]: c for c in cases}

    # ── Case-scoped Phase 1 observable indices ───────────────────────────────
    case_symptom_ids = defaultdict(list)
    for r in case_symptoms:
        case_symptom_ids[r["case_id"]].append(r["symptom_id"])

    case_component_ids = defaultdict(list)
    for r in case_components:
        case_component_ids[r["case_id"]].append(r["component_id"])

    case_required_skill_ids = defaultdict(list)
    for r in case_required_skills:
        case_required_skill_ids[r["case_id"]].append(r["skill_id"])

    similar_by_case = defaultdict(list)
    for r in similar_cases:
        score = float(r["similarity_score"])
        similar_by_case[r["case_id_a"]].append((r["case_id_b"], score))
        similar_by_case[r["case_id_b"]].append((r["case_id_a"], score))
    for cid in similar_by_case:
        similar_by_case[cid].sort(key=lambda t: -t[1])

    # symptom_id -> [(subcategory_id, weight)] — reverse of issue_subcategory_symptoms
    subcats_by_symptom = defaultdict(list)
    for r in issue_subcategory_symptoms:
        subcats_by_symptom[r["symptom_id"]].append((r["subcategory_id"], int(r["weight"])))

    # subcategory_id -> [(team_id, role, weight)]
    teams_by_subcategory = defaultdict(list)
    for r in issue_subcategory_teams:
        teams_by_subcategory[r["subcategory_id"]].append((r["team_id"], r["role"], float(r["weight"])))

    # component_id -> [(team_id, role, weight)]
    teams_by_component = defaultdict(list)
    for r in component_teams:
        teams_by_component[r["component_id"]].append((r["team_id"], r["role"], float(r["weight"])))

    # product_id -> [(team_id, role, weight)]
    teams_by_product = defaultdict(list)
    for r in product_teams:
        teams_by_product[r["product_id"]].append((r["team_id"], r["role"], float(r["weight"])))

    # product_id -> [component_id]
    components_by_product = defaultdict(list)
    for r in product_components:
        components_by_product[r["product_id"]].append(r["component_id"])

    # component_id -> {category_id: weight}, inferred from
    # issue_subcategory_components.csv (subcategory -> parent category) —
    # same derivation generators_phase2/load_phase1.py uses, reused here so a
    # "plausible wrong component under a plausible wrong category" guess is
    # grounded in the same structure Phase 2's evidence was grounded in.
    component_category_weights = defaultdict(lambda: defaultdict(float))
    for row in issue_subcategory_components:
        cat_id = subcat_id_to_cat_id.get(row["subcategory_id"])
        if cat_id:
            component_category_weights[row["component_id"]][cat_id] += float(row["weight"])

    # root_cause_id -> [(resolution_type_id, weight)]
    resolutions_by_root_cause = defaultdict(list)
    for r in root_cause_resolutions:
        resolutions_by_root_cause[r["root_cause_id"]].append((r["resolution_type_id"], float(r["weight"])))

    # subcategory_id -> [(root_cause_id, weight)] — used to name a plausible
    # "suspected_root_cause_name" for a hypothesis whose suspected subcategory
    # isn't (yet) known to be the true one.
    root_causes_by_subcategory = defaultdict(list)
    for r in issue_subcategory_root_causes:
        root_causes_by_subcategory[r["subcategory_id"]].append((r["root_cause_id"], float(r["weight"])))

    # ── Agent lookups ─────────────────────────────────────────────────────────
    agent_skill_rank = defaultdict(dict)  # agent_id -> {skill_id: rank_int}
    for r in agent_skills:
        agent_skill_rank[r["agent_id"]][r["skill_id"]] = PROFICIENCY_RANK.get(r["proficiency"], 1)

    agents_by_team = defaultdict(list)
    teams_by_agent = defaultdict(list)
    for r in agent_teams:
        agents_by_team[r["team_id"]].append(r["agent_id"])
        teams_by_agent[r["agent_id"]].append(r["team_id"])

    agent_component_set = defaultdict(set)
    for r in agent_components:
        agent_component_set[r["agent_id"]].add(r["component_id"])

    agent_product_set = defaultdict(set)
    for r in agent_products:
        agent_product_set[r["agent_id"]].add(r["product_id"])

    agent_category_experience = defaultdict(dict)  # agent_id -> {category_id: case_count}
    for r in agent_issue_category_experience:
        agent_category_experience[r["agent_id"]][r["category_id"]] = int(r["case_count"])

    utilization_by_agent = {r["agent_id"]: float(r["current_utilization_pct"]) for r in agent_capacity}

    # ── Knowledge-article relevance indices ──────────────────────────────────
    articles_by_root_cause = defaultdict(list)
    for r in article_root_causes:
        articles_by_root_cause[r["root_cause_id"]].append(r["article_id"])
    articles_by_category = defaultdict(list)
    for r in article_issue_categories:
        articles_by_category[r["category_id"]].append(r["article_id"])
    articles_by_subcategory = defaultdict(list)
    for r in article_issue_subcategories:
        articles_by_subcategory[r["subcategory_id"]].append(r["article_id"])
    articles_by_component = defaultdict(list)
    for r in article_components:
        articles_by_component[r["component_id"]].append(r["article_id"])
    articles_by_symptom = defaultdict(list)
    for r in article_symptoms:
        articles_by_symptom[r["symptom_id"]].append(r["article_id"])
    article_by_id = {a["id"]: a for a in knowledge_articles}

    # ── Phase 2 case-scoped indices ──────────────────────────────────────────
    change_events_by_case = defaultdict(list)
    for r in case_change_links:
        ch = change_by_id.get(r["change_event_id"])
        if ch:
            change_events_by_case[r["case_id"]].append(ch)
    for evs in change_events_by_case.values():
        evs.sort(key=lambda c: c["started_at"])

    telemetry_by_case = defaultdict(list)
    for r in case_telemetry:
        telemetry_by_case[r["case_id"]].append(r)
    for rows in telemetry_by_case.values():
        rows.sort(key=lambda t: t["timestamp"])

    signals_by_case = defaultdict(list)
    for r in case_signals:
        signals_by_case[r["case_id"]].append(r)
    for rows in signals_by_case.values():
        rows.sort(key=lambda s: s["timestamp"])

    config_snapshots_by_case = defaultdict(list)
    for r in configuration_snapshots:
        config_snapshots_by_case[r["case_id"]].append(r)
    for rows in config_snapshots_by_case.values():
        rows.sort(key=lambda c: c["snapshot_at"])

    incident_case_by_case = {}
    for r in incident_cases:
        incident_case_by_case[r["case_id"]] = {"incident_id": r["incident_id"], "relationship": r["relationship"]}

    dependents_by_component = defaultdict(list)
    for r in component_dependencies:
        dependents_by_component[r["depends_on_component_id"]].append(r["component_id"])
    dependencies_by_component = defaultdict(list)
    for r in component_dependencies:
        dependencies_by_component[r["component_id"]].append((r["depends_on_component_id"], float(r["weight"])))

    p2gt_by_case = {r["case_id"]: r for r in phase2_ground_truth}
    p2obs_by_case = {r["case_id"]: r for r in phase2_observable}

    support_plan_by_customer = {r["customer_id"]: r["support_plan_id"] for r in customer_entitlements}
    sla_resolution_hours = {(r["support_plan_id"], r["severity"]): float(r["resolution_time_hours"])
                             for r in sla_policies}

    def sla_target_hours(customer_id, severity):
        plan = support_plan_by_customer.get(customer_id)
        return sla_resolution_hours.get((plan, severity)) if plan else None

    return {
        "cases": cases,
        "case_by_id": case_by_id,
        "customers": customers,
        "agents": agents,
        "agent_by_id": agent_by_id,
        "products": products,
        "components": components,
        "teams": teams,
        "skills": skills,
        "symptoms": symptoms,
        "knowledge_articles": knowledge_articles,
        "article_by_id": article_by_id,
        "cat_id_to_name": cat_id_to_name,
        "subcat_id_to_name": subcat_id_to_name,
        "subcat_id_to_cat_id": subcat_id_to_cat_id,
        "root_cause_id_to_name": root_cause_id_to_name,
        "root_cause_name_to_id": root_cause_name_to_id,
        "resolution_type_id_to_name": resolution_type_id_to_name,
        "component_id_to_name": component_id_to_name,
        "product_id_to_name": product_id_to_name,
        "team_id_to_name": team_id_to_name,
        "skill_id_to_name": skill_id_to_name,
        "case_symptom_ids": case_symptom_ids,
        "case_component_ids": case_component_ids,
        "case_required_skill_ids": case_required_skill_ids,
        "similar_by_case": similar_by_case,
        "subcats_by_symptom": subcats_by_symptom,
        "teams_by_subcategory": teams_by_subcategory,
        "teams_by_component": teams_by_component,
        "teams_by_product": teams_by_product,
        "components_by_product": components_by_product,
        "component_category_weights": component_category_weights,
        "resolutions_by_root_cause": resolutions_by_root_cause,
        "root_causes_by_subcategory": root_causes_by_subcategory,
        "agent_skill_rank": agent_skill_rank,
        "agents_by_team": agents_by_team,
        "teams_by_agent": teams_by_agent,
        "agent_component_set": agent_component_set,
        "agent_product_set": agent_product_set,
        "agent_category_experience": agent_category_experience,
        "utilization_by_agent": utilization_by_agent,
        "articles_by_root_cause": articles_by_root_cause,
        "articles_by_category": articles_by_category,
        "articles_by_subcategory": articles_by_subcategory,
        "articles_by_component": articles_by_component,
        "articles_by_symptom": articles_by_symptom,
        "change_events_by_case": change_events_by_case,
        "telemetry_by_case": telemetry_by_case,
        "signals_by_case": signals_by_case,
        "signal_by_id": signal_by_id,
        "config_snapshots_by_case": config_snapshots_by_case,
        "incident_by_id": incident_by_id,
        "incident_case_by_case": incident_case_by_case,
        "dependents_by_component": dependents_by_component,
        "dependencies_by_component": dependencies_by_component,
        "p2gt_by_case": p2gt_by_case,
        "p2obs_by_case": p2obs_by_case,
        "sla_target_hours": sla_target_hours,
    }
