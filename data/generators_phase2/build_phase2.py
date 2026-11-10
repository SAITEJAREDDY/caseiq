"""
Phase 2 dataset orchestrator.

Usage:
    python3 build_phase2.py --topology-only     # topology + ops tables only, no LLM
    python3 build_phase2.py --skip-narratives   # everything except the LLM narrative stage
    python3 build_phase2.py --pilot 50          # small LLM pilot (incidents/deployments text)
    python3 build_phase2.py --full              # full run, all stages, all cases

Order: load Phase 1 (read-only) -> topology (product versions, deployments,
dependency graph, external deps) -> ops (SLA/capacity) -> changes (change
events + deployments + per-case causal/distractor links) -> evidence
(telemetry, signals, config snapshots, observable/ground-truth) -> incidents
(service-health events, incidents, incident-case classification) -> narrative
fill via Together AI (only stage that calls an LLM) -> write every CSV to
../phase2/.
"""
import argparse
import os
import random
import sys
import time
from collections import defaultdict

import load_phase1 as lp
import evidence_taxonomy as et
import generate_topology as gt
import generate_ops as go
import generate_changes as gc
import generate_evidence as ge
import generate_incidents as gi
from csv_io2 import write_csv

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generators"))
import llm_client
from llm_client import TogetherAuthError

PHASE2_SEED = 2026


def precompute_customer_touched_products(customers, cases):
    touched = defaultdict(list)
    for c in cases:
        seen = set(touched[c["customer_id"]])
        for pid in (c["product_reported_id"], c["gt_product_id"]):
            if pid not in seen:
                touched[c["customer_id"]].append(pid)
                seen.add(pid)
    for c in customers:
        c["_touched_products"] = touched.get(c["id"], [])


def run(n_cases=None, do_narratives=True, stop_after=None, seed=PHASE2_SEED):
    t0 = time.time()
    rng = random.Random(seed)

    print("Loading Phase 1 (read-only)...")
    d = lp.load_all()
    cases = d["cases"]
    if n_cases:
        cases = cases[:n_cases]
    print(f"  {len(cases):,} cases, {len(d['customers']):,} customers, "
          f"{len(d['components']):,} components loaded in {time.time() - t0:.1f}s\n")

    now = d["phase2_now"]
    cat_id_to_key = et.category_key_by_name(d["cat_id_to_name"])
    component_flavor_map = gt.infer_component_category_flavors(
        d["components"], d["component_category_weights"], cat_id_to_key)
    precompute_customer_touched_products(d["customers"], cases)

    print("Building topology...")
    t1 = time.time()
    product_versions = gt.build_product_versions(rng, d["products"], now)
    customer_deployments = gt.build_customer_deployments(rng, d["customers"], d["products"], product_versions, now)
    component_dependencies = gt.build_component_dependencies(rng, d["components"], component_flavor_map)
    external_dependencies = gt.build_external_dependencies()
    external_dependency_links = gt.build_external_dependency_links(
        rng, d["components"], component_flavor_map, d["product_id_to_name"])
    write_csv("product_versions.csv", product_versions, ["id", "product_id", "version", "release_date", "is_current"])
    write_csv("customer_deployments.csv", customer_deployments,
              ["id", "customer_id", "product_id", "product_version_id", "environment", "region",
               "deployed_at", "status"])
    write_csv("component_dependencies.csv", component_dependencies,
              ["id", "component_id", "depends_on_component_id", "dependency_type", "weight"])
    write_csv("external_dependencies.csv", external_dependencies, ["id", "name", "domain"])
    write_csv("external_dependency_links.csv", external_dependency_links,
              ["id", "component_id", "external_dependency_id"])
    print(f"  done in {time.time() - t1:.1f}s\n")
    if stop_after == "topology":
        return locals()

    print("Building ops/capacity tables...")
    t2 = time.time()
    support_plans = go.build_support_plans()
    sla_policies = go.build_sla_policies()
    customer_entitlements = go.build_customer_entitlements(rng, d["customers"], now)
    agent_capacity = go.build_agent_capacity(rng, d["agents"])
    agent_schedule = go.build_agent_schedule(rng, d["agents"])
    team_capacity_snapshots = go.build_team_capacity_snapshots(rng, d["teams"], now)
    write_csv("support_plans.csv", support_plans, ["id", "name"])
    write_csv("sla_policies.csv", sla_policies,
              ["id", "support_plan_id", "severity", "response_time_minutes", "resolution_time_hours"])
    write_csv("customer_entitlements.csv", customer_entitlements,
              ["customer_id", "support_plan_id", "entitlement_start_date", "seats"])
    write_csv("agent_capacity.csv", agent_capacity,
              ["agent_id", "max_concurrent_cases", "weekly_capacity_hours", "current_utilization_pct"])
    write_csv("agent_schedule.csv", agent_schedule, ["id", "agent_id", "day_of_week", "shift_start_hour", "shift_end_hour"])
    write_csv("team_capacity_snapshots.csv", team_capacity_snapshots,
              ["id", "team_id", "week_start_date", "open_case_count", "capacity_hours_available", "utilization_pct"])
    print(f"  done in {time.time() - t2:.1f}s\n")
    if stop_after == "ops":
        return locals()

    print(f"Building change events + deployments for {len(cases):,} cases...")
    t3 = time.time()
    changes_result = gc.build_changes(rng, cases, d, component_flavor_map, customer_deployments, product_versions, now)
    write_csv("change_events.csv", changes_result["change_events"],
              ["id", "change_type", "component_id", "product_id", "customer_id", "environment", "region",
               "started_at", "completed_at", "status", "initiated_by"])
    write_csv("deployments.csv", changes_result["deployments"],
              ["change_event_id", "product_id", "version_from", "version_to", "rollout_strategy",
               "deploy_duration_minutes", "description"])
    write_csv("case_change_links.csv", changes_result["case_change_links"],
              ["case_id", "change_event_id", "time_proximity_hours", "scope_match"])
    print(f"  done in {time.time() - t3:.1f}s\n")
    if stop_after == "changes":
        return locals()

    print(f"Building evidence (telemetry/signals/config) for {len(cases):,} cases...")
    t4 = time.time()
    evidence_result = ge.build_evidence(rng, cases, d, component_flavor_map, component_dependencies, changes_result)
    write_csv("case_telemetry.csv", evidence_result["case_telemetry"],
              ["case_id", "component_id", "metric_code", "timestamp", "value", "is_anomalous"])
    write_csv("case_signals.csv", evidence_result["case_signals"],
              ["id", "case_id", "component_id", "signal_code", "timestamp", "message"])
    write_csv("configuration_snapshots.csv", evidence_result["configuration_snapshots"],
              ["id", "case_id", "component_id", "snapshot_at", "config_key", "config_value", "note"])
    print(f"  done in {time.time() - t4:.1f}s\n")
    if stop_after == "evidence":
        return locals()

    print(f"Building incidents for {len(cases):,} cases...")
    t5 = time.time()
    incident_result = gi.build_incidents(rng, cases, d, component_flavor_map, component_dependencies, now)
    write_csv("service_health_events.csv", incident_result["service_health_events"],
              ["id", "component_id", "started_at", "ended_at", "severity", "description"])
    write_csv("incidents.csv", incident_result["incidents"],
              ["id", "component_id", "region", "started_at", "ended_at", "severity", "status", "summary"])
    write_csv("incident_cases.csv", incident_result["incident_cases"],
              ["incident_id", "case_id", "relationship"])
    print(f"  done in {time.time() - t5:.1f}s\n")
    if stop_after == "incidents":
        return locals()

    print("Assembling phase2_observable / phase2_ground_truth...")
    t6 = time.time()
    observable, ground_truth = ge.build_observable_and_ground_truth(
        cases, changes_result, evidence_result, incident_result)
    write_csv("phase2_observable.csv", observable, list(observable[0].keys()))
    write_csv("phase2_ground_truth.csv", ground_truth, list(ground_truth[0].keys()))
    print(f"  done in {time.time() - t6:.1f}s\n")

    if do_narratives:
        print("Generating narrative text via Together AI (incidents.summary, deployments.description)...")
        t7 = time.time()
        import narratives_phase2 as np2
        try:
            np2.fill_incident_summaries(incident_result["incidents"], seed=seed,
                                         component_names=d["component_id_to_name"])
            np2.fill_deployment_descriptions(changes_result["deployments"], seed=seed,
                                              product_names=d["product_id_to_name"])
        except TogetherAuthError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        llm_client.print_usage_summary()
        write_csv("incidents.csv", incident_result["incidents"],
                  ["id", "component_id", "region", "started_at", "ended_at", "severity", "status", "summary"])
        write_csv("deployments.csv", changes_result["deployments"],
                  ["change_event_id", "product_id", "version_from", "version_to", "rollout_strategy",
                   "deploy_duration_minutes", "description"])
        print(f"  done in {time.time() - t7:.1f}s\n")
    else:
        print("Skipping narrative generation; using template placeholders for summary/description text.\n")
        import narratives_phase2 as np2
        np2.template_fallback_incidents(incident_result["incidents"])
        np2.template_fallback_deployments(changes_result["deployments"])
        write_csv("incidents.csv", incident_result["incidents"],
                  ["id", "component_id", "region", "started_at", "ended_at", "severity", "status", "summary"])
        write_csv("deployments.csv", changes_result["deployments"],
                  ["change_event_id", "product_id", "version_from", "version_to", "rollout_strategy",
                   "deploy_duration_minutes", "description"])

    print(f"\nTotal Phase 2 build time: {time.time() - t0:.1f}s")
    return locals()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=int, default=0, help="Run on a small subset of N cases, with narratives")
    parser.add_argument("--full", action="store_true", help="Run the full build across all 25,000 cases")
    parser.add_argument("--skip-narratives", action="store_true", help="Skip LLM calls, use template placeholders")
    parser.add_argument("--topology-only", action="store_true", help="Stop after topology tables (dev/testing)")
    parser.add_argument("--ops-only", action="store_true", help="Stop after ops tables (dev/testing)")
    parser.add_argument("--changes-only", action="store_true", help="Stop after change tables (dev/testing)")
    parser.add_argument("--evidence-only", action="store_true", help="Stop after evidence tables (dev/testing)")
    parser.add_argument("--incidents-only", action="store_true", help="Stop after incident tables (dev/testing)")
    args = parser.parse_args()

    stop_after = None
    if args.topology_only:
        stop_after = "topology"
    elif args.ops_only:
        stop_after = "ops"
    elif args.changes_only:
        stop_after = "changes"
    elif args.evidence_only:
        stop_after = "evidence"
    elif args.incidents_only:
        stop_after = "incidents"

    if args.pilot:
        run(n_cases=args.pilot, do_narratives=True, stop_after=stop_after)
    elif args.full:
        run(n_cases=None, do_narratives=not args.skip_narratives, stop_after=stop_after)
    else:
        parser.print_help()
