"""
Phase 2 change layer: a background pool of platform change_events (ambient
deployments/config/policy churn, used as distractors and as raw material for
case_change_links), plus a per-case causal-change decision driven by
evidence_taxonomy.ROOT_CAUSE_EVIDENCE_PATTERNS.

Everything here is observable (change_events, deployments, case_change_links
carry no causal label). The causal/contributing/irrelevant split is computed
here but only ever exposed via the `per_case` dict this module returns, which
generate_evidence.build_observable_and_ground_truth() folds into
phase2_ground_truth.csv — never into an observable table.
"""
from datetime import datetime, timedelta

import evidence_taxonomy as et

REGIONS = ["US-East", "US-West", "EU-West", "EU-Central", "APAC", "LATAM", "ME", "ANZ"]


def _parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

_TYPE_WEIGHTS = [
    ("deployment", 9), ("config_change", 23), ("policy_change", 10),
    ("permission_change", 10), ("network_config_change", 10), ("credential_rotation", 8),
    ("migration", 6), ("api_contract_change", 8), ("manual_config_change", 8),
    ("data_pipeline_change", 8),
]
_DURATION_MINUTES = {
    "deployment": (10, 90), "config_change": (1, 15), "policy_change": (1, 10),
    "permission_change": (1, 5), "network_config_change": (2, 30), "credential_rotation": (1, 5),
    "migration": (30, 240), "api_contract_change": (5, 60), "manual_config_change": (1, 20),
    "data_pipeline_change": (10, 120),
}
_ROLLOUT_STRATEGIES = ["canary", "blue_green", "rolling", "big_bang"]


def _sample_change_type(rng):
    types = [t for t, _ in _TYPE_WEIGHTS]
    weights = [w for _, w in _TYPE_WEIGHTS]
    return rng.choices(types, weights=weights)[0]


def _make_deployment_detail(rng, change_id, product_id, product_versions_by_product):
    versions = product_versions_by_product.get(product_id, [])
    if len(versions) < 2:
        v_from, v_to = "", ""
    else:
        idx = rng.randint(1, len(versions) - 1)
        v_from, v_to = versions[idx - 1]["version"], versions[idx]["version"]
    return {
        "change_event_id": change_id, "product_id": product_id,
        "version_from": v_from, "version_to": v_to,
        "rollout_strategy": rng.choice(_ROLLOUT_STRATEGIES),
        "deploy_duration_minutes": rng.randint(*_DURATION_MINUTES["deployment"]),
        "description": "",  # filled by narratives_phase2.py
    }


def _new_change_event(rid, change_type, component_id, product_id, customer_id,
                       environment, region, started_at, duration_minutes, status, initiated_by):
    completed_at = started_at + timedelta(minutes=duration_minutes)
    return {
        "id": f"CH{rid:06d}", "change_type": change_type, "component_id": component_id,
        "product_id": product_id, "customer_id": customer_id or "", "environment": environment,
        "region": region, "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "completed_at": completed_at.strftime("%Y-%m-%d %H:%M:%S"), "status": status,
        "initiated_by": initiated_by,
    }


def _scope_match(change, case):
    if change["customer_id"] and change["customer_id"] == case["customer_id"]:
        return "same_customer"
    if change["component_id"] == case["gt_component_id"]:
        return "same_component"
    if change["product_id"] == case["gt_product_id"]:
        return "same_product"
    return "platform_wide"


def build_changes(rng, cases, d, component_flavor_map, customer_deployments, product_versions, now):
    components = d["components"]
    component_id_to_product_ids = d["component_id_to_product_ids"]
    root_cause_id_to_name = d["root_cause_id_to_name"]

    product_versions_by_product = {}
    for v in product_versions:
        product_versions_by_product.setdefault(v["product_id"], []).append(v)
    for vs in product_versions_by_product.values():
        vs.sort(key=lambda v: v["release_date"])

    customers_by_product = {}
    for cd in customer_deployments:
        customers_by_product.setdefault(cd["product_id"], []).append(cd["customer_id"])

    change_events, deployments = [], []
    rid = 0

    # ── Background pool: ambient platform change activity per component. ──────
    background_by_component = {}
    background_by_product = {}
    for comp in components:
        product_ids = component_id_to_product_ids.get(comp["id"], [])
        if not product_ids:
            continue
        n_bg = rng.randint(70, 170)
        comp_events = []
        for _ in range(n_bg):
            rid += 1
            change_type = _sample_change_type(rng)
            product_id = rng.choice(product_ids)
            days_ago = rng.randint(0, 730)
            started_at = now - timedelta(days=days_ago, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            duration = rng.randint(*_DURATION_MINUTES[change_type])
            status = rng.choices(["completed", "failed", "rolled_back"], weights=[92, 5, 3])[0]
            environment = rng.choices(["production", "staging"], weights=[80, 20])[0]
            region = "global" if rng.random() < 0.4 else rng.choice(REGIONS)
            customer_id = ""
            if change_type in ("config_change", "permission_change", "policy_change", "manual_config_change") \
                    and rng.random() < 0.30 and customers_by_product.get(product_id):
                customer_id = rng.choice(customers_by_product[product_id])
            initiated_by = "agent:support_ops" if customer_id else "system:automation"
            row = _new_change_event(rid, change_type, comp["id"], product_id, customer_id,
                                     environment, region, started_at, duration, status, initiated_by)
            change_events.append(row)
            comp_events.append(row)
            background_by_product.setdefault(product_id, []).append(row)
            if change_type == "deployment":
                deployments.append(_make_deployment_detail(rng, row["id"], product_id, product_versions_by_product))
        comp_events.sort(key=lambda r: r["started_at"])
        background_by_component[comp["id"]] = comp_events
    for evs in background_by_product.values():
        evs.sort(key=lambda r: r["started_at"])

    # ── Per-case causal + distractor changes. ──────────────────────────────────
    case_change_links = []
    per_case = {}

    for case in cases:
        rc_name = root_cause_id_to_name[case["gt_root_cause_id"]]
        pattern = et.ROOT_CAUSE_EVIDENCE_PATTERNS[rc_name]
        created = case["created_date"]
        causal_change_id = None
        contributing_ids = []
        linked_events = []

        if pattern["change_type"] and rng.random() < pattern["change_prob"]:
            rid += 1
            lead_minutes = rng.randint(10, 180)
            started_at = created - timedelta(minutes=lead_minutes)
            duration = rng.randint(*_DURATION_MINUTES[pattern["change_type"]])
            row = _new_change_event(
                rid, pattern["change_type"], case["gt_component_id"], case["gt_product_id"],
                case["customer_id"], case["environment"], case["region"],
                started_at, duration, "completed",
                "agent:support_ops" if pattern["change_type"] in
                ("manual_config_change", "permission_change", "policy_change") else "system:automation",
            )
            change_events.append(row)
            if pattern["change_type"] == "deployment":
                deployments.append(_make_deployment_detail(rng, row["id"], case["gt_product_id"], product_versions_by_product))
            causal_change_id = row["id"]
            linked_events.append(row)

        # Nearby distractor changes: background events anywhere on the case's
        # product (any of its components) within +/- 72h of case creation,
        # regardless of causal status — this is the realistic search space an
        # investigator would actually look at ("what changed near this product
        # recently"), not just the one component Phase 1 happened to confirm.
        product_bg = background_by_product.get(case["gt_product_id"], [])
        window = [
            r for r in product_bg
            if r["id"] != causal_change_id
            and abs((_parse_ts(r["started_at"]) - created).total_seconds()) <= 72 * 3600
        ]
        n_distractors = rng.choices([0, 1, 2, 3], weights=[30, 35, 25, 10])[0]
        distractors = rng.sample(window, k=min(n_distractors, len(window))) if window else []
        linked_events += distractors

        for r in linked_events:
            hours = abs((_parse_ts(r["started_at"]) - created).total_seconds()) / 3600
            case_change_links.append({
                "case_id": case["id"], "change_event_id": r["id"],
                "time_proximity_hours": round(hours, 1),
                "scope_match": _scope_match(r, case),
            })

        irrelevant_ids = [r["id"] for r in distractors]
        if causal_change_id and irrelevant_ids and rng.random() < 0.10:
            contributing_ids.append(irrelevant_ids.pop(rng.randrange(len(irrelevant_ids))))

        per_case[case["id"]] = {
            "causal_change_id": causal_change_id or "",
            "contributing_change_ids": contributing_ids,
            "irrelevant_change_ids": irrelevant_ids,
        }

    return {
        "change_events": change_events,
        "deployments": deployments,
        "case_change_links": case_change_links,
        "per_case": per_case,
    }
