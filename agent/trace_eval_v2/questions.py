"""The six versioned Phase 8 judgments (spec sections 11 to 14, 45).

Each judgment is a narrow, typed question about one completed trace, asked independently of the others. No question asks for an explanation, a rationale or
a score for "overall quality", and none asks for hidden truth. The wording is frozen once an experiment has run against it: a change is a new version, never an
edit. Jev and the LLM judge receive exactly these instructions, options and yes/no definitions; only the API envelope differs.

Orientation. For the five Noul judgments, P(yes) is the probability of the condition the question names. J1 and J5 name a GOOD property (supported, consistent);
J2 to J4 name a PROBLEM (missed evidence, anchoring, premature close). J6 is a Choice among three review tiers.

Nothing here imports hidden truth.
"""
from agent.jev_v2.client import choice_question, noul_question
from agent.trace_eval_v2.config import JUDGMENT_IDS, QUESTION_VERSIONS

REVIEW_OPTIONS = {
    "AUTO_CLOSE": "The investigation and its conclusion are sound enough to accept without a person reviewing them.",
    "HUMAN_REVIEW": "A person should review the result before it is trusted or acted on.",
    "PRIORITY_REVIEW": "A person should review the result urgently: it is likely wrong, unsupported, or unsafe to act on.",
}

QUESTIONS = {
    "support": {
        "version": QUESTION_VERSIONS["support"], "primitive": "noul",
        "instructions": "Judge only from this completed investigation. Does the evidence the agent actually retrieved during the investigation support the agent's final conclusion? "
                        "Answer yes if the retrieved evidence gives a reasonable, relevant basis for the final conclusion, even if the conclusion might still turn out to be wrong. "
                        "Answer no if the conclusion rests on nothing the agent retrieved, cites evidence it never retrieved, or is unrelated to what it retrieved. "
                        "This question is about support, not about whether the conclusion is correct.",
        "yes": "The retrieved evidence supports the final conclusion.",
        "no": "The retrieved evidence does not support the final conclusion.",
    },
    "missed_evidence": {
        "version": QUESTION_VERSIONS["missed_evidence"], "primitive": "noul",
        "instructions": "Judge from this investigation and the inventory of evidence that was available to the agent's tools. Does the investigation omit important available evidence "
                        "that should materially affect the conclusion? Answer yes only if some available evidence the agent never retrieved looks materially relevant to the reported problem "
                        "and to the agent's hypotheses (consider its type, timing, component and content). Ignore unretrieved items that look unrelated to the case.",
        "yes": "Important available evidence was never retrieved.",
        "no": "No important available evidence was left unretrieved.",
    },
    "distractor_anchor": {
        "version": QUESTION_VERSIONS["distractor_anchor"], "primitive": "noul",
        "instructions": "Judge from this investigation and the inventory of available evidence. Did the agent over-weight a plausible but weak or irrelevant piece of evidence while failing to "
                        "sufficiently account for stronger competing evidence? Examples: a recent but unrelated change, a coincidental incident, noisy telemetry, a customer's mistaken assumption, "
                        "a dependency that looks suspicious but is not the cause. Answer yes only if the conclusion appears anchored on such evidence rather than on the stronger evidence.",
        "yes": "The agent anchored on plausible but weak or irrelevant evidence.",
        "no": "The agent did not anchor on weak or irrelevant evidence.",
    },
    "premature_close": {
        "version": QUESTION_VERSIONS["premature_close"], "primitive": "noul",
        "instructions": "Judge the agent's investigative behaviour: what it had gathered when it concluded. Did the agent commit to a diagnosis before gathering enough relevant evidence, or before "
                        "resolving important competing hypotheses or contradictions visible in the trace? A short investigation can still be complete if it retrieved what mattered. "
                        "If the agent itself flagged insufficient evidence or asked for review, that is not premature commitment. If it was stopped by the tool budget rather than choosing to conclude, that is not premature commitment either.",
        "yes": "The agent committed to a diagnosis too early.",
        "no": "The agent did not commit too early.",
    },
    "final_consistency": {
        "version": QUESTION_VERSIONS["final_consistency"], "primitive": "noul",
        "instructions": "Is the agent's final answer consistent with the evidence it retrieved and the hypotheses it stated during the investigation? Check exactly these four things. "
                        "(1) Does the final answer cite evidence that was never retrieved? "
                        "(2) Is the final top hypothesis one that the agent never stated at any step and that no retrieved evidence relates to? "
                        "(3) Is the stated overall confidence far above the top hypothesis' own confidence, or 0.8 or higher despite the agent's own stated uncertainty or claim of insufficient evidence, "
                        "or does the answer claim insufficient evidence without asking for review? "
                        "(4) Is a structured prediction filled in without its confidence? "
                        "Answer no if any of these holds and yes if none does. Empty or missing fields are not by themselves inconsistent, and a hypothesis the agent revised after seeing new evidence is not inconsistent.",
        "yes": "The final answer is consistent with the investigation.",
        "no": "The final answer is inconsistent with the investigation.",
    },
    "human_review": {
        "version": QUESTION_VERSIONS["human_review"], "primitive": "choice",
        "instructions": "Based only on this completed investigation, should a person review the result before it is trusted or acted on? Weigh whether the conclusion is supported, whether "
                        "important evidence was missed or misweighted, whether the agent concluded too early, whether the final answer is consistent and complete, and whether the run had "
                        "tool or contract problems. Choose exactly one option.",
        "options": REVIEW_OPTIONS,
    },
}


# Wording superseded during the Stage A correction pass (kept for the record; never sent after the correction).
SUPERSEDED_WORDING = {
    "final_consistency_v1": "Is the agent's final answer consistent with the evidence it retrieved and the hypotheses it stated during the investigation? Answer no if, for example, the final answer "
                            "cites evidence that was never retrieved, arrives at a top hypothesis its own last stated hypotheses and evidence do not lead to, expresses confidence that its own stated "
                            "uncertainty contradicts, or fills structured fields inconsistently.",
}


def question_version(judgment: str) -> str:
    return QUESTIONS[judgment]["version"]


def primitive(judgment: str) -> str:
    return QUESTIONS[judgment]["primitive"]


def jev_question(judgment: str) -> dict:
    """The Jev API question object."""
    spec = QUESTIONS[judgment]
    if spec["primitive"] == "noul":
        return noul_question(spec["instructions"], {"true": spec["yes"], "false": spec["no"]})
    return choice_question(spec["instructions"], dict(spec["options"]))


def catalog_rows() -> list:
    return [{"id": JUDGMENT_IDS[j], "judgment": j, "version": s["version"], "primitive": s["primitive"]} for j, s in QUESTIONS.items()]
