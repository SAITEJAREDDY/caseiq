"""Reference/taxonomy nodes and their population-level association edges.
Always loaded in full -- small, static, the shared "world" every case sits
in. No per-case data here.
"""
from agent.graph_v2.config import DATA_PHASE2, DATA_RAW_V2
from agent.graph_v2.db import read_csv, run_batched


def load(session):
    _load_issue_categories(session)
    _load_issue_subcategories(session)
    _load_symptoms(session)
    _load_teams(session)
    _load_skills(session)
    _load_products(session)
    _load_components(session)
    _load_root_cause_families(session)
    _load_resolution_types(session)
    _load_support_plans(session)
    _load_sla_policies(session)
    _load_external_services(session)
    _load_product_components(session)
    _load_component_teams(session)
    _load_product_teams(session)
    _load_subcategory_associations(session)
    _load_root_cause_resolutions(session)
    _load_external_dependency_links(session)


def _load_issue_categories(session):
    rows = read_csv(DATA_RAW_V2 / "issue_categories.csv")
    run_batched(
        session, rows,
        "UNWIND $rows AS r MERGE (n:IssueCategory {id: r.id}) SET n.name = r.name",
        "IssueCategory",
    )


def _load_issue_subcategories(session):
    rows = read_csv(DATA_RAW_V2 / "issue_subcategories.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:IssueSubcategory {id: r.id})
        SET n.name = r.name
        WITH n, r
        MATCH (c:IssueCategory {id: r.category_id})
        MERGE (n)-[:BELONGS_TO]->(c)
        """,
        "IssueSubcategory",
    )


def _load_symptoms(session):
    rows = read_csv(DATA_RAW_V2 / "symptoms.csv")
    run_batched(session, rows, "UNWIND $rows AS r MERGE (n:Symptom {id: r.id}) SET n.name = r.name", "Symptom")


def _load_teams(session):
    rows = read_csv(DATA_RAW_V2 / "teams.csv")
    run_batched(
        session, rows,
        "UNWIND $rows AS r MERGE (n:Team {id: r.id}) SET n.name = r.name, n.description = r.description",
        "Team",
    )


def _load_skills(session):
    rows = read_csv(DATA_RAW_V2 / "skills.csv")
    run_batched(
        session, rows,
        "UNWIND $rows AS r MERGE (n:Skill {id: r.id}) SET n.name = r.name, n.category = r.category",
        "Skill",
    )


def _load_products(session):
    rows = read_csv(DATA_RAW_V2 / "products.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:Product {id: r.id})
        SET n.name = r.name, n.category = r.category, n.version = r.version
        """,
        "Product",
    )


def _load_components(session):
    rows = read_csv(DATA_RAW_V2 / "components.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:Component {id: r.id})
        SET n.name = r.name, n.origin_product_category = r.origin_product_category
        """,
        "Component",
    )


def _load_root_cause_families(session):
    rows = read_csv(DATA_RAW_V2 / "root_causes.csv")
    run_batched(
        session, rows,
        "UNWIND $rows AS r MERGE (n:RootCauseFamily {id: r.id}) SET n.name = r.name",
        "RootCauseFamily",
    )


def _load_resolution_types(session):
    rows = read_csv(DATA_RAW_V2 / "resolution_types.csv")
    run_batched(
        session, rows,
        "UNWIND $rows AS r MERGE (n:ResolutionType {id: r.id}) SET n.name = r.name",
        "ResolutionType",
    )


def _load_support_plans(session):
    rows = read_csv(DATA_PHASE2 / "support_plans.csv")
    run_batched(session, rows, "UNWIND $rows AS r MERGE (n:SupportPlan {id: r.id}) SET n.name = r.name", "SupportPlan")


def _load_sla_policies(session):
    rows = read_csv(DATA_PHASE2 / "sla_policies.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:SLAPolicy {id: r.id})
        SET n.severity = r.severity,
            n.response_time_minutes = toInteger(r.response_time_minutes),
            n.resolution_time_hours = toFloat(r.resolution_time_hours)
        WITH n, r
        MATCH (p:SupportPlan {id: r.support_plan_id})
        MERGE (p)-[:HAS_SLA]->(n)
        """,
        "SLAPolicy",
    )


def _load_external_services(session):
    rows = read_csv(DATA_PHASE2 / "external_dependencies.csv")
    run_batched(
        session, rows,
        "UNWIND $rows AS r MERGE (n:ExternalService {id: r.id}) SET n.name = r.name, n.domain = r.domain",
        "ExternalService",
    )


def _load_external_dependency_links(session):
    rows = read_csv(DATA_PHASE2 / "external_dependency_links.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Component {id: r.component_id})
        MATCH (e:ExternalService {id: r.external_dependency_id})
        MERGE (c)-[:DEPENDS_ON_EXTERNAL]->(e)
        """,
        "DEPENDS_ON_EXTERNAL",
    )


def _load_product_components(session):
    rows = read_csv(DATA_RAW_V2 / "product_components.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (p:Product {id: r.product_id})
        MATCH (c:Component {id: r.component_id})
        MERGE (p)-[:HAS_COMPONENT]->(c)
        """,
        "Product-HAS_COMPONENT",
    )


def _load_component_teams(session):
    rows = read_csv(DATA_RAW_V2 / "component_teams.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c:Component {id: r.component_id})
        MATCH (t:Team {id: r.team_id})
        MERGE (c)-[rel:SUPPORTED_BY]->(t)
        SET rel.role = r.role, rel.weight = toFloat(r.weight)
        """,
        "Component-SUPPORTED_BY",
    )


def _load_product_teams(session):
    rows = read_csv(DATA_RAW_V2 / "product_teams.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (p:Product {id: r.product_id})
        MATCH (t:Team {id: r.team_id})
        MERGE (p)-[rel:SUPPORTED_BY]->(t)
        SET rel.role = r.role, rel.weight = toFloat(r.weight)
        """,
        "Product-SUPPORTED_BY",
    )


def _load_subcategory_associations(session):
    # (IssueSubcategory)-[:TYPICALLY_*]->(...) {weight} -- population-level
    # taxonomy facts (e.g. "this subcategory is typically caused by X 30% of
    # historical cases"), never a case-specific truth assertion.
    specs = [
        ("issue_subcategory_components.csv", "Component", "TYPICALLY_INVOLVES_COMPONENT"),
        ("issue_subcategory_root_causes.csv", "RootCauseFamily", "TYPICALLY_CAUSED_BY"),
        ("issue_subcategory_skills.csv", "Skill", "TYPICALLY_REQUIRES_SKILL"),
        ("issue_subcategory_symptoms.csv", "Symptom", "TYPICALLY_PRESENTS_AS"),
    ]
    id_col = {
        "issue_subcategory_components.csv": "component_id",
        "issue_subcategory_root_causes.csv": "root_cause_id",
        "issue_subcategory_skills.csv": "skill_id",
        "issue_subcategory_symptoms.csv": "symptom_id",
    }
    for fname, target_label, rel_type in specs:
        rows = read_csv(DATA_RAW_V2 / fname)
        target_id = id_col[fname]
        cypher = f"""
        UNWIND $rows AS r
        MATCH (s:IssueSubcategory {{id: r.subcategory_id}})
        MATCH (t:{target_label} {{id: r.{target_id}}})
        MERGE (s)-[rel:{rel_type}]->(t)
        SET rel.weight = toFloat(r.weight)
        """
        run_batched(session, rows, cypher, f"IssueSubcategory-{rel_type}")

    # issue_subcategory_teams.csv has an extra `role` column
    rows = read_csv(DATA_RAW_V2 / "issue_subcategory_teams.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (s:IssueSubcategory {id: r.subcategory_id})
        MATCH (t:Team {id: r.team_id})
        MERGE (s)-[rel:TYPICALLY_OWNED_BY]->(t)
        SET rel.role = r.role, rel.weight = toFloat(r.weight)
        """,
        "IssueSubcategory-TYPICALLY_OWNED_BY",
    )


def _load_root_cause_resolutions(session):
    rows = read_csv(DATA_RAW_V2 / "root_cause_resolutions.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (rc:RootCauseFamily {id: r.root_cause_id})
        MATCH (rt:ResolutionType {id: r.resolution_type_id})
        MERGE (rc)-[rel:TYPICALLY_RESOLVED_BY]->(rt)
        SET rel.weight = toFloat(r.weight)
        """,
        "RootCauseFamily-TYPICALLY_RESOLVED_BY",
    )
