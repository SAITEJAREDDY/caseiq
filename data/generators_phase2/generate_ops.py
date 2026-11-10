"""
Phase 2 operational-capacity layer: support_plans, sla_policies,
customer_entitlements, agent_capacity, agent_schedule, team_capacity_snapshots.

Deterministic, no LLM. Per the Phase 2 spec: support tier must never determine
technical severity (that's already fixed in Phase 1 — gt_severity is driven
purely by impact, see generate_cases._severity_from_impact). What tier *does*
plausibly affect is response-time/resolution-time SLA targets, which is what
this module models.
"""
from datetime import timedelta

SUPPORT_PLANS = [
    ("SP01", "Basic"), ("SP02", "Standard"), ("SP03", "Premium"), ("SP04", "Enterprise"),
]

# tier -> weighted plan pool (gold customers skew toward higher plans, but this
# is a commercial/entitlement fact, not a technical-severity input).
_PLAN_POOL_BY_TIER = {
    "gold":   [("SP03", 3), ("SP04", 5)],
    "silver": [("SP02", 4), ("SP03", 3)],
    "bronze": [("SP01", 5), ("SP02", 2)],
}

SEVERITIES = ["Sev1", "Sev2", "Sev3", "Sev4"]

# plan -> {severity: (response_minutes, resolution_hours)}
_SLA_TARGETS = {
    "SP01": {"Sev1": (240, 24), "Sev2": (480, 48), "Sev3": (1440, 96), "Sev4": (2880, 168)},
    "SP02": {"Sev1": (120, 12), "Sev2": (240, 24), "Sev3": (720, 72), "Sev4": (1440, 120)},
    "SP03": {"Sev1": (60, 6), "Sev2": (120, 12), "Sev3": (360, 48), "Sev4": (720, 96)},
    "SP04": {"Sev1": (15, 4), "Sev2": (60, 8), "Sev3": (240, 24), "Sev4": (480, 72)},
}


def build_support_plans():
    return [{"id": pid, "name": name} for pid, name in SUPPORT_PLANS]


def build_sla_policies():
    rows = []
    rid = 0
    for plan_id, targets in _SLA_TARGETS.items():
        for sev, (resp_min, res_hr) in targets.items():
            rid += 1
            rows.append({
                "id": f"SLA{rid:02d}", "support_plan_id": plan_id, "severity": sev,
                "response_time_minutes": resp_min, "resolution_time_hours": res_hr,
            })
    return rows


def build_customer_entitlements(rng, customers, now):
    rows = []
    for c in customers:
        pool = _PLAN_POOL_BY_TIER[c["tier"]]
        plan_id = rng.choices([p for p, _ in pool], weights=[w for _, w in pool])[0]
        start_days_ago = int(c["tenure_months"]) * 30 + rng.randint(0, 20)
        rows.append({
            "customer_id": c["id"],
            "support_plan_id": plan_id,
            "entitlement_start_date": (now - timedelta(days=start_days_ago)).strftime("%Y-%m-%d"),
            "seats": {"small": rng.randint(1, 10), "mid": rng.randint(10, 100),
                      "enterprise": rng.randint(50, 2000)}[c["company_size"]],
        })
    return rows


_SENIORITY_CAPACITY = {"junior": (12, 30), "mid": (18, 40), "senior": (25, 45)}


def build_agent_capacity(rng, agents):
    rows = []
    for a in agents:
        lo, hi = _SENIORITY_CAPACITY.get(a["seniority"], (15, 35))
        max_concurrent = rng.randint(lo, hi) // 3
        weekly_hours = rng.choice([32, 40, 40, 40])
        utilization = round(rng.uniform(0.55, 0.95), 2)
        rows.append({
            "agent_id": a["id"],
            "max_concurrent_cases": max_concurrent,
            "weekly_capacity_hours": weekly_hours,
            "current_utilization_pct": round(utilization * 100, 1),
        })
    return rows


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_SHIFT_BLOCKS = [(0, 8), (8, 16), (16, 24)]


def build_agent_schedule(rng, agents):
    rows = []
    rid = 0
    for a in agents:
        n_days = rng.choice([4, 5, 5, 5, 6])
        work_days = rng.sample(_DAYS[:5] if n_days <= 5 else _DAYS, k=n_days)
        shift = rng.choice(_SHIFT_BLOCKS)
        for day in work_days:
            rid += 1
            rows.append({
                "id": f"ASCH{rid:05d}", "agent_id": a["id"], "day_of_week": day,
                "shift_start_hour": shift[0], "shift_end_hour": shift[1],
            })
    return rows


def build_team_capacity_snapshots(rng, teams, now, weeks=25):
    rows = []
    rid = 0
    for t in teams:
        base_cases = rng.randint(15, 90)
        base_hours = rng.randint(200, 900)
        for w in range(weeks):
            week_start = now - timedelta(weeks=weeks - w)
            drift = rng.uniform(0.8, 1.2)
            open_cases = max(0, int(base_cases * drift))
            capacity_hours = max(1, int(base_hours * rng.uniform(0.9, 1.1)))
            utilization = round(min(1.4, (open_cases * 3.5) / capacity_hours), 2)
            rid += 1
            rows.append({
                "id": f"TCS{rid:05d}", "team_id": t["id"],
                "week_start_date": week_start.strftime("%Y-%m-%d"),
                "open_case_count": open_cases,
                "capacity_hours_available": capacity_hours,
                "utilization_pct": round(utilization * 100, 1),
            })
    return rows
