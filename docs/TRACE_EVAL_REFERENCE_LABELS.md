# Phase 8 reference labels (`reference_labels_v1`, `review_policy_v1`)

Jev and the LLM judge are never the ground truth. Both are scored against the deterministic labels defined here. The labels live in evaluation-only code
(`agent/trace_eval_v2/labels.py`), read hidden truth only there, and were written and frozen before the first judge call. Nothing in this file was tuned to any judge's output. A change
to a rule is a new label version, never an edit.

## Common definitions

| Term | Meaning |
|---|---|
| Retrieved | Evidence ids returned by the trace's diagnostic tool calls. |
| Accessible | Evidence the agent's own time-gated tools could return by the end of its run (the *inventory* in the review packet: signals, recent changes, deployments, active incidents, configuration snapshots, read through Phase 5's own query functions). Evidence outside it can never be "missed". |
| Critical | The hidden causal evidence: Phase 3 `critical_evidence_ids`, plus Phase 2 `causal_signal_ids` and `causal_change_id`. |
| Distractors | Hidden known-misleading evidence: Phase 2 `distractor_signal_ids` and `irrelevant_change_ids`. |
| Top hypothesis | The final hypothesis with the highest confidence. |
| Link | The number of content words (three letters or more, minus a short stop list) that the top hypothesis label and description share with an evidence item's own text (its type, message, description). A citation in the final answer counts as a maximal link. |
| Committed | The agent submitted by its own choice, did not flag review, did not claim `insufficient` evidence, and stated overall confidence of 0.5 or more. |

What a judge sees (`trace_projection_v1`): the agent's instructions, the case as reported, every diagnostic step (tool, arguments, outcome, compact result, returned evidence, the hypotheses the agent
restated at that step), invalid-tool and repair events, the final structured answer exactly as the harness validated it (missing fields stay null), and the inventory of available evidence with a
`retrieved_by_agent` flag. Every internal id is an opaque alias. The free-text `rationale` field is not included. Hidden fields, Phase 6 scores and labels never appear.

## J1 conclusion support (`trace_support_v1`, Noul, YES = supported)

- **Target.** Does the retrieved evidence support the final conclusion? Support, not correctness: a wrong conclusion resting on misleading evidence can be supported.
- **Rule.** UNSUPPORTED when there are no final hypotheses, or when no retrieved item is cited or linked to the top hypothesis. SUPPORTED when some retrieved item has a strong tie (cited, or link of 2 or more)
  and every citation was retrieved, and some supporting item is not a known distractor, and, if accessible critical evidence exists, at least half of it was retrieved. PARTIALLY_SUPPORTED otherwise
  (single-word tie only; a citation of never-retrieved evidence; support only from distractors; less than half the critical evidence retrieved).
- **Hidden fields used only for scoring.** Which items are critical and which are distractors.
- **Scoring.** The binary headline is SUPPORTED against UNSUPPORTED; PARTIALLY_SUPPORTED is the ambiguous middle band, excluded from it and reported separately (mean P(yes) by band, and a wider view with the band as positive).
- **Known limits.** The link is lexical: a correct paraphrase with no shared word reads as unsupported. Agents' hypothesis labels are often generic, so UNSUPPORTED is the common class.

## J2 missed critical evidence (`missed_evidence_v1`, Noul, YES = important evidence was missed)

- **Target.** Was important available evidence never retrieved?
- **Rule.** Positive when at least one accessible critical item was never retrieved. If nothing critical is accessible the label is negative (nothing to miss).
- **Hidden fields.** The critical set. Judges see only the inventory, with no marking of which items matter.
- **Known limits.** An unretrieved item counts as missed even if the agent could have judged it irrelevant at the time; the inventory is bounded by the tools' own row limit (8), so an item beyond the limit is not counted as accessible.

## J3 distractor anchoring (`distractor_anchor_v1`, Noul, YES = anchored)

- **Target.** Did the agent over-weight a plausible but weak item while failing to account for stronger evidence?
- **Rule.** Positive when the conclusion's tie (citation or link) to a retrieved known distractor is at least 1 and strictly greater than its tie to any retrieved critical item (which may be absent).
- **Hidden fields.** Distractor and critical sets.
- **Known limits.** Attribution is by shared words, so two items with identical text cannot be told apart from the conclusion's side; the label is conservative where the agent's wording is generic. Natural positives are few.

## J4 premature conclusion (`premature_close_v1`, Noul, YES = committed too early)

- **Target.** Did the agent commit before gathering enough evidence or resolving competition between its own hypotheses?
- **Rule.** Positive when the agent committed (definition above) and either accessible critical evidence had not been retrieved, or its top two hypotheses were within 0.2 of each other with none confirmed.
  Tool-call count is never used. A forced submit at the tool budget is not a choice to conclude, so it is not premature. An agent that flags review or claims insufficient evidence is not premature.
- **Hidden fields.** The critical set (for the gap).
- **Distinct from Phase 7 `evidence_sufficiency`.** That asked about static case-state sufficiency; this asks about the agent's behaviour when it closed.

## J5 final-answer consistency (`final_consistency_v2`, Noul, YES = consistent; the question was reworded once after Stage A, this rule was not)

- **Target.** Is the final answer consistent with the evidence retrieved and the hypotheses stated?
- **Rule.** Consistent unless a violation is found. V1: cites evidence never retrieved. V2: the final top hypothesis is not among the last stated top hypotheses, was never stated at any step,
  and shares no word with any retrieved evidence. V3: overall confidence more than 0.3 above the top hypothesis; confidence of 0.8 or more with unresolved uncertainties or a claimed `insufficient`;
  a claimed `insufficient` with no review request. V4: a structured prediction populated without its confidence.
- **Hidden fields.** None. This label is a function of the observable packet, so it is an intentionally easy control task: an observable rule can match it exactly, and the comparison of interest is
  whether a judge adds anything to code.

## J6 human review (`human_review_v1`, Choice: AUTO_CLOSE / HUMAN_REVIEW / PRIORITY_REVIEW; `review_policy_v1`)

- **PRIORITY_REVIEW** when the result is wrong or unanswered and was stated with overall confidence of 0.8 or more with no review flag (false-confident); or the run failed (fallback diagnosis);
  or a warranted escalation was not flagged on a wrong or unanswered result.
- **HUMAN_REVIEW** when any of: wrong or unanswered result (Phase 6); unsupported conclusion (J1); missed critical evidence (J2); a tool error together with an evidence gap; unresolved competition between hypotheses
  while committed; citation violations, a fallback diagnosis or an inconsistent answer (J5); hidden low evidence availability; a warranted escalation the agent did not flag.
- **AUTO_CLOSE** otherwise.
- **Process-only variant** (secondary, reported beside the full policy): the same rules without the hidden-outcome triggers (wrong result, low evidence, escalation), which is what a reviewer could conclude from the trace's own defects.
- **Not a trigger, on purpose.** The final-diagnosis repair event. It is present in 300 of 300 baseline traces (the agent's submit call never matches the output schema), so it carries no information about any one trace.
  It is reported as a corpus-level finding. This was decided at label design, after seeing that it is universal and before any judge was called.
- **Known limits.** "Wrong" comes from Phase 6's deterministic text matching, which under-counts correct answers phrased differently from the ground truth; some WRONG traces are semantically right, so the
  PRIORITY tier carries label noise. The baseline agent's traces are almost all defective, so AUTO_CLOSE is rare (see the class balance below); auto-close precision can barely be measured.

## Outcome, process and the 2x2

- **Outcome** (`outcome_label`, Phase 6 authority): CORRECT / WRONG / UNANSWERED from `evaluate_run`. If any primary diagnostic field (root cause, component, category, causal change) is populated the outcome is CORRECT when
  at least one is correct and none is wrong; if none is populated, Phase 6's hypothesis recovery decides. No baseline trace populates any ID-valued field (0 of 300), so the outcome rests on hypothesis recovery.
- **Process** (`process_label`): GOOD when none of these major defects is present: unsupported conclusion, missed critical evidence, distractor anchoring, premature conclusion, inconsistent final answer, fallback diagnosis.
  PARTIALLY_SUPPORTED is a minor defect and tolerated. Independent of correctness.
- **Quadrant:** A correct and good process; B correct and bad process; C wrong and good process; D wrong and bad process.

## Class balance and validation

Pool (300 dev traces, one per case): outcome CORRECT 16, WRONG 220, UNANSWERED 64; process GOOD 1, BAD 299; quadrants A 1, B 15, C 0, D 284;
J1 SUPPORTED 8, PARTIALLY_SUPPORTED 39, UNSUPPORTED 253; J2 positive 211; J3 positive 23; J4 positive 114; J5 violations 16 (consistent 284);
J6 full policy AUTO_CLOSE 1, HUMAN_REVIEW 199, PRIORITY_REVIEW 100; process-only AUTO_CLOSE 8, HUMAN_REVIEW 292.

The corpus (150 traces) keeps every pool trace that has a rare property the study needs and fills the rest by a seeded archetype-stratified sample, so its prevalences are not population rates:
J1 SUPPORTED 8 / PARTIALLY 38 / UNSUPPORTED 104; J2 positive 105; J3 positive 23; J4 positive 65; J5 violations 16; J6 AUTO_CLOSE 1 (process-only 8), HUMAN_REVIEW 94, PRIORITY_REVIEW 55;
outcome CORRECT 16, WRONG 108, UNANSWERED 26; quadrants A 1, B 15, D 134.

What the baseline agent does (measured on the 300 pool traces): every trace contains 1 to 3 invalid tool calls (a hallucinated `get_system_logs` 244 times, missing-argument validation errors 227 times, others);
every trace's final submission was repaired (`final_diagnosis_repair` 300 of 300); no trace populates a predicted ID field; `get_technical_signals` succeeded in 4 traces, so the causal signals are usually never retrieved;
4 traces cite evidence in the validated final answer (all four cite ids that were never retrieved), although 231 raw submissions listed evidence ids under a field name the schema does not recognise, so the harness dropped them;
0 traces have a call marked redundant and 5 contain an exact repeated call. The projection shows the validated final answer, exactly as Phase 6 sees it; the historical traces are not repaired.

Checks. The rules are exercised by unit tests on synthetic traces (each rule, each boundary); `Trace.to_run()` rebuilds the persisted-run shape so Phase 6's `evaluate_run` scores originals and variants with the same code,
and a test shows the rebuilt run scores identically to the stored one on outcome, evidence, process, predictions, tags and stratification; ten traces were read by hand against their labels before freezing (which led to the V2 refinement).

## Design decisions made from the pool before any judge was called

The 300-trace pool was read (statistics and about ten traces by hand) while the labels and perturbations were being written; nothing from a judge was available. Each decision below was made then, for the reason given.

1. The final-diagnosis repair event is not a review trigger: it occurs in 300 of 300 traces, so it cannot separate traces.
2. Process GOOD tolerates PARTIALLY_SUPPORTED: with support required to be strong, one trace in 300 was good and the 2x2 was degenerate.
3. Rule V2 (final answer with no basis) was narrowed to "never stated at any step and tied to no retrieved evidence". A first version flagged legitimate late revisions that the agent's own retrieved evidence supported.
4. P3 (truncation) does not require that the base had retrieved all critical evidence (only 5 of 300 traces qualified); P4 takes its alternative from unretrieved inventory evidence (a first version reused earlier stated hypotheses and was
   "explained" by rule V2); P5 inserts an exact repeated call when the trace has none to remove (only 5 of 300 traces contain a duplicate).
5. The corpus target is 150 (the top of the range) and the selection keeps every trace with a retrieved critical item, so that P1 and P3 have bases.

The rules above are the ones in `labels.py` and `perturbations.py` at the time of the first judge call.
