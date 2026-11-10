"""
Phase 1 case ground-truth generation — the deterministic "world physics" behind
every one of the 25,000 historical cases: product -> component -> issue
subcategory -> symptoms / root cause / resolution / team / skills / severity /
impact / dates / agent / CSAT, plus a difficulty archetype.

Ground truth is decided here, entirely in Python (random.seed(42)) — no LLM
calls happen in this file. narratives.py later turns each brief's *observable*
fields into customer-voice ticket text, using the difficulty archetype to
decide how much to hide, blur, or (for a tagged subset) get wrong.
"""
import random
from datetime import datetime, timedelta

random.seed(42)

REGIONS = ["US-East", "US-West", "EU-West", "EU-Central", "APAC", "LATAM", "ME", "ANZ"]
ENVIRONMENTS = ["production", "staging", "development", "sandbox"]
ENV_WEIGHTS = [0.65, 0.15, 0.12, 0.08]
IMPACT_BUCKETS = ["none", "low", "moderate", "high", "critical"]
IMPACT_WEIGHTS = [0.05, 0.30, 0.35, 0.20, 0.10]
DIFFICULTY_ARCHETYPES = [
    ("clear", 0.55), ("vague", 0.12), ("customer_misdiagnosis", 0.12),
    ("wrong_product_mentioned", 0.07), ("multi_component_symptoms", 0.08),
    ("dependency_root_cause", 0.06),
]

_OTHER_W = 0.40 / 47
_PRODUCT_CASE_WEIGHTS_OVERRIDE = {"P001": 0.25, "P002": 0.20, "P003": 0.15}


def _weighted_choice(pool):
    """pool: [(item, weight), ...] -> single item."""
    items = [p[0] for p in pool]
    weights = [p[1] for p in pool]
    return random.choices(items, weights=weights)[0]


def _weighted_sample(pool, k):
    items = [p[0] for p in pool]
    weights = [p[1] for p in pool]
    k = min(k, len(items))
    chosen, attempts = [], 0
    while len(chosen) < k and attempts < k * 25:
        pick = random.choices(items, weights=weights)[0]
        if pick not in chosen:
            chosen.append(pick)
        attempts += 1
    return chosen


def _zipf_choice(names):
    """Deterministic mild skew toward earlier items in a fixed-order list."""
    weights = [1.0 / (i + 1) for i in range(len(names))]
    return random.choices(names, weights=weights)[0]


def _impact_bucket_from_users(n_users):
    if n_users == 0:
        return "none"
    if n_users < 10:
        return "low"
    if n_users < 100:
        return "moderate"
    if n_users < 1000:
        return "high"
    return "critical"


def _sample_affected_users(company_size):
    scale = {"small": (0, 50), "mid": (0, 800), "enterprise": (0, 20000)}[company_size]
    lo, hi = scale
    if random.random() < 0.10:
        return 0
    return int(random.paretovariate(1.3) * (hi / 30)) if random.random() < 0.5 else random.randint(1, max(hi, 1))


def _severity_from_impact(impact_bucket):
    table = {
        "critical": [("Sev1", 0.70), ("Sev2", 0.25), ("Sev3", 0.05)],
        "high":     [("Sev1", 0.20), ("Sev2", 0.50), ("Sev3", 0.30)],
        "moderate": [("Sev2", 0.05), ("Sev3", 0.60), ("Sev4", 0.35)],
        "low":      [("Sev3", 0.10), ("Sev4", 0.90)],
        "none":     [("Sev3", 0.05), ("Sev4", 0.95)],
    }
    return _weighted_choice(table[impact_bucket])


def _priority_from_severity(sev):
    return {"Sev1": "high", "Sev2": "high", "Sev3": "medium", "Sev4": "low"}[sev]


def _rand_created_date(days_back=730):
    return datetime.now() - timedelta(days=random.randint(0, days_back))


def generate_case_briefs(n, structural):
    products = structural["products"]
    components = structural["components"]
    tag_lookup = structural["tag_lookup"]
    product_component_ids = structural["product_component_ids"]
    subcategories = structural["subcategories"]
    cat_id_to_key = structural["cat_id_to_key"]
    customers = structural["customers"]
    agents = structural["agents"]

    comp_by_id = {c["id"]: c for c in components}
    subs_by_category = {}
    for s in subcategories:
        subs_by_category.setdefault(s["category_id"], []).append(s)

    sub_symptoms_by_id, sub_rc_by_id, sub_skills_by_id, sub_teams_by_id = {}, {}, {}, {}
    for r in structural["sub_symptoms"]:
        sub_symptoms_by_id.setdefault(r["subcategory_id"], []).append((r["symptom_id"], r["weight"]))
    for r in structural["sub_root_causes"]:
        sub_rc_by_id.setdefault(r["subcategory_id"], []).append((r["root_cause_id"], r["weight"]))
    for r in structural["sub_skills"]:
        sub_skills_by_id.setdefault(r["subcategory_id"], []).append((r["skill_id"], r["weight"]))
    for r in structural["sub_teams"]:
        sub_teams_by_id.setdefault(r["subcategory_id"], []).append(r)

    rc_res_by_id = {}
    for r in structural["root_cause_resolutions"]:
        rc_res_by_id.setdefault(r["root_cause_id"], []).append((r["resolution_type_id"], r["weight"]))

    symptom_name_by_id = {s["id"]: s["name"] for s in structural["symptoms"]}
    root_cause_name_by_id = {r["id"]: r["name"] for r in structural["root_causes"]}
    resolution_name_by_id = {r["id"]: r["name"] for r in structural["resolution_types"]}
    component_name_by_id = {c["id"]: c["name"] for c in components}
    product_name_by_id = {p["id"]: p["name"] for p in products}
    subcat_by_id = {s["id"]: s for s in subcategories}
    category_name_by_id = {c["id"]: c["name"] for c in structural["categories"]}
    root_causes_by_name = {r["name"]: r for r in structural["root_causes"]}

    prod_ids = [p["id"] for p in products]
    prod_weights = [_PRODUCT_CASE_WEIGHTS_OVERRIDE.get(pid, _OTHER_W) for pid in prod_ids]

    tier_w = {"gold": 12, "silver": 5, "bronze": 2}
    cust_pool = [c["id"] for c in customers]
    cust_wts = [tier_w[c["tier"]] for c in customers]
    cust_by_id = {c["id"]: c for c in customers}

    # Agent pool with a fixed productivity-tier weighting (mirrors the original generator).
    n_ag = len(agents)
    order = list(range(n_ag))
    random.shuffle(order)
    prod_wts_agent = [0.0] * n_ag
    for rank, idx in enumerate(order):
        if rank < int(n_ag * 0.20):
            prod_wts_agent[idx] = 6.0
        elif rank < int(n_ag * 0.70):
            prod_wts_agent[idx] = 2.0
        else:
            prod_wts_agent[idx] = 0.5
    agent_ids = [a["id"] for a in agents]
    agent_sen = {a["id"]: a["seniority"] for a in agents}
    agent_team = {a["id"]: a["primary_team_id"] for a in agents}
    agents_by_team = {}
    for idx, a in enumerate(agents):
        agents_by_team.setdefault(a["primary_team_id"], []).append((a["id"], prod_wts_agent[idx]))

    briefs = []
    for i in range(1, n + 1):
        case_id = f"CS{i:05d}"

        product_id = _weighted_choice(list(zip(prod_ids, prod_weights)))
        component_id = random.choice(product_component_ids[product_id])
        comp_tags = tag_lookup[component_id]  # [(category_id, rank), ...]
        tag_weights = [(cat_id, 2.0 if rank == 0 else 1.0) for cat_id, rank in comp_tags]
        category_id = _weighted_choice(tag_weights)
        subcategory = _zipf_choice(subs_by_category[category_id])
        subcategory_id = subcategory["id"]

        symptom_pool = sub_symptoms_by_id[subcategory_id]
        n_symptoms = random.choices([1, 2, 3], weights=[0.35, 0.45, 0.20])[0]
        symptom_ids = _weighted_sample(symptom_pool, n_symptoms)

        root_cause_id = _weighted_choice(sub_rc_by_id[subcategory_id])
        root_cause_name = root_cause_name_by_id[root_cause_id]

        skill_pool = sub_skills_by_id[subcategory_id]
        n_skills = random.choices([1, 2, 3], weights=[0.30, 0.50, 0.20])[0]
        required_skill_ids = _weighted_sample(skill_pool, n_skills)

        team_rows = sub_teams_by_id[subcategory_id]
        primary_team_id = next(r["team_id"] for r in team_rows if r["role"] == "primary")
        secondary_candidates = [r["team_id"] for r in team_rows if r["role"] == "secondary"]
        secondary_team_id = random.choice(secondary_candidates) if secondary_candidates and random.random() < 0.6 else ""

        customer_id = _weighted_choice(list(zip(cust_pool, cust_wts)))
        customer = cust_by_id[customer_id]

        environment = _weighted_choice(list(zip(ENVIRONMENTS, ENV_WEIGHTS)))
        region = customer["region"] if random.random() < 0.85 else random.choice(REGIONS)

        true_affected_users = _sample_affected_users(customer["company_size"])
        true_impact = _impact_bucket_from_users(true_affected_users)
        severity = _severity_from_impact(true_impact)
        priority = _priority_from_severity(severity)

        # Reported (observable) figures can diverge from the true/confirmed ones.
        noise = random.uniform(0.5, 1.5)
        reported_affected_users = max(0, int(true_affected_users * noise))
        reported_impact = _impact_bucket_from_users(reported_affected_users)

        difficulty_archetype = _weighted_choice(DIFFICULTY_ARCHETYPES)

        status = random.choices(["resolved", "open", "escalated"], weights=[0.65, 0.25, 0.10])[0]
        created = _rand_created_date(730)

        tier_res_factor = {"gold": 0.85, "silver": 0.95, "bronze": 1.05}[customer["tier"]]
        sev_hours = {"Sev1": (1, 8), "Sev2": (4, 24), "Sev3": (12, 72), "Sev4": (24, 168)}[severity]
        duration_hours, resolved_date, resolution_type_id, escalated, reopened, csat = (
            "", "", "", False, False, "",
        )
        if status in ("resolved", "escalated"):
            lo, hi = sev_hours
            duration_hours = round(random.uniform(lo, hi) * tier_res_factor, 1)
            resolved_date = created + timedelta(hours=duration_hours)
            resolution_type_id = _weighted_choice(rc_res_by_id[root_cause_id])
            escalated = status == "escalated" or (severity in ("Sev1", "Sev2") and random.random() < 0.15)
            weak_resolution = resolution_name_by_id[resolution_type_id] in (
                "workaround", "customer-side fix confirmed", "known-issue workaround",
            )
            reopened = random.random() < (0.12 if weak_resolution else 0.05)
            base_csat = 4.2 - (duration_hours / max(sev_hours[1], 1)) * 1.5 - (0.8 if reopened else 0)
            csat = round(min(5.0, max(1.0, base_csat + random.uniform(-0.7, 0.7))), 1)
        else:
            escalated = severity == "Sev1" and random.random() < 0.2

        agent_pool = agents_by_team.get(primary_team_id, []) or list(zip(agent_ids, prod_wts_agent))
        if severity == "Sev1":
            agent_pool = [(aid, w) for aid, w in agent_pool if agent_sen[aid] != "junior"] or agent_pool
        assigned_agent_id = _weighted_choice(agent_pool) if agent_pool else random.choice(agent_ids)

        product_reported_id = product_id
        customer_asserted_cause = ""
        if difficulty_archetype == "wrong_product_mentioned":
            confusable = [p["id"] for p in products if p["category"] == next(
                pp["category"] for pp in products if pp["id"] == product_id) and p["id"] != product_id]
            if confusable:
                product_reported_id = random.choice(confusable)
        if difficulty_archetype == "customer_misdiagnosis":
            other_causes = [r["name"] for r in structural["root_causes"] if r["name"] != root_cause_name]
            customer_asserted_cause = random.choice(other_causes)

        extra_component_id = ""
        if difficulty_archetype == "multi_component_symptoms":
            others = [c for c in product_component_ids[product_id] if c != component_id]
            if others:
                extra_component_id = random.choice(others)

        briefs.append({
            "id": case_id,
            "customer_id": customer_id,
            "product_reported_id": product_reported_id,
            "environment": environment,
            "region": region,
            "reported_symptom_ids": symptom_ids,
            "reported_business_impact": reported_impact,
            "reported_affected_users": reported_affected_users,
            "priority": priority,
            "status": status,
            "created_date": created,
            "difficulty_archetype": difficulty_archetype,
            "customer_asserted_cause": customer_asserted_cause,
            "extra_component_id": extra_component_id,

            "gt_product_id": product_id,
            "gt_component_id": component_id,
            "gt_issue_category_id": category_id,
            "gt_issue_subcategory_id": subcategory_id,
            "gt_confirmed_symptom_ids": symptom_ids,
            "gt_root_cause_id": root_cause_id,
            "gt_resolution_type_id": resolution_type_id,
            "gt_primary_team_id": primary_team_id,
            "gt_secondary_team_id": secondary_team_id,
            "gt_required_skill_ids": required_skill_ids,
            "gt_severity": severity,
            "gt_true_business_impact": true_impact,
            "gt_true_affected_users": true_affected_users,
            "gt_resolution_duration_hours": duration_hours,
            "gt_resolved_date": resolved_date,
            "gt_escalated": escalated,
            "gt_reopened": reopened,
            "gt_csat_score": csat,
            "gt_assigned_agent_id": assigned_agent_id,

            # denormalized names, handy for narrative prompting / QA — not written as case columns
            "_product_name": product_name_by_id[product_id],
            "_product_reported_name": product_name_by_id[product_reported_id],
            "_component_name": component_name_by_id[component_id],
            "_extra_component_name": component_name_by_id.get(extra_component_id, ""),
            "_category_name": category_name_by_id[category_id],
            "_subcategory_name": subcategory["name"],
            "_symptom_names": [symptom_name_by_id[sid] for sid in symptom_ids],
            "_root_cause_name": root_cause_name,
            "_resolution_name": resolution_name_by_id.get(resolution_type_id, ""),
            "_customer_name": customer["name"],
            "_customer_tier": customer["tier"],
        })

    return briefs
