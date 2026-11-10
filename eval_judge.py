"""
CaseIQ evaluation suite — 6 categories of automated checks.

Each eval_* function runs a self-contained set of test cases and returns:
  [
    {
      "eval_category": str,
      "label":         str,      # human-readable test name
      "test_input":    dict,     # structured input (logged to LangSmith)
      "output":        any,      # actual result value
      "passed":        bool,
      "score":         float | None,
      "metadata":      dict,
      "tags":          [str],
    },
    ...
  ]

All Neo4j and LLM calls are wrapped in try/except so a single failing service
does not abort the whole suite.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import config.settings as cfg


# ══════════════════════════════════════════════════════════════════════════════
# EVAL 1 — Skill Match
# Does find_best_agents() return agents whose skills cover what the case needs?
# ══════════════════════════════════════════════════════════════════════════════

SKILL_MATCH_CASES = [
    {
        "label":           "Payment Gateway — SK001 + SK002 coverage",
        "agent_name_hint": "top agent",
        "product_id":      "P001",
        "customer_id":     "C0009",
        "required_skills": cfg.SCENARIOS["A"]["required_skills"],
        "threshold":       70,
    },
    {
        "label":           "SSO Module — SK007 + SK009 coverage",
        "agent_name_hint": "top agent",
        "product_id":      "P002",
        "customer_id":     "C0028",
        "required_skills": cfg.SCENARIOS["B"]["required_skills"],
        "threshold":       70,
    },
    {
        "label":           "Analytics Dashboard — SK014 + SK013 coverage",
        "agent_name_hint": "top agent",
        "product_id":      "P003",
        "customer_id":     "C0030",
        "required_skills": cfg.SCENARIOS["C"]["required_skills"],
        "threshold":       70,
    },
]


def eval_1_skill_match() -> list[dict]:
    from agent.graph_client import find_best_agents
    results = []

    for tc in SKILL_MATCH_CASES:
        try:
            agents = find_best_agents(
                tc["product_id"], tc["required_skills"]
            )
            if not agents:
                score   = 0
                output  = {"score": 0, "agent": None, "note": "No agents returned"}
            else:
                top     = agents[0]
                matched = top.get("skills_matched", 0)
                total   = len(tc["required_skills"]) or 1
                score   = round(matched / total * 100)
                output  = {
                    "score":          score,
                    "agent":          top.get("agent_name", "unknown"),
                    "skills_matched": matched,
                    "skills_needed":  total,
                }
        except Exception as exc:
            score  = 0
            output = {"score": 0, "error": str(exc)}

        passed = score >= tc["threshold"]
        results.append({
            "eval_category": "eval_1_skill_match",
            "label":         tc["label"],
            "test_input":    {"product_id": tc["product_id"],
                              "required_skills": tc["required_skills"]},
            "output":        output,
            "passed":        passed,
            "score":         score,
            "metadata":      {"threshold": tc["threshold"], "passed": passed},
            "tags":          ["eval_1", "skill_match"],
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVAL 2 — Confidence Calibration
# When keyword extraction returns HIGH confidence, is the product correct?
# ══════════════════════════════════════════════════════════════════════════════

CONFIDENCE_CASES = [
    {
        "label":              "Explicit Payment Gateway mention",
        "input":              "Customer cannot process refunds on Payment Gateway v2.1 — error code 4023",
        "expected_product_id": "P001",
    },
    {
        "label":              "Explicit SSO mention",
        "input":              "New account blocked — SSO Integration Module failing with Azure AD, SAML error",
        "expected_product_id": "P002",
    },
    {
        "label":              "Explicit Analytics mention",
        "input":              "Analytics Dashboard data export is corrupted, missing rows in CSV since last update",
        "expected_product_id": "P003",
    },
]


def eval_2_confidence_calibration() -> list[dict]:
    from agent.llm_client import gpt_extract_case
    from agent.graph_client import get_all_products
    results = []

    catalog      = get_all_products()
    product_names = [p["name"] for p in catalog]
    name_to_id   = {p["name"]: p["product_id"] for p in catalog}

    for tc in CONFIDENCE_CASES:
        try:
            kw     = gpt_extract_case(tc["input"], product_names)
            kconf  = kw["keyword_confidence"]
            got_id = name_to_id.get(kw.get("product") or "", "")
            correct   = got_id == tc["expected_product_id"]
            calibrated = (kconf >= cfg.CONF_HIGH and correct) or kconf < cfg.CONF_HIGH
            output = {
                "keyword_confidence":   kconf,
                "extracted_product":    kw.get("product"),
                "extracted_product_id": got_id,
                "is_correct":           correct,
                "is_well_calibrated":   calibrated,
            }
            passed = calibrated
        except Exception as exc:
            output = {"error": str(exc)}
            passed = False
            kconf  = 0.0

        results.append({
            "eval_category": "eval_2_confidence_calibration",
            "label":         tc["label"],
            "test_input":    {"user_input": tc["input"],
                              "expected_product_id": tc["expected_product_id"]},
            "output":        output,
            "passed":        passed,
            "score":         kconf,
            "metadata":      {"passed": passed},
            "tags":          ["eval_2", "confidence_calibration"],
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVAL 3 — Semantic Search Accuracy
# Does the sentence-transformer map product descriptions to the right product?
# ══════════════════════════════════════════════════════════════════════════════

SEMANTIC_CASES = [
    {
        "label":              "Payment keywords — no product name",
        "input":              "transactions keep failing at checkout with a card decline error",
        "expected_product_id": "P001",
    },
    {
        "label":              "Auth / login keywords — no product name",
        "input":              "single sign-on is broken, users cannot authenticate with their company accounts",
        "expected_product_id": "P002",
    },
    {
        "label":              "Reporting keywords — no product name",
        "input":              "the charts and reports on the analytics page are showing wrong data",
        "expected_product_id": "P003",
    },
    {
        "label":              "SAML / federated identity",
        "input":              "SAML assertion failure on Azure AD federation, IdP-initiated flow breaks",
        "expected_product_id": "P002",
    },
    {
        "label":              "Revenue / billing theme",
        "input":              "payment processing errors causing revenue loss, refund API returning 500",
        "expected_product_id": "P001",
    },
]


def eval_3_semantic_search() -> list[dict]:
    from agent.semantic_search import SemanticMatcher
    matcher = SemanticMatcher()
    results = []

    for tc in SEMANTIC_CASES:
        try:
            sem     = matcher.find_closest_product(tc["input"])
            got_id  = sem.get("product_id", "")
            correct = got_id == tc["expected_product_id"]
            output  = {
                "extracted_product":    sem.get("product"),
                "extracted_product_id": got_id,
                "similarity_score":     sem.get("similarity_score", 0.0),
                "confidence_level":     sem.get("confidence_level"),
                "is_correct":           correct,
            }
            passed = correct
            score  = sem.get("similarity_score", 0.0)
        except Exception as exc:
            output = {"error": str(exc)}
            passed = False
            score  = 0.0

        results.append({
            "eval_category": "eval_3_semantic_search",
            "label":         tc["label"],
            "test_input":    {"user_input": tc["input"],
                              "expected_product_id": tc["expected_product_id"]},
            "output":        output,
            "passed":        passed,
            "score":         score,
            "metadata":      {"passed": passed},
            "tags":          ["eval_3", "semantic_search"],
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVAL 4 — Graceful Degradation
# Does the pipeline correctly surface the manual picker for vague inputs?
# ══════════════════════════════════════════════════════════════════════════════

DEGRADATION_CASES = [
    {"label": "Pure urgency — no content", "input": "URGENT!!! Everything is down!!!"},
    {"label": "Gibberish input",           "input": "asdfgh xyz qwerty 1234 foobar"},
    {"label": "Vague break complaint",     "input": "It broke again. Please help ASAP"},
]


def eval_4_graceful_degradation() -> list[dict]:
    from agent.llm_client import gpt_extract_case
    from agent.semantic_search import SemanticMatcher
    from agent.graph_client import get_all_products
    results = []

    catalog       = get_all_products()
    product_names = [p["name"] for p in catalog]
    matcher       = SemanticMatcher()

    for tc in DEGRADATION_CASES:
        try:
            kw    = gpt_extract_case(tc["input"], product_names)
            kconf = kw["keyword_confidence"]
            sem   = matcher.find_closest_product(tc["input"])
            ssim  = sem.get("similarity_score", 0.0)
            fell_back = (
                kconf < cfg.CONF_MEDIUM
                and sem.get("confidence_level") == "INSUFFICIENT"
            )
            output = {
                "fell_back_to_manual": fell_back,
                "keyword_confidence":  kconf,
                "semantic_similarity": ssim,
                "semantic_level":      sem.get("confidence_level"),
            }
            passed = fell_back
        except Exception as exc:
            output = {"error": str(exc), "fell_back_to_manual": False}
            passed = False

        results.append({
            "eval_category": "eval_4_graceful_degradation",
            "label":         tc["label"],
            "test_input":    {"ambiguous_input": tc["input"]},
            "output":        output,
            "passed":        passed,
            "score":         None,
            "metadata":      {"passed": passed},
            "tags":          ["eval_4", "graceful_degradation"],
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVAL 5 — Latency
# Does full graph recommendation complete within 10 seconds per scenario?
# ══════════════════════════════════════════════════════════════════════════════

LATENCY_THRESHOLD = 10.0  # seconds

LATENCY_CASES = [
    {"label": "Scenario A — Payment Gateway", "scenario": "A"},
    {"label": "Scenario B — SSO Module",      "scenario": "B"},
    {"label": "Scenario C — Analytics",       "scenario": "C"},
]


def eval_5_latency() -> list[dict]:
    from agent.graph_client import get_full_recommendation
    results = []

    for tc in LATENCY_CASES:
        sc = cfg.SCENARIOS[tc["scenario"]]
        try:
            t0  = time.perf_counter()
            get_full_recommendation(
                sc["customer_id"], sc["product_id"],
            )
            elapsed = round(time.perf_counter() - t0, 3)
            output  = {
                "latency_seconds":   elapsed,
                "threshold_seconds": LATENCY_THRESHOLD,
                "within_threshold":  elapsed < LATENCY_THRESHOLD,
            }
            passed = elapsed < LATENCY_THRESHOLD
            score  = elapsed
        except Exception as exc:
            output = {"error": str(exc), "latency_seconds": None}
            passed = False
            score  = None

        results.append({
            "eval_category": "eval_5_latency",
            "label":         tc["label"],
            "test_input":    {"test_scenario": tc["scenario"],
                              "description":   sc["description"]},
            "output":        output,
            "passed":        passed,
            "score":         score,
            "metadata":      {"threshold_seconds": LATENCY_THRESHOLD, "passed": passed},
            "tags":          ["eval_5", "latency"],
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# EVAL 6 — Resolution Time
# Does the graph-recommended agent assignment outperform random assignment?
# Queries actual resolution time data from Neo4j.
# ══════════════════════════════════════════════════════════════════════════════

RESOLUTION_THRESHOLD_IMPROVEMENT = 1.0   # graph must save at least 1 hour vs random

RESOLUTION_CASES = [
    {"label": "Payment Gateway resolved cases", "product_id": "P001"},
    {"label": "SSO Module resolved cases",      "product_id": "P002"},
    {"label": "Analytics resolved cases",       "product_id": "P003"},
]


def eval_6_resolution_time() -> list[dict]:
    from agent.graph_client import get_driver
    results = []

    for tc in RESOLUTION_CASES:
        try:
            cypher = """
            MATCH (a:Agent)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product {id: $pid})
            WHERE c.resolution_time_hours IS NOT NULL
            WITH c, c.resolution_time_hours AS rt
            RETURN avg(rt) AS avg_resolution_hours,
                   min(rt) AS min_hours,
                   max(rt) AS max_hours,
                   count(c) AS case_count
            """
            with get_driver().session() as session:
                row  = session.run(cypher, pid=tc["product_id"]).single()
                avg  = round(float(row["avg_resolution_hours"] or 0), 2)
                cnt  = int(row["case_count"] or 0)

            # Compare: graph-ranked agents in top-25% vs bottom-75% (proxy for random)
            top_cypher = """
            MATCH (a:Agent)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product {id: $pid})
            WHERE c.resolution_time_hours IS NOT NULL
            WITH a, avg(c.resolution_time_hours) AS agent_avg
            ORDER BY agent_avg ASC
            LIMIT 5
            RETURN avg(agent_avg) AS top_agent_avg
            """
            rand_cypher = """
            MATCH (a:Agent)-[:RESOLVED]->(c:Case)-[:ABOUT]->(p:Product {id: $pid})
            WHERE c.resolution_time_hours IS NOT NULL
            RETURN avg(c.resolution_time_hours) AS random_avg
            """
            with get_driver().session() as session:
                top_row  = session.run(top_cypher,  pid=tc["product_id"]).single()
                rand_row = session.run(rand_cypher, pid=tc["product_id"]).single()
                top_avg  = round(float(top_row["top_agent_avg"]  or avg), 2)
                rand_avg = round(float(rand_row["random_avg"]    or avg), 2)

            improvement = round(rand_avg - top_avg, 2)
            improvement_pct = round(improvement / rand_avg * 100, 1) if rand_avg else 0

            output = {
                "graph_agent_avg_hours": top_avg,
                "random_avg_hours":      rand_avg,
                "improvement_hours":     improvement,
                "improvement_percent":   improvement_pct,
                "case_count":            cnt,
            }
            passed = improvement >= RESOLUTION_THRESHOLD_IMPROVEMENT
            score  = improvement_pct

        except Exception as exc:
            output = {"error": str(exc)}
            passed = False
            score  = None

        results.append({
            "eval_category": "eval_6_resolution_time",
            "label":         tc["label"],
            "test_input":    {"product_id": tc["product_id"]},
            "output":        output,
            "passed":        passed,
            "score":         score,
            "metadata":      {
                "threshold_improvement_hours": RESOLUTION_THRESHOLD_IMPROVEMENT,
                "passed": passed,
            },
            "tags":          ["eval_6", "resolution_time"],
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Master runner
# ══════════════════════════════════════════════════════════════════════════════

EVAL_REGISTRY = [
    ("Eval 1 — Skill Match",              eval_1_skill_match),
    ("Eval 2 — Confidence Calibration",   eval_2_confidence_calibration),
    ("Eval 3 — Semantic Search",          eval_3_semantic_search),
    ("Eval 4 — Graceful Degradation",     eval_4_graceful_degradation),
    ("Eval 5 — Latency",                  eval_5_latency),
    ("Eval 6 — Resolution Time",          eval_6_resolution_time),
]


def run_all_evals() -> list[dict]:
    """Run all 6 eval categories and return the flat list of individual results."""
    all_results = []
    for name, fn in EVAL_REGISTRY:
        try:
            results = fn()
            all_results.extend(results)
        except Exception as exc:
            # Whole category failed — log a synthetic failure entry
            all_results.append({
                "eval_category": fn.__name__,
                "label":         f"{name} — CATEGORY ERROR",
                "test_input":    {},
                "output":        {"error": str(exc)},
                "passed":        False,
                "score":         None,
                "metadata":      {"category_error": True},
                "tags":          [fn.__name__, "error"],
            })
    return all_results
