"""Loads the support ticket for a case: the base case fields that exist before any retrieval. This is a single case-record read (the same record the agent's harness
shows as step 1); it is NOT a diagnostic retrieval tool, and it returns names and text only (no case, customer or product ids)."""
from agent.agent_v2.tools import q_case_context

TICKET_FIELDS = ("title", "description", "environment", "region", "priority", "reported_business_impact", "reported_affected_users", "created_date",
                 "customer_tier", "customer_industry", "customer_company_size", "reported_product_name", "reported_symptoms")


def load_ticket(session, case_id: str) -> dict:
    ctx = q_case_context(session, case_id)
    if "error" in ctx:
        raise ValueError(ctx["error"])
    return {k: ctx.get(k) for k in TICKET_FIELDS}
