"""
Loads all CSV data from /data/raw/ into Neo4j AuraDB.
Uses MERGE to avoid duplicates — safe to re-run.
Run once after generating CSVs and before using the agent.

Usage:
    python agent/neo4j_loader.py
"""
import csv
import os
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

# Allow running from project root or agent/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

RAW = PROJECT_ROOT / "data" / "raw"
BATCH = 500  # rows per transaction


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_csv(filename):
    path = RAW / filename
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_batched(session, rows, cypher, label):
    total = len(rows)
    for start in range(0, total, BATCH):
        batch = rows[start : start + BATCH]
        session.run(cypher, rows=batch)
    print(f"  ✓  {label:<35} {total:>7,} rows")


# ── Constraints (run once, idempotent) ────────────────────────────────────────

CONSTRAINTS = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Customer)         REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Case)             REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Product)          REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:KnowledgeArticle) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Agent)            REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Skill)            REQUIRE n.id IS UNIQUE",
]


# ── Node loaders ──────────────────────────────────────────────────────────────

def load_customers(session):
    rows = read_csv("customers.csv")
    cypher = """
    UNWIND $rows AS r
    MERGE (n:Customer {id: r.id})
    SET n.name   = r.name,
        n.tier   = r.tier,
        n.region = r.region
    """
    run_batched(session, rows, cypher, "Customer nodes")


def load_cases(session):
    rows = read_csv("cases.csv")
    # Coerce numeric field; empty string → null
    for r in rows:
        r["resolution_time_hours"] = (
            float(r["resolution_time_hours"]) if r["resolution_time_hours"] else None
        )
    cypher = """
    UNWIND $rows AS r
    MERGE (n:Case {id: r.id})
    SET n.title                  = r.title,
        n.description            = r.description,
        n.status                 = r.status,
        n.priority               = r.priority,
        n.created_date           = r.created_date,
        n.resolution_time_hours  = r.resolution_time_hours
    """
    run_batched(session, rows, cypher, "Case nodes")


def load_products(session):
    rows = read_csv("products.csv")
    cypher = """
    UNWIND $rows AS r
    MERGE (n:Product {id: r.id})
    SET n.name     = r.name,
        n.category = r.category,
        n.version  = r.version
    """
    run_batched(session, rows, cypher, "Product nodes")


def load_knowledge_articles(session):
    rows = read_csv("knowledge_articles.csv")
    for r in rows:
        r["resolution_rate"] = float(r["resolution_rate"])
        r["views"]           = int(r["views"])
    cypher = """
    UNWIND $rows AS r
    MERGE (n:KnowledgeArticle {id: r.id})
    SET n.title           = r.title,
        n.content_summary = r.content_summary,
        n.resolution_rate = r.resolution_rate,
        n.views           = r.views,
        n.created_date    = r.created_date
    """
    run_batched(session, rows, cypher, "KnowledgeArticle nodes")


def load_agents(session):
    rows = read_csv("agents.csv")
    for r in rows:
        r["avg_resolution_time_hours"] = float(r["avg_resolution_time_hours"])
    cypher = """
    UNWIND $rows AS r
    MERGE (n:Agent {id: r.id})
    SET n.name                      = r.name,
        n.seniority                 = r.seniority,
        n.avg_resolution_time_hours = r.avg_resolution_time_hours
    """
    run_batched(session, rows, cypher, "Agent nodes")


def load_skills(session):
    rows = read_csv("skills.csv")
    cypher = """
    UNWIND $rows AS r
    MERGE (n:Skill {id: r.id})
    SET n.name     = r.name,
        n.category = r.category
    """
    run_batched(session, rows, cypher, "Skill nodes")


# ── Relationship loaders ──────────────────────────────────────────────────────

def load_customer_cases(session):
    rows = read_csv("customer_cases.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (c:Customer {id: r.customer_id})
    MATCH (cs:Case    {id: r.case_id})
    MERGE (c)-[:RAISED]->(cs)
    """
    run_batched(session, rows, cypher, "Customer -[RAISED]-> Case")


def load_case_products(session):
    rows = read_csv("case_products.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (cs:Case    {id: r.case_id})
    MATCH (p:Product  {id: r.product_id})
    MERGE (cs)-[:ABOUT]->(p)
    """
    run_batched(session, rows, cypher, "Case -[ABOUT]-> Product")


def load_agent_cases(session):
    rows = read_csv("agent_cases.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (a:Agent {id: r.agent_id})
    MATCH (cs:Case {id: r.case_id})
    MERGE (a)-[:RESOLVED]->(cs)
    """
    run_batched(session, rows, cypher, "Agent -[RESOLVED]-> Case")


def load_agent_skills(session):
    rows = read_csv("agent_skills.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (a:Agent {id: r.agent_id})
    MATCH (s:Skill {id: r.skill_id})
    MERGE (a)-[:HAS_SKILL]->(s)
    """
    run_batched(session, rows, cypher, "Agent -[HAS_SKILL]-> Skill")


def load_case_skills(session):
    rows = read_csv("case_skills.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (cs:Case {id: r.case_id})
    MATCH (s:Skill {id: r.skill_id})
    MERGE (cs)-[:REQUIRES_SKILL]->(s)
    """
    run_batched(session, rows, cypher, "Case -[REQUIRES_SKILL]-> Skill")


def load_article_products(session):
    rows = read_csv("article_products.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (ka:KnowledgeArticle {id: r.article_id})
    MATCH (p:Product           {id: r.product_id})
    MERGE (ka)-[:COVERS]->(p)
    """
    run_batched(session, rows, cypher, "KnowledgeArticle -[COVERS]-> Product")


def load_agent_articles(session):
    rows = read_csv("agent_articles.csv")
    cypher = """
    UNWIND $rows AS r
    MATCH (a:Agent             {id: r.agent_id})
    MATCH (ka:KnowledgeArticle {id: r.article_id})
    MERGE (a)-[:USED]->(ka)
    """
    run_batched(session, rows, cypher, "Agent -[USED]-> KnowledgeArticle")


def load_similar_cases(session):
    rows = read_csv("similar_cases.csv")
    for r in rows:
        r["similarity_score"] = float(r["similarity_score"])
    cypher = """
    UNWIND $rows AS r
    MATCH (a:Case {id: r.case_id_a})
    MATCH (b:Case {id: r.case_id_b})
    MERGE (a)-[rel:SIMILAR_TO]-(b)
    SET rel.similarity_score = r.similarity_score
    """
    run_batched(session, rows, cypher, "Case -[SIMILAR_TO]- Case")


# ── Summary query ─────────────────────────────────────────────────────────────

def print_summary(session):
    node_q = """
    MATCH (n)
    RETURN labels(n)[0] AS label, count(n) AS count
    ORDER BY count DESC
    """
    rel_q = """
    MATCH ()-[r]->()
    RETURN type(r) AS type, count(r) AS count
    ORDER BY count DESC
    """
    print("\n── Node counts ──────────────────────────────────────────────")
    total_nodes = 0
    for rec in session.run(node_q):
        print(f"  {rec['label']:<25} {rec['count']:>8,}")
        total_nodes += rec["count"]
    print(f"  {'TOTAL':<25} {total_nodes:>8,}")

    print("\n── Relationship counts ──────────────────────────────────────")
    total_rels = 0
    for rec in session.run(rel_q):
        print(f"  {rec['type']:<25} {rec['count']:>8,}")
        total_rels += rec["count"]
    print(f"  {'TOTAL':<25} {total_rels:>8,}")
    print("─────────────────────────────────────────────────────────────")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Connecting to Neo4j: {NEO4J_URI}")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    driver.verify_connectivity()
    print("Connected.\n")

    with driver.session() as session:
        # Constraints
        print("Creating constraints...")
        for stmt in CONSTRAINTS:
            session.run(stmt)
        print("  ✓  Constraints ready\n")

        # Nodes
        print("Loading nodes...")
        t0 = time.time()
        load_customers(session)
        load_cases(session)
        load_products(session)
        load_knowledge_articles(session)
        load_agents(session)
        load_skills(session)
        print(f"  Nodes loaded in {time.time() - t0:.1f}s\n")

        # Relationships
        print("Loading relationships...")
        t1 = time.time()
        load_customer_cases(session)
        load_case_products(session)
        load_agent_cases(session)
        load_agent_skills(session)
        load_case_skills(session)
        load_article_products(session)
        load_agent_articles(session)
        load_similar_cases(session)
        print(f"  Relationships loaded in {time.time() - t1:.1f}s\n")

        print_summary(session)

    driver.close()
    print("\nLoad complete.")


if __name__ == "__main__":
    main()
