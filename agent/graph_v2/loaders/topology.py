"""Product versions, customer deployments, and the component dependency
graph -- all purely structural/observable, no case-specific judgment.
"""
from agent.graph_v2.config import DATA_PHASE2
from agent.graph_v2.db import read_csv, run_batched


def load(session):
    _load_product_versions(session)
    _load_component_dependencies(session)
    _load_customer_deployments(session)


def _load_product_versions(session):
    rows = read_csv(DATA_PHASE2 / "product_versions.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (v:ProductVersion {id: r.id})
        SET v.product_id = r.product_id,
            v.version = r.version,
            v.release_date = r.release_date,
            v.is_current = (r.is_current = 'true')
        WITH v, r
        MATCH (p:Product {id: r.product_id})
        MERGE (p)-[:HAS_VERSION]->(v)
        """,
        "ProductVersion",
    )


def _load_component_dependencies(session):
    rows = read_csv(DATA_PHASE2 / "component_dependencies.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (c1:Component {id: r.component_id})
        MATCH (c2:Component {id: r.depends_on_component_id})
        MERGE (c1)-[rel:DEPENDS_ON]->(c2)
        SET rel.dependency_type = r.dependency_type, rel.weight = toFloat(r.weight)
        """,
        "Component-DEPENDS_ON",
    )


def _load_customer_deployments(session):
    rows = read_csv(DATA_PHASE2 / "customer_deployments.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (cust:Customer {id: r.customer_id})
        MATCH (v:ProductVersion {id: r.product_version_id})
        MERGE (cust)-[rel:DEPLOYED {id: r.id}]->(v)
        SET rel.environment = r.environment,
            rel.region = r.region,
            rel.deployed_at = r.deployed_at,
            rel.status = r.status
        """,
        "Customer-DEPLOYED",
    )
