"""
Synthetic data generator for Customer Support Intelligence Graph POC.
Scale: 2,000 customers · 10,000 cases · 50 products · 500 KB articles
       150 agents · 40 skills · ~35,000+ relationship edges
"""
import csv
import random
import os
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

RAW = "raw"
os.makedirs(RAW, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────

REGIONS = ["US-East", "US-West", "EU-West", "EU-Central", "APAC", "LATAM", "ME", "ANZ"]
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# ── Products (50) ──────────────────────────────────────────────────────────────
# P001/P002/P003 drive 60% of cases; remaining 47 share 40% evenly.

PRODUCT_DATA = [
    ("P001", "Payment Gateway v2",      "Payments",        "2.1"),
    ("P002", "SSO Integration Module",  "Identity",        "3.0"),
    ("P003", "Analytics Dashboard",     "Analytics",       "1.5"),
    ("P004", "Billing Engine",          "Payments",        "1.8"),
    ("P005", "Data Export Service",     "Analytics",       "2.0"),
    ("P006", "API Gateway",             "Infrastructure",  "2.5"),
    ("P007", "Customer Portal",         "Frontend",        "4.2"),
    ("P008", "Refund Manager",          "Payments",        "1.3"),
    ("P009", "OAuth Service",           "Identity",        "2.8"),
    ("P010", "Report Builder",          "Analytics",       "1.2"),
    ("P011", "Billing Disputes Handler","Payments",        "1.0"),
    ("P012", "LDAP Connector",          "Identity",        "3.2"),
    ("P013", "Webhook Engine",          "Infrastructure",  "1.7"),
    ("P014", "Notification Hub",        "Messaging",       "2.3"),
    ("P015", "Admin Console",           "Frontend",        "3.5"),
    ("P016", "Invoice Service",         "Payments",        "2.2"),
    ("P017", "Active Directory Sync",   "Identity",        "4.0"),
    ("P018", "KPI Tracker",             "Analytics",       "1.9"),
    ("P019", "Load Balancer",           "Infrastructure",  "3.1"),
    ("P020", "Self-Service Hub",        "Frontend",        "2.7"),
    ("P021", "Tax Calculator",          "Payments",        "1.4"),
    ("P022", "MFA Manager",             "Identity",        "2.1"),
    ("P023", "Event Tracker",           "Analytics",       "1.6"),
    ("P024", "Rate Limiter",            "Infrastructure",  "2.0"),
    ("P025", "Onboarding Wizard",       "Frontend",        "1.3"),
    ("P026", "Subscription Manager",    "Payments",        "2.6"),
    ("P027", "Token Service",           "Identity",        "3.3"),
    ("P028", "Funnel Analyzer",         "Analytics",       "1.1"),
    ("P029", "Cache Service",           "Infrastructure",  "4.1"),
    ("P030", "Help Center",             "Frontend",        "2.4"),
    ("P031", "Currency Converter",      "Payments",        "1.5"),
    ("P032", "Permission Engine",       "Identity",        "2.9"),
    ("P033", "Data Pipeline",           "Analytics",       "1.8"),
    ("P034", "Queue Manager",           "Infrastructure",  "2.2"),
    ("P035", "Chat Widget",             "Frontend",        "3.0"),
    ("P036", "Fee Analyzer",            "Payments",        "1.2"),
    ("P037", "Role Manager",            "Identity",        "2.0"),
    ("P038", "Cohort Builder",          "Analytics",       "1.4"),
    ("P039", "Config Manager",          "Infrastructure",  "3.7"),
    ("P040", "Status Page",             "Frontend",        "2.1"),
    ("P041", "Chargeback Handler",      "Payments",        "1.6"),
    ("P042", "Session Controller",      "Identity",        "2.4"),
    ("P043", "Attribution Engine",      "Analytics",       "1.7"),
    ("P044", "Secret Store",            "Infrastructure",  "4.3"),
    ("P045", "Mobile App",              "Frontend",        "5.0"),
    ("P046", "Wallet Service",          "Payments",        "1.9"),
    ("P047", "Identity Vault",          "Identity",        "3.1"),
    ("P048", "Metrics Engine",          "Analytics",       "2.3"),
    ("P049", "Deploy Manager",          "Infrastructure",  "2.8"),
    ("P050", "Feedback Collector",      "Frontend",        "1.5"),
]

_OTHER_W = 0.40 / 47
PRODUCT_CASE_WEIGHTS = {
    p[0]: (0.25 if p[0] == "P001" else 0.20 if p[0] == "P002"
           else 0.15 if p[0] == "P003" else _OTHER_W)
    for p in PRODUCT_DATA
}
_PROD_IDS    = [p[0] for p in PRODUCT_DATA]
_PROD_WLIST  = [PRODUCT_CASE_WEIGHTS[pid] for pid in _PROD_IDS]
_PROD_NAME   = {p[0]: p[1] for p in PRODUCT_DATA}

# ── Skills (40) ───────────────────────────────────────────────────────────────

SKILL_DATA = [
    ("SK001", "Payment Processing",          "technical"),
    ("SK002", "Refund Handling",             "billing"),
    ("SK003", "Chargeback Resolution",       "billing"),
    ("SK004", "Invoice Management",          "billing"),
    ("SK005", "Subscription Billing",        "billing"),
    ("SK006", "Tax & Compliance",            "billing"),
    ("SK007", "SSO Configuration",           "technical"),
    ("SK008", "OAuth & Token Management",    "technical"),
    ("SK009", "LDAP / Active Directory",     "technical"),
    ("SK010", "MFA & Security",              "technical"),
    ("SK011", "Identity Troubleshooting",    "technical"),
    ("SK012", "Permission Management",       "technical"),
    ("SK013", "Dashboard Analytics",         "technical"),
    ("SK014", "Data Export & ETL",           "technical"),
    ("SK015", "Report Configuration",        "technical"),
    ("SK016", "KPI & Metrics Setup",         "product"),
    ("SK017", "Event Tracking",              "technical"),
    ("SK018", "API Integration",             "technical"),
    ("SK019", "Webhook Debugging",           "technical"),
    ("SK020", "Rate Limiting & Throttling",  "technical"),
    ("SK021", "Load Balancing",              "technical"),
    ("SK022", "Cache Management",            "technical"),
    ("SK023", "Queue & Async Processing",    "technical"),
    ("SK024", "Performance Tuning",          "technical"),
    ("SK025", "Enterprise Onboarding",       "product"),
    ("SK026", "Customer Portal Setup",       "product"),
    ("SK027", "Mobile App Support",          "product"),
    ("SK028", "Notification Configuration",  "technical"),
    ("SK029", "Escalation Management",       "product"),
    ("SK030", "Audit & Compliance Logging",  "technical"),
    ("SK031", "Secret & Config Management",  "technical"),
    ("SK032", "Deploy & Release Management", "technical"),
    ("SK033", "Infrastructure Debug",        "technical"),
    ("SK034", "Billing Dispute Resolution",  "billing"),
    ("SK035", "Account Management",          "product"),
    ("SK036", "SLA Management",              "product"),
    ("SK037", "Enterprise Support",          "product"),
    ("SK038", "Data Pipeline Debugging",     "technical"),
    ("SK039", "Security Incident Response",  "technical"),
    ("SK040", "Product Training",            "product"),
]

# ── Case Templates  (title, primary_skill, secondary_skill) ───────────────────

CASE_TEMPLATES = [
    ("Unable to process refunds on {product} — error code {error_code}", "SK001", "SK002"),
    ("SSO authentication failing for {product} after latest update",      "SK007", "SK008"),
    ("Data export missing rows in {product} CSV output",                  "SK014", "SK013"),
    ("Dashboard not loading for {product} — blank screen on login",       "SK013", "SK024"),
    ("API rate limiting causing timeouts in {product} integration",       "SK018", "SK020"),
    ("Billing discrepancy on {product} — overcharged for {month}",        "SK002", "SK034"),
    ("User permissions not syncing correctly in {product}",               "SK012", "SK011"),
    ("Performance degradation on {product} — response time exceeds 10s", "SK024", "SK021"),
    ("Onboarding blocked for new enterprise account on {product}",        "SK025", "SK035"),
    ("Audit logs missing for {product} compliance report",                "SK030", "SK006"),
    ("Mobile app crashing on {product} iOS version after update",         "SK027", "SK024"),
    ("Webhook notifications not firing in {product} event stream",        "SK019", "SK018"),
]

# ── KB Article title components ────────────────────────────────────────────────

_ART_ISSUES   = ["authentication failures","timeout errors","data inconsistencies",
                 "permission errors","performance degradation","sync failures",
                 "export issues","webhook failures","login loops","API errors"]
_ART_FEATURES = ["single sign-on","data export","user permissions","audit logging",
                 "rate limiting","webhook events","billing reconciliation",
                 "cache settings","queue management","token refresh"]
_ART_ERRORS   = ["4xx","5xx","timeout","authentication","authorization",
                 "validation","connection","rate limit","data integrity","sync"]
_ART_ACTIONS  = ["initial setup","migration","disaster recovery","scaling",
                 "maintenance","upgrade","rollback","configuration","integration","debugging"]
_ART_CATS     = ["enterprise accounts","high availability","compliance",
                 "performance","security","data management","user management",
                 "API consumers","billing teams","operations teams"]
_ART_TMPLS    = [
    "Troubleshooting {issue} in {product}",
    "How to configure {feature} for {product}",
    "Resolving {error_type} errors in {product}",
    "Step-by-step guide: {product} {action}",
    "{product} best practices for {category}",
    "Common {product} issues and resolutions",
    "{product} integration checklist",
    "Debugging {issue} on {product}",
    "Administrator guide: {product} {feature}",
    "{product} performance optimization",
    "Security hardening for {product}",
    "Enterprise setup guide: {product}",
    "API reference for {product} {feature}",
    "Migration guide: upgrading {product}",
    "{product} audit and compliance setup",
    "Incident response playbook for {product}",
    "{product} monitoring and alerting setup",
    "Data retention policies for {product}",
    "User onboarding with {product}",
    "SLA management for {product} incidents",
]

# ── Helpers ────────────────────────────────────────────────────────────────────

def write_csv(filename, rows, headers):
    path = f"{RAW}/{filename}"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)
    print(f"  ✓  {filename:<30} {len(rows):>7,} rows")

def rand_date(days_back=730):
    return (datetime.now() - timedelta(days=random.randint(0, days_back))).strftime("%Y-%m-%d")

def rand_date_obj(days_back=730):
    return datetime.now() - timedelta(days=random.randint(0, days_back))

# ── Generators ─────────────────────────────────────────────────────────────────

def gen_customers(n=2000):
    n_gold   = int(n * 0.10)
    n_silver = int(n * 0.30)
    n_bronze = n - n_gold - n_silver
    tiers = ["gold"] * n_gold + ["silver"] * n_silver + ["bronze"] * n_bronze
    random.shuffle(tiers)
    rows = [{"id": f"C{i:04d}", "name": fake.company(),
             "tier": tiers[i-1], "region": random.choice(REGIONS)}
            for i in range(1, n + 1)]
    write_csv("customers.csv", rows, ["id", "name", "tier", "region"])
    return rows


def gen_products():
    rows = [{"id": p[0], "name": p[1], "category": p[2], "version": p[3]}
            for p in PRODUCT_DATA]
    write_csv("products.csv", rows, ["id", "name", "category", "version"])
    return rows


def gen_skills():
    rows = [{"id": s[0], "name": s[1], "category": s[2]} for s in SKILL_DATA]
    write_csv("skills.csv", rows, ["id", "name", "category"])
    return rows


def gen_agents(n=150):
    n_senior = int(n * 0.20)
    n_mid    = int(n * 0.50)
    n_junior = n - n_senior - n_mid
    seniorities = ["senior"] * n_senior + ["mid"] * n_mid + ["junior"] * n_junior
    random.shuffle(seniorities)
    res_range = {"senior": (1.0, 12.0), "mid": (2.0, 20.0), "junior": (4.0, 36.0)}
    rows = []
    for i in range(1, n + 1):
        s = seniorities[i-1]
        lo, hi = res_range[s]
        rows.append({"id": f"A{i:03d}", "name": fake.name(), "seniority": s,
                     "avg_resolution_time_hours": round(random.uniform(lo, hi), 1)})
    write_csv("agents.csv", rows, ["id", "name", "seniority", "avg_resolution_time_hours"])
    return rows


def gen_articles():
    # Article count per product:
    #   P001 → 25,  P002 → 25,  P003 → 20
    #   P004-P015 → 13 each   (12 products × 13 = 156)
    #   P016-P030 → 9 each    (15 products × 9  = 135)
    #   P031-P050 → 7 each    (20 products × 7  = 140)  → total ≈ 501
    def article_count(pid):
        n = int(pid[1:])
        if   n == 1:             return 25
        elif n == 2:             return 25
        elif n == 3:             return 20
        elif 4  <= n <= 15:      return 13
        elif 16 <= n <= 30:      return 9
        else:                    return 7

    rows = []
    art_prod_rows = []
    art_id = 1
    for p in PRODUCT_DATA:
        pid, pname = p[0], p[1]
        for _ in range(article_count(pid)):
            aid     = f"KA{art_id:04d}"
            created = rand_date_obj(730)
            age     = (datetime.now() - created).days
            views   = min(int(random.expovariate(1/200)) + 10, 2000)

            if   age < 30:                  res_rate = round(random.uniform(0.30, 0.60), 2)
            elif age > 180 and views > 100: res_rate = round(random.uniform(0.75, 0.95), 2)
            elif views < 30:                res_rate = round(random.uniform(0.20, 0.50), 2)
            else:                           res_rate = round(random.uniform(0.50, 0.80), 2)

            tmpl  = random.choice(_ART_TMPLS)
            title = tmpl.format(product=pname, issue=random.choice(_ART_ISSUES),
                                feature=random.choice(_ART_FEATURES),
                                error_type=random.choice(_ART_ERRORS),
                                action=random.choice(_ART_ACTIONS),
                                category=random.choice(_ART_CATS))
            rows.append({"id": aid, "title": title,
                         "content_summary": fake.paragraph(nb_sentences=2),
                         "resolution_rate": res_rate, "views": views,
                         "created_date": created.strftime("%Y-%m-%d")})
            art_prod_rows.append({"article_id": aid, "product_id": pid})
            art_id += 1

    write_csv("knowledge_articles.csv", rows,
              ["id", "title", "content_summary", "resolution_rate", "views", "created_date"])
    write_csv("article_products.csv", art_prod_rows, ["article_id", "product_id"])
    return rows, art_prod_rows


def gen_cases(customers, n=10000):
    # Weighted customer pool: Gold=12×, Silver=5×, Bronze=2×
    tier_w  = {"gold": 12, "silver": 5, "bronze": 2}
    cust_pool = [c["id"]    for c in customers]
    cust_wts  = [tier_w[c["tier"]] for c in customers]
    cust_tier = {c["id"]: c["tier"] for c in customers}
    tier_res_factor = {"gold": 0.60, "silver": 0.85, "bronze": 1.00}
    priority_range  = {"high": (2, 8), "medium": (8, 48), "low": (24, 120)}

    priorities = random.choices(["high","medium","low"],  weights=[0.15, 0.55, 0.30], k=n)
    statuses   = random.choices(["resolved","open","escalated"], weights=[0.65, 0.25, 0.10], k=n)

    rows, cust_case_rows, case_prod_rows, case_skill_rows = [], [], [], []

    for i in range(1, n + 1):
        cid      = f"CS{i:05d}"
        priority = priorities[i-1]
        status   = statuses[i-1]
        pid      = random.choices(_PROD_IDS, weights=_PROD_WLIST)[0]
        pname    = _PROD_NAME[pid]
        tmpl     = random.choice(CASE_TEMPLATES)
        title    = tmpl[0].format(product=pname,
                                  error_code=random.randint(1000, 9999),
                                  month=random.choice(MONTHS))
        cust_id  = random.choices(cust_pool, weights=cust_wts)[0]

        res_time = ""
        if status == "resolved":
            lo, hi   = priority_range[priority]
            tf       = tier_res_factor[cust_tier[cust_id]]
            res_time = round(random.uniform(lo, hi) * tf, 1)

        rows.append({"id": cid, "title": title,
                     "description": fake.paragraph(nb_sentences=3),
                     "status": status, "priority": priority,
                     "created_date": rand_date(730),
                     "resolution_time_hours": res_time})
        cust_case_rows.append({"customer_id": cust_id, "case_id": cid})
        case_prod_rows.append({"case_id": cid, "product_id": pid})
        case_skill_rows.append({"case_id": cid, "skill_id": tmpl[1]})      # primary
        if random.random() < 0.60:
            case_skill_rows.append({"case_id": cid, "skill_id": tmpl[2]})  # secondary

    write_csv("cases.csv", rows,
              ["id","title","description","status","priority",
               "created_date","resolution_time_hours"])
    write_csv("customer_cases.csv",  cust_case_rows,  ["customer_id","case_id"])
    write_csv("case_products.csv",   case_prod_rows,  ["case_id","product_id"])
    write_csv("case_skills.csv",     case_skill_rows, ["case_id","skill_id"])
    return rows, cust_case_rows, case_prod_rows, case_skill_rows


def gen_agent_skills(agents):
    all_ids    = [s[0] for s in SKILL_DATA]
    cat_weight = {"technical": 3, "billing": 2, "product": 1, "logistics": 1}
    all_wts    = [cat_weight.get(s[2], 1) for s in SKILL_DATA]
    rows, seen = [], set()
    for ag in agents:
        chosen, attempts = set(), 0
        target = random.randint(3, 6)
        while len(chosen) < target and attempts < 100:
            sk = random.choices(all_ids, weights=all_wts)[0]
            chosen.add(sk)
            attempts += 1
        for sk in chosen:
            key = (ag["id"], sk)
            if key not in seen:
                rows.append({"agent_id": ag["id"], "skill_id": sk})
                seen.add(key)
    write_csv("agent_skills.csv", rows, ["agent_id","skill_id"])
    return rows


def gen_agent_cases(agents, cases):
    resolved = [c for c in cases if c["status"] == "resolved"]

    # Productivity weights: top 20% → 6×, mid 50% → 2×, bottom 30% → 0.5×
    n = len(agents)
    order = list(range(n))
    random.shuffle(order)
    prod_wts = [0.0] * n
    for rank, idx in enumerate(order):
        if   rank < int(n * 0.20): prod_wts[idx] = 6.0
        elif rank < int(n * 0.70): prod_wts[idx] = 2.0
        else:                      prod_wts[idx] = 0.5

    sen_map = {a["id"]: a["seniority"] for a in agents}
    ag_ids  = [a["id"] for a in agents]

    rows, seen = [], set()
    for case in resolved:
        priority = case["priority"]
        eligible, elig_wts = [], []
        for idx, aid in enumerate(ag_ids):
            sen = sen_map[aid]
            # High priority → senior or mid only; Junior → medium/low only
            if priority == "high" and sen == "junior":
                continue
            eligible.append(aid)
            elig_wts.append(prod_wts[idx])

        if not eligible:
            continue
        aid = random.choices(eligible, weights=elig_wts)[0]
        key = (aid, case["id"])
        if key not in seen:
            rows.append({"agent_id": aid, "case_id": case["id"]})
            seen.add(key)

    write_csv("agent_cases.csv", rows, ["agent_id","case_id"])
    return rows


def gen_agent_articles(agents, articles):
    # Power law: top 10 articles → weight 10, next 40 → 2.5, rest → 0.5
    art_ids = [a["id"] for a in articles]
    art_wts = []
    for i in range(len(art_ids)):
        if   i < 10:  art_wts.append(10.0)
        elif i < 50:  art_wts.append(2.5)
        else:         art_wts.append(0.5)

    rows, seen = [], set()
    for ag in agents:
        target, attempts, chosen = random.randint(4, 15), 0, set()
        while len(chosen) < target and attempts < 200:
            aid = random.choices(art_ids, weights=art_wts)[0]
            chosen.add(aid)
            attempts += 1
        for aid in chosen:
            key = (ag["id"], aid)
            if key not in seen:
                rows.append({"agent_id": ag["id"], "article_id": aid})
                seen.add(key)
    write_csv("agent_articles.csv", rows, ["agent_id","article_id"])
    return rows


def gen_similar_cases(case_prod_rows, max_pairs=5000):
    # Group cases by product (same product → high similarity)
    by_product = {}
    for cp in case_prod_rows:
        by_product.setdefault(cp["product_id"], []).append(cp["case_id"])

    rows, seen = [], set()
    for pid, clist in by_product.items():
        if len(clist) < 2:
            continue
        n_pairs = min(len(clist) // 2, 80)
        added, attempts = 0, 0
        while added < n_pairs and attempts < n_pairs * 10:
            a, b = random.sample(clist, 2)
            key  = tuple(sorted([a, b]))
            if key not in seen:
                rows.append({"case_id_a": a, "case_id_b": b,
                             "similarity_score": round(random.uniform(0.60, 0.99), 2)})
                seen.add(key)
                added += 1
            attempts += 1

    random.shuffle(rows)
    rows = rows[:max_pairs]
    write_csv("similar_cases.csv", rows, ["case_id_a","case_id_b","similarity_score"])
    return rows


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating synthetic support data...\n")

    customers                                          = gen_customers(2000)
    gen_products()
    gen_skills()
    agents                                             = gen_agents(150)
    articles, art_prod_rows                            = gen_articles()
    cases, cust_case_rows, case_prod_rows, case_skill_rows = gen_cases(customers, 10000)
    agent_skill_rows                                   = gen_agent_skills(agents)
    agent_case_rows                                    = gen_agent_cases(agents, cases)
    agent_art_rows                                     = gen_agent_articles(agents, articles)
    sim_rows                                           = gen_similar_cases(case_prod_rows, 5000)

    total_edges = (len(cust_case_rows) + len(case_prod_rows) + len(case_skill_rows)
                   + len(art_prod_rows) + len(agent_skill_rows) + len(agent_case_rows)
                   + len(agent_art_rows) + len(sim_rows))

    print(f"""
── Edge summary ─────────────────────────────────────────
  customer_cases:    {len(cust_case_rows):>7,}
  case_products:     {len(case_prod_rows):>7,}
  case_skills:       {len(case_skill_rows):>7,}
  article_products:  {len(art_prod_rows):>7,}
  agent_skills:      {len(agent_skill_rows):>7,}
  agent_cases:       {len(agent_case_rows):>7,}
  agent_articles:    {len(agent_art_rows):>7,}
  similar_cases:     {len(sim_rows):>7,}
  ─────────────────────────────────
  TOTAL edges:       {total_edges:>7,}
─────────────────────────────────────────────────────────
Done. All CSVs written to ./raw/
""")
