"""Phase 4 graph build orchestrator.

Usage:
    python3 -m agent.graph_v2.build_graph --mode small --wipe        # standing graph, 2500 cases (default)
    python3 -m agent.graph_v2.build_graph --mode small --n-cases 500 # fast dev iteration
    python3 -m agent.graph_v2.build_graph --mode full                # all 25,000 -- needs a paid Aura
                                                                      # tier or local Neo4j; Free tier's
                                                                      # 400K-relationship cap rejects it
    python3 -m agent.graph_v2.build_graph --stats-only

See docs/GRAPH_SCHEMA.md "Scale note" for how 2500 was chosen (measured
~72.7 relationships/case -> ~326K total, comfortably under Aura Free's
400K-relationship ceiling).

Never reads any evaluation_only file (case_ground_truth.csv,
phase2_ground_truth.csv, phase3_ground_truth.csv,
phase3_event_quality_labels.csv, ideal_investigation_requirements.csv,
case_components.csv, case_products.csv, case_team_ownership.csv,
agent_cases.csv, cases.csv) -- confirmed by validate_graph.py's import scan.
"""
import argparse
import time

from agent.graph_v2 import checksums, schema
from agent.graph_v2.config import DATA_RAW_V2
from agent.graph_v2.db import get_driver, read_csv
from agent.graph_v2.loaders import agents_teams, customers_cases, evidence, investigation, kb, similarity, taxonomy, topology


def _small_mode_case_ids(n_cases):
    rows = read_csv(DATA_RAW_V2 / "case_observable.csv")
    ids = sorted(r["id"] for r in rows)
    return set(ids[:n_cases])


def print_summary(session):
    print("\n-- Node counts --------------------------------------------------")
    total_nodes = 0
    for rec in session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC, label ASC"):
        print(f"  {rec['label']:<28} {rec['count']:>8,}")
        total_nodes += rec["count"]
    print(f"  {'TOTAL':<28} {total_nodes:>8,}")

    print("\n-- Relationship counts -------------------------------------------")
    total_rels = 0
    for rec in session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC, type ASC"):
        print(f"  {rec['type']:<28} {rec['count']:>8,}")
        total_rels += rec["count"]
    print(f"  {'TOTAL':<28} {total_rels:>8,}")
    print("-------------------------------------------------------------------")


def run(mode, n_cases, wipe, stats_only):
    checksums.verify_or_die()

    driver = get_driver()
    driver.verify_connectivity()
    t_start = time.time()
    try:
        with driver.session() as session:
            if stats_only:
                print_summary(session)
                return

            if wipe:
                print("Wiping existing graph (--wipe)...")
                session.run("MATCH (n) DETACH DELETE n")

            print("Applying schema (constraints + indexes)...")
            schema.apply(session)

            case_ids = _small_mode_case_ids(n_cases) if mode == "small" else None
            if case_ids is not None:
                print(f"Small mode: {len(case_ids)} cases (first {n_cases} by case id, deterministic)")

            print("\nLoading reference/taxonomy (always full)...")
            taxonomy.load(session)

            print("\nLoading agents/teams (always full)...")
            agents_teams.load(session)

            print("\nLoading customers/cases...")
            customers_cases.load(session, case_ids)

            print("\nLoading topology (always full; DEPLOYED needs Customer nodes above)...")
            topology.load(session)

            print("\nLoading KB (always full)...")
            kb.load(session)

            print("\nLoading evidence (changes/incidents/signals/telemetry/config)...")
            evidence.load(session, case_ids)

            print("\nLoading case similarity...")
            similarity.load(session)

            print("\nLoading investigation timeline (Phase 3)...")
            investigation.load(session, case_ids)

            print_summary(session)
    finally:
        driver.close()

    print(f"\nTotal build time: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "small"], default="full")
    parser.add_argument("--n-cases", type=int, default=2500, help="AuraDB Free caps at 400K relationships; 2500 is the measured-safe default (see docs/GRAPH_SCHEMA.md)")
    parser.add_argument("--wipe", action="store_true", help="DETACH DELETE all nodes before loading")
    parser.add_argument("--stats-only", action="store_true", help="print current graph stats and exit")
    args = parser.parse_args()
    run(args.mode, args.n_cases, args.wipe, args.stats_only)
