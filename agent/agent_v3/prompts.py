"""Versioned prompts for the contract-hardened agent (`PROMPT_VERSION`). Deliberately short: the contract is carried by the tool catalog,
the enumerated schemas and the deterministic validators, not by prose. Nothing here was written from a wrong diagnosis, a missed root cause
or a hidden label; every rule answers an observed protocol failure (phantom tools, component tools called before a component was known,
final answers that ignored their schema, free-text ids the model was never shown).
"""
import json

from agent.agent_v3.catalog import TOOLS_BY_NAME, catalog_text
from agent.agent_v3.config import MAX_TOOL_CALLS
from agent.agent_v3.registry import CITABLE_KINDS, ObservedEntityRegistry

SYSTEM_TEMPLATE = """You are CaseIQ's diagnostic agent. You investigate one support case using ONLY the registered tools below. \
Every reply is one JSON object that follows the schema supplied with the request.

Protocol
1. Investigation. Each turn choose ONE tool and its arguments; set every argument the tool does not take to null. Tool results contain \
only aliases such as COMPONENT_XXX. Use aliases exactly as shown in the registry. Never write an internal id, and never write an alias \
that is not in the registry. There is no raw-log search, metrics query or customer-account tool: use only the tools listed.
2. Hypothesis state. Every turn restate ALL your current hypotheses: label, confidence (0-1), status (active, rejected or confirmed), and \
the evidence aliases from the ledger that support or contradict each one. State at least one hypothesis every turn, starting with your first, \
even a low-confidence one; the list may never be empty. Leave the citation lists empty until evidence supports or contradicts it.
3. Finalization. Choose submit_diagnosis when you can conclude, when the evidence is insufficient, or when a person should review. You will \
then be asked for the structured diagnosis.
4. Uncertainty. A null selection is the correct answer when the evidence does not justify one. Do not guess. Insufficient evidence and human \
review are legitimate outcomes.
5. Evidence. Cite only evidence in the ledger (items you retrieved). Tool results are not labelled relevant or causal: some items are noise, \
distractors or contradictory. Time proximity does not imply causation, an overlapping incident may be unrelated, and a similar case's \
outcome does not prove this case's answer.
You have a limited number of tool calls; pick the tool most likely to move the investigation forward.

Tool catalog
{catalog}
"""


def system_prompt() -> str:
    return SYSTEM_TEMPLATE.format(catalog=catalog_text())


def _line(e) -> str:
    name = f" = {e.display_name}" if e.display_name else ""
    return f"{e.alias}{name}"


def render_registry(registry: ObservedEntityRegistry, *, taxonomy: bool) -> str:
    out = []
    for title, kind in (("Products", "PRODUCT"), ("Components", "COMPONENT"), ("Teams", "TEAM")):
        ents = registry.by_kind(kind)
        if ents:
            out.append(f"{title}: " + "; ".join(_line(e) for e in ents))
    if not out:
        out.append("(no products, components or teams observed yet)")
    if taxonomy:
        out.append("Issue categories (for issue_category):\n" + "\n".join(_line(e) for e in registry.by_kind("CATEGORY")))
        out.append("Root causes (for root_cause):\n" + "\n".join(_line(e) for e in registry.by_kind("CAUSE")))
    return "\n".join(out)


def render_ledger(registry: ObservedEntityRegistry) -> str:
    ents = registry.by_kind(*CITABLE_KINDS)
    if not ents:
        return "(no evidence retrieved yet)"
    return "\n".join(f"{e.alias} | {e.type} | step {e.first_observed_step} | {e.summary}" for e in ents)


def render_hypotheses(hyps: list) -> str:
    if not hyps:
        return "(none stated yet)"
    return "\n".join(f"- {h['label']} (confidence {h['confidence']}, {h['status']}) supports {h['supporting_evidence']} "
                     f"contradicts {h['contradicting_evidence']}" for h in hyps)


def _state(case_report: dict, registry, history: list, hyps: list, *, taxonomy: bool) -> str:
    return (f"CASE REPORT\n{json.dumps(case_report, default=str)}\n\nREGISTRY (use these aliases exactly)\n{render_registry(registry, taxonomy=taxonomy)}\n\n"
            f"EVIDENCE LEDGER (retrieved so far)\n{render_ledger(registry)}\n\nCALLS SO FAR\n" + "\n".join(history) +
            f"\n\nYOUR CURRENT HYPOTHESES\n{render_hypotheses(hyps)}")


def _feedback_block(feedback: str) -> str:
    return f"\n\nVERIFICATION FEEDBACK (from the runtime verifier)\n{feedback}" if feedback else ""


def _triage_block(triage_hint: str) -> str:
    """The provisional early-triage hint (agent_v3/triage_hint.py). Empty when there is no usable hint, which leaves every prompt unchanged."""
    return f"\n\n{triage_hint}" if triage_hint else ""


def step_messages(case_report: dict, registry, history: list, hyps: list, latest: dict, next_step: int, error_note: str = "", feedback: str = "",
                  budget: int = MAX_TOOL_CALLS, triage_hint: str = "") -> list:
    body = _state(case_report, registry, history, hyps, taxonomy=False) + _triage_block(triage_hint)
    if latest is not None:
        body += f"\n\nLATEST RESULT (step {latest['step']}, {latest['tool']})\n{json.dumps(latest['result'], default=str)}"
    body += _feedback_block(feedback)
    body += f"\n\nStep {next_step} of {budget}. Choose the next tool."
    if error_note:
        body += "\n\n" + error_note
    return [{"role": "system", "content": system_prompt()}, {"role": "user", "content": body}]


def tool_error_note(errors: list, available: list) -> str:
    return ("CONTRACT ERROR: your previous reply was rejected and nothing was executed. Errors: "
            f"{json.dumps(errors)}. Tools available now: {available}. Reply again with a valid object.")


FINAL_RULES = """FINALIZATION. Produce the structured diagnosis for this case now.
- status: DIAGNOSIS_PROPOSED needs at least one non-rejected hypothesis with supporting evidence and evidence_sufficiency other than \
insufficient. INSUFFICIENT_EVIDENCE may leave every selection null. HUMAN_REVIEW_REQUIRED needs human_review_required true and a review_reason.
- Each selection (issue_category, root_cause, affected_component, causal_change, owning_team) is an alias from the registry or null. Set its \
confidence when you select it, and leave the confidence null when the selection is null.
- evidence_ids must list every evidence alias cited by any hypothesis, plus the causal_change if you select one. Cite only ledger items.
- hypotheses may not be empty: keep at least one, with its status and confidence.
- Write no internal ids. Free text may mention aliases that exist in the registry."""


def final_messages(case_report: dict, registry, history: list, hyps: list, *, forced: bool, error_note: str = "", feedback: str = "", triage_hint: str = "") -> list:
    body = _state(case_report, registry, history, hyps, taxonomy=True) + _triage_block(triage_hint) + _feedback_block(feedback)
    if forced:
        body += "\n\nThe investigation budget is exhausted."
    body += "\n\n" + FINAL_RULES
    if error_note:
        body += "\n\n" + error_note
    return [{"role": "system", "content": system_prompt()}, {"role": "user", "content": body}]


def final_error_note(errors: list) -> str:
    return ("CONTRACT ERROR: your previous final answer failed validation. Errors: "
            f"{json.dumps(errors)}. Return a corrected object that follows the schema and the rules above. This is your only correction.")


assert "submit_diagnosis" in TOOLS_BY_NAME
