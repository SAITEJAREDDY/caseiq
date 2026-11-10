"""
Phase 1 structural generation — every table that does NOT need natural-language
text. Fully deterministic (random.seed(42) / Faker.seed(42)), no LLM calls.

Customer/agent "historical_*" aggregate fields and KB article title/body text
are intentionally left blank here: they depend on cases (not generated yet) or
on the LLM narrative stage, and are filled in by build_dataset.py afterwards.
"""
import random
from datetime import datetime, timedelta

from faker import Faker

import taxonomy as tax
from csv_io import write_csv

fake = Faker()
random.seed(42)
Faker.seed(42)

REGIONS = ["US-East", "US-West", "EU-West", "EU-Central", "APAC", "LATAM", "ME", "ANZ"]
INDUSTRIES = ["Financial Services", "Healthcare", "Retail & E-commerce", "SaaS / Technology",
              "Manufacturing", "Public Sector", "Media & Entertainment", "Education",
              "Logistics & Transportation", "Energy & Utilities", "Telecom", "Insurance"]
COMPANY_SIZES = [("small", 0.40), ("mid", 0.40), ("enterprise", 0.20)]
MATURITY_LEVELS = ["low", "medium", "high"]


def _weighted_sample_unique(pool, k):
    """Sample up to k unique items from a [(item, weight), ...] pool."""
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


# ── Reference / taxonomy tables ────────────────────────────────────────────────

def build_issue_categories():
    rows, key_to_id = [], {}
    for i, (key, name) in enumerate(tax.ISSUE_CATEGORY_DEFS, start=1):
        cid = f"IC{i:02d}"
        key_to_id[key] = cid
        rows.append({"id": cid, "name": name})
    return rows, key_to_id


def build_issue_subcategories(key_to_id):
    rows, id_by_key = [], {}
    i = 1
    for cat_key, names in tax.ISSUE_SUBCATEGORY_DEFS.items():
        for name in names:
            sid = f"IS{i:03d}"
            rows.append({"id": sid, "category_id": key_to_id[cat_key], "name": name})
            id_by_key[(cat_key, name)] = sid
            i += 1
    return rows, id_by_key


def build_symptoms():
    rows, id_by_name = [], {}
    for i, name in enumerate(tax.SYMPTOM_NAMES, start=1):
        sid = f"SY{i:03d}"
        rows.append({"id": sid, "name": name})
        id_by_name[name] = sid
    return rows, id_by_name


def build_root_causes():
    rows, id_by_name = [], {}
    for i, name in enumerate(tax.ROOT_CAUSE_NAMES, start=1):
        rid = f"RC{i:02d}"
        rows.append({"id": rid, "name": name})
        id_by_name[name] = rid
    return rows, id_by_name


def build_resolution_types():
    rows, id_by_name = [], {}
    for i, name in enumerate(tax.RESOLUTION_TYPE_NAMES, start=1):
        rid = f"RT{i:02d}"
        rows.append({"id": rid, "name": name})
        id_by_name[name] = rid
    return rows, id_by_name


def build_teams():
    rows, id_by_key = [], {}
    for i, (key, name, desc) in enumerate(tax.TEAM_DEFS, start=1):
        tid = f"TM{i:02d}"
        rows.append({"id": tid, "name": name, "description": desc})
        id_by_key[key] = tid
    return rows, id_by_key


def build_skills():
    return [{"id": sid, "name": name, "category": cat} for sid, name, cat in tax.SKILL_DATA]


def build_products():
    return [{"id": pid, "name": name, "category": cat, "version": ver}
            for pid, name, cat, ver in tax.PRODUCT_DATA]


def build_components(cat_key_to_id):
    """Returns (rows, tag_lookup) where tag_lookup[component_id] = [(category_id, rank), ...]
    rank 0 = primary tag (weight 2), rank>=1 = secondary tag (weight 1)."""
    rows, tag_lookup = [], {}
    i = 1
    for prod_category, comps in tax.COMPONENT_ARCHETYPES.items():
        for name, cat_keys in comps:
            cid = f"CM{i:03d}"
            rows.append({"id": cid, "name": name, "origin_product_category": prod_category})
            tag_lookup[cid] = [(cat_key_to_id[k], rank) for rank, k in enumerate(cat_keys)]
            i += 1
    for name, cat_keys in tax.SHARED_COMPONENT_DATA:
        cid = f"CM{i:03d}"
        rows.append({"id": cid, "name": name, "origin_product_category": "Shared"})
        tag_lookup[cid] = [(cat_key_to_id[k], rank) for rank, k in enumerate(cat_keys)]
        i += 1
    return rows, tag_lookup


# ── Relationship tables built from the taxonomy pools ──────────────────────────

def build_product_components(products, components, tag_lookup):
    """Each product draws 5-8 components from its own category's archetype pool
    (by origin_product_category) plus 1-3 shared components."""
    by_origin = {}
    for c in components:
        by_origin.setdefault(c["origin_product_category"], []).append(c["id"])
    shared_ids = by_origin.get("Shared", [])

    rows = []
    product_component_ids = {}
    for p in products:
        own_pool = by_origin.get(p["category"], [])
        own_pool_weighted = [(cid, 1.0) for cid in own_pool]
        k_own = random.randint(5, 8)
        picked_own = _weighted_sample_unique(own_pool_weighted, k_own)

        shared_weighted = [(cid, 1.0) for cid in shared_ids]
        k_shared = random.randint(1, 3)
        picked_shared = _weighted_sample_unique(shared_weighted, k_shared)

        chosen = picked_own + picked_shared
        product_component_ids[p["id"]] = chosen
        for cid in chosen:
            rows.append({"product_id": p["id"], "component_id": cid})

    # Coverage guarantee: every component must belong to >=1 product. Force-attach
    # any orphaned component to a random product from its origin category (or any
    # product, for shared components).
    used = {cid for cids in product_component_ids.values() for cid in cids}
    products_by_origin = {}
    for p in products:
        products_by_origin.setdefault(p["category"], []).append(p["id"])
    all_product_ids = [p["id"] for p in products]

    for c in components:
        if c["id"] in used:
            continue
        candidates = products_by_origin.get(c["origin_product_category"], all_product_ids)
        pid = random.choice(candidates)
        product_component_ids[pid].append(c["id"])
        rows.append({"product_id": pid, "component_id": c["id"]})
        used.add(c["id"])

    return rows, product_component_ids


def build_product_teams(products, team_id_by_key):
    rows = []
    for p in products:
        pool = tax.PRODUCT_CATEGORY_TEAM_POOL[p["category"]]
        ranked = sorted(pool, key=lambda x: -x[1])
        for rank, (team_key, weight) in enumerate(ranked):
            rows.append({
                "product_id": p["id"], "team_id": team_id_by_key[team_key],
                "role": "primary" if rank == 0 else "secondary", "weight": weight,
            })
    return rows


def build_component_teams(components, tag_lookup, cat_id_to_key, team_id_by_key):
    rows = []
    for c in components:
        merged = {}
        for cat_id, rank in tag_lookup[c["id"]]:
            cat_key = cat_id_to_key[cat_id]
            for team_key, weight in tax.CATEGORY_TEAM_POOL.get(cat_key, []):
                # a primary category tag (rank 0) counts full weight; secondary tag half
                w = weight if rank == 0 else weight * 0.5
                merged[team_key] = max(merged.get(team_key, 0), w)
        ranked = sorted(merged.items(), key=lambda x: -x[1])[:2]
        for rank, (team_key, weight) in enumerate(ranked):
            rows.append({
                "component_id": c["id"], "team_id": team_id_by_key[team_key],
                "role": "primary" if rank == 0 else "secondary", "weight": round(weight, 2),
            })
    return rows


def build_issue_subcategory_relations(subcategories, cat_id_to_key, symptom_id_by_name,
                                       root_cause_id_by_name, skill_id_by_name,
                                       team_id_by_key, components, tag_lookup):
    comps_by_category = {}
    for c in components:
        for cat_id, rank in tag_lookup[c["id"]]:
            comps_by_category.setdefault(cat_id, []).append((c["id"], 2 if rank == 0 else 1))

    sub_symptoms, sub_components, sub_skills, sub_teams, sub_root_causes = [], [], [], [], []

    for s in subcategories:
        cat_key = cat_id_to_key[s["category_id"]]

        sym_pool = tax.CATEGORY_SYMPTOM_POOL[cat_key]
        for name in _weighted_sample_unique(sym_pool, random.randint(4, 6)):
            w = dict(sym_pool)[name]
            sub_symptoms.append({"subcategory_id": s["id"], "symptom_id": symptom_id_by_name[name], "weight": w})

        rc_pool = tax.CATEGORY_ROOT_CAUSE_POOL[cat_key]
        for name in _weighted_sample_unique(rc_pool, random.randint(2, min(4, len(rc_pool)))):
            w = dict(rc_pool)[name]
            sub_root_causes.append({"subcategory_id": s["id"], "root_cause_id": root_cause_id_by_name[name], "weight": w})

        sk_pool = tax.CATEGORY_SKILL_POOL[cat_key]
        for name in _weighted_sample_unique(sk_pool, random.randint(2, min(3, len(sk_pool)))):
            w = dict(sk_pool)[name]
            sub_skills.append({"subcategory_id": s["id"], "skill_id": skill_id_by_name[name], "weight": w})

        team_pool = tax.CATEGORY_TEAM_POOL[cat_key]
        # Weighted-random primary pick (ties in the pool → genuine ambiguity across subcategories)
        team_keys = [t[0] for t in team_pool]
        team_wts = [t[1] for t in team_pool]
        primary_key = random.choices(team_keys, weights=team_wts)[0]
        sub_teams.append({"subcategory_id": s["id"], "team_id": team_id_by_key[primary_key],
                           "role": "primary", "weight": dict(team_pool)[primary_key]})
        for team_key, weight in team_pool:
            if team_key != primary_key:
                sub_teams.append({"subcategory_id": s["id"], "team_id": team_id_by_key[team_key],
                                   "role": "secondary", "weight": weight})

        comp_pool = comps_by_category.get(s["category_id"], [])
        for cid in _weighted_sample_unique(comp_pool, min(8, len(comp_pool))):
            w = dict(comp_pool)[cid]
            sub_components.append({"subcategory_id": s["id"], "component_id": cid, "weight": w})

    return sub_symptoms, sub_components, sub_skills, sub_teams, sub_root_causes


def build_root_cause_resolutions(root_causes, resolution_id_by_name, root_cause_id_by_name):
    rows = []
    for rc in root_causes:
        pool = tax.ROOT_CAUSE_RESOLUTION_POOL[rc["name"]]
        for name, weight in pool:
            rows.append({"root_cause_id": rc["id"], "resolution_type_id": resolution_id_by_name[name], "weight": weight})
    return rows


# ── Customers ───────────────────────────────────────────────────────────────────

def build_customers(n=5000):
    n_gold, n_silver = int(n * 0.10), int(n * 0.30)
    n_bronze = n - n_gold - n_silver
    tiers = ["gold"] * n_gold + ["silver"] * n_silver + ["bronze"] * n_bronze
    random.shuffle(tiers)

    size_names = [s[0] for s in COMPANY_SIZES]
    size_wts = [s[1] for s in COMPANY_SIZES]

    rows = []
    for i in range(1, n + 1):
        size = random.choices(size_names, weights=size_wts)[0]
        num_products = {"small": random.randint(1, 3), "mid": random.randint(2, 6),
                         "enterprise": random.randint(4, 15)}[size]
        complexity = random.choices(["low", "medium", "high"],
                                     weights={"small": [0.6, 0.3, 0.1], "mid": [0.3, 0.5, 0.2],
                                              "enterprise": [0.1, 0.4, 0.5]}[size])[0]
        rows.append({
            "id": f"C{i:05d}",
            "name": fake.company(),
            "tier": tiers[i - 1],
            "region": random.choice(REGIONS),
            "industry": random.choice(INDUSTRIES),
            "company_size": size,
            "num_products_deployed": num_products,
            "deployment_complexity": complexity,
            "technical_maturity": random.choices(MATURITY_LEVELS, weights=[0.3, 0.45, 0.25])[0],
            "tenure_months": random.randint(1, 96),
            # filled after case generation:
            "historical_case_volume": 0,
            "historical_escalation_rate": 0.0,
        })
    return rows


# ── Agents ──────────────────────────────────────────────────────────────────────

def build_agents(n, teams, skills, products, components, team_id_by_key):
    n_senior, n_mid = int(n * 0.20), int(n * 0.50)
    n_junior = n - n_senior - n_mid
    seniorities = ["senior"] * n_senior + ["mid"] * n_mid + ["junior"] * n_junior
    random.shuffle(seniorities)
    res_range = {"senior": (1.0, 12.0), "mid": (2.0, 20.0), "junior": (4.0, 36.0)}

    team_ids = [t["id"] for t in teams]
    product_ids = [p["id"] for p in products]
    component_ids = [c["id"] for c in components]
    skill_ids = [s["id"] for s in skills]
    skill_cat_by_id = {s["id"]: s["category"] for s in skills}
    cat_weight = {"technical": 3, "billing": 2, "product": 1}

    rows, agent_skills, agent_products, agent_components, agent_teams = [], [], [], [], []
    for i in range(1, n + 1):
        aid = f"A{i:03d}"
        sen = seniorities[i - 1]
        lo, hi = res_range[sen]
        team_id = random.choice(team_ids)

        rows.append({
            "id": aid, "name": fake.name(), "seniority": sen, "primary_team_id": team_id,
            "avg_resolution_time_hours": round(random.uniform(lo, hi), 1),
            "historical_case_volume": 0,
        })
        agent_teams.append({"agent_id": aid, "team_id": team_id})

        n_skills = {"senior": random.randint(5, 9), "mid": random.randint(4, 7),
                    "junior": random.randint(2, 4)}[sen]
        wts = [cat_weight.get(skill_cat_by_id[sid], 1) for sid in skill_ids]
        chosen_skills = _weighted_sample_unique(list(zip(skill_ids, wts)), n_skills)
        for sid in chosen_skills:
            proficiency = random.choices(["basic", "intermediate", "expert"],
                                          weights={"senior": [0.1, 0.35, 0.55], "mid": [0.25, 0.55, 0.20],
                                                   "junior": [0.55, 0.40, 0.05]}[sen])[0]
            agent_skills.append({"agent_id": aid, "skill_id": sid, "proficiency": proficiency})

        n_products = {"senior": random.randint(3, 6), "mid": random.randint(2, 4),
                      "junior": random.randint(1, 3)}[sen]
        for pid in random.sample(product_ids, min(n_products, len(product_ids))):
            agent_products.append({"agent_id": aid, "product_id": pid})

        n_components = {"senior": random.randint(4, 8), "mid": random.randint(3, 6),
                        "junior": random.randint(2, 4)}[sen]
        for cid in random.sample(component_ids, min(n_components, len(component_ids))):
            agent_components.append({"agent_id": aid, "component_id": cid})

    return rows, agent_skills, agent_products, agent_components, agent_teams


# ── Knowledge base article briefs (metadata only — text filled by narratives.py) ─

def build_kb_article_briefs(n, categories, subcategories, cat_id_to_key, symptom_id_by_name,
                             root_cause_id_by_name, resolution_id_by_name, components, tag_lookup,
                             product_component_ids, sub_symptoms, sub_root_causes):
    comps_by_category = {}
    for c in components:
        for cat_id, rank in tag_lookup[c["id"]]:
            comps_by_category.setdefault(cat_id, []).append(c["id"])

    products_by_component = {}
    for pid, cids in product_component_ids.items():
        for cid in cids:
            products_by_component.setdefault(cid, []).append(pid)

    sub_symptoms_by_id, sub_rc_by_id = {}, {}
    for row in sub_symptoms:
        sub_symptoms_by_id.setdefault(row["subcategory_id"], []).append(row["symptom_id"])
    for row in sub_root_causes:
        sub_rc_by_id.setdefault(row["subcategory_id"], []).append(row["root_cause_id"])

    cat_symptom_ids = {c["id"]: [symptom_id_by_name[n] for n, _ in tax.CATEGORY_SYMPTOM_POOL[cat_id_to_key[c["id"]]]]
                       for c in categories}
    cat_rc_ids = {c["id"]: [root_cause_id_by_name[n] for n, _ in tax.CATEGORY_ROOT_CAUSE_POOL[cat_id_to_key[c["id"]]]]
                  for c in categories}

    briefs = []
    for i in range(1, n + 1):
        aid = f"KA{i:04d}"
        specificity = random.choices(["specific", "broad"], weights=[0.6, 0.4])[0]
        category = random.choice(categories)

        if specificity == "specific":
            subcat_candidates = [s for s in subcategories if s["category_id"] == category["id"]]
            subcat = random.choice(subcat_candidates)
            symptom_ids = random.sample(sub_symptoms_by_id.get(subcat["id"], []),
                                         k=min(3, len(sub_symptoms_by_id.get(subcat["id"], []))))
            rc_ids = random.sample(sub_rc_by_id.get(subcat["id"], []),
                                    k=min(2, len(sub_rc_by_id.get(subcat["id"], []))))
            subcat_ids = [subcat["id"]]
        else:
            subcat_candidates = [s for s in subcategories if s["category_id"] == category["id"]]
            subcat_ids = [s["id"] for s in random.sample(subcat_candidates, k=min(3, len(subcat_candidates)))]
            symptom_ids = random.sample(cat_symptom_ids[category["id"]],
                                         k=min(6, len(cat_symptom_ids[category["id"]])))
            rc_ids = random.sample(cat_rc_ids[category["id"]], k=min(3, len(cat_rc_ids[category["id"]])))

        resolution_ids = set()
        for rc_id in rc_ids:
            pool = [row["resolution_type_id"] for row in _rc_res_rows_cache[rc_id]]
            resolution_ids.update(random.sample(pool, k=min(2, len(pool))))

        comp_candidates = comps_by_category.get(category["id"], [])
        comp_ids = random.sample(comp_candidates, k=min(random.randint(1, 2), len(comp_candidates))) if comp_candidates else []
        prod_candidates = sorted({p for cid in comp_ids for p in products_by_component.get(cid, [])})
        if not prod_candidates:
            prod_candidates = [p for p, cids in product_component_ids.items()
                                if set(cids) & set(comp_candidates)]
        product_ids = random.sample(prod_candidates, k=min(random.randint(1, 2), len(prod_candidates))) if prod_candidates else []

        created = datetime.now() - timedelta(days=random.randint(0, 730))
        age = (datetime.now() - created).days
        views = min(int(random.expovariate(1 / 220)) + 8, 2500)
        if age < 30:
            res_rate = round(random.uniform(0.30, 0.60), 2)
        elif age > 540:
            res_rate = round(random.uniform(0.20, 0.55), 2)
        elif age > 180 and views > 100:
            res_rate = round(random.uniform(0.75, 0.95), 2)
        elif views < 30:
            res_rate = round(random.uniform(0.20, 0.50), 2)
        else:
            res_rate = round(random.uniform(0.50, 0.80), 2)
        outdated = age > 540 and random.random() < 0.5

        briefs.append({
            "id": aid, "title": "", "content_summary": "",
            "specificity": specificity, "resolution_rate": res_rate, "views": views,
            "created_date": created.strftime("%Y-%m-%d"), "outdated": outdated,
            "_category_id": category["id"], "_subcategory_ids": subcat_ids,
            "_symptom_ids": symptom_ids, "_root_cause_ids": rc_ids,
            "_resolution_ids": sorted(resolution_ids), "_component_ids": comp_ids,
            "_product_ids": product_ids,
        })
    return briefs


_rc_res_rows_cache = {}


def build_all(n_customers=5000, n_agents=180, n_articles=900):
    global _rc_res_rows_cache

    categories, cat_key_to_id = build_issue_categories()
    cat_id_to_key = {v: k for k, v in cat_key_to_id.items()}
    subcategories, _ = build_issue_subcategories(cat_key_to_id)
    symptoms, symptom_id_by_name = build_symptoms()
    root_causes, root_cause_id_by_name = build_root_causes()
    resolution_types, resolution_id_by_name = build_resolution_types()
    teams, team_id_by_key = build_teams()
    skills = build_skills()
    skill_id_by_name = {s["name"]: s["id"] for s in skills}
    products = build_products()
    components, tag_lookup = build_components(cat_key_to_id)

    product_components, product_component_ids = build_product_components(products, components, tag_lookup)
    product_teams = build_product_teams(products, team_id_by_key)
    component_teams = build_component_teams(components, tag_lookup, cat_id_to_key, team_id_by_key)

    sub_symptoms, sub_components, sub_skills, sub_teams, sub_root_causes = build_issue_subcategory_relations(
        subcategories, cat_id_to_key, symptom_id_by_name, root_cause_id_by_name,
        skill_id_by_name, team_id_by_key, components, tag_lookup,
    )
    root_cause_resolutions = build_root_cause_resolutions(root_causes, resolution_id_by_name, root_cause_id_by_name)

    _rc_res_rows_cache = {}
    for row in root_cause_resolutions:
        _rc_res_rows_cache.setdefault(row["root_cause_id"], []).append(row)

    customers = build_customers(n_customers)
    agents, agent_skills, agent_products, agent_components, agent_teams = build_agents(
        n_agents, teams, skills, products, components, team_id_by_key,
    )
    kb_briefs = build_kb_article_briefs(
        n_articles, categories, subcategories, cat_id_to_key, symptom_id_by_name,
        root_cause_id_by_name, resolution_id_by_name, components, tag_lookup,
        product_component_ids, sub_symptoms, sub_root_causes,
    )

    return {
        "categories": categories, "cat_key_to_id": cat_key_to_id, "cat_id_to_key": cat_id_to_key,
        "subcategories": subcategories, "symptoms": symptoms, "symptom_id_by_name": symptom_id_by_name,
        "root_causes": root_causes, "root_cause_id_by_name": root_cause_id_by_name,
        "resolution_types": resolution_types, "resolution_id_by_name": resolution_id_by_name,
        "teams": teams, "team_id_by_key": team_id_by_key,
        "skills": skills, "skill_id_by_name": skill_id_by_name,
        "products": products, "components": components, "tag_lookup": tag_lookup,
        "product_components": product_components, "product_component_ids": product_component_ids,
        "product_teams": product_teams, "component_teams": component_teams,
        "sub_symptoms": sub_symptoms, "sub_components": sub_components, "sub_skills": sub_skills,
        "sub_teams": sub_teams, "sub_root_causes": sub_root_causes,
        "root_cause_resolutions": root_cause_resolutions,
        "customers": customers, "agents": agents,
        "agent_skills": agent_skills, "agent_products": agent_products,
        "agent_components": agent_components, "agent_teams": agent_teams,
        "kb_briefs": kb_briefs,
    }


def write_static_tables(d):
    write_csv("teams.csv", d["teams"], ["id", "name", "description"])
    write_csv("skills.csv", d["skills"], ["id", "name", "category"])
    write_csv("products.csv", d["products"], ["id", "name", "category", "version"])
    write_csv("components.csv", d["components"], ["id", "name", "origin_product_category"])
    write_csv("issue_categories.csv", d["categories"], ["id", "name"])
    write_csv("issue_subcategories.csv", d["subcategories"], ["id", "category_id", "name"])
    write_csv("symptoms.csv", d["symptoms"], ["id", "name"])
    write_csv("root_causes.csv", d["root_causes"], ["id", "name"])
    write_csv("resolution_types.csv", d["resolution_types"], ["id", "name"])

    write_csv("product_components.csv", d["product_components"], ["product_id", "component_id"])
    write_csv("product_teams.csv", d["product_teams"], ["product_id", "team_id", "role", "weight"])
    write_csv("component_teams.csv", d["component_teams"], ["component_id", "team_id", "role", "weight"])

    write_csv("issue_subcategory_symptoms.csv", d["sub_symptoms"], ["subcategory_id", "symptom_id", "weight"])
    write_csv("issue_subcategory_components.csv", d["sub_components"], ["subcategory_id", "component_id", "weight"])
    write_csv("issue_subcategory_skills.csv", d["sub_skills"], ["subcategory_id", "skill_id", "weight"])
    write_csv("issue_subcategory_teams.csv", d["sub_teams"], ["subcategory_id", "team_id", "role", "weight"])
    write_csv("issue_subcategory_root_causes.csv", d["sub_root_causes"], ["subcategory_id", "root_cause_id", "weight"])
    write_csv("root_cause_resolutions.csv", d["root_cause_resolutions"], ["root_cause_id", "resolution_type_id", "weight"])

    write_csv("agent_skills.csv", d["agent_skills"], ["agent_id", "skill_id", "proficiency"])
    write_csv("agent_products.csv", d["agent_products"], ["agent_id", "product_id"])
    write_csv("agent_components.csv", d["agent_components"], ["agent_id", "component_id"])
    write_csv("agent_teams.csv", d["agent_teams"], ["agent_id", "team_id"])
