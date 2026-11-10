"""
Shared formatting helpers used by both agent/main.py (CLI) and app.py (Streamlit UI).
Pure functions — no external dependencies, safe to import anywhere.
"""


def format_executive_context(
    scenario: dict,
    similar: list[dict],
    agents:   list[dict],
    articles: list[dict],
    recommendation: dict,
) -> str:
    lines = [
        f"SUPPORT CASE: {scenario['description']}",
        "",
        "INTELLIGENCE DATA",
        "─" * 50,
        "",
    ]

    # Customer context
    cust = recommendation.get("customer", {})
    if cust:
        tier  = str(cust.get("customer_tier", "Unknown")).upper()
        name  = cust.get("customer_name", "Unknown")
        prior = cust.get("prior_cases_on_product", 0)
        lines += [
            "CUSTOMER PROFILE:",
            f"  Name          : {name}",
            f"  Account tier  : {tier}",
            f"  Prior cases on this product: {prior}",
            "",
        ]

    # Similar resolved cases
    lines.append("SIMILAR CASES PREVIOUSLY RESOLVED:")
    if similar:
        for c in similar:
            rt = f"{c['resolution_time_hours']:.1f} hours" if c.get("resolution_time_hours") else "unknown"
            lines.append(f"  • \"{c['title']}\" — resolved in {rt}")
        avg_rt = recommendation.get("avg_resolution_hours")
        if avg_rt:
            lines.append(f"  Historical average for this product: {avg_rt} hours")
    else:
        lines.append("  No similar resolved cases found in the system.")
    lines.append("")

    # Recommended agents
    lines.append("RECOMMENDED SUPPORT AGENTS (ranked by skill match and past performance):")
    if agents:
        for i, a in enumerate(agents, 1):
            avg = a.get("avg_resolution_time") or a.get("avg_resolution_hours")
            avg_str = f", average resolution {avg} hours" if avg else ""
            lines.append(f"  {i}. {a['name']} — {a['seniority'].title()} agent{avg_str}")
    else:
        lines.append("  No matching agents identified.")
    lines.append("")

    # KB articles
    lines.append("RELEVANT KNOWLEDGE BASE ARTICLES (filtered by effectiveness > 70%):")
    if articles:
        for i, a in enumerate(articles, 1):
            lines.append(
                f"  {i}. \"{a['title']}\" "
                f"— {a['resolution_rate']:.0%} resolution rate, "
                f"used in {a['times_used']} past cases"
            )
    else:
        lines.append("  No relevant knowledge articles found.")
    lines.append("")

    lines += [
        "─" * 50,
        "Using only the intelligence data above, provide:",
        "1. The 2 best agents to assign, with reasoning",
        "2. The 3 most relevant KB articles, with reasoning",
        "3. Estimated resolution time",
        "4. Escalation risk assessment",
    ]

    return "\n".join(lines)


def build_citation_block(
    similar:  list[dict],
    agents:   list[dict],
    articles: list[dict],
) -> str:
    top_agent = "None identified"
    if agents:
        a = agents[0]
        top_agent = f"{a['name']} ({a['seniority'].title()})"

    article_titles = [f"\"{a['title']}\"" for a in articles[:3]] if articles else ["None found"]

    n_similar  = len(similar)
    n_agents   = len(agents)
    n_articles = len(articles)

    if n_similar >= 3 and n_agents >= 2 and n_articles >= 2:
        confidence = "High"
    elif n_similar >= 1 or (n_agents >= 1 and n_articles >= 1):
        confidence = "Medium"
    else:
        confidence = "Low"

    lines = [
        "--- Graph Intelligence Summary ---",
        f"Similar cases found    : {n_similar}",
        f"Top recommended agent  : {top_agent}",
        "Recommended KB articles:",
    ]
    for title in article_titles:
        lines.append(f"  • {title}")
    lines += [
        "Hops traversed         : 4",
        f"Confidence             : {confidence}",
    ]
    return "\n".join(lines)
