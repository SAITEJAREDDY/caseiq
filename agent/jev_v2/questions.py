"""The versioned question catalog (spec section 6). One entry per decision
type; wording is frozen once an experiment has run against it (spec
section 6's "do not overwrite question definitions after experiments
exist -- create a new version") -- bump the key in
agent.jev_v2.config.QUESTION_VERSIONS and add a new wording variant below
rather than editing an existing one in place.
"""
from agent.jev_v2.client import choice_question, noul_question
from agent.jev_v2.config import QUESTION_VERSIONS

QUESTIONS = {
    "issue_category": {
        "version": QUESTION_VERSIONS["issue_category"],
        "primitive": "choice",
        "instructions": "Based only on the observable case state, which issue category best describes the current problem?",
    },
    "root_cause": {
        "version": QUESTION_VERSIONS["root_cause"],
        "primitive": "choice",
        "instructions": "Which root-cause family best explains the observable evidence currently available? "
        "If the evidence does not clearly point to one, choose the option indicating insufficient information "
        "rather than guessing.",
    },
    "causal_change": {
        "version": QUESTION_VERSIONS["causal_change"],
        "primitive": "choice",
        "instructions": "Which, if any, of these recent changes is most likely causally related to the observed "
        "incident? Recency alone is not evidence of causation -- consider the change's type, affected component, "
        "and relationship to the reported symptoms. Choose the 'none' option if no listed change appears causally "
        "related.",
    },
    "owning_team": {
        "version": QUESTION_VERSIONS["owning_team"],
        "primitive": "choice",
        "instructions": "Given the case and the currently available evidence, which team should own the next "
        "stage of investigation?",
    },
    "evidence_sufficiency": {
        "version": QUESTION_VERSIONS["evidence_sufficiency"],
        "primitive": "choice",
        "instructions": "Classify the diagnostic evidence visible at this snapshot. Choose 'sufficient' when "
        "the observable signals, recent changes, or abnormal telemetry provide a concrete basis to proceed with "
        "a supported diagnosis; choose 'partially_sufficient' when relevant indicators exist but are still "
        "ambiguous; choose 'insufficient' when the visible evidence is too limited or inconclusive. Do not require "
        "certainty or a fully proven root cause before choosing 'sufficient'.",
    },
    "incident_relationship": {
        "version": QUESTION_VERSIONS["incident_relationship"],
        "primitive": "noul",
        "instructions": "Is this case materially explained by the candidate active incident described in "
        "'candidate_incident'? A time or region overlap alone is not sufficient -- judge whether the incident "
        "actually accounts for the customer's reported symptoms.",
    },
}


def build_question(decision_type: str, candidates: dict = None) -> dict:
    spec = QUESTIONS[decision_type]
    if spec["primitive"] == "choice":
        return choice_question(spec["instructions"], candidates)
    if spec["primitive"] == "noul":
        return noul_question(spec["instructions"])
    raise ValueError(f"unsupported primitive for {decision_type}: {spec['primitive']}")


def question_version(decision_type: str) -> str:
    return QUESTIONS[decision_type]["version"]


def primitive_type(decision_type: str) -> str:
    return QUESTIONS[decision_type]["primitive"]
