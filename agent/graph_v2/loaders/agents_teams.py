"""Agent/Team roster: nodes, skills, memberships, expertise, capacity."""
from agent.graph_v2.config import DATA_PHASE2, DATA_RAW_V2
from agent.graph_v2.db import read_csv, run_batched


def load(session):
    _load_agents(session)
    _load_agent_teams(session)
    _load_agent_skills(session)
    _load_agent_products(session)
    _load_agent_components(session)
    _load_agent_category_experience(session)
    _load_agent_capacity(session)
    _load_agent_schedule(session)


def _load_agents(session):
    rows = read_csv(DATA_RAW_V2 / "agents.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MERGE (n:Agent {id: r.id})
        SET n.name = r.name,
            n.seniority = r.seniority,
            n.avg_resolution_time_hours = toFloat(r.avg_resolution_time_hours),
            n.historical_case_volume = toInteger(r.historical_case_volume)
        WITH n, r
        MATCH (t:Team {id: r.primary_team_id})
        MERGE (n)-[:MEMBER_OF {role: 'primary'}]->(t)
        """,
        "Agent",
    )


def _load_agent_teams(session):
    rows = read_csv(DATA_RAW_V2 / "agent_teams.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (t:Team {id: r.team_id})
        MERGE (a)-[:MEMBER_OF]->(t)
        """,
        "Agent-MEMBER_OF",
    )


def _load_agent_skills(session):
    rows = read_csv(DATA_RAW_V2 / "agent_skills.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (s:Skill {id: r.skill_id})
        MERGE (a)-[rel:HAS_SKILL]->(s)
        SET rel.proficiency = r.proficiency
        """,
        "Agent-HAS_SKILL",
    )


def _load_agent_products(session):
    rows = read_csv(DATA_RAW_V2 / "agent_products.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (p:Product {id: r.product_id})
        MERGE (a)-[:SUPPORTS_PRODUCT]->(p)
        """,
        "Agent-SUPPORTS_PRODUCT",
    )


def _load_agent_components(session):
    rows = read_csv(DATA_RAW_V2 / "agent_components.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (c:Component {id: r.component_id})
        MERGE (a)-[:SUPPORTS_COMPONENT]->(c)
        """,
        "Agent-SUPPORTS_COMPONENT",
    )


def _load_agent_category_experience(session):
    rows = read_csv(DATA_RAW_V2 / "agent_issue_category_experience.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        MATCH (c:IssueCategory {id: r.category_id})
        MERGE (a)-[rel:HAS_EXPERIENCE]->(c)
        SET rel.case_count = toInteger(r.case_count)
        """,
        "Agent-HAS_EXPERIENCE",
    )


def _load_agent_capacity(session):
    rows = read_csv(DATA_PHASE2 / "agent_capacity.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        SET a.max_concurrent_cases = toInteger(r.max_concurrent_cases),
            a.weekly_capacity_hours = toFloat(r.weekly_capacity_hours),
            a.current_utilization_pct = toFloat(r.current_utilization_pct)
        """,
        "Agent capacity properties",
    )


def _load_agent_schedule(session):
    rows = read_csv(DATA_PHASE2 / "agent_schedule.csv")
    run_batched(
        session, rows,
        """
        UNWIND $rows AS r
        MATCH (a:Agent {id: r.agent_id})
        MERGE (sh:AgentShift {id: r.id})
        SET sh.day_of_week = r.day_of_week,
            sh.shift_start_hour = toInteger(r.shift_start_hour),
            sh.shift_end_hour = toInteger(r.shift_end_hour)
        MERGE (a)-[:HAS_SHIFT]->(sh)
        """,
        "AgentShift",
    )
