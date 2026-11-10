"""
Phase 2 topology: product_versions, customer_deployments, component_dependencies,
external_dependencies, external_dependency_links.

Everything here is deterministic Python driven by an injected random.Random
instance (no LLM, no global random state) and derived from Phase 1's own
structure — component flavors come from issue_subcategory_components.csv via
evidence_taxonomy.component_flavors(), so the dependency graph reflects the
same category ontology Phase 1 already established rather than being random.
"""
from datetime import timedelta

import evidence_taxonomy as et

EXTERNAL_DEPENDENCIES = [
    ("ED01", "Primary Identity Provider", "identity"),
    ("ED02", "Payment Processor Network", "payments"),
    ("ED03", "Tax Calculation Vendor", "payments"),
    ("ED04", "Currency Exchange Rate Feed", "payments"),
    ("ED05", "SMS Gateway Vendor", "messaging"),
    ("ED06", "Email Delivery Provider (ESP)", "messaging"),
    ("ED07", "Push Notification Service", "messaging"),
    ("ED08", "DNS / CDN Provider", "infrastructure"),
    ("ED09", "Cloud IaaS Provider", "infrastructure"),
    ("ED10", "Fraud Detection Vendor", "security"),
]

_LINKABLE_BY_TARGET_CATEGORY = {
    "IDENTITY_AUTH": ["ED01"],
    "BILLING": ["ED02", "ED03", "ED04"],
    "SECURITY": ["ED10"],
    "NETWORKING": ["ED08", "ED09"],
    "THIRD_PARTY": ["ED02", "ED05", "ED06", "ED07", "ED09", "ED10"],
    # MESSAGING isn't one of the 18 issue categories (it's a product category),
    # so messaging-flavored components are reached via origin_product_category
    # directly in build_component_dependencies().
}


def build_product_versions(rng, products, now):
    """~6 versions per product, ending at Phase 1's recorded "current" version."""
    rows = []
    for p in products:
        current = p["version"]
        try:
            major, minor = current.split(".")
            major, minor = int(major), int(minor)
        except ValueError:
            major, minor = 1, 0
        n_versions = rng.choice([4, 5, 6, 7])
        # Walk backward from current to build a plausible ascending history.
        versions = [(major, minor)]
        m, n = major, minor
        for _ in range(n_versions - 1):
            if n > 0 and rng.random() < 0.7:
                n -= 1
            elif m > 1:
                m -= 1
                n = rng.choice([0, 2, 4, 6, 8])
            else:
                n = max(0, n - 1)
            versions.append((m, n))
        versions = sorted(set(versions))
        span_days = 700
        step = span_days / max(len(versions) - 1, 1)
        for i, (vm, vn) in enumerate(versions):
            days_ago = int(span_days - i * step)
            release_date = now - timedelta(days=max(days_ago, 0))
            rows.append({
                "id": f"PV{len(rows) + 1:05d}",
                "product_id": p["id"],
                "version": f"{vm}.{vn}",
                "release_date": release_date.strftime("%Y-%m-%d"),
                "is_current": "true" if (vm, vn) == (major, minor) else "false",
            })
    return rows


def build_customer_deployments(rng, customers, products, product_versions, now):
    """One row per (customer, product, environment). Product selection favors
    products the customer's own case history actually touched (stashed on
    each customer dict as "_touched_products" by build_phase2.py); version
    selection favors recent versions with a long tail of laggards (this is
    what makes "version incompatibility" root causes plausible later)."""
    versions_by_product = {}
    for v in product_versions:
        versions_by_product.setdefault(v["product_id"], []).append(v)
    for vs in versions_by_product.values():
        vs.sort(key=lambda v: v["release_date"])

    product_ids_all = [p["id"] for p in products]
    rows = []
    rid = 0
    for c in customers:
        target_n = int(c["num_products_deployed"])
        chosen = list(dict.fromkeys(c.get("_touched_products", [])))[:target_n]
        remaining = max(target_n - len(chosen), 0)
        pool = [pid for pid in product_ids_all if pid not in chosen]
        if remaining and pool:
            chosen += rng.sample(pool, k=min(remaining, len(pool)))
        if not chosen:
            chosen = rng.sample(product_ids_all, k=min(max(target_n, 1), len(product_ids_all)))

        for pid in chosen:
            versions = versions_by_product.get(pid, [])
            if not versions:
                continue
            weights = list(range(1, len(versions) + 1))  # later (newer) index -> higher weight
            version = rng.choices(versions, weights=weights)[0]
            envs = ["production"]
            if rng.random() < 0.45:
                envs.append("staging")
            if c["deployment_complexity"] != "low" and rng.random() < 0.20:
                envs.append("sandbox")
            for env in envs:
                rid += 1
                deployed_days_ago = rng.randint(30, 700)
                rows.append({
                    "id": f"CD{rid:06d}",
                    "customer_id": c["id"],
                    "product_id": pid,
                    "product_version_id": version["id"],
                    "environment": env,
                    "region": c["region"],
                    "deployed_at": (now - timedelta(days=deployed_days_ago)).strftime("%Y-%m-%d"),
                    "status": "active" if rng.random() > 0.03 else "decommissioned",
                })
    return rows


def infer_component_category_flavors(components, component_category_weights, cat_id_to_key):
    flavors = {}
    for c in components:
        cat_ids = et.component_flavors(c["id"], component_category_weights, top_n=2)
        flavors[c["id"]] = [cat_id_to_key[cid] for cid in cat_ids if cid in cat_id_to_key]
        if not flavors[c["id"]]:
            flavors[c["id"]] = ["UNKNOWN"]
    return flavors


def build_component_dependencies(rng, components, component_flavor_map):
    by_flavor = {}
    for comp_id, keys in component_flavor_map.items():
        for k in keys:
            by_flavor.setdefault(k, []).append(comp_id)

    dep_type_by_target = {
        "IDENTITY_AUTH": "authenticates_via", "NETWORKING": "routes_through",
        "STORAGE_DB": "reads_writes", "THIRD_PARTY": "calls_external",
        "CAPACITY": "scales_with",
    }

    rows, seen, rid = [], set(), 0
    for comp in components:
        comp_id = comp["id"]
        flavors = component_flavor_map[comp_id]
        for flavor in flavors:
            targets = et.DEPENDENCY_RULES.get(flavor, [])
            if not targets:
                continue
            target_keys = [t[0] for t in targets]
            target_weights = [t[1] for t in targets]
            n_edges = rng.randint(4, 7)
            for _ in range(n_edges):
                target_key = rng.choices(target_keys, weights=target_weights)[0]
                candidates = [cid for cid in by_flavor.get(target_key, [])
                              if cid != comp_id and (comp_id, cid) not in seen]
                if not candidates:
                    continue
                dep_id = rng.choice(candidates)
                seen.add((comp_id, dep_id))
                rid += 1
                rows.append({
                    "id": f"CDEP{rid:05d}",
                    "component_id": comp_id,
                    "depends_on_component_id": dep_id,
                    "dependency_type": dep_type_by_target.get(target_key, "depends_on"),
                    "weight": target_weights[target_keys.index(target_key)],
                })
    return rows


def build_external_dependencies():
    return [{"id": eid, "name": name, "domain": domain} for eid, name, domain in EXTERNAL_DEPENDENCIES]


def build_external_dependency_links(rng, components, component_flavor_map, product_id_to_name):
    rows, rid = [], 0
    for comp in components:
        comp_id = comp["id"]
        flavors = component_flavor_map[comp_id]
        candidate_eds = []
        for flavor in flavors:
            candidate_eds += _LINKABLE_BY_TARGET_CATEGORY.get(flavor, [])
        if comp["origin_product_category"] == "Messaging":
            candidate_eds += ["ED05", "ED06", "ED07"]
        candidate_eds = list(dict.fromkeys(candidate_eds))
        if not candidate_eds:
            continue
        if rng.random() > 0.80:
            continue
        n = rng.choice([1, 2, 2, 3])
        picked = rng.sample(candidate_eds, k=min(n, len(candidate_eds)))
        for ed_id in picked:
            rid += 1
            rows.append({
                "id": f"EDL{rid:05d}",
                "component_id": comp_id,
                "external_dependency_id": ed_id,
            })
    return rows
