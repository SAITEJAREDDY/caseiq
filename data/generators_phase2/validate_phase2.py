"""
Phase 2 dataset validator. Run after build_phase2.py --full completes:

    python3 validate_phase2.py

Every check either passes silently (a "OK" line) or prints one FAIL line per
violation found (capped) plus a final summary. Exit code is nonzero if any
check failed.
"""
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

RAW_V1 = os.path.join(os.path.dirname(__file__), "..", "raw_v2")
PHASE2 = os.path.join(os.path.dirname(__file__), "..", "phase2")
CHECKSUM_MANIFEST = os.path.join(os.path.dirname(__file__), ".phase1_checksums.json")

failures = []


def read1(fn):
    with open(os.path.join(RAW_V1, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read2(fn):
    with open(os.path.join(PHASE2, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check(label, bad):
    if bad:
        n = bad if isinstance(bad, int) else len(bad)
        print(f"  FAIL  {label}: {n} violation(s)" + (f", e.g. {bad[:5]}" if isinstance(bad, list) else ""))
        failures.append(label)
    else:
        print(f"  OK    {label}")


def main():
    print("Checking Phase 1 immutability (checksum diff against pre-Phase-2 baseline)...")
    with open(CHECKSUM_MANIFEST) as f:
        baseline = json.load(f)
    changed = []
    for fn, expected_hash in baseline.items():
        path = os.path.join(RAW_V1, fn)
        with open(path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        if actual_hash != expected_hash:
            changed.append(fn)
    check("Phase 1 files unchanged since Phase 2 build started", changed)

    print("\nLoading tables...")
    cases = read1("cases.csv")
    case_ids = {c["id"] for c in cases}
    customers = {c["id"] for c in read1("customers.csv")}
    agents = {a["id"] for a in read1("agents.csv")}
    products = {p["id"] for p in read1("products.csv")}
    components = {c["id"] for c in read1("components.csv")}
    teams = {t["id"] for t in read1("teams.csv")}
    case_by_id = {c["id"]: c for c in cases}

    product_versions = read2("product_versions.csv")
    version_ids = {v["id"] for v in product_versions}
    customer_deployments = read2("customer_deployments.csv")
    component_dependencies = read2("component_dependencies.csv")
    external_dependencies = read2("external_dependencies.csv")
    ed_ids = {e["id"] for e in external_dependencies}
    external_dependency_links = read2("external_dependency_links.csv")
    support_plans = read2("support_plans.csv")
    plan_ids = {p["id"] for p in support_plans}
    sla_policies = read2("sla_policies.csv")
    customer_entitlements = read2("customer_entitlements.csv")
    agent_capacity = read2("agent_capacity.csv")
    agent_schedule = read2("agent_schedule.csv")
    team_capacity_snapshots = read2("team_capacity_snapshots.csv")
    change_events = read2("change_events.csv")
    change_ids = {c["id"] for c in change_events}
    change_by_id = {c["id"]: c for c in change_events}
    deployments = read2("deployments.csv")
    case_change_links = read2("case_change_links.csv")
    case_telemetry = read2("case_telemetry.csv")
    case_signals = read2("case_signals.csv")
    signal_ids = {s["id"] for s in case_signals}
    configuration_snapshots = read2("configuration_snapshots.csv")
    service_health_events = read2("service_health_events.csv")
    incidents = read2("incidents.csv")
    incident_ids = {i["id"] for i in incidents}
    incident_by_id = {i["id"]: i for i in incidents}
    incident_cases = read2("incident_cases.csv")
    observable = read2("phase2_observable.csv")
    ground_truth = read2("phase2_ground_truth.csv")

    print(f"\nRow counts: product_versions={len(product_versions):,} customer_deployments={len(customer_deployments):,} "
          f"component_dependencies={len(component_dependencies):,} change_events={len(change_events):,} "
          f"deployments={len(deployments):,} case_change_links={len(case_change_links):,} "
          f"case_telemetry={len(case_telemetry):,} case_signals={len(case_signals):,} "
          f"configuration_snapshots={len(configuration_snapshots):,} service_health_events={len(service_health_events):,} "
          f"incidents={len(incidents):,} incident_cases={len(incident_cases):,}\n")

    print("Foreign-key integrity...")
    check("product_versions.product_id -> products", [v["id"] for v in product_versions if v["product_id"] not in products])
    check("customer_deployments.customer_id -> customers",
          [r["id"] for r in customer_deployments if r["customer_id"] not in customers])
    check("customer_deployments.product_id -> products",
          [r["id"] for r in customer_deployments if r["product_id"] not in products])
    check("customer_deployments.product_version_id -> product_versions",
          [r["id"] for r in customer_deployments if r["product_version_id"] not in version_ids])
    check("component_dependencies.component_id -> components",
          [r["id"] for r in component_dependencies if r["component_id"] not in components])
    check("component_dependencies.depends_on_component_id -> components",
          [r["id"] for r in component_dependencies if r["depends_on_component_id"] not in components])
    check("external_dependency_links.component_id -> components",
          [r["id"] for r in external_dependency_links if r["component_id"] not in components])
    check("external_dependency_links.external_dependency_id -> external_dependencies",
          [r["id"] for r in external_dependency_links if r["external_dependency_id"] not in ed_ids])
    check("customer_entitlements.customer_id -> customers",
          [r["customer_id"] for r in customer_entitlements if r["customer_id"] not in customers])
    check("customer_entitlements.support_plan_id -> support_plans",
          [r["customer_id"] for r in customer_entitlements if r["support_plan_id"] not in plan_ids])
    check("sla_policies.support_plan_id -> support_plans",
          [r["id"] for r in sla_policies if r["support_plan_id"] not in plan_ids])
    check("agent_capacity.agent_id -> agents", [r["agent_id"] for r in agent_capacity if r["agent_id"] not in agents])
    check("agent_schedule.agent_id -> agents", [r["id"] for r in agent_schedule if r["agent_id"] not in agents])
    check("team_capacity_snapshots.team_id -> teams",
          [r["id"] for r in team_capacity_snapshots if r["team_id"] not in teams])
    check("change_events.component_id -> components", [r["id"] for r in change_events if r["component_id"] not in components])
    check("change_events.product_id -> products", [r["id"] for r in change_events if r["product_id"] not in products])
    check("change_events.customer_id -> customers (when set)",
          [r["id"] for r in change_events if r["customer_id"] and r["customer_id"] not in customers])
    check("deployments.change_event_id -> change_events",
          [r["change_event_id"] for r in deployments if r["change_event_id"] not in change_ids])
    check("case_change_links.case_id -> cases", [r["case_id"] for r in case_change_links if r["case_id"] not in case_ids])
    check("case_change_links.change_event_id -> change_events",
          [r["case_id"] for r in case_change_links if r["change_event_id"] not in change_ids])
    check("case_telemetry.case_id -> cases", [r["case_id"] for r in case_telemetry if r["case_id"] not in case_ids])
    check("case_telemetry.component_id -> components",
          [r["case_id"] for r in case_telemetry if r["component_id"] not in components])
    check("case_signals.case_id -> cases", [r["id"] for r in case_signals if r["case_id"] not in case_ids])
    check("case_signals.component_id -> components", [r["id"] for r in case_signals if r["component_id"] not in components])
    check("configuration_snapshots.case_id -> cases",
          [r["id"] for r in configuration_snapshots if r["case_id"] not in case_ids])
    check("service_health_events.component_id -> components",
          [r["id"] for r in service_health_events if r["component_id"] not in components])
    check("incidents.component_id -> components", [r["id"] for r in incidents if r["component_id"] not in components])
    check("incident_cases.incident_id -> incidents",
          [r["case_id"] for r in incident_cases if r["incident_id"] not in incident_ids])
    check("incident_cases.case_id -> cases", [r["case_id"] for r in incident_cases if r["case_id"] not in case_ids])
    check("phase2_observable.case_id -> cases (exact set, every case present)",
          set(case_ids) ^ {r["case_id"] for r in observable})
    check("phase2_ground_truth.case_id -> cases (exact set, every case present)",
          set(case_ids) ^ {r["case_id"] for r in ground_truth})

    def semi_ids(s):
        return [x for x in s.split(";") if x]

    bad_causal_change = [g["case_id"] for g in ground_truth if g["causal_change_id"] and g["causal_change_id"] not in change_ids]
    check("phase2_ground_truth.causal_change_id -> change_events", bad_causal_change)
    bad_contrib = [g["case_id"] for g in ground_truth for cid in semi_ids(g["contributing_change_ids"]) if cid not in change_ids]
    check("phase2_ground_truth.contributing_change_ids -> change_events", bad_contrib)
    bad_irrel = [g["case_id"] for g in ground_truth for cid in semi_ids(g["irrelevant_change_ids"]) if cid not in change_ids]
    check("phase2_ground_truth.irrelevant_change_ids -> change_events", bad_irrel)
    bad_causal_sig = [g["case_id"] for g in ground_truth for sid in semi_ids(g["causal_signal_ids"]) if sid not in signal_ids]
    check("phase2_ground_truth.causal_signal_ids -> case_signals", bad_causal_sig)
    bad_distractor_sig = [g["case_id"] for g in ground_truth for sid in semi_ids(g["distractor_signal_ids"]) if sid not in signal_ids]
    check("phase2_ground_truth.distractor_signal_ids -> case_signals", bad_distractor_sig)
    bad_component = [g["case_id"] for g in ground_truth if g["causal_component_id"] not in components]
    check("phase2_ground_truth.causal_component_id -> components", bad_component)
    bad_incident_ref = [g["case_id"] for g in ground_truth if g["incident_id"] and g["incident_id"] not in incident_ids]
    check("phase2_ground_truth.incident_id -> incidents", bad_incident_ref)

    print("\nTemporal / logical consistency...")

    def parse_dt(s, fmt="%Y-%m-%d %H:%M:%S"):
        return datetime.strptime(s, fmt)

    bad_change_order = [c["id"] for c in change_events if parse_dt(c["started_at"]) > parse_dt(c["completed_at"])]
    check("change_events: started_at <= completed_at", bad_change_order)

    causal_after_case = []
    for g in ground_truth:
        if not g["causal_change_id"]:
            continue
        ch = change_by_id.get(g["causal_change_id"])
        case = case_by_id.get(g["case_id"])
        if not ch or not case:
            continue
        case_created = datetime.strptime(case["created_date"], "%Y-%m-%d")
        if parse_dt(ch["started_at"]).date() > case_created.date():
            causal_after_case.append(g["case_id"])
    check("causal changes start on/before the case's created_date", causal_after_case)

    bad_incident_order = [i["id"] for i in incidents if parse_dt(i["started_at"]) > parse_dt(i["ended_at"])]
    check("incidents: started_at <= ended_at", bad_incident_order)

    # generate_incidents.py enforces a +/-30min window at construction time;
    # this check re-verifies with a generous 1-day buffer (cases.csv only
    # stores a date, not a time-of-day) to catch any gross construction bug.
    gross_violations = []
    for row in incident_cases:
        inc = incident_by_id[row["incident_id"]]
        case = case_by_id.get(row["case_id"])
        if not case:
            continue
        lo = parse_dt(inc["started_at"])
        hi = parse_dt(inc["ended_at"])
        case_created_dt = datetime.strptime(case["created_date"], "%Y-%m-%d") if isinstance(case["created_date"], str) else case["created_date"]
        # case created_date has no time-of-day in cases.csv's raw string form;
        # compare by date with a 1-day buffer around the incident window.
        if not (lo.date() - _days(1) <= case_created_dt.date() <= hi.date() + _days(1)):
            gross_violations.append(row["case_id"])
    check("incident_cases: case created_date falls near the incident's window", gross_violations)

    print("\nSLA coverage...")
    severities = {"Sev1", "Sev2", "Sev3", "Sev4"}
    missing_sla = []
    for plan_id in plan_ids:
        covered = {s["severity"] for s in sla_policies if s["support_plan_id"] == plan_id}
        if covered != severities:
            missing_sla.append(plan_id)
    check("every support_plan has all 4 severities in sla_policies", missing_sla)

    print("\nObservable/hidden separation...")
    obs_cols = set(observable[0].keys()) if observable else set()
    leaked = [c for c in obs_cols if c.startswith("gt_") or "causal" in c or "sufficiency" in c or "confidence" in c]
    check("phase2_observable.csv has no gt_/causal/sufficiency/confidence columns", leaked)

    print(f"\n{'='*60}")
    if failures:
        print(f"VALIDATION FAILED: {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED: all checks OK.")


def _days(n):
    from datetime import timedelta
    return timedelta(days=n)


if __name__ == "__main__":
    main()
