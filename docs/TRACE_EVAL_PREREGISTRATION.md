# Phase 8 pre-registration (dev trace evaluation)

Written before the first judge call. Its sha256 is recorded on every experiment (`config.pre_registration`); it is not edited afterwards. The results are reported in
`docs/PHASE8_TRACE_EVALUATION.md`.

## Scope and fixed elements

Dev cases only. No validation or locked case is read. The Phase 5 agent is not modified and is not run again after the corpus was generated. Jev (`jev-1.13.0`, the model frozen in
`stage_b_frozen_v1`) and the LLM judge (`meta-llama/Llama-3.3-70B-Instruct-Turbo`, temperature 0.1, one repair re-prompt) are used as configured in Phase 7. Nothing is installed or upgraded.

| Element | Version |
|---|---|
| Trace pool | `trace_pool_v1`: 300 dev cases (all 16 insufficient and all partially sufficient dev cases, plus a seeded sample of the sufficient strata), seed 20260924 |
| Corpus | `trace_corpus_v1`: 150 traces selected from the pool by rare properties, then a seeded archetype-stratified fill |
| Projection | `trace_projection_v1`, identifiers `trace_alias_v1`, no free-text rationale |
| Reference labels | `reference_labels_v1`; review policy `review_policy_v1` (see `TRACE_EVAL_REFERENCE_LABELS.md`) |
| Questions | `trace_support_v1`, `missed_evidence_v1`, `distractor_anchor_v1`, `premature_close_v1`, `final_consistency_v1`, `human_review_v1` |
| Perturbations | `perturbations_v1`: P1 to P6, seed 20260924, up to 30/25/30/30/25/25 variants |

Each judgment is one call per (packet, judge): five Noul judgments and one Choice. The judges see the identical packet and question. No judge is asked for an explanation.

## Procedure

1. Stage A smoke on about 12 traces and a few variants (both judges). Purpose: API integration, typed outputs, no leakage, projection, reference scoring, judge parity, perturbation mechanics.
2. At most one correction pass: implementation bugs and question wording only, on dev, every material change versioned, before the main run. Reference labels and this document are not changed by results.
3. Freeze. The main run: the 150 corpus traces plus their variants, both judges, once.
4. Analysis and capability map. Phase 8 then closes. No validation freeze, no locked benchmark, no further benchmark-hardening loop, no runtime gating.

## Metrics

- Binary judgments: accuracy (Wilson interval), precision, recall, F1 (bootstrap interval), ROC-AUC (bootstrap interval), PR-AUC, Brier, ECE (10 equal-width bins), false-confident errors (wrong at confidence 0.9 or more).
  Decisions are at P(yes) >= 0.5. Positive is the YES condition of each question. J1 is SUPPORTED against UNSUPPORTED with the middle band excluded and reported separately.
- J6: tier accuracy, macro F1 and confusion; review recall on problematic traces; false-review rate on clean traces; PRIORITY recall and under-escalation; auto-close precision and coverage;
  unsafe auto-close (an auto-closed trace whose reference is not AUTO_CLOSE). Threshold simulation for Jev at 0.70, 0.80, 0.85, 0.90, 0.95 on P(AUTO_CLOSE). Full policy and the process-only variant.
- Jev against the LLM: exact McNemar on correct-at-0.5, and a paired bootstrap of the AUC difference. Each judge's confidence is its own and is never ranked across judges (Jev gives typed probabilities, the LLM a self-stated number).
- Deterministic baselines, observable-only (no hidden truth): J1 the J1 rule without its hidden conditions; J2 "some signal, change or deployment in the inventory was not retrieved"; J3 the majority answer (no natural rule);
  J4 committed and (an unretrieved item or a hypothesis tie); J5 the J5 rule itself (a control); J6 the agent's own review flag, and "any observable defect".
- Perturbation (metamorphic) evaluation: for each variant, the change in each judge's probability against the base trace. Direction consistency = share of variants that moved the expected way
  (strictly); "material" = moved by 0.05 or more. Stability (P5, P6) = share within 0.10, plus decision flips at 0.5. J6 uses P(not AUTO_CLOSE) for Jev and the hard choice for the LLM.
  Expected directions: P1 support down, missed evidence up, review up; P2 anchoring up; P3 premature up, review up, support down; P4 consistency down, review up; P5 and P6 all stable.
- Slices (reported, never tuned): archetype, evidence sufficiency, final outcome, agent confidence, tool calls, hypothesis revisions, invalid-tool count. Trace length in terciles of packet size: accuracy, Brier, ECE, latency, cost.
- Quadrant analysis: for each cell of the 2x2, the judges' probabilities, tier choices and a descriptive conjunction of the five judgments ("judged good process": supported, no missed evidence, no anchoring, not premature, consistent).
  This is a conjunction of independent judgments, never a composite quality score. Because the corpus has almost no good-process traces, a proxy cell (wrong, at most one process defect) is also reported and labelled as a proxy.
- Failure taxonomy: false support, false unsupported, missed missed-evidence, false missed-evidence alarm, missed distractor anchoring, false anchoring alarm, missed premature closure, false premature alarm,
  missed final inconsistency, false inconsistency alarm, unsafe auto-close, unnecessary human review, priority under-escalation.
- Cost, latency (P50 and P95, under 8-way concurrency) and contract behaviour (first-attempt validity, repair, unrecoverable) per judge and judgment. Turbo pricing is an assumed rate carried from Phase 7.

## Capability rubric (fixed now; the constants are conventions, not derived from results)

Applied per judgment, in this order, on the original traces, using ROC-AUC (threshold-free, so robust to the corpus's enriched prevalence):

1. **Better deterministic**: an observable-only rule's AUC is within 0.02 of the better judge, or above it (not applied to J3, which has no natural rule).
2. **Weak**: neither judge has AUC of at least 0.65 with a bootstrap lower bound above 0.5.
3. **Better LLM**: the LLM's AUC exceeds Jev's by 0.05 or more and the paired bootstrap interval of the difference lies below 0.
4. **Strong Jev use case**: Jev AUC of at least 0.80 with lower bound of at least 0.70, direction consistency of at least 0.80 and stability of at least 0.85 where the judgment has those tests, ECE of at most 0.15,
   and AUC not more than 0.02 below the LLM's.
5. **Useful supporting signal**: otherwise, if Jev AUC is at least 0.65 with lower bound above 0.5.

A judgment with fewer than 8 positives or 8 negatives in the corpus is labelled "provisional". J6 is judged on two operational questions: whether the judge avoids unsafe auto-close (at most 5% unsafe among what it
auto-closes) and whether it separates PRIORITY from the rest (AUC as above); with fewer than 8 clean traces the report says auto-close precision cannot be established.

## Known before the run

The baseline agent's traces are almost all defective (see `TRACE_EVAL_REFERENCE_LABELS.md`): the corpus has 8 SUPPORTED, 1 good-process and 1 AUTO_CLOSE trace (8 under the process-only variant).
Several categories will therefore be provisional; cell C of the 2x2 (wrong but reasonable) is empty in natural traces; the perturbations, not natural traces, carry the evidence for judgments whose positive class is rare.
The corpus is enriched on purpose and is not population-representative. One run per judge per item: sampling variation is described by intervals, not removed.

## Completion questions and where they are answered

1 to 5: the per-judgment performance and perturbation tables (J1 to J5). 6: J6 tables and the threshold simulation. 7 and 8: the quadrant analysis (B, and the C proxy). 9: the perturbation tables.
10: the paired Jev-versus-LLM table. 11: the deterministic baselines. 12: the cost, latency and contract tables.

## Amendment 1 (after Stage A, before the main run)

Stage A (`trace_eval_smoke_v1`: 12 traces, 12 variants, 288 calls, both judges) worked end to end: every answer was typed, no request was refused by the leakage guard, Jev resolved `jev-1.13.0`, the LLM judge had
no contract failure, and the reference scoring and perturbation mechanics ran. The experiments carry the sha256 of the text above this amendment. The single allowed correction pass changes only these things:

1. **J5 wording (`final_consistency_v1` -> `final_consistency_v2`).** Both judges read empty structured fields and late revisions as "inconsistent", which the reference definition does not count (J5 asks about consistency,
   not completeness). The corrected question states the four checks the reference uses and says that empty fields and revisions after new evidence are not inconsistency. The v1 text is kept in `questions.SUPERSEDED_WORDING`.
   The other five questions are unchanged (`_v1`). The change is checked only for typed, parseable output on the Stage A items; it is not iterated.
2. **J6 metamorphic scalar.** Jev's P(AUTO_CLOSE) was 0.00 for every Stage A trace, including the one genuinely clean trace, so "review probability goes up" had no headroom. For the perturbation tests J6 is measured on the
   expected review level, (P_HUMAN + 2 P_PRIORITY) / 2 for Jev and 0, 0.5, 1 for the LLM's hard choice. The binary "problematic" view for the accuracy tables still uses 1 - P(AUTO_CLOSE).

Nothing else in this document, the reference labels, the corpus, the perturbations, the metrics or the capability rubric changes. The Stage A results are not part of the main results.
