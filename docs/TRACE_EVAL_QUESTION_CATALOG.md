# Phase 8 question catalog

Six narrow, typed judgments about one completed agent trace. Each is asked independently, one call per (packet, judge). No question asks for an explanation, a rationale or an overall quality score, and
there is deliberately no combined "trace quality" number. The wording is versioned in `agent/trace_eval_v2/questions.py`; a change is a new version, never an edit.

Jev and the LLM judge receive the same instructions, the same yes/no meanings (Noul) or option descriptions (Choice), and the same packet. Only the API envelope differs. For a Noul question P(yes) is the
probability of the condition the question names: J1 and J5 name a good property (supported, consistent), J2 to J4 a problem.

## The packet (`trace_projection_v1`)

`agent_instructions`, `available_tools`, `case_as_reported` (the ticket), `investigation` (per diagnostic step: tool, arguments, outcome, compact result, returned evidence, the hypotheses the agent restated;
plus invalid-tool events, repair events, budget and stop reason), `final_output` (hypotheses with status and citations, structured predictions and their confidences with nulls left visible, overall
confidence, claimed evidence sufficiency, review flag, next action, evidence summary, unresolved uncertainties, cited-but-never-retrieved evidence), and `available_evidence_inventory` (the observable evidence the
agent's tools could return by the end of its run, each item flagged `retrieved_by_agent` and `first_retrieved_at_step`). Every internal id is an opaque alias (`SIG_`, `CHG_`, `CMP_` and so on, derived from a hash;
no order, number, time or role is encoded). Event types, timestamps, components and text are unchanged. Steps keep their order and clocks, so a judge can see what the agent knew and when.
Typical size: 2,000 to 3,900 tokens.

## Questions

| ID | Version | Primitive | Purpose | Reads | Interpretation | Known failure modes |
|---|---|---|---|---|---|---|
| J1 | `trace_support_v1` | Noul | Does the retrieved evidence support the final conclusion (support, not correctness)? | steps, final output | high P(yes) = supported | Jev over-calls support (recall 0.88, precision 0.11 at 0.5); neither judge orders SUPPORTED > PARTIAL > UNSUPPORTED reliably; the reference is lexical |
| J2 | `missed_evidence_v1` | Noul | Was important available evidence never retrieved? | steps, inventory | high P(yes) = important evidence missed | false alarms on unretrieved but irrelevant items (32 for Jev); the response to removing one of several critical items is small |
| J3 | `distractor_anchor_v1` | Noul | Did the agent over-weight weak evidence against stronger evidence? | steps, final output, inventory | high P(yes) = anchored | poorly calibrated (over-predicts yes); does not react to a distractor being made more prominent |
| J4 | `premature_close_v1` | Noul | Did the agent commit before gathering enough evidence or resolving competing hypotheses? | steps, final output, inventory | high P(yes) = premature | equals a simple observable rule; the LLM answers yes almost always |
| J5 | `final_consistency_v2` | Noul | Is the final answer consistent with what was retrieved and stated? (`_v1` was reworded once after Stage A) | steps, final output | high P(yes) = consistent | Jev over-alarms (61 false inconsistency alarms); a deterministic checker is exact |
| J6 | `human_review_v1` | Choice | Should a person review this before it is trusted? AUTO_CLOSE / HUMAN_REVIEW / PRIORITY_REVIEW | everything | argmax tier; Jev also gives probabilities | never chose AUTO_CLOSE (0 of 150); cannot identify clean traces; separates PRIORITY from HUMAN only moderately |

Full wording, options and yes/no definitions: `agent/trace_eval_v2/questions.py`. The superseded `final_consistency_v1` wording is kept in `SUPERSEDED_WORDING`.

## Deterministic references and baselines

Each judgment's reference label and rule: [TRACE_EVAL_REFERENCE_LABELS.md](TRACE_EVAL_REFERENCE_LABELS.md). Observable-only baselines used for comparison: J1 the J1 rule without hidden conditions; J2 "an unretrieved signal, change or
deployment exists"; J3 the majority answer; J4 "committed and (an unretrieved item exists or two hypotheses tie)"; J5 the J5 rule itself; J6 the agent's own review flag and an "any observable defect" rule.
