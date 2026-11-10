"""
Neo4j graph client — executes the 4 core Cypher queries used by the agent.
Falls back to mock data when USE_MOCK=True (useful before Neo4j is connected).
"""
import sys
import random
from pathlib import Path

from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

USE_MOCK = False  # flip to True to skip Neo4j during local development


# ── Driver (module-level singleton) ──────────────────────────────────────────

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    return _driver


def close_driver():
    global _driver
    if _driver:
        _driver.close()
        _driver = None


# ── Query 1: Find similar resolved cases ─────────────────────────────────────

def find_similar_cases(case_description: str, product_id: str) -> list[dict]:
    """
    Given a product, return top 5 resolved cases about that product,
    ordered by fastest resolution time.
    Returns: [{ case_id, title, resolution_time_hours, agent_id }]
    """
    if USE_MOCK:
        return _mock_similar_cases()

    cypher = """
    MATCH (c:Case)-[:ABOUT]->(p:Product {id: $product_id})
    WHERE c.status = 'resolved'
      AND c.resolution_time_hours IS NOT NULL
    OPTIONAL MATCH (a:Agent)-[:RESOLVED]->(c)
    RETURN c.id                    AS case_id,
           c.title                 AS title,
           c.resolution_time_hours AS resolution_time_hours,
           a.id                    AS agent_id
    ORDER BY c.resolution_time_hours ASC
    LIMIT 5
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_id=product_id)
        return [dict(r) for r in result]


# ── Query 2: Find best agents for a case ─────────────────────────────────────

def find_best_agents(product_id: str, required_skills: list[str]) -> list[dict]:
    """
    Given a product and required skill IDs, return top 5 agents ranked by:
    - skill match count (weight 3.0)
    - number of resolved cases on this product (weight 1.0)
    - KB article usage on this product (weight 0.5)
    - avg resolution time penalty (weight -RESOLUTION_TIME_WEIGHT per hour)
    Returns: [{ agent_id, name, seniority, avg_resolution_time, match_score }]
    """
    if USE_MOCK:
        return _mock_best_agents()

    import config.settings as _cfg
    rt_weight = _cfg.RESOLUTION_TIME_WEIGHT

    cypher = f"""
    MATCH (a:Agent)-[:HAS_SKILL]->(s:Skill)
    WHERE s.id IN $required_skills
    WITH a, count(DISTINCT s) AS skill_match

    OPTIONAL MATCH (a)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product {{id: $product_id}})
    WITH a, skill_match, count(DISTINCT c) AS cases_on_product

    OPTIONAL MATCH (a)-[:USED]->(ka:KnowledgeArticle)-[:COVERS]->(p2:Product {{id: $product_id}})
    WITH a, skill_match, cases_on_product, count(DISTINCT ka) AS articles_used

    WITH a,
         skill_match,
         cases_on_product,
         articles_used,
         (skill_match * 3.0 + cases_on_product * 1.0 + articles_used * 0.5
          - coalesce(a.avg_resolution_time_hours, 10.0) * {rt_weight}) AS match_score

    WHERE match_score > 0
    RETURN a.id                          AS agent_id,
           a.name                        AS name,
           a.seniority                   AS seniority,
           a.avg_resolution_time_hours   AS avg_resolution_time,
           skill_match                   AS skills_matched,
           round(match_score, 2)         AS match_score
    ORDER BY match_score DESC
    LIMIT 5
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_id=product_id, required_skills=required_skills)
        return [dict(r) for r in result]


# ── Random agent for triage assignment ───────────────────────────────────────

def get_random_agent(product_id: str, required_skills: list[str]) -> dict | None:
    """
    Return a truly random agent from the full pool of agents who have resolved
    cases for this product — bypasses the skill-rank entirely to simulate naive
    triage, maximising contrast with the graph-ranked recommendation shown later.
    Uses Cypher rand() so the result differs on every call.
    """
    if USE_MOCK:
        agents = _mock_best_agents()
        return agents[-1] if agents else None

    cypher = """
    MATCH (a:Agent)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product {id: $product_id})
    WITH DISTINCT a
    RETURN a.name      AS name,
           a.seniority AS seniority,
           a.avg_resolution_time_hours AS avg_resolution_time
    ORDER BY rand()
    LIMIT 1
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_id=product_id)
        records = [dict(r) for r in result]
        return records[0] if records else None


# ── All agents (for workload panel) ──────────────────────────────────────────

def get_all_agents() -> list[dict]:
    """Return all agents with name, seniority, and avg resolution time."""
    if USE_MOCK:
        return [
            {"agent_id": "A005", "name": "Sarah Chen",    "seniority": "senior", "avg_resolution_time": 4.2},
            {"agent_id": "A012", "name": "Marcus Webb",   "seniority": "mid",    "avg_resolution_time": 7.1},
            {"agent_id": "A023", "name": "Priya Nair",    "seniority": "senior", "avg_resolution_time": 3.9},
            {"agent_id": "A031", "name": "James Kim",     "seniority": "junior", "avg_resolution_time": 9.4},
            {"agent_id": "A044", "name": "Olivia Torres", "seniority": "mid",    "avg_resolution_time": 6.3},
        ]

    cypher = """
    MATCH (a:Agent)
    RETURN a.id                        AS agent_id,
           a.name                      AS name,
           a.seniority                 AS seniority,
           a.avg_resolution_time_hours AS avg_resolution_time
    ORDER BY a.name
    """
    with get_driver().session() as session:
        result = session.run(cypher)
        return [dict(r) for r in result]


# ── Query 3: Find relevant KB articles ───────────────────────────────────────

def find_kb_articles(product_id: str) -> list[dict]:
    """
    Given a product, return top KB articles that cover it,
    filtered to resolution_rate > 0.7, ranked by rate then usage.
    Returns: [{ article_id, title, resolution_rate, times_used }]
    """
    if USE_MOCK:
        return _mock_kb_articles()

    cypher = """
    MATCH (ka:KnowledgeArticle)-[:COVERS]->(p:Product {id: $product_id})
    WHERE ka.resolution_rate > 0.7
    OPTIONAL MATCH (a:Agent)-[:USED]->(ka)
    WITH ka, count(DISTINCT a) AS times_used
    RETURN ka.id              AS article_id,
           ka.title           AS title,
           ka.resolution_rate AS resolution_rate,
           times_used
    ORDER BY ka.resolution_rate DESC, times_used DESC
    LIMIT 5
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_id=product_id)
        return [dict(r) for r in result]


# ── Query 4: Full 4-hop recommendation ───────────────────────────────────────

def get_full_recommendation(customer_id: str, product_id: str) -> dict:
    """
    4-hop traversal:
      Customer -[RAISED]-> Case -[ABOUT]-> Product
                                           -[COVERS]- KnowledgeArticle
                                           <- Agent -[RESOLVED]-> Case

    Returns a complete recommendation package:
    {
      customer: { id, name, tier },
      product:  { id, name },
      similar_cases: [...],
      top_agents:    [...],
      top_articles:  [...],
      avg_resolution_hours: float
    }
    """
    if USE_MOCK:
        return _mock_full_recommendation(customer_id, product_id)

    # Hop 1+2: customer context for this product
    customer_q = """
    MATCH (cust:Customer {id: $customer_id})
    OPTIONAL MATCH (cust)-[:RAISED]->(prev:Case)-[:ABOUT]->(p:Product {id: $product_id})
    WHERE prev.status = 'resolved'
    RETURN cust.id   AS customer_id,
           cust.name AS customer_name,
           cust.tier AS customer_tier,
           count(prev) AS prior_cases_on_product
    """

    # Hop 3: KB articles for this product
    articles_q = """
    MATCH (ka:KnowledgeArticle)-[:COVERS]->(p:Product {id: $product_id})
    WHERE ka.resolution_rate > 0.65
    OPTIONAL MATCH (a:Agent)-[:USED]->(ka)
    WITH ka, count(DISTINCT a) AS times_used
    RETURN ka.id              AS article_id,
           ka.title           AS title,
           ka.resolution_rate AS resolution_rate,
           times_used
    ORDER BY ka.resolution_rate DESC, times_used DESC
    LIMIT 3
    """

    # Hop 3+4: agents who resolved cases about this product + used its KB articles
    agents_q = """
    MATCH (a:Agent)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product {id: $product_id})
    WITH a, count(DISTINCT c) AS cases_resolved, avg(c.resolution_time_hours) AS avg_time
    OPTIONAL MATCH (a)-[:USED]->(ka:KnowledgeArticle)-[:COVERS]->(p2:Product {id: $product_id})
    WITH a, cases_resolved, avg_time, count(DISTINCT ka) AS articles_used
    RETURN a.id                        AS agent_id,
           a.name                      AS name,
           a.seniority                 AS seniority,
           round(avg_time, 1)          AS avg_resolution_hours,
           cases_resolved,
           articles_used
    ORDER BY cases_resolved DESC, avg_time ASC
    LIMIT 3
    """

    # Similar resolved cases
    similar_q = """
    MATCH (c:Case)-[:ABOUT]->(p:Product {id: $product_id})
    WHERE c.status = 'resolved' AND c.resolution_time_hours IS NOT NULL
    RETURN c.id                    AS case_id,
           c.title                 AS title,
           c.priority              AS priority,
           c.resolution_time_hours AS resolution_time_hours
    ORDER BY c.resolution_time_hours ASC
    LIMIT 5
    """

    with get_driver().session() as session:
        customer_rec = dict(session.run(customer_q, customer_id=customer_id,
                                        product_id=product_id).single() or {})
        articles     = [dict(r) for r in session.run(articles_q, product_id=product_id)]
        agents       = [dict(r) for r in session.run(agents_q,   product_id=product_id)]
        similar      = [dict(r) for r in session.run(similar_q,  product_id=product_id)]

    avg_res = (
        sum(c["resolution_time_hours"] for c in similar if c["resolution_time_hours"])
        / max(len(similar), 1)
    )

    return {
        "customer":              customer_rec,
        "product_id":            product_id,
        "similar_cases":         similar,
        "top_agents":            agents,
        "top_articles":          articles,
        "avg_resolution_hours":  round(avg_res, 1),
    }


# ── Product catalogue (for extraction pipeline) ───────────────────────────────

def get_all_products() -> list[dict]:
    """Return every product node: [{product_id, name}] ordered by name."""
    if USE_MOCK:
        return [
            {"product_id": "P001", "name": "Payment Gateway v2.1"},
            {"product_id": "P002", "name": "SSO Integration Module"},
            {"product_id": "P003", "name": "Analytics Dashboard"},
        ]
    cypher = """
    MATCH (p:Product)
    RETURN p.id AS product_id, p.name AS name
    ORDER BY p.name
    """
    with get_driver().session() as session:
        result = session.run(cypher)
        return [dict(r) for r in result]


def get_skills_for_product(product_id: str) -> list[str]:
    """
    Return up to 3 skill IDs most frequently required by cases about this product.
    Used when the matched product is not in the hardcoded PRODUCT_SKILLS dict.
    """
    if USE_MOCK:
        _mock_skills = {
            "P001": ["SK001", "SK002"],
            "P002": ["SK007", "SK009"],
            "P003": ["SK014", "SK013"],
        }
        return _mock_skills.get(product_id, [])
    cypher = """
    MATCH (c:Case)-[:ABOUT]->(p:Product {id: $product_id})
    MATCH (c)-[:REQUIRES_SKILL]->(s:Skill)
    WITH s, count(*) AS freq
    ORDER BY freq DESC
    LIMIT 3
    RETURN s.id AS skill_id
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_id=product_id)
        return [r["skill_id"] for r in result]


def get_customer_for_product(product_id: str) -> str:
    """
    Return the ID of the customer with the most cases on this product.
    Fallback for products not in the hardcoded PRODUCT_CUSTOMER dict.
    """
    if USE_MOCK:
        return "C0009"
    cypher = """
    MATCH (cust:Customer)-[:RAISED]->(c:Case)-[:ABOUT]->(p:Product {id: $product_id})
    RETURN cust.id AS customer_id, count(c) AS case_count
    ORDER BY case_count DESC
    LIMIT 1
    """
    with get_driver().session() as session:
        rec = session.run(cypher, product_id=product_id).single()
        return rec["customer_id"] if rec else "C0001"


# ── Analytics Query 1: Agent performance per product ─────────────────────────

def analyze_product_performance(product_name: str, top_n: int = 10) -> list[dict]:
    """
    Returns top agents ranked by cases resolved for a product name (partial match).
    Returns: [{ agent_name, seniority, cases_resolved, avg_resolution_time }]
    """
    if USE_MOCK:
        return _mock_product_performance(product_name, top_n)

    cypher = """
    MATCH (a:Agent)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product)
    WHERE toLower(p.name) CONTAINS toLower($product_name)
    RETURN a.name                              AS agent_name,
           a.seniority                         AS seniority,
           count(c)                            AS cases_resolved,
           round(avg(c.resolution_time_hours), 1) AS avg_resolution_time
    ORDER BY cases_resolved DESC
    LIMIT $top_n
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_name=product_name, top_n=top_n)
        return [dict(r) for r in result]


# ── Analytics Query 2: Skill coverage ────────────────────────────────────────

def analyze_skill_coverage(skill_name: str) -> list[dict]:
    """
    If skill_name is provided: agents who have that skill.
    If empty: all skills with agent counts (for understaffing analysis).
    Returns: [{ skill, agent_name, seniority }] OR [{ skill, agent_count }]
    """
    if USE_MOCK:
        return _mock_skill_coverage(skill_name)

    if skill_name:
        cypher = """
        MATCH (a:Agent)-[:HAS_SKILL]->(s:Skill)
        WHERE toLower(s.name) CONTAINS toLower($skill_name)
        RETURN s.name AS skill, a.name AS agent_name, a.seniority AS seniority
        ORDER BY s.name, a.seniority DESC, a.name
        """
        with get_driver().session() as session:
            result = session.run(cypher, skill_name=skill_name)
            return [dict(r) for r in result]
    else:
        cypher = """
        MATCH (s:Skill)
        OPTIONAL MATCH (a:Agent)-[:HAS_SKILL]->(s)
        WITH s, count(a) AS agent_count
        RETURN s.name AS skill, agent_count
        ORDER BY agent_count ASC
        LIMIT 15
        """
        with get_driver().session() as session:
            result = session.run(cypher)
            return [dict(r) for r in result]


# ── Analytics Query 3: KB article effectiveness per product ──────────────────

def analyze_kb_effectiveness(product_name: str) -> list[dict]:
    """
    Returns KB articles for a product with resolution rates and usage counts.
    Returns: [{ title, resolution_rate_pct, usage, product_name }]
    """
    if USE_MOCK:
        return _mock_kb_effectiveness(product_name)

    cypher = """
    MATCH (kb:KnowledgeArticle)-[:COVERS]->(p:Product)
    WHERE toLower(p.name) CONTAINS toLower($product_name)
    OPTIONAL MATCH (a:Agent)-[:USED]->(kb)
    WITH kb, p.name AS product_name, count(DISTINCT a) AS usage
    RETURN kb.title                            AS title,
           round(kb.resolution_rate * 100, 1)  AS resolution_rate_pct,
           usage,
           product_name
    ORDER BY kb.resolution_rate DESC, usage DESC
    """
    with get_driver().session() as session:
        result = session.run(cypher, product_name=product_name)
        return [dict(r) for r in result]


# ── Analytics Query 4: Escalation risk by customer tier ──────────────────────

def analyze_escalation_risk(tier: str, days_old: int) -> list[dict]:
    """
    Returns open/in-progress cases raised by customers of a given tier.
    days_old is ignored if Case nodes lack a created_date property.
    Returns: [{ case_id, title, status, priority, customer_name }]
    """
    if USE_MOCK:
        return _mock_escalation_risk(tier, days_old)

    cypher = """
    MATCH (cust:Customer)-[:RAISED]->(c:Case)
    WHERE toLower(cust.tier) = toLower($tier)
      AND c.status <> 'resolved'
    RETURN c.id          AS case_id,
           c.title       AS title,
           c.status      AS status,
           c.priority    AS priority,
           cust.name     AS customer_name
    ORDER BY c.priority DESC
    LIMIT 20
    """
    with get_driver().session() as session:
        result = session.run(cypher, tier=tier)
        return [dict(r) for r in result]


# ── Mock responses (used when USE_MOCK = True) ────────────────────────────────

def _mock_similar_cases():
    return [
        {"case_id": "CS00001", "title": "Unable to process refunds on Payment Gateway v2 — error code 4023",
         "resolution_time_hours": 3.2, "agent_id": "A005"},
        {"case_id": "CS00002", "title": "Unable to process refunds on Payment Gateway v2 — error code 4019",
         "resolution_time_hours": 5.1, "agent_id": "A012"},
        {"case_id": "CS00003", "title": "Payment webhook not firing on Payment Gateway v2",
         "resolution_time_hours": 6.8, "agent_id": "A005"},
    ]


def _mock_best_agents():
    return [
        {"agent_id": "A005", "name": "Sarah Chen",     "seniority": "senior",
         "avg_resolution_time": 4.2, "match_score": 9.5},
        {"agent_id": "A012", "name": "Marcus Webb",    "seniority": "mid",
         "avg_resolution_time": 7.1, "match_score": 7.0},
        {"agent_id": "A023", "name": "Priya Nair",     "seniority": "senior",
         "avg_resolution_time": 3.9, "match_score": 6.5},
    ]


def _mock_kb_articles():
    return [
        {"article_id": "KA0001", "title": "Resolving Error Code 4023 in Payment Gateway v2",
         "resolution_rate": 0.92, "times_used": 28},
        {"article_id": "KA0002", "title": "Payment Gateway v2 Refund Flow Troubleshooting",
         "resolution_rate": 0.88, "times_used": 21},
        {"article_id": "KA0027", "title": "Payment Gateway PCI Compliance Checklist",
         "resolution_rate": 0.94, "times_used": 15},
    ]


def _mock_full_recommendation(customer_id, product_id):
    return {
        "customer":     {"customer_id": customer_id, "customer_name": "Acme Corp",
                         "customer_tier": "gold", "prior_cases_on_product": 3},
        "product_id":   product_id,
        "similar_cases":  _mock_similar_cases(),
        "top_agents":     _mock_best_agents(),
        "top_articles":   _mock_kb_articles(),
        "avg_resolution_hours": 5.0,
    }


def _mock_product_performance(_product_name: str, top_n: int = 10) -> list[dict]:
    data = [
        {"agent_name": "Sarah Chen",    "seniority": "senior", "cases_resolved": 42, "avg_resolution_time": 4.2},
        {"agent_name": "Priya Nair",    "seniority": "senior", "cases_resolved": 35, "avg_resolution_time": 3.9},
        {"agent_name": "Marcus Webb",   "seniority": "mid",    "cases_resolved": 28, "avg_resolution_time": 7.1},
        {"agent_name": "Olivia Torres", "seniority": "mid",    "cases_resolved": 21, "avg_resolution_time": 6.3},
        {"agent_name": "James Kim",     "seniority": "junior", "cases_resolved": 12, "avg_resolution_time": 9.4},
    ]
    return data[:top_n]


def _mock_skill_coverage(skill_name: str) -> list[dict]:
    if skill_name:
        return [
            {"skill": "Payment Processing", "agent_name": "Sarah Chen",    "seniority": "senior"},
            {"skill": "Payment Processing", "agent_name": "Marcus Webb",   "seniority": "mid"},
            {"skill": "Payment Processing", "agent_name": "Priya Nair",    "seniority": "senior"},
        ]
    return [
        {"skill": "PCI Compliance",      "agent_count": 1},
        {"skill": "SAML/OAuth",          "agent_count": 2},
        {"skill": "Data Exports",        "agent_count": 2},
        {"skill": "Payment Processing",  "agent_count": 3},
        {"skill": "SSO Configuration",   "agent_count": 3},
        {"skill": "Error Diagnostics",   "agent_count": 4},
        {"skill": "Analytics Debugging", "agent_count": 5},
    ]


def _mock_kb_effectiveness(_product_name: str) -> list[dict]:
    return [
        {"title": "Payment Gateway PCI Compliance Checklist",        "resolution_rate_pct": 94.0, "usage": 15, "product_name": "Payment Gateway v2.1"},
        {"title": "Resolving Error Code 4023 in Payment Gateway v2", "resolution_rate_pct": 92.0, "usage": 28, "product_name": "Payment Gateway v2.1"},
        {"title": "Payment Gateway v2 Refund Flow Troubleshooting",  "resolution_rate_pct": 88.0, "usage": 21, "product_name": "Payment Gateway v2.1"},
        {"title": "SSO Azure AD Integration Guide",                   "resolution_rate_pct": 85.0, "usage": 18, "product_name": "SSO Integration Module"},
        {"title": "Analytics Dashboard Export Troubleshooting",       "resolution_rate_pct": 78.0, "usage": 11, "product_name": "Analytics Dashboard"},
    ]


def _mock_escalation_risk(_tier: str, _days_old: int) -> list[dict]:
    return [
        {"case_id": "CS00201", "title": "Unable to process refunds on Payment Gateway v2",
         "status": "open",        "priority": "critical", "customer_name": "Acme Corp"},
        {"case_id": "CS00189", "title": "SSO login intermittently failing for 200 users",
         "status": "in_progress", "priority": "high",     "customer_name": "GlobalTech Inc"},
        {"case_id": "CS00175", "title": "Analytics export missing 30% of rows",
         "status": "open",        "priority": "high",     "customer_name": "DataCorp LLC"},
    ]
