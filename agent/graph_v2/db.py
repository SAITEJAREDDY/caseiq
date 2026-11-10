"""Shared Neo4j session/batching helpers for the Phase 4 loaders, mirroring
agent/neo4j_loader.py's proven pattern (UNWIND + batched session.run, single
driver + single session per build run).
"""
import csv
import time

from neo4j import GraphDatabase

from agent.graph_v2.config import BATCH, NEO4J_V2_PASSWORD, NEO4J_V2_URI, NEO4J_V2_USERNAME, require_credentials


def get_driver():
    require_credentials()
    return GraphDatabase.driver(NEO4J_V2_URI, auth=(NEO4J_V2_USERNAME, NEO4J_V2_PASSWORD))


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_batched(session, rows, cypher, label, quiet=False):
    total = len(rows)
    if total == 0:
        if not quiet:
            print(f"  -  {label:<35} {0:>7,} rows (skipped, none)")
        return
    t0 = time.time()
    for start in range(0, total, BATCH):
        batch = rows[start : start + BATCH]
        session.run(cypher, rows=batch)
    if not quiet:
        print(f"  ok {label:<35} {total:>7,} rows  ({time.time() - t0:.1f}s)")
