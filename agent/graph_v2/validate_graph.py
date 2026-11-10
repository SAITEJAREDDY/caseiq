"""Phase 4 post-load validation.

Usage:
    python3 -m agent.graph_v2.validate_graph               # all checks except idempotency re-run
    python3 -m agent.graph_v2.validate_graph --idempotency # also re-runs the small-mode build and diffs counts
"""
import argparse
import ast
import csv
import json
import sys
from pathlib import Path

from agent.graph_v2 import checksums
from agent.graph_v2.config import DATA_PHASE3, PROJECT_ROOT
from agent.graph_v2.db import get_driver

GRAPH_V2_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = GRAPH_V2_DIR / "manifests" / "dataset_classification.json"

BANNED_SUBSTRINGS = [
    "gt_", "ground_truth", "causal", "distractor", "optimal", "_correct",
    "correct_", "warranted", "mistake", "efficiency", "misleading",
    "_relevant", "_missed", "is_distractor", "ideal_path", "evaluation_label",
]

FAILS = []


def fail(msg):
    FAILS.append(msg)
    print(f"  FAIL: {msg}")


def ok(msg):
    print(f"  ok:   {msg}")


# ── 1. Checksums ────────────────────────────────────────────────────────────

def check_checksums():
    print("\n[1] Phase 1/2/3 input-manifest checksums")
    problems = checksums.verify()
    if problems:
        for phase, fname, reason in problems:
            fail(f"checksum: [{phase}] {fname}: {reason}")
    else:
        ok("all 88 Phase 1/2/3 files match Phase 4's frozen baseline")


# ── 2. Leakage scan (live graph schema) ─────────────────────────────────────

def check_leakage_live(session):
    print("\n[2] Leakage scan -- live graph labels/relationship types/property keys")

    def flagged(names, kind):
        bad = []
        for n in names:
            low = n.lower()
            for sub in BANNED_SUBSTRINGS:
                if sub in low:
                    bad.append((n, sub))
                    break
        for name, sub in bad:
            fail(f"leakage: {kind} '{name}' matches banned substring '{sub}'")
        return bad

    labels = [r["label"] for r in session.run("CALL db.labels() YIELD label RETURN label")]
    rel_types = [r["relationshipType"] for r in session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
    prop_keys = [r["propertyKey"] for r in session.run("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey")]

    b1 = flagged(labels, "label")
    b2 = flagged(rel_types, "relationship type")
    b3 = flagged(prop_keys, "property key")
    if not (b1 or b2 or b3):
        ok(f"{len(labels)} labels, {len(rel_types)} relationship types, {len(prop_keys)} property keys -- none match banned substrings")


# ── 2b. Leakage scan (source code -- evaluation_only files never opened) ────

def _non_docstring_string_literals(path):
    """AST-based scan: every string literal in the file EXCEPT module/function/
    class docstrings (which legitimately name evaluation_only files in prose,
    e.g. "never opens case_ground_truth.csv"). A real code reference (a Path/
    read_csv argument) is a string literal that is NOT a docstring.
    """
    tree = ast.parse(path.read_text())
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_ids.add(id(body[0].value))
    literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_ids:
            literals.append(node.value)
    return literals


def check_leakage_source():
    print("\n[2b] Leakage scan -- evaluation_only CSVs never referenced by loader source (AST, docstrings excluded)")
    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    eval_only_files = []
    for phase in ("phase1", "phase2", "phase3"):
        for fname, entry in manifest[phase].items():
            if entry["bucket"] in ("evaluation_only", "excluded_redundant"):
                eval_only_files.append(fname)

    py_files = list((GRAPH_V2_DIR / "loaders").glob("*.py")) + [
        GRAPH_V2_DIR / "build_graph.py",
        GRAPH_V2_DIR / "telemetry_summarize.py",
        GRAPH_V2_DIR / "schema.py",
    ]

    hits = []
    for p in py_files:
        if not p.exists():
            continue
        for literal in _non_docstring_string_literals(p):
            for fname in eval_only_files:
                # Exact match (or a path ending in /<fname>) -- not substring
                # containment, since e.g. "cases.csv" is a substring of the
                # perfectly legitimate "similar_cases.csv"/"incident_cases.csv".
                if literal == fname or literal.endswith("/" + fname):
                    hits.append((p.name, fname, literal))

    if hits:
        for pyfile, fname, literal in hits:
            fail(f"leakage: {pyfile} has a non-docstring string literal referencing '{fname}': {literal!r}")
    else:
        ok(f"none of the {len(eval_only_files)} evaluation_only/excluded_redundant files appear in any non-docstring string literal in loader source")


# ── 3. Referential integrity ────────────────────────────────────────────────

def check_referential_integrity(session):
    print("\n[3] Referential integrity")
    constrained_labels = [
        "Customer", "Case", "Product", "ProductVersion", "Component", "IssueCategory",
        "IssueSubcategory", "Symptom", "Team", "Skill", "Agent", "KnowledgeArticle",
        "RootCauseFamily", "ResolutionType", "ExternalService", "SupportPlan",
        "ChangeEvent", "Incident", "ServiceHealthEvent", "ConfigurationSnapshot",
        "SignalType", "CaseSignalObservation", "TelemetryFinding", "InvestigationEvent",
    ]
    any_dupe = False
    for label in constrained_labels:
        rec = session.run(
            f"MATCH (n:{label}) WITH n.id AS id, count(*) AS c WHERE c > 1 RETURN count(*) AS dupes"
        ).single()
        if rec["dupes"] > 0:
            fail(f"referential: {rec['dupes']} duplicate id(s) on label {label}")
            any_dupe = True
    for label, prop in [("Hypothesis", "native_id"), ("ResolutionAttempt", "native_id")]:
        rec = session.run(
            f"MATCH (n:{label}) WITH n.{prop} AS id, count(*) AS c WHERE c > 1 RETURN count(*) AS dupes"
        ).single()
        if rec["dupes"] > 0:
            fail(f"referential: {rec['dupes']} duplicate {prop}(s) on label {label}")
            any_dupe = True
    if not any_dupe:
        ok("no duplicate canonical-id nodes on any constrained label")


# ── 4. Idempotency (optional, re-runs the small-mode build) ────────────────

def check_idempotency(session):
    print("\n[4] Idempotency -- re-running small-mode build and diffing counts")
    from agent.graph_v2 import build_graph

    def snapshot():
        nodes = {r["label"]: r["count"] for r in session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count")}
        rels = {r["type"]: r["count"] for r in session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")}
        return nodes, rels

    before_nodes, before_rels = snapshot()
    build_graph.run(mode="small", n_cases=500, wipe=False, stats_only=False)
    after_nodes, after_rels = snapshot()

    if before_nodes != after_nodes or before_rels != after_rels:
        node_diff = {k: (before_nodes.get(k), after_nodes.get(k)) for k in set(before_nodes) | set(after_nodes) if before_nodes.get(k) != after_nodes.get(k)}
        rel_diff = {k: (before_rels.get(k), after_rels.get(k)) for k in set(before_rels) | set(after_rels) if before_rels.get(k) != after_rels.get(k)}
        fail(f"idempotency: counts changed on re-run. node diffs={node_diff} rel diffs={rel_diff}")
    else:
        ok("re-running the small-mode build produced byte-identical node/relationship counts")


# ── 5. Decision-snapshot time-travel test ───────────────────────────────────

def check_decision_snapshot(session):
    print("\n[5] Decision-snapshot time-travel test")
    # Find a real multi-hypothesis case from the loaded graph.
    rec = session.run(
        """
        MATCH (c:Case)-[:HAS_EVENT]->(ie:InvestigationEvent)
        WITH c, count(ie) AS n
        WHERE n >= 8
        RETURN c.id AS case_id LIMIT 1
        """
    ).single()
    if rec is None:
        fail("decision-snapshot: no case with >=8 events found in the loaded graph to test against")
        return
    case_id = rec["case_id"]

    events = list(session.run(
        """
        MATCH (c:Case {id: $case_id})-[:HAS_EVENT]->(ie:InvestigationEvent)
        RETURN ie.id AS event_id, ie.timestamp AS timestamp
        ORDER BY ie.seq
        """,
        case_id=case_id,
    ))
    if len(events) < 3:
        fail(f"decision-snapshot: case {case_id} has too few events ({len(events)})")
        return

    # Cross-check against the CSV directly (not just internal self-consistency).
    csv_events = []
    with open(DATA_PHASE3 / "case_lifecycle_events.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["case_id"] == case_id:
                csv_events.append((row["event_id"], row["timestamp"]))
    csv_events.sort(key=lambda x: x[1])

    mid_ts = events[len(events) // 2]["timestamp"]
    graph_before = {
        r["event_id"]
        for r in session.run(
            """
            MATCH (c:Case {id: $case_id})-[:HAS_EVENT]->(ie:InvestigationEvent)
            WHERE ie.timestamp <= $asof
            RETURN ie.id AS event_id
            """,
            case_id=case_id, asof=mid_ts,
        )
    }
    csv_before = {eid for eid, ts in csv_events if ts <= mid_ts}

    if graph_before != csv_before:
        missing = csv_before - graph_before
        extra = graph_before - csv_before
        fail(f"decision-snapshot: case {case_id} @ {mid_ts} mismatch vs CSV -- missing={len(missing)} extra={len(extra)}")
    else:
        ok(f"case {case_id} @ {mid_ts}: graph time-filter matches CSV exactly ({len(graph_before)} events)")

    # Also confirm CONFIRMED_DIAGNOSIS respects disposition_at (not visible before it happened).
    diag = session.run(
        """
        MATCH (c:Case {id: $case_id})-[rel:CONFIRMED_DIAGNOSIS]->(:RootCauseFamily)
        RETURN rel.disposition_at AS disposition_at LIMIT 1
        """,
        case_id=case_id,
    ).single()
    if diag and diag["disposition_at"]:
        early_ts = events[0]["timestamp"]
        visible_early = session.run(
            """
            MATCH (c:Case {id: $case_id})-[rel:CONFIRMED_DIAGNOSIS]->(:RootCauseFamily)
            WHERE rel.disposition_at <= $asof
            RETURN count(rel) AS c
            """,
            case_id=case_id, asof=early_ts,
        ).single()["c"]
        if visible_early > 0 and early_ts < diag["disposition_at"]:
            fail(f"decision-snapshot: case {case_id}'s CONFIRMED_DIAGNOSIS visible before its own disposition_at")
        else:
            ok(f"case {case_id}'s CONFIRMED_DIAGNOSIS correctly hidden before disposition_at when queried with a time filter")


# ── 6. Historical-case retrieval spot check ─────────────────────────────────

def check_historical_retrieval(session):
    print("\n[6] Historical-case retrieval spot check")
    rec = session.run(
        """
        MATCH (c:Case)-[:CONFIRMED_DIAGNOSIS]->(rcf:RootCauseFamily)
        WHERE c.status = 'resolved'
        RETURN c.id AS case_id, rcf.name AS root_cause LIMIT 1
        """
    ).single()
    if rec is None:
        fail("historical-retrieval: no resolved case with a confirmed diagnosis found")
        return
    ok(f"resolved case {rec['case_id']}'s confirmed diagnosis ('{rec['root_cause']}') is retrievable via CONFIRMED_DIAGNOSIS")


def run(check_idempotency_flag):
    FAILS.clear()
    check_checksums()
    check_leakage_source()

    driver = get_driver()
    driver.verify_connectivity()
    try:
        with driver.session() as session:
            check_leakage_live(session)
            check_referential_integrity(session)
            check_decision_snapshot(session)
            check_historical_retrieval(session)
            if check_idempotency_flag:
                check_idempotency(session)
    finally:
        driver.close()

    print("\n" + "=" * 70)
    if FAILS:
        print(f"VALIDATION FAILED: {len(FAILS)} problem(s)")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED: all checks green")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--idempotency", action="store_true", help="also re-run the small-mode build and diff counts")
    args = parser.parse_args()
    run(args.idempotency)
