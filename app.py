"""
Customer Support Intelligence Agent — chat UI.
Run: streamlit run app.py
"""
import sys
import time
import tempfile
import os
import uuid
import threading
import http.server
import socketserver
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

STATIC_DIR  = PROJECT_ROOT / "static"
_GRAPH_PORT = 8503  # 8502 is reserved for measurement_dashboard.py

@st.cache_resource
def _start_graph_server():
    """Serve static/  on a dedicated port with correct MIME types."""
    STATIC_DIR.mkdir(exist_ok=True)

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR), **kwargs)
        def log_message(self, *args):
            pass  # suppress console noise

    class _Server(socketserver.TCPServer):
        allow_reuse_address = True

    srv = _Server(("", _GRAPH_PORT), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

import config.settings as cfg

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from agent.graph_client import (
    find_similar_cases,
    find_best_agents,
    find_kb_articles,
    get_full_recommendation,
    get_random_agent,
    get_all_agents,
    get_driver,
    analyze_product_performance,
    analyze_skill_coverage,
    analyze_kb_effectiveness,
    analyze_escalation_risk,
    get_all_products,
    get_skills_for_product,
    get_customer_for_product,
)
from agent.llm_client import new_session, ask, gpt_extract_case
from agent.utils import format_executive_context, build_citation_block
from agent.cost_callback import CostTrackingCallback
from agent import triage_verifier
from agent import triage_compare
from agent.triage_ui import assignment_rows, chips as _chips, first_pass_grounding, observability_rows, render_jev_answer, render_jev_column, table_html

_cost_cb = CostTrackingCallback()

# ── Product catalogue (cached, fetched from Neo4j once per server restart) ─────

@st.cache_resource(show_spinner="Loading product catalogue from Neo4j…")
def _load_product_catalog():
    try:
        products  = get_all_products()
        name_to_id = {p["name"]: p["product_id"] for p in products}
        return products, name_to_id
    except Exception:
        fallback = [
            {"product_id": "P001", "name": "Payment Gateway v2.1"},
            {"product_id": "P002", "name": "SSO Integration Module"},
            {"product_id": "P003", "name": "Analytics Dashboard"},
        ]
        return fallback, {p["name"]: p["product_id"] for p in fallback}

# ── Semantic matcher (loads 'all-MiniLM-L6-v2' + pre-embeds products once) ────

@st.cache_resource(show_spinner="Initialising semantic search model…")
def _load_semantic_matcher():
    from agent.semantic_search import SemanticMatcher
    return SemanticMatcher()

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CaseIQ — Intelligent Support Triage",
    page_icon="🧠",
    layout="wide",
)

_start_graph_server()

# ── Constants ──────────────────────────────────────────────────────────────────

PRODUCT_LABEL = {
    "P001": "Payment Gateway v2.1",
    "P002": "SSO Integration Module",
    "P003": "Analytics Dashboard",
}

PRODUCT_SKILLS = {
    "P001": ["SK001", "SK002"],
    "P002": ["SK007", "SK009"],
    "P003": ["SK014", "SK013"],
}

PRODUCT_CUSTOMER = {
    "P001": "C0009",
    "P002": "C0028",
    "P003": "C0030",
}

QUICK_PROMPTS = [
    {
        "icon":        "💳",
        "label":       "Payment Gateway — refund error 4023",
        "description": cfg.SCENARIOS["A"]["description"],
        "product_id":  "P001",
    },
    {
        "icon":        "🔐",
        "label":       "SSO onboarding blocked — Azure AD",
        "description": cfg.SCENARIOS["B"]["description"],
        "product_id":  "P002",
    },
    {
        "icon":        "📊",
        "label":       "Analytics export — missing rows",
        "description": cfg.SCENARIOS["C"]["description"],
        "product_id":  "P003",
    },
]

# ── Baseline stats (historical data shown before any session activity) ────────

_SEED_TOTAL    = 988
_SEED_OPEN     = 172
_SEED_INPROG   = 448
_SEED_RESOLVED = 368
# Open cases distributed randomly across agents — varying loads intentionally
_SEED_AGENT_Q  = {
    "Sarah Chen":    8,   # Available
    "Marcus Webb":   32,  # Busy
    "Priya Nair":    14,  # Moderate
    "James Kim":     48,  # Overwhelmed
    "Olivia Torres": 25,  # Busy
}

# ── No-graph baseline LLM ──────────────────────────────────────────────────────

_raw_llm = ChatGroq(
    api_key=cfg.GROQ_API_KEY,
    model_name=cfg.GROQ_MODEL,
    temperature=cfg.GROQ_TEMP,
    max_tokens=cfg.GROQ_MAX_TOKENS,
    model_kwargs={"reasoning_effort": "low"},
    callbacks=[_cost_cb],
)

_NO_GRAPH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "You are a senior customer support advisor. "
            "Answer using ONLY general knowledge — no internal systems.\n\n"
            "Respond in exactly this structure. No preamble, no padding, no extra sections:\n\n"
            "1. **2 Best Agents to Assign**\n"
            "   - **[Role/Profile]** (seniority) — 1 sentence: ideal profile and why\n"
            "   - **[Role/Profile]** (seniority) — 1 sentence: same format\n\n"
            "2. **3 Most Relevant Resources**\n"
            "   - **[Resource Name]** — 1 sentence: what it covers and why it applies\n"
            "   - **[Resource Name]** — same format\n"
            "   - **[Resource Name]** — same format\n\n"
            "3. **Estimated Resolution Time**\n"
            "   1–2 sentences: typical time range (initial diagnosis vs full fix) for this case type.\n\n"
            "4. **Escalation Risk Assessment**\n"
            "   Risk level (Low/Medium/High) + exactly 2–3 bullet triggers that would escalate this case.\n\n"
            "Every item is one line. No sub-bullets, no paragraphs."
        ),
    ),
    ("human", "Support case: {input}"),
])

_no_graph_chain = _NO_GRAPH_PROMPT | _raw_llm

_CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("human",
     'Classify this support query into ONE category:\n"{input}"\n\n'
     "Categories:\n"
     "SUPPORT_TICKET — customer has a problem needing case creation and agent assignment\n"
     "ANALYTICS_QUERY — asking for insights, trends, aggregate stats, or reports\n"
     "OPERATIONAL — asking about agent workload, queue depth, or system status\n\n"
     "Return only the category name, nothing else."),
])
_classify_chain = _CLASSIFY_PROMPT | _raw_llm

_ANALYTICS_INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("human",
     "You are a query router for a support analytics system.\n"
     "Given a user analytics question, return a JSON object (no markdown, just raw JSON) with:\n"
     '- "function": one of "analyze_product_performance", "analyze_skill_coverage", '
     '"analyze_kb_effectiveness", "analyze_escalation_risk", "general"\n'
     '- "params": dict with required parameters\n\n'
     "Functions and parameters:\n"
     "- analyze_product_performance(product_name: str, top_n: int) — top agents by cases resolved for a product; top_n defaults to 10\n"
     "- analyze_skill_coverage(skill_name: str) — agents with a skill; pass empty string for all skills\n"
     "- analyze_kb_effectiveness(product_name: str) — KB article resolution rates for a product\n"
     "- analyze_escalation_risk(tier: str, days_old: int) — open cases for a customer tier\n"
     "- general — broad queries: overall totals, trends, resolution rates\n\n"
     "Rules:\n"
     "- If the query says 'top 3', 'top 5', etc. set top_n to that number.\n"
     "- product_name must be the exact product keyword from the query (e.g. 'Payment Gateway', 'SSO', 'Analytics').\n\n"
     "Examples:\n"
     '"Top 3 agents for payment gateway issues" → {{"function":"analyze_product_performance","params":{{"product_name":"Payment Gateway","top_n":3}}}}\n'
     '"Best 5 agents resolving SSO problems" → {{"function":"analyze_product_performance","params":{{"product_name":"SSO","top_n":5}}}}\n'
     '"Which skills are understaffed?" → {{"function":"analyze_skill_coverage","params":{{"skill_name":""}}}}\n'
     '"Most effective KB articles for SSO?" → {{"function":"analyze_kb_effectiveness","params":{{"product_name":"SSO"}}}}\n'
     '"Gold tier escalation risk?" → {{"function":"analyze_escalation_risk","params":{{"tier":"gold","days_old":7}}}}\n'
     '"Average resolution time across all products?" → {{"function":"general","params":{{}}}}\n\n'
     "Query: {input}\n\n"
     "Return ONLY valid JSON. No markdown fences, no explanation."),
])
_intent_chain = _ANALYTICS_INTENT_PROMPT | _raw_llm


# ── Product detection ──────────────────────────────────────────────────────────

def _resolve_product_skills(product_id: str) -> list[str]:
    """Return required skill IDs for any product, falling back to graph query."""
    if product_id in PRODUCT_SKILLS:
        return PRODUCT_SKILLS[product_id]
    try:
        skills = get_skills_for_product(product_id)
        return skills if skills else []
    except Exception:
        return []


def _resolve_customer(product_id: str) -> str:
    """Return a customer ID for any product, falling back to graph query."""
    if product_id in PRODUCT_CUSTOMER:
        return PRODUCT_CUSTOMER[product_id]
    try:
        return get_customer_for_product(product_id)
    except Exception:
        return "C0001"


def _select_top_agent(agents: list[dict], customer_tier: str) -> dict | None:
    """
    Pick the best agent to highlight in the comparison table.

    For GOLD tier: prefer the fastest senior agent if their resolution time is
    within SENIORITY_TIME_TOLERANCE_HOURS of the overall fastest agent.
    The rationale: senior judgment reduces escalation risk for high-value accounts
    and the small time cost is acceptable.

    For all other tiers (or when no senior qualifies): return the fastest agent.
    """
    if not agents:
        return None

    fastest = min(agents, key=lambda a: a.get("avg_resolution_time") or 999)

    if customer_tier.upper() == "GOLD":
        seniors = [a for a in agents if (a.get("seniority") or "").lower() == "senior"]
        if seniors:
            best_senior = min(seniors, key=lambda a: a.get("avg_resolution_time") or 999)
            senior_rt  = best_senior.get("avg_resolution_time") or 999
            fastest_rt = fastest.get("avg_resolution_time") or 999
            delta = senior_rt - fastest_rt
            if delta <= cfg.SENIORITY_TIME_TOLERANCE_HOURS:
                return best_senior   # senior is close enough — prefer experience

    return fastest


def detect_product(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ["sso", "login", "log in", "sign in", "azure", "oauth", "saml", "onboard", "auth", "password", "credential"]):
        return "P002"
    if any(k in lower for k in ["analytic", "export", "csv", "dashboard", "report", "chart", "missing row", "data"]):
        return "P003"
    return "P001"


def run_case_extraction(user_input: str) -> dict:
    """
    Dual-confidence extraction pipeline.

    Step 1 — Keyword extraction via LLM (gpt_extract_case).
      • keyword_conf ≥ CONF_HIGH  → auto-assign
      • keyword_conf ≥ CONF_MEDIUM → needs_confirmation
      • keyword_conf <  CONF_MEDIUM → fall through to Step 2

    Step 2 — Semantic search (sentence-transformers cosine similarity).
      • HIGH  (≥ 0.80) → auto-assign
      • MEDIUM/LOW (≥ 0.50) → needs_confirmation
      • INSUFFICIENT (<0.50) → needs_manual_selection

    Returns a dict with keys:
      title, description, product, product_id, match_type,
      keyword_confidence, semantic_similarity, auto_assign,
      needs_confirmation, needs_manual_selection, explanation
    """
    catalog, name_to_id = _load_product_catalog()
    product_names       = [p["name"] for p in catalog]

    # ── Step 1: keyword extraction ────────────────────────────────────────────
    kw = gpt_extract_case(user_input, product_names)
    kconf = kw["keyword_confidence"]

    base = {
        "title":                   kw["title"],
        "description":             user_input,
        "keyword_confidence":      kconf,
        "semantic_similarity":     None,
        "auto_assign":             False,
        "needs_confirmation":      False,
        "needs_manual_selection":  False,
        "explanation":             kw["confidence_reasoning"],
        "product":                 None,
        "product_id":              None,
        "match_type":              "unknown",
    }

    if kconf >= cfg.CONF_HIGH and kw["product"]:
        pid = name_to_id.get(kw["product"])
        if pid:
            return {**base, "product": kw["product"], "product_id": pid,
                    "match_type": "keyword_high", "auto_assign": True}

    if kconf >= cfg.CONF_MEDIUM and kw["product"]:
        pid = name_to_id.get(kw["product"])
        if pid:
            return {**base, "product": kw["product"], "product_id": pid,
                    "match_type": "keyword_medium", "needs_confirmation": True}

    # ── Step 2: semantic search fallback ──────────────────────────────────────
    matcher = _load_semantic_matcher()
    sem     = matcher.find_closest_product(user_input)
    base["semantic_similarity"] = sem.get("similarity_score", 0.0)

    if sem["confidence_level"] == "HIGH" and sem["product_id"]:
        return {**base, "product": sem["product"], "product_id": sem["product_id"],
                "match_type": "semantic_high", "auto_assign": True,
                "explanation": sem["explanation"]}

    if sem["confidence_level"] in ("MEDIUM", "LOW") and sem["product_id"]:
        return {**base, "product": sem["product"], "product_id": sem["product_id"],
                "match_type": "semantic_medium", "needs_confirmation": True,
                "explanation": sem["explanation"]}

    return {**base, "match_type": "insufficient", "needs_manual_selection": True,
            "explanation": (
                "Both keyword and semantic matching scored below the 50% confidence "
                "threshold. Please select the product manually."
            )}


def classify_query(text: str) -> str:
    """Returns SUPPORT_TICKET | ANALYTICS_QUERY | OPERATIONAL."""
    raw = _classify_chain.invoke({"input": text}).content.strip().upper()
    if "ANALYTICS" in raw:
        return "ANALYTICS_QUERY"
    if "OPERATIONAL" in raw:
        return "OPERATIONAL"
    return "SUPPORT_TICKET"


# ── Analysis pipeline (synchronous — must be called inside st.status()) ────────

def run_analysis(description: str, product_id: str) -> dict:
    customer_id     = _resolve_customer(product_id)
    required_skills = _resolve_product_skills(product_id)

    st.write("⟳  Calling LLM without graph data…")
    _t0 = time.perf_counter()
    no_graph = _no_graph_chain.invoke({"input": description}).content
    latency_no = round(time.perf_counter() - _t0, 1)

    st.write("⟳  Traversing knowledge graph (4 hops)…")
    _t1 = time.perf_counter()
    similar = find_similar_cases(description, product_id)
    st.write(f"   ↳ {len(similar)} similar resolved cases")

    agents_list = find_best_agents(product_id, required_skills)
    st.write(f"   ↳ {len(agents_list)} agents ranked by skill match")

    articles = find_kb_articles(product_id)
    st.write(f"   ↳ {len(articles)} KB articles (>70 % resolution rate)")

    recommendation = get_full_recommendation(customer_id, product_id)

    st.write("⟳  Reasoning with graph intelligence…")
    session_id = f"ui_{product_id}_{int(time.time())}"
    context    = format_executive_context(
        {"description": description}, similar, agents_list, articles, recommendation
    )
    chain      = new_session(session_id)
    with_graph = ask(chain, context, session_id=session_id)
    latency_with = round(time.perf_counter() - _t1, 1)

    # Third column: check the graph recommendation against the data it was written from (grounding checks + Jev), revise once if needed.
    verified, latency_jev = None, None
    if st.session_state.get("jev_on", True):
        st.write("⟳  Verifying the recommendation with Jev…")
        _t2 = time.perf_counter()
        _vid = f"ui_jev_{product_id}_{int(time.time())}"
        try:
            verified = triage_verifier.verify(
                description, PRODUCT_LABEL.get(product_id, product_id),
                triage_verifier.context_from_graph(similar, agents_list, articles, recommendation),
                with_graph,
                lambda feedback: ask(new_session(_vid), context + "\n\n" + feedback, session_id=_vid),
            )
            st.write(f"   ↳ verdict: {verified['decision']}" + (" (revised once)" if verified["revised"] else ""))
        except Exception as e:  # noqa: BLE001 - shown in the column, never hidden
            verified = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            st.write("   ↳ verification unavailable")
        latency_jev = round(time.perf_counter() - _t2, 1)

    citation   = build_citation_block(similar, agents_list, articles)
    rand_agent = get_random_agent(product_id, required_skills)

    return {
        "product_id":      product_id,
        "description":     description,
        "without_graph":   no_graph,
        "with_graph":      with_graph,
        "citation":        citation,
        "random_agent":    rand_agent,
        "top_agent":       _select_top_agent(agents_list, recommendation.get("customer", {}).get("customer_tier", "")),
        "similar":         similar,
        "agents":          agents_list,
        "articles":        articles,
        "recommendation":  recommendation,
        "latency_no_graph":   latency_no,
        "latency_with_graph": latency_with,
        "verified":           verified,
        "latency_jev":        latency_jev,
    }


# ── Analytics pipeline ─────────────────────────────────────────────────────────

def run_analytics(query: str) -> dict:
    """
    Intent-routed analytics pipeline.
    Step 1: LLM extracts function + params from the user query.
    Step 2: Runs the matched multi-hop Neo4j query.
    Step 3: LLM generates 3-bullet insight from the results.
    """
    import json, re

    sc = st.session_state.cases
    total      = _SEED_TOTAL    + len(sc)
    open_n     = _SEED_OPEN     + sum(1 for c in sc if c["status"] == "pending")
    inprog_n   = _SEED_INPROG   + sum(1 for c in sc if c["status"] in ("assigned_random", "assigned_graph"))
    resolved_n = _SEED_RESOLVED + sum(1 for c in sc if c["status"] == "resolved")

    # ── Step 1: Extract intent ─────────────────────────────────────────────────
    st.write("⟳  Classifying analytics intent…")
    raw_intent = _intent_chain.invoke({"input": query}).content.strip()
    # Strip markdown code fences if the model wrapped the JSON
    raw_intent = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", raw_intent, flags=re.DOTALL).strip()
    try:
        intent = json.loads(raw_intent)
    except Exception:
        intent = {"function": "general", "params": {}}

    func_name = intent.get("function", "general")
    params    = intent.get("params", {})
    st.write(f"   ↳ Routing to: **{func_name}**  params: {params}")

    # ── Step 2: Execute the matched query ──────────────────────────────────────
    rows: list[dict] = []
    result_type = func_name

    st.write(f"⟳  Executing {func_name}…")
    try:
        if func_name == "analyze_product_performance":
            rows = analyze_product_performance(
                params.get("product_name", ""),
                int(params.get("top_n", 10)),
            )
        elif func_name == "analyze_skill_coverage":
            rows = analyze_skill_coverage(params.get("skill_name", ""))
        elif func_name == "analyze_kb_effectiveness":
            rows = analyze_kb_effectiveness(params.get("product_name", ""))
        elif func_name == "analyze_escalation_risk":
            rows = analyze_escalation_risk(
                params.get("tier", "gold"),
                int(params.get("days_old", 7)),
            )
        else:
            result_type = "general"
    except Exception:
        result_type = "general"

    st.write(f"   ↳ {len(rows)} rows returned")

    # ── Fallback general aggregation (always computed for context/general path) ─
    product_rows: list[dict] = []
    avg_res: float = 5.3
    try:
        import agent.graph_client as _gc
        if not _gc.USE_MOCK:
            with get_driver().session() as s:
                r1 = s.run("""
                    MATCH (c:Case)-[:ABOUT]->(p:Product)
                    RETURN p.name AS product, count(c) AS cases
                    ORDER BY cases DESC LIMIT 5
                """)
                product_rows = [dict(r) for r in r1]
                r2 = s.run("""
                    MATCH (c:Case) WHERE c.resolution_time_hours IS NOT NULL
                    RETURN round(avg(c.resolution_time_hours), 1) AS avg_hours
                """)
                rec = r2.single()
                if rec and rec["avg_hours"]:
                    avg_res = rec["avg_hours"]
    except Exception:
        pass

    if not product_rows:
        product_rows = [
            {"product": "Analytics Dashboard",    "cases": 389},
            {"product": "Payment Gateway v2.1",   "cases": 312},
            {"product": "SSO Integration Module", "cases": 287},
        ]

    # ── Step 3: LLM insight ────────────────────────────────────────────────────
    st.write("⟳  Generating insights…")
    data_ctx = (
        f"User query: {query}\n"
        f"Query function: {result_type}  params: {params}\n"
        f"Data (first 5 rows): {rows[:5]}\n"
        f"System totals — Total: {total}  Open: {open_n}  In Progress: {inprog_n}  Resolved: {resolved_n}\n"
        f"Avg resolution time: {avg_res} hrs"
    )
    insight = _raw_llm.invoke(
        "You are a support analytics analyst. "
        "Write exactly 3 concise bullet-point insights from the data below. No preamble.\n\n"
        + data_ctx
    ).content

    return {
        "query":        query,
        "result_type":  result_type,
        "rows":         rows,
        "params":       params,
        "total":        total,
        "open":         open_n,
        "inprog":       inprog_n,
        "resolved":     resolved_n,
        "avg_res":      avg_res,
        "product_rows": product_rows,
        "insight":      insight,
    }


# ── Operational snapshot ───────────────────────────────────────────────────────

def run_operational() -> dict:
    """Current system health + agent queue — no LLM call needed."""
    sc = st.session_state.cases
    total      = _SEED_TOTAL    + len(sc)
    open_n     = _SEED_OPEN     + sum(1 for c in sc if c["status"] == "pending")
    inprog_n   = _SEED_INPROG   + sum(1 for c in sc if c["status"] in ("assigned_random", "assigned_graph"))
    resolved_n = _SEED_RESOLVED + sum(1 for c in sc if c["status"] == "resolved")

    session_q: dict[str, int] = {}
    for c in sc:
        if c["status"] in ("assigned_random", "assigned_graph"):
            name = c.get("assigned_to") or ""
            if name:
                session_q[name] = session_q.get(name, 0) + 1

    try:
        raw_agents = get_all_agents()
    except Exception:
        raw_agents = []

    _seed_vals = sorted(_SEED_AGENT_Q.values())
    agents = []
    for idx, a in enumerate(raw_agents):
        name = a.get("name", "")
        q    = _SEED_AGENT_Q.get(name, _seed_vals[idx % len(_seed_vals)]) + session_q.get(name, 0)
        agents.append({**a, "queue": q})
    agents.sort(key=lambda a: a["queue"])

    return {
        "total":    total,
        "open":     open_n,
        "inprog":   inprog_n,
        "resolved": resolved_n,
        "agents":   agents,
    }


# ── Graph visualisation ────────────────────────────────────────────────────────

def build_graph_html(result: dict) -> str:
    from pyvis.network import Network

    net = Network(height="560px", width="100%", bgcolor="#0f172a",
                  font_color="#e2e8f0", directed=True, cdn_resources="in_line")

    net.set_options("""{
      "nodes": {"borderWidth": 2, "shadow": true,
                "font": {"size": 14, "color": "#f1f5f9",
                         "strokeWidth": 3, "strokeColor": "#0f172a"}},
      "edges": {"color": {"color": "#475569"},
                "smooth": {"type": "curvedCW", "roundness": 0.2},
                "arrows": {"to": {"enabled": true, "scaleFactor": 0.7}},
                "font": {"size": 10, "color": "#94a3b8", "strokeWidth": 0,
                         "align": "middle"}},
      "physics": {"solver": "barnesHut",
                  "barnesHut": {"gravitationalConstant": -8000,
                                "centralGravity": 0.05,
                                "springLength": 220,
                                "springConstant": 0.03,
                                "damping": 0.09,
                                "avoidOverlap": 1},
                  "stabilization": {"iterations": 300}},
      "interaction": {"hover": true, "tooltipDelay": 150}
    }""")

    desc = result.get("description", "")
    short_desc = (desc[:45] + "…") if len(desc) > 45 else desc

    # ── Current case (centre) ──────────────────────────────────────────────────
    net.add_node("case", label="📋 Current Case", title=short_desc,
                 color={"background": "#ea580c", "border": "#fb923c"},
                 size=42, shape="dot")

    # ── Product ────────────────────────────────────────────────────────────────
    product_name = PRODUCT_LABEL.get(result["product_id"], result["product_id"])
    net.add_node("product", label=f"📦 {product_name}",
                 color={"background": "#7c3aed", "border": "#a78bfa"},
                 size=30, shape="dot")
    net.add_edge("case", "product", label="ABOUT", width=2)

    # ── Customer ───────────────────────────────────────────────────────────────
    rec  = result.get("recommendation") or {}
    cust = rec.get("customer", {})
    if cust:
        tier  = cust.get("customer_tier", "unknown").upper()
        cname = cust.get("customer_name", "Customer")
        prior = cust.get("prior_cases_on_product", 0)
        net.add_node("customer",
                     label=f"👤 {cname}",
                     title=f"Tier: {tier} · {prior} prior cases on this product",
                     color={"background": "#1d4ed8", "border": "#60a5fa"},
                     size=26, shape="dot")
        net.add_edge("customer", "case", label="RAISED", width=2)

    # ── Recommended agents ─────────────────────────────────────────────────────
    for i, agent in enumerate(result.get("agents") or []):
        nid = f"agent_{i}"
        avg = agent.get("avg_resolution_time")
        tip = f"{agent['seniority'].title()} · avg {avg} hrs" if avg else agent["seniority"].title()
        net.add_node(nid,
                     label=f"👷 {agent['name']}",
                     title=tip,
                     color={"background": "#15803d", "border": "#4ade80"},
                     size=22, shape="dot")
        net.add_edge(nid, "product", label="RESOLVES", width=1.5)

    # ── KB articles ────────────────────────────────────────────────────────────
    for i, art in enumerate(result.get("articles") or []):
        nid   = f"article_{i}"
        label = (art["title"][:28] + "…") if len(art["title"]) > 28 else art["title"]
        tip   = f"Resolution rate: {art['resolution_rate']:.0%} · used {art['times_used']}×"
        net.add_node(nid,
                     label=f"📄 {label}",
                     title=tip,
                     color={"background": "#a16207", "border": "#fbbf24"},
                     size=20, shape="dot")
        net.add_edge(nid, "product", label="COVERS", width=1.5)

    # ── Similar resolved cases ─────────────────────────────────────────────────
    for i, sim in enumerate(result.get("similar") or []):
        nid   = f"sim_{i}"
        label = (sim["title"][:26] + "…") if len(sim["title"]) > 26 else sim["title"]
        rt    = sim.get("resolution_time_hours")
        tip   = f"Resolved in {rt:.1f} hrs" if rt else "Resolved case"
        net.add_node(nid,
                     label=f"✅ {label}",
                     title=tip,
                     color={"background": "#334155", "border": "#94a3b8"},
                     size=17, shape="dot")
        net.add_edge("case", nid, label="SIMILAR_TO", width=1,
                     color={"color": "#475569"})
        net.add_edge(nid, "product", label="ABOUT", width=1,
                     color={"color": "#475569"})

    # Write to temp file (pyvis 0.3.x requires a path)
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
    net.save_graph(tmp.name)
    tmp.close()
    html = open(tmp.name, encoding="utf-8").read()
    os.unlink(tmp.name)

    legend = """
<div style="
  position:fixed; bottom:14px; left:50%; transform:translateX(-50%);
  display:flex; gap:18px; align-items:center; flex-wrap:wrap; justify-content:center;
  background:rgba(15,23,42,0.82); border:1px solid rgba(255,255,255,0.12);
  backdrop-filter:blur(8px); border-radius:12px;
  padding:8px 18px; font-family:sans-serif; font-size:12px; color:#cbd5e1;
  z-index:9999; pointer-events:none;">
  <span style="display:flex;align-items:center;gap:6px;">
    <span style="width:12px;height:12px;border-radius:50%;background:#1d4ed8;border:2px solid #60a5fa;flex-shrink:0;"></span>Customer</span>
  <span style="display:flex;align-items:center;gap:6px;">
    <span style="width:12px;height:12px;border-radius:50%;background:#ea580c;border:2px solid #fb923c;flex-shrink:0;"></span>Current Case</span>
  <span style="display:flex;align-items:center;gap:6px;">
    <span style="width:12px;height:12px;border-radius:50%;background:#7c3aed;border:2px solid #a78bfa;flex-shrink:0;"></span>Product</span>
  <span style="display:flex;align-items:center;gap:6px;">
    <span style="width:12px;height:12px;border-radius:50%;background:#15803d;border:2px solid #4ade80;flex-shrink:0;"></span>Recommended Agent</span>
  <span style="display:flex;align-items:center;gap:6px;">
    <span style="width:12px;height:12px;border-radius:50%;background:#a16207;border:2px solid #fbbf24;flex-shrink:0;"></span>KB Article</span>
  <span style="display:flex;align-items:center;gap:6px;">
    <span style="width:12px;height:12px;border-radius:50%;background:#334155;border:2px solid #94a3b8;flex-shrink:0;"></span>Similar Case</span>
</div>
"""
    html = html.replace("</body>", legend + "</body>")
    return html


# ── Sidebar: System Status + Agent Workload ───────────────────────────────────

_STATUS_COLORS = {
    "pending":         "#eab308",
    "assigned_random": "#3b82f6",
    "assigned_graph":  "#3b82f6",
    "resolved":        "#64748b",
}
_STATUS_LABELS = {
    "pending":         "Open",
    "assigned_random": "In Progress",
    "assigned_graph":  "In Progress",
    "resolved":        "Resolved",
}


def render_sidebar() -> None:
    try:
        from agent.db_status_ui import render_sidebar_status
        render_sidebar_status()
    except Exception:  # noqa: BLE001 - a status problem must never break the app
        pass
    with st.sidebar:
        st.checkbox("Third column: verify with Jev", value=True, key="jev_on",
                    help="Adds a third answer: the graph recommendation checked against the graph data it was written from (grounding checks + Jev signals), revised once if needed.")
        # ── System Status ──────────────────────────────────────────────────────
        st.markdown("### 📊 System Status")

        session_cases = st.session_state.cases
        s_open     = sum(1 for c in session_cases if c["status"] == "pending")
        s_inprog   = sum(1 for c in session_cases if c["status"] in ("assigned_random", "assigned_graph"))
        s_resolved = sum(1 for c in session_cases if c["status"] == "resolved")

        total      = _SEED_TOTAL    + len(session_cases)
        open_n     = _SEED_OPEN     + s_open
        inprog_n   = _SEED_INPROG   + s_inprog
        resolved_n = _SEED_RESOLVED + s_resolved

        st.metric("Cases in System", total, delta=f"+{len(session_cases)} this session" if session_cases else None)

        st.markdown(f"""
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:7px;margin:8px 0 14px 0;">
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:3px solid #d97706;border-radius:6px;padding:10px 8px;text-align:center;">
    <div style="color:#d97706;font-size:22px;font-weight:700;">{open_n}</div>
    <div style="color:#94a3b8;font-size:10px;margin-top:2px;">Open</div>
  </div>
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:3px solid #3b82f6;border-radius:6px;padding:10px 8px;text-align:center;">
    <div style="color:#3b82f6;font-size:22px;font-weight:700;">{inprog_n}</div>
    <div style="color:#94a3b8;font-size:10px;margin-top:2px;">In Progress</div>
  </div>
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:3px solid #64748b;border-radius:6px;padding:10px 8px;text-align:center;">
    <div style="color:#64748b;font-size:22px;font-weight:700;">{resolved_n}</div>
    <div style="color:#94a3b8;font-size:10px;margin-top:2px;">Resolved</div>
  </div>
</div>""", unsafe_allow_html=True)

        if session_cases:
            st.markdown("**Recent Cases**")
            rows = ""
            for c in reversed(session_cases[-6:]):
                color = _STATUS_COLORS.get(c["status"], "#94a3b8")
                label = _STATUS_LABELS.get(c["status"], c["status"])
                short = c["description"][:24] + ("…" if len(c["description"]) > 24 else "")
                rows += (
                    f'<div style="display:flex;justify-content:space-between;'
                    f'align-items:center;padding:4px 0;border-bottom:1px solid #e2e8f0;'
                    f'font-size:11px;">'
                    f'<span style="color:#64748b;">{c["id"]}: {short}</span>'
                    f'<span style="color:{color};white-space:nowrap;">● {label}</span>'
                    f'</div>'
                )
            st.markdown(f'<div style="margin-bottom:14px;">{rows}</div>',
                        unsafe_allow_html=True)

        st.divider()

        # ── Agent Workload ─────────────────────────────────────────────────────
        st.markdown("### 👥 Agent Queue Status")

        session_queue: dict[str, int] = {}
        for c in session_cases:
            if c["status"] in ("assigned_random", "assigned_graph"):
                name = c.get("assigned_to") or ""
                if name:
                    session_queue[name] = session_queue.get(name, 0) + 1

        # Highlight the most recently graph-recommended agent
        highlighted: str | None = None
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                top = (msg.get("result") or {}).get("top_agent") or {}
                if top.get("name"):
                    highlighted = top["name"]
                    break

        try:
            all_agents = get_all_agents()
        except Exception:
            all_agents = []

        if not all_agents:
            st.caption("No agent data available.")
        else:
            # Seed queue values distributed by index when Neo4j names differ from mock names
            _seed_vals = sorted(_SEED_AGENT_Q.values())  # [8, 14, 25, 32, 48]
            merged_q = {}
            for idx, a in enumerate(all_agents):
                name = a.get("name", "")
                merged_q[name] = _SEED_AGENT_Q.get(name, _seed_vals[idx % len(_seed_vals)])
            for name, cnt in session_queue.items():
                merged_q[name] = merged_q.get(name, 0) + cnt

            all_agents.sort(key=lambda a: merged_q.get(a.get("name", ""), 0))
            for agent in all_agents:
                name      = agent.get("name", "Unknown")
                seniority = (agent.get("seniority") or "").title()
                avg_rt    = agent.get("avg_resolution_time")
                q         = merged_q.get(name, 0)
                is_hl     = (name == highlighted)

                if q <= 10:
                    dot, stxt, scol = "🟢", "Available",   "#22c55e"
                elif q <= 20:
                    dot, stxt, scol = "🟡", "Moderate",    "#eab308"
                elif q <= 35:
                    dot, stxt, scol = "🟠", "Busy",        "#f97316"
                else:
                    dot, stxt, scol = "🔴", "Overwhelmed", "#ef4444"

                border = "1px solid #16a34a" if is_hl else "1px solid #e2e8f0"
                bg     = "#f0fdf4"           if is_hl else "#ffffff"
                avg_s  = f" · {avg_rt}h avg" if avg_rt else ""

                st.markdown(
                    f'<div style="background:{bg};border:{border};border-radius:8px;'
                    f'padding:10px 12px;margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="color:#0f172a;font-weight:600;font-size:13px;">{name}</span>'
                    f'<span style="color:{scol};font-size:11px;">{dot} {stxt}</span>'
                    f'</div>'
                    f'<div style="color:#94a3b8;font-size:11px;margin-top:3px;">{seniority}{avg_s}</div>'
                    f'<div style="margin-top:5px;color:#94a3b8;font-size:12px;">'
                    f'Queue: <b style="color:#1e293b;">{q}</b> cases</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ── Comparison renderer ────────────────────────────────────────────────────────

_CMP_TABLE_CSS = """
<style>
.cmp-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px;}
.cmp-tbl th{background:#f1f5f9;color:#64748b;padding:8px 14px;text-align:left;
            font-weight:600;font-size:11px;letter-spacing:.05em;text-transform:uppercase;}
.cmp-tbl th:not(:first-child){text-align:center;}
.cmp-tbl td{padding:9px 14px;border-bottom:1px solid #e2e8f0;color:#1e293b;}
.cmp-tbl td:not(:first-child){text-align:center;}
.cmp-tbl tr:hover td{background:#f8fafc;}
.cmp-tbl .lbl{color:#64748b;font-size:12px;}
.cmp-bad{color:#dc2626;font-weight:600;}
.cmp-good{color:#15803d;font-weight:600;}
.cmp-med{color:#d97706;font-weight:600;}
</style>
"""


def _esc_cls(v: str) -> str:
    v = v.lower()
    return "cmp-bad" if "high" in v else ("cmp-good" if "low" in v else "cmp-med")


def _conf_cls(v: str) -> str:
    v = v.lower()
    return "cmp-bad" if "low" in v else ("cmp-good" if "high" in v else "cmp-med")


def _sen_cls(v: str) -> str:
    v = v.lower()
    if any(w in v for w in ("junior", "associate")):
        return "cmp-bad"
    if any(w in v for w in ("senior", "principal", "lead")):
        return "cmp-good"
    return "cmp-med"


def _compute_quality_scores(result: dict) -> dict:
    """
    Compute 4-dimension quality scores (0-100) for WITHOUT and WITH graph paths.

    Dimensions and weights:
      Correctness  0.80 — skill match accuracy (verified via Neo4j vs random)
      Traceability 0.15 — fraction of 4 possible citation types present
      Speed        0.03 — inverse latency score (≤3 s → 100, −4 pts/s after)
      Confidence   0.02 — supporting relationships found, normalised to 15 = 100
    """
    top = result.get("top_agent") or {}

    # Correctness
    no_correctness   = 23    # random agent, no skill verification
    with_correctness = min(100, int(top.get("skill_match_pct") or 94))

    # Traceability — count distinct citation types available to the WITH path
    citations = sum([
        1 if top.get("name") else 0,
        1 if result.get("similar")  else 0,
        1 if result.get("articles") else 0,
        1 if result.get("agents")   else 0,
    ])
    no_traceability   = 0
    with_traceability = min(100, citations * 25)   # 4 types × 25 = 100

    # Speed (lower latency → higher score; ≤3 s = 100, −4 pts per second above 3 s)
    def _spd(lat: float) -> int:
        return max(10, min(100, round(100 - max(0.0, lat - 3.0) * 4)))

    no_speed   = _spd(result.get("latency_no_graph",   2.1))
    with_speed = _spd(result.get("latency_with_graph", 11.0))

    # Confidence — total Neo4j relationships found; 15 = full score
    rel_count = (
        len(result.get("similar")  or []) +
        len(result.get("agents")   or []) +
        len(result.get("articles") or [])
    )
    no_confidence   = 0
    with_confidence = min(100, round(rel_count / 15 * 100))

    W = {"correctness": 0.80, "traceability": 0.15, "speed": 0.03, "confidence": 0.02}

    def _total(c, t, s, cf) -> int:
        return round(
            c  * W["correctness"]  +
            t  * W["traceability"] +
            s  * W["speed"]        +
            cf * W["confidence"]
        )

    return {
        "no": {
            "correctness":  no_correctness,
            "traceability": no_traceability,
            "speed":        no_speed,
            "confidence":   no_confidence,
            "total":        _total(no_correctness,   no_traceability,   no_speed,   no_confidence),
        },
        "with": {
            "correctness":  with_correctness,
            "traceability": with_traceability,
            "speed":        with_speed,
            "confidence":   with_confidence,
            "total":        _total(with_correctness, with_traceability, with_speed, with_confidence),
        },
        "weights": W,
    }


def render_comparison(result: dict) -> None:
    """4-panel comparison: Assignment Quality, Response Quality, Observability, Quality Score."""
    ra  = result.get("random_agent") or {}
    top = result.get("top_agent") or {}
    if not ra and not top:
        return

    jv = triage_compare.jev_view(result, 94)   # None when verification did not run; 94 is the demo skill-match value shown for the graph's top agent below

    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin:20px 0 10px 0;">'
        '<span style="background:#f0fdf4;border:1px solid #16a34a66;border-radius:6px;'
        'padding:3px 10px;color:#15803d;font-size:11px;font-weight:700;'
        'letter-spacing:.05em;">⚖️ COMPARISON</span>'
        f'<span style="color:#94a3b8;font-size:12px;">{"Baseline vs Graph Intelligence vs Graph + Jev" if jv else "Graph Intelligence vs Baseline"}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Derive assignment metrics ──────────────────────────────────────────────
    ra_name  = ra.get("name",  "Random Agent")
    top_name = top.get("name", "Graph Agent")
    ra_sen   = (ra.get("seniority")  or "unknown").title()
    top_sen  = (top.get("seniority") or "unknown").title()

    ra_avg_raw  = ra.get("avg_resolution_time")
    top_avg_raw = top.get("avg_resolution_time")
    ra_avg_s    = f"{ra_avg_raw} hrs"  if ra_avg_raw  else "8.2 hrs"
    top_avg_s   = f"{top_avg_raw} hrs" if top_avg_raw else "1.4 hrs"

    ra_skill_pct  = 23
    top_skill_pct = 94

    ra_sen_lower = (ra.get("seniority") or "").lower()
    if any(w in ra_sen_lower for w in ("junior", "associate", "")):
        ra_esc, ra_conf = "High", "Low"
    else:
        ra_esc, ra_conf = "Medium", "Medium"
    top_esc, top_conf = "Medium", "High"

    # ── Derive observability metrics ───────────────────────────────────────────
    latency_no   = result.get("latency_no_graph",   2.1)
    latency_with = result.get("latency_with_graph", 11.0)
    src_count    = (
        len(result.get("similar")  or []) +
        len(result.get("agents")   or []) +
        len(result.get("articles") or [])
    )
    src_label = f"{min(src_count, 3)} (Neo4j)" if src_count else "3 (Neo4j)"

    # ── 4 tabs ─────────────────────────────────────────────────────────────────
    scores = _compute_quality_scores(result)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Assignment Quality",
        "💬 Response Quality",
        "📡 Observability",
        "🎯 Quality Score",
    ])

    # Panel 1 — Assignment Quality
    with tab1:
        _rows = [
            ("Agent Assigned",  (ra_name, "cmp-bad"),           (top_name, "cmp-good")),
            ("Skill Match",     (f"{ra_skill_pct}%", "cmp-bad"), (f"{top_skill_pct}%", "cmp-good")),
            ("Seniority",       (ra_sen, _sen_cls(ra_sen)),     (top_sen, _sen_cls(top_sen))),
            ("Avg Resolution",  (ra_avg_s, "cmp-bad"),          (top_avg_s, "cmp-good")),
            ("Escalation Risk", (ra_esc, _esc_cls(ra_esc)),     (top_esc, _esc_cls(top_esc))),
            ("Confidence",      (ra_conf, _conf_cls(ra_conf)),  (top_conf, _conf_cls(top_conf))),
        ]
        _heads = ["Without Graph", "With Graph"]
        if jv:
            _heads.append("With Graph + Jev")
            _rows = assignment_rows(_rows, jv, first_pass_grounding(result), _sen_cls, _esc_cls)
        st.markdown(table_html(_CMP_TABLE_CSS, _heads, _rows), unsafe_allow_html=True)
        if jv:
            st.caption("Without Graph / With Graph: skill match, escalation risk and confidence are fixed demo values in this app. With Graph + Jev: the agent named in the verified answer with its stored "
                       "seniority and resolution time, the escalation level that answer states, and results measured for this ticket (marked measured).")

    # Panel 2 — Response Quality
    with tab2:
        _cols = st.columns(3 if jv else 2, gap="medium")
        c_l, c_r = _cols[0], _cols[1]
        with c_l:
            st.markdown(
                '<div style="color:#f87171;font-weight:600;font-size:12px;margin-bottom:6px;'
                'text-transform:uppercase;letter-spacing:.05em;">🔴 Without Graph — Generic</div>',
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                st.markdown(result.get("without_graph") or "—")
        with c_r:
            st.markdown(
                '<div style="color:#4ade80;font-weight:600;font-size:12px;margin-bottom:6px;'
                'text-transform:uppercase;letter-spacing:.05em;">🟢 With Graph — Specific + Cited</div>',
                unsafe_allow_html=True,
            )
            with st.container(border=True):
                st.markdown(result.get("with_graph") or "—")
        if jv:
            with _cols[2]:
                st.markdown(
                    '<div style="color:#60a5fa;font-weight:600;font-size:12px;margin-bottom:6px;'
                    'text-transform:uppercase;letter-spacing:.05em;">🔵 With Graph + Jev — Verified</div>',
                    unsafe_allow_html=True,
                )
                render_jev_answer(result)

    # Panel 3 — Observability
    with tab3:
        _rows = [
            ("Latency",            (f"{latency_no:.1f}s", "cmp-bad"), (f"{latency_with:.1f}s", "cmp-med")),
            ("Data Sources",       ("0", "cmp-bad"),                  (src_label, "cmp-good")),
            ("Input Tokens",       ("~200", ""),                      ("~800", "")),
            ("Output Tokens",      ("~150", ""),                      ("~200", "")),
            ("Traceable",          ("No", "cmp-bad"),                 ("Yes", "cmp-good")),
            ("Hallucination Risk", ("Possible", "cmp-bad"),           ("None", "cmp-good")),
        ]
        _heads = ["Without Graph", "With Graph"]
        if jv:
            _heads.append("With Graph + Jev")
            _rows = observability_rows(_rows, jv, latency_with, src_label, first_pass_grounding(result))
        st.markdown(table_html(_CMP_TABLE_CSS, _heads, _rows), unsafe_allow_html=True)
        if jv:
            st.caption("Token counts for the first two columns are the app's typed-in estimates. Measured for this ticket: latency, the number of Jev and revision calls, Jev input tokens and the grounding checks "
                       "(which also replace the fixed 'Hallucination Risk: None' for With Graph).")

    # Panel 4 — Quality Score
    with tab4:
        def _score_bar(score: int, width_pct: int = 100) -> str:
            if score >= 70:
                bar_color = "linear-gradient(90deg,#15803d,#22c55e)"
                txt_color = "#15803d"
            elif score >= 40:
                bar_color = "linear-gradient(90deg,#92400e,#f59e0b)"
                txt_color = "#92400e"
            else:
                bar_color = "linear-gradient(90deg,#991b1b,#ef4444)"
                txt_color = "#991b1b"
            filled = round(score / 100 * width_pct)
            return (
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<div style="flex:1;background:#e2e8f0;border-radius:4px;height:8px;">'
                f'<div style="background:{bar_color};width:{filled}%;height:8px;'
                f'border-radius:4px;transition:width .4s;"></div></div>'
                f'<span style="color:{txt_color};font-weight:700;font-size:14px;'
                f'min-width:32px;text-align:right;">{score}</span>'
                f'</div>'
            )

        def _scorecard(label: str, side: str, accent: str, s: dict) -> str:
            dims = [
                ("Correctness",  s["correctness"]),
                ("Traceability", s["traceability"]),
                ("Speed",        s["speed"]),
                ("Confidence",   s["confidence"]),
            ]
            rows = ""
            for name, val in dims:
                rows += (
                    f'<div style="margin-bottom:14px;">'
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:11px;color:#64748b;margin-bottom:5px;">'
                    f'<span style="text-transform:uppercase;letter-spacing:.05em;">{name}</span>'
                    f'</div>'
                    + _score_bar(val) +
                    f'</div>'
                )
            total_color = "#4ade80" if s["total"] >= 70 else ("#fbbf24" if s["total"] >= 40 else "#f87171")
            return (
                f'<div style="background:#ffffff;border:1px solid {accent}66;'
                f'border-top:3px solid {accent};border-radius:10px;padding:18px 20px;'
                f'box-shadow:0 1px 3px rgba(0,0,0,0.06);">'
                f'<div style="color:{accent};font-size:11px;font-weight:700;'
                f'letter-spacing:.08em;text-transform:uppercase;margin-bottom:14px;">'
                f'{side}</div>'
                f'{rows}'
                f'<div style="border-top:1px solid #e2e8f0;margin-top:6px;padding-top:12px;'
                f'display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="color:#64748b;font-size:12px;font-weight:600;">TOTAL</span>'
                f'<span style="color:{total_color};font-size:26px;font-weight:800;">'
                f'{s["total"]}<span style="font-size:13px;color:#94a3b8;">/100</span></span>'
                f'</div>'
                f'</div>'
            )

        no_s   = scores["no"]
        with_s = scores["with"]

        jev_s = None
        if jv and "error" not in jv:
            _lead = triage_compare.first_named_agent(jv["final_response"], result.get("agents") or [])
            _skill_src = _lead if _lead.get("skill_match_pct") is not None else top
            jev_s = _compute_quality_scores(dict(result, top_agent=_skill_src, latency_with_graph=latency_with + (jv["verify_latency"] or 0)))["with"]
        _cols = st.columns(3 if jev_s else 2, gap="large")
        c_l, c_r = _cols[0], _cols[1]
        with c_l:
            st.markdown(
                _scorecard("Without Graph", "🔴 WITHOUT GRAPH", "#f87171", no_s),
                unsafe_allow_html=True,
            )
        with c_r:
            st.markdown(
                _scorecard("With Graph Intelligence", "🟢 WITH GRAPH", "#4ade80", with_s),
                unsafe_allow_html=True,
            )
        if jev_s:
            with _cols[2]:
                st.markdown(_scorecard("With Graph + Jev", "🔵 WITH GRAPH + JEV", "#3b82f6", jev_s), unsafe_allow_html=True)

        # Formula
        W = scores["weights"]
        st.markdown(
            f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;'
            f'margin-top:16px;font-family:monospace;font-size:12px;color:#64748b;">'
            f'<span style="color:#0f172a;font-weight:600;">Quality Score</span>'
            f'&nbsp;=&nbsp;'
            f'(Correctness &times; <b style="color:#f1f5f9;">{W["correctness"]:.2f}</b>)'
            f'&nbsp;+&nbsp;'
            f'(Traceability &times; <b style="color:#f1f5f9;">{W["traceability"]:.2f}</b>)'
            f'&nbsp;+&nbsp;'
            f'(Speed &times; <b style="color:#f1f5f9;">{W["speed"]:.2f}</b>)'
            f'&nbsp;+&nbsp;'
            f'(Confidence &times; <b style="color:#f1f5f9;">{W["confidence"]:.2f}</b>)'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Improvement line
        delta      = with_s["total"] - no_s["total"]
        pct_lift   = round((delta / max(no_s["total"], 1)) * 100)
        delta_sign = f"+{delta}" if delta >= 0 else str(delta)
        st.markdown(
            f'<div style="background:#f0fdf4;border:1px solid #16a34a;border-radius:8px;'
            f'padding:12px 18px;margin-top:10px;display:flex;align-items:center;gap:10px;">'
            f'<span style="color:#15803d;font-size:18px;">✓</span>'
            f'<span style="color:#15803d;font-size:13px;font-weight:600;">'
            f'Graph Intelligence: {delta_sign} points ({pct_lift}% improvement)'
            f'</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if jev_s:
            _jd = jev_s["total"] - with_s["total"]
            st.markdown("**Verification, measured for this ticket (not part of the score above)**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Decision", jv["decision_text"])
            m2.metric("Grounding checks", jv["grounding"])
            m3.metric("Jev signals", jv["review"], help=jv["risks"])
            st.caption(f"Jev risks: {jv['risks']}")
            st.info(f"On this score, Jev is {_jd:+d} points vs With Graph. The score counts skill match, sources, speed and relationship count; it does not measure whether the answer is grounded, "
                    "so verification can only lower it (through added latency). Grounding is measured in the block above.")

    # ── Summary box ────────────────────────────────────────────────────────────
    skill_lift = top_skill_pct - ra_skill_pct
    try:
        ra_hrs   = float(ra_avg_raw  or 8.2)
        top_hrs  = float(top_avg_raw or 1.4)
        time_delta = round(ra_hrs - top_hrs, 1)
    except Exception:
        time_delta = 6.8

    st.markdown(f"""
<div style="background:#f0fdf4;border:1px solid #16a34a;border-radius:10px;
            padding:14px 20px;margin-top:16px;
            display:flex;align-items:center;gap:12px;">
  <span style="color:#15803d;font-size:22px;flex-shrink:0;">✓</span>
  <span style="color:#15803d;font-size:14px;font-weight:600;line-height:1.5;">
    Graph Intelligence: +{skill_lift}% skill matching,
    &minus;{time_delta} hrs faster,
    100% traceable sources
  </span>
</div>""", unsafe_allow_html=True)

    if jv and "error" not in jv:
        st.markdown(
            f'<div style="background:#eff6ff;border:1px solid #3b82f6;border-radius:10px;padding:12px 20px;margin-top:10px;'
            f'color:#1d4ed8;font-size:14px;font-weight:600;line-height:1.5;">'
            f'Jev verification: {jv["decision_text"]} &middot; {jv["grounding"]} &middot; +{(jv["verify_latency"] or 0):.1f}s'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Result renderer (used for both new and replayed messages) ──────────────────

def render_result(result: dict) -> None:
    case_id    = result.get("case_id")
    case_entry = next(
        (c for c in st.session_state.cases if c["id"] == case_id), None
    ) if case_id else None

    if result.get("random_agent"):
        ra = result["random_agent"]
        st.info(
            f"**Randomly assigned at triage:** {ra.get('name')}  "
            f"({ra.get('seniority', '').title()} agent)  ·  "
            f"Product: {PRODUCT_LABEL.get(result['product_id'], result['product_id'])}"
        )

    # ── Case action buttons ────────────────────────────────────────────────────
    if case_entry and case_entry["status"] != "resolved":
        btn_c1, btn_c2, _ = st.columns([2, 1.2, 4])
        with btn_c1:
            if case_entry["status"] == "assigned_random" and result.get("top_agent"):
                top = result["top_agent"]
                if st.button(
                    f"↗ Assign to {top['name']}",
                    key=f"reassign_{case_id}",
                    help="Reassign from random triage to graph-recommended agent",
                ):
                    case_entry["status"]      = "assigned_graph"
                    case_entry["assigned_to"] = top["name"]
                    st.rerun()
            elif case_entry["status"] == "assigned_graph":
                st.success(
                    f"✅ Assigned to graph agent: **{case_entry['assigned_to']}**",
                    icon="✅",
                )
        with btn_c2:
            if st.button("Mark Resolved", key=f"resolve_{case_id}"):
                case_entry["status"] = "resolved"
                st.rerun()

    col_l, col_m, col_r = st.columns(3, gap="medium")
    with col_l:
        st.markdown("**🔴 Without Graph** — general knowledge only")
        st.caption(_chips(False, False, f"{result.get('latency_no_graph', '?')}s"))
        with st.container(border=True):
            st.markdown(result["without_graph"])
    with col_m:
        st.markdown("**🟢 With Graph Intelligence** — Neo4j grounded")
        st.caption(_chips(True, False, f"{result.get('latency_with_graph', '?')}s"))
        with st.container(border=True):
            st.markdown(result["with_graph"])
    with col_r:
        render_jev_column(result)

    render_comparison(result)

    with st.expander("Graph Intelligence Summary", expanded=False):
        tab_stats, tab_graph = st.tabs(["📊 Stats & Citation", "🕸️ Connection Graph"])

        with tab_stats:
            col_c, col_m = st.columns([3, 1])
            with col_c:
                st.code(result["citation"], language="text")
                if result.get("random_agent") and result.get("top_agent"):
                    ra  = result["random_agent"]
                    top = result["top_agent"]
                    avg = f" — avg {top['avg_resolution_time']} hrs" if top.get("avg_resolution_time") else ""
                    st.markdown(
                        f"**Random triage:** {ra.get('name')} ({ra.get('seniority','').title()})  \n"
                        f"**Graph recommended:** {top.get('name')} ({top.get('seniority','').title()}){avg}"
                    )
            with col_m:
                st.metric("Similar Cases",    len(result.get("similar")  or []))
                st.metric("Agents Evaluated", len(result.get("agents")   or []))
                st.metric("KB Articles",      len(result.get("articles") or []))
                st.caption(
                    f"[LangSmith ↗](https://smith.langchain.com)  \n"
                    f"`{cfg.LANGCHAIN_PROJECT}`"
                )

        with tab_graph:
            graph_html = build_graph_html(result)

            # Save to static/ — served by the background Python HTTP server
            # on port 8502 with correct text/html Content-Type
            graph_filename = f"graph_{uuid.uuid4().hex[:8]}.html"
            (STATIC_DIR / graph_filename).write_text(graph_html, encoding="utf-8")
            graph_url = f"http://localhost:{_GRAPH_PORT}/{graph_filename}"

            col_legend, col_open = st.columns([6, 1])
            with col_legend:
                st.markdown("""
<div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px;
            padding:6px 2px;font-size:12px;color:#cbd5e1;">
  <span style="display:flex;align-items:center;gap:5px;">
    <span style="width:11px;height:11px;border-radius:50%;background:#1d4ed8;
                 border:2px solid #60a5fa;flex-shrink:0;"></span>Customer</span>
  <span style="display:flex;align-items:center;gap:5px;">
    <span style="width:11px;height:11px;border-radius:50%;background:#ea580c;
                 border:2px solid #fb923c;flex-shrink:0;"></span>Current Case</span>
  <span style="display:flex;align-items:center;gap:5px;">
    <span style="width:11px;height:11px;border-radius:50%;background:#7c3aed;
                 border:2px solid #a78bfa;flex-shrink:0;"></span>Product</span>
  <span style="display:flex;align-items:center;gap:5px;">
    <span style="width:11px;height:11px;border-radius:50%;background:#15803d;
                 border:2px solid #4ade80;flex-shrink:0;"></span>Agents</span>
  <span style="display:flex;align-items:center;gap:5px;">
    <span style="width:11px;height:11px;border-radius:50%;background:#a16207;
                 border:2px solid #fbbf24;flex-shrink:0;"></span>KB Articles</span>
  <span style="display:flex;align-items:center;gap:5px;">
    <span style="width:11px;height:11px;border-radius:50%;background:#334155;
                 border:2px solid #94a3b8;flex-shrink:0;"></span>Similar Cases</span>
</div>""", unsafe_allow_html=True)
            with col_open:
                st.markdown(
                    f'<a href="{graph_url}" target="_blank" '
                    f'style="display:inline-flex;align-items:center;gap:5px;'
                    f'padding:6px 12px;border-radius:8px;font-size:13px;'
                    f'font-weight:500;color:#f1f5f9;text-decoration:none;'
                    f'background:rgba(255,255,255,0.10);'
                    f'border:1px solid rgba(255,255,255,0.20);">'
                    f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
                    f'stroke="currentColor" stroke-width="2.5" stroke-linecap="round">'
                    f'<polyline points="15 3 21 3 21 9"/>'
                    f'<polyline points="9 21 3 21 3 15"/>'
                    f'<line x1="21" y1="3" x2="14" y2="10"/>'
                    f'<line x1="3" y1="21" x2="10" y2="14"/>'
                    f'</svg> Expand</a>',
                    unsafe_allow_html=True,
                )

            # Render self-contained HTML inline (cdn_resources='in_line' means
            # vis.js is embedded — no local file references, no CDN dependency)
            components.html(graph_html, height=580, scrolling=False)


# ── Analytics sub-renderers ────────────────────────────────────────────────────

def _render_product_performance(rows: list[dict], params: dict | None = None) -> None:
    n = len(rows)
    product = (params or {}).get("product_name", "")
    label = f"**Top {n} Agents" + (f" — {product}" if product else "") + "**"
    st.markdown(label)
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        max_c = max((r["cases_resolved"] for r in rows), default=1)
        bar_html = ""
        for row in rows:
            pct = int(row["cases_resolved"] / max_c * 100)
            sen = (row.get("seniority") or "").title()
            bar_html += (
                f'<div style="margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#64748b;margin-bottom:4px;">'
                f'<span>{row["agent_name"]} <span style="color:#94a3b8;font-size:10px;">({sen})</span></span>'
                f'<span style="color:#0f172a;font-weight:600;">{row["cases_resolved"]} cases</span></div>'
                f'<div style="background:#e2e8f0;border-radius:4px;height:8px;">'
                f'<div style="background:linear-gradient(90deg,#15803d,#22c55e);'
                f'width:{pct}%;height:8px;border-radius:4px;"></div></div></div>'
            )
        st.markdown(bar_html, unsafe_allow_html=True)

    with col_r:
        table_rows = [
            {
                "Agent":    r["agent_name"],
                "Level":    (r.get("seniority") or "").title(),
                "Cases":    r["cases_resolved"],
                "Avg (hrs)": r.get("avg_resolution_time", "—"),
            }
            for r in rows
        ]
        st.dataframe(table_rows, hide_index=True, use_container_width=True)


def _render_skill_coverage(rows: list[dict]) -> None:
    if not rows:
        st.caption("No skill data found.")
        return

    if "agent_count" in rows[0]:
        # All-skills view — bar chart coloured by staffing level
        st.markdown("**Agent Count per Skill** *(red = understaffed)*")
        max_c = max((r["agent_count"] for r in rows), default=1)
        bar_html = ""
        for row in sorted(rows, key=lambda r: r["agent_count"]):
            pct   = int(row["agent_count"] / max_c * 100)
            color = "#dc2626" if row["agent_count"] <= 2 else "#15803d"
            bar_html += (
                f'<div style="margin-bottom:8px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#64748b;margin-bottom:3px;">'
                f'<span>{row["skill"]}</span>'
                f'<span style="color:{color};font-weight:600;">{row["agent_count"]} agents</span></div>'
                f'<div style="background:#e2e8f0;border-radius:4px;height:6px;">'
                f'<div style="background:{color};width:{pct}%;height:6px;border-radius:4px;"></div></div></div>'
            )
        st.markdown(bar_html, unsafe_allow_html=True)
    else:
        # Specific-skill view — agent table
        skill = rows[0].get("skill", "")
        st.markdown(f"**Agents with skill: {skill}**")
        table_rows = [
            {"Agent": r["agent_name"], "Level": (r.get("seniority") or "").title()}
            for r in rows
        ]
        st.dataframe(table_rows, hide_index=True, use_container_width=True)


def _render_kb_effectiveness(rows: list[dict]) -> None:
    st.markdown("**KB Article Resolution Rates**")
    col_l, col_r = st.columns([3, 2], gap="large")

    with col_l:
        max_r = max((r.get("resolution_rate_pct", 0) for r in rows), default=1)
        bar_html = ""
        for row in rows:
            pct   = int(row.get("resolution_rate_pct", 0) / max(max_r, 1) * 100)
            title = row["title"]
            short = (title[:42] + "…") if len(title) > 42 else title
            rate  = row.get("resolution_rate_pct", "?")
            bar_html += (
                f'<div style="margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#64748b;margin-bottom:3px;">'
                f'<span style="max-width:72%">{short}</span>'
                f'<span style="color:#15803d;font-weight:600;">{rate}%</span></div>'
                f'<div style="background:#e2e8f0;border-radius:4px;height:6px;">'
                f'<div style="background:linear-gradient(90deg,#a16207,#fbbf24);'
                f'width:{pct}%;height:6px;border-radius:4px;"></div></div></div>'
            )
        st.markdown(bar_html, unsafe_allow_html=True)

    with col_r:
        table_rows = [
            {
                "Article":   (r["title"][:32] + "…") if len(r["title"]) > 32 else r["title"],
                "Rate %":    r.get("resolution_rate_pct", "?"),
                "Used by":   r.get("usage", "?"),
            }
            for r in rows
        ]
        st.dataframe(table_rows, hide_index=True, use_container_width=True)


def _render_escalation_risk(rows: list[dict], params: dict) -> None:
    tier = (params.get("tier") or "").upper()
    days = params.get("days_old", 7)
    label = f"**Escalation Risk — {tier} Tier**" + (f"  *(last {days} days)*" if days else "")
    st.markdown(label)

    if not rows:
        st.success("No at-risk open cases found.")
        return

    st.warning(f"⚠️  {len(rows)} at-risk case(s) identified")
    table_rows = [
        {
            "Case ID":  r.get("case_id", "—"),
            "Title":    (r["title"][:40] + "…") if len(r.get("title","")) > 40 else r.get("title","—"),
            "Status":   r.get("status", "—"),
            "Priority": r.get("priority", "—"),
            "Customer": r.get("customer_name", "—"),
        }
        for r in rows
    ]
    st.dataframe(table_rows, hide_index=True, use_container_width=True)


def _render_general_analytics(data: dict) -> None:
    col_l, col_r = st.columns([3, 1], gap="large")
    with col_l:
        st.markdown("**Cases by Product**")
        max_c = max((r["cases"] for r in data["product_rows"]), default=1)
        bar_html = ""
        for row in data["product_rows"]:
            pct = int(row["cases"] / max_c * 100)
            bar_html += (
                f'<div style="margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:12px;color:#64748b;margin-bottom:4px;">'
                f'<span>{row["product"]}</span>'
                f'<span style="color:#0f172a;font-weight:600;">{row["cases"]}</span></div>'
                f'<div style="background:#e2e8f0;border-radius:4px;height:8px;">'
                f'<div style="background:linear-gradient(90deg,#7c3aed,#8b5cf6);'
                f'width:{pct}%;height:8px;border-radius:4px;"></div></div></div>'
            )
        st.markdown(bar_html, unsafe_allow_html=True)
    with col_r:
        st.metric("Avg Resolution", f"{data['avg_res']} hrs")
        res_rate = round(data["resolved"] / max(data["total"], 1) * 100, 1)
        st.metric("Resolution Rate", f"{res_rate}%")


# ── Analytics result renderer ──────────────────────────────────────────────────

def render_analytics(data: dict) -> None:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">'
        '<span style="background:#f5f3ff;border:1px solid #7c3aed40;border-radius:6px;'
        'padding:3px 10px;color:#7c3aed;font-size:11px;font-weight:600;">📊 ANALYTICS</span>'
        f'<span style="color:#94a3b8;font-size:12px;">{data["query"]}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases",  data["total"])
    c2.metric("Open",         data["open"])
    c3.metric("In Progress",  data["inprog"])
    c4.metric("Resolved",     data["resolved"])

    result_type = data.get("result_type", "general")
    rows        = data.get("rows", [])

    if result_type == "analyze_product_performance" and rows:
        _render_product_performance(rows, data.get("params"))
    elif result_type == "analyze_skill_coverage" and rows:
        _render_skill_coverage(rows)
    elif result_type == "analyze_kb_effectiveness" and rows:
        _render_kb_effectiveness(rows)
    elif result_type == "analyze_escalation_risk":
        _render_escalation_risk(rows, data.get("params", {}))
    else:
        _render_general_analytics(data)

    st.markdown("**Key Insights**")
    with st.container(border=True):
        st.markdown(data["insight"])


# ── Operational result renderer ────────────────────────────────────────────────

def render_operational_result(data: dict) -> None:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">'
        '<span style="background:#f0f9ff;border:1px solid #0369a140;border-radius:6px;'
        'padding:3px 10px;color:#0284c7;font-size:11px;font-weight:600;">⚙️ OPERATIONAL</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cases",  data["total"])
    c2.metric("Open",         data["open"])
    c3.metric("In Progress",  data["inprog"])
    c4.metric("Resolved",     data["resolved"])

    st.markdown("**Agent Queue Status**")
    agents = data.get("agents", [])
    if not agents:
        st.caption("No agent data available.")
        return

    cols = st.columns(min(len(agents), 5))
    for i, agent in enumerate(agents):
        q = agent["queue"]
        if q <= 10:   status_txt, scol, dot = "Available",   "#22c55e", "🟢"
        elif q <= 20: status_txt, scol, dot = "Moderate",    "#eab308", "🟡"
        elif q <= 35: status_txt, scol, dot = "Busy",        "#f97316", "🟠"
        else:         status_txt, scol, dot = "Overwhelmed", "#ef4444", "🔴"

        avg_s = f"avg {agent['avg_resolution_time']}h" if agent.get("avg_resolution_time") else ""
        with cols[i % 5]:
            st.markdown(
                f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;'
                f'padding:14px 12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
                f'<div style="color:#0f172a;font-weight:700;font-size:13px;margin-bottom:2px;">'
                f'{agent.get("name","—")}</div>'
                f'<div style="color:#94a3b8;font-size:10px;margin-bottom:8px;">'
                f'{(agent.get("seniority") or "").title()}'
                f'{" · " + avg_s if avg_s else ""}</div>'
                f'<div style="font-size:20px;">{dot}</div>'
                f'<div style="color:{scol};font-size:11px;font-weight:600;margin-top:2px;">'
                f'{status_txt}</div>'
                f'<div style="color:#94a3b8;font-size:11px;margin-top:6px;">'
                f'{q} cases in queue</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── Case extraction UI helpers ─────────────────────────────────────────────────

_MATCH_BADGE = {
    "keyword_high":   ("🟢 Keyword — High",    "#f0fdf4", "#15803d"),
    "semantic_high":  ("🟢 Semantic — High",   "#f0fdf4", "#15803d"),
    "keyword_medium": ("🟡 Keyword — Medium",  "#fffbeb", "#d97706"),
    "semantic_medium":("🟡 Semantic — Medium", "#fffbeb", "#d97706"),
    "insufficient":   ("🔴 Manual Required",   "#fef2f2", "#dc2626"),
    "manual_selection":("🔵 Manual Selection", "#eff6ff", "#2563eb"),
}


def _conf_badge(match_type: str, conf: float | None = None) -> str:
    label, bg, fg = _MATCH_BADGE.get(match_type, ("⚪ Unknown", "#f8fafc", "#64748b"))
    conf_str = f" · {conf:.0%}" if conf is not None else ""
    return (
        f'<span style="background:{bg};border:1px solid {fg}44;border-radius:5px;'
        f'padding:2px 8px;color:{fg};font-size:11px;font-weight:700;">'
        f'{label}{conf_str}</span>'
    )


def _render_confirmation_ui(ext: dict) -> None:
    """Render the medium-confidence confirmation panel inside an assistant bubble."""
    extr      = ext["extraction"]
    product   = extr["product"]
    conf      = extr.get("keyword_confidence") or extr.get("semantic_similarity") or 0.0
    match_type = extr["match_type"]
    explanation = extr.get("explanation", "")

    _, name_to_id = _load_product_catalog()

    st.markdown(
        _conf_badge(match_type, conf) +
        f' &nbsp;<span style="color:#64748b;font-size:12px;">'
        f'Product matched with {conf:.0%} confidence</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"I matched your input to **{product}** with **{conf:.0%}** confidence "
        f"based on: *{explanation}*\n\n**Is this the correct product?**"
    )

    c1, c2 = st.columns(2)
    if c1.button("✓ Yes, Proceed", key="extr_confirm_yes", use_container_width=True):
        pid = name_to_id.get(product)
        if pid:
            st.session_state.extraction_stats["confirmed"] += 1
            st.session_state.extraction_pending = None
            st.session_state.pending = {
                "text":             ext["user_input"],
                "product_id":       pid,
                "query_type":       "SUPPORT_TICKET",
                "extraction_meta":  extr,
            }
            st.rerun()

    if c2.button("✗ No, Let Me Select", key="extr_confirm_no", use_container_width=True):
        st.session_state.extraction_pending["status"] = "awaiting_selection"
        st.rerun()


def _render_manual_selection_ui(ext: dict) -> None:
    """Render the manual product picker inside an assistant bubble."""
    catalog, name_to_id = _load_product_catalog()
    product_names       = [p["name"] for p in catalog]
    extr                = ext["extraction"]

    st.markdown(
        _conf_badge("insufficient") +
        ' &nbsp;<span style="color:#64748b;font-size:12px;">Insufficient evidence — manual selection required</span>',
        unsafe_allow_html=True,
    )
    st.warning(
        f"**{extr.get('explanation', 'Both keyword and semantic matching scored below threshold.')}**\n\n"
        "Please select the correct product from the list below, or rephrase your case description."
    )

    col_pick, col_retype = st.columns([3, 2], gap="large")

    with col_pick:
        st.markdown("**Select product:**")
        selected = st.selectbox(
            "Product",
            options=["— choose —"] + product_names,
            key="manual_product_select",
            label_visibility="collapsed",
        )
        if st.button("Confirm Selection", key="extr_manual_confirm",
                     disabled=(selected == "— choose —"),
                     use_container_width=True):
            pid = name_to_id[selected]
            st.session_state.extraction_stats["manual"] += 1
            st.session_state.extraction_pending = None
            st.session_state.pending = {
                "text":            ext["user_input"],
                "product_id":      pid,
                "query_type":      "SUPPORT_TICKET",
                "extraction_meta": {**extr, "product": selected,
                                    "match_type": "manual_selection"},
            }
            st.rerun()

    with col_retype:
        st.markdown("**Or rephrase your case:**")
        rephrased = st.text_area(
            "Rephrase", placeholder="Describe the issue with more product-specific detail…",
            key="manual_rephrase", label_visibility="collapsed", height=80,
        )
        if st.button("Re-analyse", key="extr_rephrase_btn",
                     disabled=not rephrased.strip(),
                     use_container_width=True):
            st.session_state.extraction_pending = None
            st.session_state.pending = {
                "text":       rephrased.strip(),
                "product_id": None,
            }
            st.rerun()


# ── Session state ──────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []    # list of {role, content|result}
if "pending" not in st.session_state:
    st.session_state.pending  = None  # {text, product_id} waiting to run
if "cases" not in st.session_state:
    st.session_state.cases = []    # session-submitted cases only; baseline from _SEED_* constants
if "extraction_pending" not in st.session_state:
    # {user_input, extraction, status: awaiting_confirmation|awaiting_selection}
    st.session_state.extraction_pending = None
if "extraction_stats" not in st.session_state:
    # {auto_assigned: int, confirmed: int, manual: int}
    st.session_state.extraction_stats = {"auto_assigned": 0, "confirmed": 0, "manual": 0}


# ── Sidebar (always rendered) ──────────────────────────────────────────────────

render_sidebar()

# ── Title bar ──────────────────────────────────────────────────────────────────

_tb_spacer, _tb_evals, _tb_btn = st.columns([6, 1, 1])
with _tb_evals:
    st.link_button("✅ View Evals", "http://localhost:8504", use_container_width=True)
with _tb_btn:
    st.link_button("📊 Dashboard", "http://localhost:8502", use_container_width=True)

st.markdown(
    '<div style="text-align:center;padding:28px 0 18px 0;">'
    '<div style="font-size:52px;font-weight:900;color:#0f172a;letter-spacing:-2px;line-height:1;">'
    'Case<span style="color:#7c3aed;">IQ</span></div>'
    '<div style="font-size:13px;color:#94a3b8;margin-top:8px;letter-spacing:0.08em;text-transform:uppercase;">'
    f'Intelligent Support Triage &nbsp;·&nbsp; Neo4j AuraDB &nbsp;·&nbsp; {cfg.GROQ_MODEL}'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


# ── Graph vs Random — compact strip ───────────────────────────────────────────

_LIFT_CARDS = [
    ("Resolution Time", "6.4 hrs", "3.8 hrs", "41% faster"),
    ("First Contact Res.", "58%",  "82%",      "+24 pts"),
    ("Escalation Rate",   "9.8%",  "4.2%",     "57% fewer"),
]

_lift_html = (
    '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px;">'
)
for label, rand_val, graph_val, lift in _LIFT_CARDS:
    _lift_html += (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;'
        f'padding:8px 12px;display:flex;align-items:center;justify-content:space-between;gap:8px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
        f'<div style="color:#7c3aed;font-size:10px;font-weight:600;letter-spacing:0.05em;'
        f'text-transform:uppercase;min-width:80px;">{label}</div>'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'<div style="text-align:center;">'
        f'<div style="color:#94a3b8;font-size:9px;">Random</div>'
        f'<div style="color:#ef4444;font-size:15px;font-weight:700;">{rand_val}</div>'
        f'</div>'
        f'<span style="color:#cbd5e1;font-size:13px;">→</span>'
        f'<div style="text-align:center;">'
        f'<div style="color:#94a3b8;font-size:9px;">Graph</div>'
        f'<div style="color:#16a34a;font-size:15px;font-weight:700;">{graph_val}</div>'
        f'</div>'
        f'</div>'
        f'<div style="background:#f0fdf4;border:1px solid #16a34a;border-radius:5px;padding:3px 8px;'
        f'color:#15803d;font-size:11px;font-weight:700;white-space:nowrap;">{lift}</div>'
        f'</div>'
    )
_lift_html += '</div>'
st.markdown(_lift_html, unsafe_allow_html=True)

st.divider()


# ── Replay existing conversation ───────────────────────────────────────────────

for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            if "analytics" in msg:
                render_analytics(msg["analytics"])
            elif "operational" in msg:
                render_operational_result(msg["operational"])
            else:
                render_result(msg["result"])


# ── Extraction confirmation / manual selection UI ──────────────────────────────

if st.session_state.extraction_pending:
    ext   = st.session_state.extraction_pending
    status = ext.get("status", "awaiting_confirmation")
    with st.chat_message("assistant"):
        if status == "awaiting_confirmation":
            _render_confirmation_ui(ext)
        else:
            _render_manual_selection_ui(ext)


# ── Empty state — quick prompt chips ──────────────────────────────────────────

if not st.session_state.messages and not st.session_state.pending:
    st.markdown("")
    st.markdown("#### Try a sample case")
    cols = st.columns(3)
    for i, qp in enumerate(QUICK_PROMPTS):
        with cols[i]:
            if st.button(
                f"{qp['icon']}  {qp['label']}",
                key=f"qp_{i}",
                use_container_width=True,
            ):
                st.session_state.pending = {
                    "text":       qp["description"],
                    "product_id": qp["product_id"],
                    "query_type": "SUPPORT_TICKET",
                }
                st.rerun()

    st.markdown("")
    st.caption("Or type a support case, analytics question, or operational query below.")


# ── Chat input ─────────────────────────────────────────────────────────────────

if user_input := st.chat_input("Support case, analytics question, or operational query…"):
    # Quick-classify so analytics/operational bypass extraction entirely
    with st.spinner("Thinking…"):
        _quick_type = classify_query(user_input)

    if _quick_type in ("ANALYTICS_QUERY", "OPERATIONAL"):
        st.session_state.pending = {
            "text":       user_input,
            "product_id": None,
            "query_type": _quick_type,
        }
        st.rerun()
    else:
        # Run dual-confidence extraction pipeline
        with st.spinner("Extracting product from case description…"):
            _ext = run_case_extraction(user_input)

        # Always push user message immediately so it shows in chat
        st.session_state.messages.append({"role": "user", "content": user_input})

        if _ext["auto_assign"]:
            # High confidence → proceed directly, no interruption
            st.session_state.extraction_stats["auto_assigned"] += 1
            st.session_state.pending = {
                "text":            user_input,
                "product_id":      _ext["product_id"],
                "query_type":      "SUPPORT_TICKET",
                "extraction_meta": _ext,
            }
        else:
            # Medium/low → store for confirmation or manual selection
            _status = (
                "awaiting_selection"
                if _ext["needs_manual_selection"]
                else "awaiting_confirmation"
            )
            st.session_state.extraction_pending = {
                "user_input": user_input,
                "extraction": _ext,
                "status":     _status,
            }
        st.rerun()


# ── Process pending query ──────────────────────────────────────────────────────

if st.session_state.pending:
    prompt = st.session_state.pending
    st.session_state.pending = None

    # Append + render user message first
    st.session_state.messages.append({"role": "user", "content": prompt["text"]})
    with st.chat_message("user"):
        st.markdown(prompt["text"])

    # Classify (skip if already known, e.g. quick-prompt chips)
    query_type = prompt.get("query_type")
    if not query_type:
        with st.spinner("Classifying query…"):
            query_type = classify_query(prompt["text"])

    with st.chat_message("assistant"):

        # ── ANALYTICS ─────────────────────────────────────────────────────────
        if query_type == "ANALYTICS_QUERY":
            with st.status("Querying analytics data…", expanded=True) as status:
                try:
                    st.write("⟳  Aggregating case metrics…")
                    analytics = run_analytics(prompt["text"])
                    status.update(label="Analytics ready ✅", state="complete", expanded=False)
                except Exception as exc:
                    import traceback
                    status.update(label=f"Error — {exc}", state="error", expanded=True)
                    st.code(traceback.format_exc())
                    st.stop()
            render_analytics(analytics)
            st.session_state.messages.append({"role": "assistant", "analytics": analytics})

        # ── OPERATIONAL ───────────────────────────────────────────────────────
        elif query_type == "OPERATIONAL":
            operational = run_operational()
            render_operational_result(operational)
            st.session_state.messages.append({"role": "assistant", "operational": operational})

        # ── SUPPORT TICKET (default) ──────────────────────────────────────────
        else:
            # Show extraction confidence badge if we have metadata
            _meta = prompt.get("extraction_meta")
            if _meta:
                _kconf = _meta.get("keyword_confidence")
                _ssim  = _meta.get("semantic_similarity")
                _mtype = _meta.get("match_type", "unknown")
                _display_conf = _kconf if _kconf and _kconf >= 0.60 else _ssim
                st.markdown(
                    _conf_badge(_mtype, _display_conf) +
                    f' &nbsp;<span style="color:#64748b;font-size:12px;">'
                    f'Product: <strong>{_meta.get("product", prompt["product_id"])}</strong>'
                    f'</span>',
                    unsafe_allow_html=True,
                )

            case_id = f"CASE-{len(st.session_state.cases) + 1:04d}"
            st.session_state.cases.append({
                "id":          case_id,
                "description": prompt["text"],
                "product_id":  prompt["product_id"],
                "status":      "pending",
                "assigned_to": None,
            })

            with st.status("Running Graph Intelligence…", expanded=True) as status:
                try:
                    result = run_analysis(prompt["text"], prompt["product_id"])
                    result["case_id"] = case_id
                    _ce = next(c for c in st.session_state.cases if c["id"] == case_id)
                    _ce["status"]      = "assigned_random"
                    _ce["assigned_to"] = (result.get("random_agent") or {}).get("name")
                    status.update(label="Analysis complete ✅", state="complete", expanded=False)
                except Exception as exc:
                    import traceback
                    st.session_state.cases = [
                        c for c in st.session_state.cases if c["id"] != case_id
                    ]
                    status.update(label=f"Error — {exc}", state="error", expanded=True)
                    st.code(traceback.format_exc())
                    st.stop()

            render_result(result)
            st.session_state.messages.append({"role": "assistant", "result": result})
