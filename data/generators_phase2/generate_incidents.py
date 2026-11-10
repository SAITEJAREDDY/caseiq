"""
Phase 2 incident layer: service_health_events (ambient, case-independent
health blips), incidents (platform-wide events), and incident_cases (the
per-case classification into directly_caused / partially_influenced /
coincidental_unrelated / customer_assumed_incorrectly).

Incidents are seeded from real cases whose own root cause already belongs to
an incident-eligible category (evidence_taxonomy.INCIDENT_CATEGORY_WEIGHTS) —
this guarantees each incident has at least one genuinely-caused case by
construction, then classifies every other case whose time/region happens to
overlap. Deliberately NOT "inside window = caused" (spec's Scenario E): most
overlapping cases end up coincidental_unrelated / customer_assumed_incorrectly.
"""
from datetime import timedelta

import evidence_taxonomy as et

REGIONS = ["US-East", "US-West", "EU-West", "EU-Central", "APAC", "LATAM", "ME", "ANZ"]

_HEALTH_EVENT_TEMPLATES = [
    "Brief {severity} health blip on {component}: elevated error rate for {mins} minutes.",
    "{severity} latency spike observed on {component}, self-resolved after {mins} minutes.",
    "Automated health check flagged {component} as degraded ({severity}) for {mins} minutes.",
    "Transient {severity} availability dip on {component}, recovered within {mins} minutes.",
]


def build_service_health_events(rng, components, now):
    rows, rid = [], 0
    for comp in components:
        n = rng.randint(15, 25)
        for _ in range(n):
            days_ago = rng.randint(0, 730)
            started = now - timedelta(days=days_ago, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            mins = rng.choice([5, 10, 15, 20, 30, 45, 60])
            severity = rng.choices(["minor", "major", "critical"], weights=[75, 20, 5])[0]
            ended = started + timedelta(minutes=mins)
            rid += 1
            rows.append({
                "id": f"SHE{rid:05d}", "component_id": comp["id"],
                "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
                "ended_at": ended.strftime("%Y-%m-%d %H:%M:%S"), "severity": severity,
                "description": rng.choice(_HEALTH_EVENT_TEMPLATES).format(
                    severity=severity, component=comp["name"], mins=mins),
            })
    return rows


def build_incidents(rng, cases, d, component_flavor_map, component_dependencies, now, n_incidents=650):
    cat_id_to_key = et.category_key_by_name(d["cat_id_to_name"])
    incident_categories = {k for k, _ in et.INCIDENT_CATEGORY_WEIGHTS}
    weight_by_cat = dict(et.INCIDENT_CATEGORY_WEIGHTS)

    seed_pool = [
        c for c in cases
        if cat_id_to_key.get(c["gt_issue_category_id"]) in incident_categories
        and c["gt_severity"] in ("Sev1", "Sev2")
    ]
    if not seed_pool:
        seed_pool = cases[:1]
    seed_weights = [weight_by_cat.get(cat_id_to_key.get(c["gt_issue_category_id"]), 1) for c in seed_pool]
    n_incidents = min(n_incidents, len(seed_pool))
    seeds = _weighted_sample_without_replacement(rng, seed_pool, seed_weights, n_incidents)

    dependents_by_component = {}
    for e in component_dependencies:
        dependents_by_component.setdefault(e["depends_on_component_id"], []).append(e["component_id"])

    cases_by_region = {}
    for c in cases:
        cases_by_region.setdefault(c["region"], []).append(c)

    incidents = []
    severity_map = {"Sev1": "critical", "Sev2": "major"}
    windows = []  # (incident_id, seed, window_lo, window_hi, region)

    for i, seed in enumerate(seeds, start=1):
        lead_min = rng.randint(10, 90)
        duration_min = rng.choices([30, 60, 120, 180, 300, 480], weights=[30, 25, 20, 12, 8, 5])[0]
        started_at = seed["created_date"] - timedelta(minutes=lead_min)
        ended_at = started_at + timedelta(minutes=duration_min)
        region = "global" if rng.random() < 0.35 else seed["region"]
        incident_id = f"INC{i:04d}"
        incidents.append({
            "id": incident_id, "component_id": seed["gt_component_id"], "region": region,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": ended_at.strftime("%Y-%m-%d %H:%M:%S"),
            "severity": severity_map.get(seed["gt_severity"], "minor"), "status": "resolved",
            "summary": "",  # filled by narratives_phase2.py
        })
        windows.append((incident_id, seed, started_at - timedelta(minutes=30), ended_at + timedelta(minutes=30), region))

    # Pass 1: every seed unconditionally owns "directly_caused" on its own
    # incident — this must win even if the same case would otherwise have
    # fallen into another incident's coincidental-overlap window below.
    case_relationship = {}
    for incident_id, seed, *_ in windows:
        case_relationship[seed["id"]] = {"incident_id": incident_id, "relationship": "directly_caused"}

    # Pass 2: classify every other case whose time/region happens to overlap
    # an incident window. A case already claimed (as a seed, or by an earlier
    # incident it overlapped first) is left alone — each case belongs to at
    # most one incident.
    incident_cases = []
    for incident_id, seed, window_lo, window_hi, region in windows:
        candidate_pool = cases if region == "global" else cases_by_region.get(region, [])
        candidates = [c for c in candidate_pool
                      if c["id"] != seed["id"] and window_lo <= c["created_date"] <= window_hi]
        if len(candidates) > 14:
            candidates = rng.sample(candidates, k=14)

        dependents = set(dependents_by_component.get(seed["gt_component_id"], []))
        for cand in candidates:
            if cand["id"] in case_relationship:
                continue
            if cand["gt_component_id"] == seed["gt_component_id"]:
                rel = "directly_caused" if rng.random() < 0.7 else "partially_influenced"
            elif cand["gt_component_id"] in dependents:
                rel = "partially_influenced" if rng.random() < 0.6 else "coincidental_unrelated"
            else:
                rel = "customer_assumed_incorrectly" if rng.random() < 0.35 else "coincidental_unrelated"
            case_relationship[cand["id"]] = {"incident_id": incident_id, "relationship": rel}

    for case_id, info in case_relationship.items():
        incident_cases.append({"incident_id": info["incident_id"], "case_id": case_id,
                                "relationship": info["relationship"]})

    return {
        "service_health_events": build_service_health_events(rng, d["components"], now),
        "incidents": incidents,
        "incident_cases": incident_cases,
        "case_relationship": case_relationship,
    }


def _weighted_sample_without_replacement(rng, population, weights, k):
    pool = list(zip(population, weights))
    chosen = []
    for _ in range(min(k, len(pool))):
        items = [p[0] for p in pool]
        wts = [p[1] for p in pool]
        pick = rng.choices(items, weights=wts)[0]
        chosen.append(pick)
        pool = [(it, w) for it, w in pool if it["id"] != pick["id"]]
    return chosen
