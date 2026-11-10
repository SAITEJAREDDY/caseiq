"""KnowledgeArticle nodes and their own authored coverage edges. These are
population-level facts about what a KB article covers/discusses -- never a
case-specific "this article solves this case" assertion (that only enters
the graph via a Case's own kb_interactions record, loaded in investigation.py).
"""
from agent.graph_v2.config import DATA_RAW_V2
from agent.graph_v2.db import read_csv, run_batched


def load(session):
    _load_articles(session)
    _load_coverage(session, "article_components.csv", "component_id", "Component", "COVERS_COMPONENT")
    _load_coverage(session, "article_issue_categories.csv", "category_id", "IssueCategory", "COVERS_CATEGORY")
    _load_coverage(session, "article_issue_subcategories.csv", "subcategory_id", "IssueSubcategory", "COVERS_SUBCATEGORY")
    _load_coverage(session, "article_products.csv", "product_id", "Product", "COVERS_PRODUCT")
    _load_coverage(session, "article_resolutions.csv", "resolution_type_id", "ResolutionType", "COVERS_RESOLUTION_TYPE")
    _load_coverage(session, "article_root_causes.csv", "root_cause_id", "RootCauseFamily", "COVERS_ROOT_CAUSE")
    _load_coverage(session, "article_symptoms.csv", "symptom_id", "Symptom", "COVERS_SYMPTOM")


def _load_articles(session):
    rows = read_csv(DATA_RAW_V2 / "knowledge_articles.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:KnowledgeArticle {id: r.id})
        SET n.title = r.title,
            n.content_summary = r.content_summary,
            n.specificity = r.specificity,
            n.resolution_rate = toFloat(r.resolution_rate),
            n.views = toInteger(r.views),
            n.created_date = r.created_date,
            n.outdated = (r.outdated = 'true')
        """,
        "KnowledgeArticle",
    )


def _load_coverage(session, fname, target_col, target_label, rel_type):
    rows = read_csv(DATA_RAW_V2 / fname)
    cypher = f"""
    UNWIND $rows AS r
    MATCH (a:KnowledgeArticle {{id: r.article_id}})
    MATCH (t:{target_label} {{id: r.{target_col}}})
    MERGE (a)-[:{rel_type}]->(t)
    """
    run_batched(session, rows, cypher, f"KnowledgeArticle-{rel_type}")
