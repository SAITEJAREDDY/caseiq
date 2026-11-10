"""Read-only tool backend for the Phase 9A agent: the frozen Phase 5 query functions (`agent.agent_v2.tools.q_*`), unchanged, plus two
standing-taxonomy reads. Every statement is MATCH/RETURN; `as_of` is supplied by the harness clock, never by the model."""
from agent.agent_v2 import tools as t


class Neo4jBackend:
    def __init__(self, session, case_id: str):
        self.session, self.case_id = session, case_id

    def case_context(self) -> dict:
        return t.q_case_context(self.session, self.case_id)

    def execute(self, tool: str, a: dict, as_of: str) -> dict:
        s, cid, comp = self.session, self.case_id, a.get("component_id")
        if tool == "get_customer_deployment":
            return t.q_customer_deployment(s, cid)
        if tool == "get_component_topology":
            return t.q_component_topology(s, comp)
        if tool == "get_technical_signals":
            return t.q_technical_signals(s, cid, as_of, comp)
        if tool == "get_telemetry":
            return t.q_telemetry(s, cid, as_of, a.get("metric_category"), comp)
        if tool == "get_recent_changes":
            return t.q_recent_changes(s, cid, as_of, comp)
        if tool == "get_deployment_history":
            return t.q_deployment_history(s, cid, as_of, comp)
        if tool == "get_configuration_history":
            return t.q_configuration_history(s, cid, as_of, comp)
        if tool == "get_service_health":
            return t.q_service_health(s, comp, as_of)
        if tool == "get_active_incidents":
            return t.q_active_incidents(s, cid, as_of)
        if tool == "get_similar_cases":
            return t.q_similar_cases(s, cid, as_of)
        if tool == "search_knowledge_base":
            return t.q_search_kb(s, a.get("keyword"), comp, None)
        if tool == "get_team_capability":
            return t.q_team_capability(s, component_id=comp)
        if tool == "get_agent_availability":
            return t.q_agent_availability(s, a["team_id"])
        raise ValueError(f"backend has no implementation for {tool!r}")

    def taxonomy(self) -> tuple:
        """Standing reference vocabulary (every case sees the same list): issue categories and root-cause families."""
        cats = [(r["id"], r["name"]) for r in self.session.run("MATCH (c:IssueCategory) RETURN c.id AS id, c.name AS name ORDER BY c.id")]
        causes = [(r["id"], r["name"]) for r in self.session.run("MATCH (r:RootCauseFamily) RETURN r.id AS id, r.name AS name ORDER BY r.id")]
        return cats, causes

    def component_names(self, ids: list) -> dict:
        rows = self.session.run("MATCH (c:Component) WHERE c.id IN $ids RETURN c.id AS id, c.name AS name", ids=ids)
        return {r["id"]: r["name"] for r in rows}
