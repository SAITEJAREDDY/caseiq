# Phase 8: Jev agent-trace evaluation

Phase 8 asks whether Jev can look at a completed run of the Phase 5 autonomous agent and reliably judge its quality, support, risk and need for human review. Jev is used as a passive observer of a
finished trace, not as a root-cause classifier and not as ground truth. Measured on 150 dev traces and 165 controlled variants; the phase is closed on this evidence. Runtime use is Phase 9.

## Architecture

```text
Support case -> Phase 5 agent -> Neo4j observable evidence -> tool calls + hypothesis states -> final structured answer
                                                   |
                                        completed observable trace
                          ______________________|______________________
                         |                                             |
                Phase 6 deterministic scoring              Phase 8 projection (opaque ids, no rationale)
                (correctness, evidence, contract)                       |
                         |                       six independent typed questions to Jev (Noul x5, Choice x1)
                         |                       and, on the identical packet, to an LLM judge
                         |                                             |
                         +---------- reference labels (evaluation-only) + observable rules ----------+
                                                   |
                          scoring, perturbation tests, review-policy simulation, capability map
```

Neo4j decides what was observable. The agent investigates. Phase 6 scores what can be checked deterministically. Jev judges fuzzy properties visible in the trace. Deterministic code combines measured outputs. Jev is
never the ground truth and neither is the LLM judge: both are scored against the deterministic reference labels in `TRACE_EVAL_REFERENCE_LABELS.md`, which read hidden truth only in evaluation-only code and were
frozen before the first judge call. The judgments are kept independent; there is no combined quality score.

Code: `agent/trace_eval_v2/` (`trace_loader`, `trace_projection`, `guard`, `questions`, `jev_evaluator`, `llm_evaluator`, `labels`, `perturbations`, `scorer`, `metrics`, `analysis`, `corpus`, `experiments`, `cli`,
`validate_boundaries`, `test_trace_eval`). Reuses Phase 5's agent and tools, Phase 6's `evaluate_run`, splits, registry and bootstrap settings, and Phase 7's direct-HTTP Jev client and LLM transport (nothing in Phase 5, 6
or 7 was modified; the Phase 7 locked freeze is untouched). Other documents: [question catalog](TRACE_EVAL_QUESTION_CATALOG.md), [reference labels](TRACE_EVAL_REFERENCE_LABELS.md),
[data boundaries](TRACE_EVAL_DATA_BOUNDARIES.md), [pre-registration](TRACE_EVAL_PREREGISTRATION.md).

## The trace corpus

- **Pool.** 300 dev cases: all 16 insufficient-evidence and all partially sufficient dev cases plus a seeded stratified sample of the sufficient strata. Ten valid Phase 6 runs were reused; 290 fresh runs used the current
  Phase 5 agent unchanged (Llama-3.3-70B-Instruct-Turbo; 7 failed once on Together 503 outages and were re-run; about $4.3 at the assumed price).
- **Corpus.** 150 traces, one per case, selected from the pool by reference properties only (no judge output): every trace with a rare property the study needs (correct outcome, good process, an auto-close reference,
  supported conclusion, anchoring, final inconsistency, insufficient-evidence case, or a retrieved critical item), then a seeded archetype-stratified fill. The corpus is enriched on purpose; its prevalences are not population rates.
  Archetypes: clear 81, customer misdiagnosis 24, vague 16, wrong product 11, dependency 10, multi-component 8. Evidence: sufficient 117, partial 17, insufficient 16. Incident-involved 31, dependency-driven 16.
  Agent confidence: high 61, mid 52, low 37.
- **Variants.** 165 synthetic perturbation variants of corpus traces: P1 30, P2 25, P3 30, P4 30, P5 25, P6 25 (stored and reported as synthetic).
- **Outcome (Phase 6 authority).** Correct 16, wrong 108, unanswered 26. 2x2 with process: A (correct, good) 1; B (correct, bad process) 15; C (wrong, good process) 0; D (wrong, bad) 134.
- **What the baseline agent does** (measured over the 300 pool traces). Every trace has 1 to 3 invalid tool calls (a hallucinated `get_system_logs` 244 times, missing-argument validation errors 227 times). Every final submission was repaired
  (300 of 300). No trace fills a predicted ID field. `get_technical_signals` succeeded in 4 traces, so the causal signals are usually never retrieved. Four final answers cite evidence, all of it never retrieved, although 231 raw
  submissions listed evidence ids under a field name the schema drops. Traces are 2,000 to 3,900 tokens as packets. Historical traces were not repaired; missing fields are trace behaviour.

Reference labels in the corpus: J1 supported 8 / partial 38 / unsupported 104; J2 missed 105; J3 anchored 23; J4 premature 65; J5 inconsistent 16; J6 AUTO_CLOSE 1, HUMAN_REVIEW 94, PRIORITY_REVIEW 55 (process-only variant: AUTO_CLOSE 8).

## Results (dev corpus, one run per judge; all figures measured)

Full generated report: `data/eval/trace_eval/analysis/exp_trace_eval_dev_v1_jev_20260924T011354Z_c92ea332/trace_eval_report.{md,json}`. Jev `jev-1.13.0`; LLM Llama-3.3-70B-Instruct-Turbo. 1,890 judgments per judge, none failed.

### Discrimination against the reference labels (binary judgments; decisions at P(yes) 0.5)

| Judgment | n (positive) | Judge | Accuracy | F1 | ROC-AUC [95% CI] | Brier | ECE |
|---|---|---|---:|---:|---|---:|---:|
| J1 support | 112 (8) | Jev | 50.0% | 0.20 | 0.70 [0.53, 0.86] | 0.27 | 0.43 |
| | | LLM | 75.0% | 0.30 | 0.75 [0.55, 0.92] | 0.17 | 0.21 |
| | | rule | 100% | 1.00 | 1.00 (by construction) | | |
| J2 missed evidence | 150 (105) | Jev | 76.0% | 0.85 | 0.84 [0.77, 0.90] | 0.16 | 0.09 |
| | | LLM | 84.7% | 0.90 | 0.77 [0.69, 0.85] | 0.13 | 0.04 |
| | | rule | 76.7% | 0.86 | 0.61 [0.55, 0.68] | 0.23 | 0.23 |
| J3 distractor anchoring | 150 (23) | Jev | 58.7% | 0.40 | 0.85 [0.77, 0.92] | 0.23 | 0.34 |
| | | LLM | 18.0% | 0.27 | 0.47 [0.44, 0.50] | 0.55 | 0.64 |
| | | rule (majority) | 84.7% | | 0.50 | | |
| J4 premature close | 150 (65) | Jev | 85.3% | 0.84 | 0.93 [0.88, 0.96] | 0.12 | 0.12 |
| | | LLM | 43.3% | 0.60 | 0.33 [0.26, 0.40] | 0.43 | 0.41 |
| | | rule | 93.3% | 0.93 | 0.94 [0.91, 0.97] | 0.07 | 0.07 |
| J5 final consistency | 150 (134 consistent) | Jev | 58.7% | 0.70 | 0.85 [0.77, 0.93] | 0.22 | 0.37 |
| | | LLM | 11.3% | 0.01 | 0.50 [0.50, 0.51] | 0.89 | 0.89 |
| | | rule (control) | 100% | 1.00 | 1.00 | | |

Paired, Jev minus LLM (AUC difference, paired bootstrap): J1 -0.05 [-0.23, 0.12]; J2 +0.07 [-0.03, 0.17]; J3 +0.38 [0.29, 0.45]; J4 +0.60 [0.51, 0.68]; J5 +0.35 [0.26, 0.42]. Exact McNemar on correct-at-0.5:
J2 favours the LLM (only Jev right 6, only LLM right 19, p = 0.015; Jev's ranking is better, the LLM's default operating point is), J3 to J5 favour Jev (66/5, 72/9, 72/1), J1 favours the LLM (11/39).
Jev minus the observable rule: J2 +0.23 [0.12, 0.32]; J4 -0.01 [-0.05, 0.02]; J1 -0.30 [-0.47, -0.14]; J5 -0.15 [-0.23, -0.07].

Reading. Jev's probabilities rank well on J2 to J5 but are shifted: at 0.5 it over-calls support, anchoring and inconsistency (ECE 0.34 to 0.43 on J1, J3, J5). Nothing was recalibrated. The LLM judge, given the same
prompt, answers almost constant values on several judgments (yes to J3 and J4 nearly always, no to J5 nearly always, HUMAN_REVIEW to J6 always), so its AUC is near 0.5 or below there; this is one shared, unoptimised prompt,
not a statement about the best an LLM judge could do. For J1 the "rule" scores 1.00 because the label is itself defined by an observable lexical rule plus two hidden conditions that rarely bind (see limitations);
the fair reading is that code suffices for that lexical notion of support and that this reference cannot say whether a semantic judge would do better. The middle band shows neither judge orders support cleanly:
mean P(yes) SUPPORTED / PARTIAL / UNSUPPORTED is Jev 0.63 / 0.41 / 0.49 and the LLM 0.61 / 0.49 / 0.22.

### Controlled perturbations (share of variants whose probability moved the expected way)

| Perturbation (expected) | Judgment | Jev | LLM |
|---|---|---|---|
| P1 remove one critical evidence item (support down, missed up, review up) | support down | 29/30, mean -0.25 | 15/30, mean -0.31 |
| | missed evidence up | 23/30 (77%), mean +0.03, 5 material | 5/30 |
| | review level up | 29/30, mean +0.06 | 0/30 |
| P2 distractor moved to the end and repeated (anchoring up) | anchoring up | 13/25 (52%), mean +0.004 | 1/25 |
| P3 truncate before the first critical retrieval (premature up, review up, support down) | premature up | 30/30, mean +0.13 | 27/30, mean +0.09 |
| | review level up | 29/30, mean +0.10 | 0/30 |
| | support down | 30/30, mean -0.41 | 21/30, mean -0.54 |
| P4 alternative from unretrieved evidence as final top (consistency down, review up) | consistency down | 30/30, mean -0.53 | 0/30 (already 0) |
| | review level up | 30/30, mean +0.20 | 0/30 |
| P5 duplicate call removed or inserted (stable within 0.10) | all six | 25/25 on five, 23/25 on J5 | 25/25 on five, 22/25 on J1 |
| P6 identifiers re-aliased (stable within 0.10) | all six | 25/25 on every judgment | 25/25 on four, 22/25 J1, 24/25 J2 |

Jev responds strongly and in the right direction to removed evidence (support), truncation (premature close, support, review) and a contradicted final answer (consistency, review), is stable under redundant calls and
identifier changes, and does not respond to distractor prominence (P2). The response of J2 to P1 is small: removing one of several critical items rarely changes a judgment that already says "something important was missed".
P2's expected direction is weakly grounded, since the reference label does not change under P2 either; the pre-registered rubric scores it as written. The LLM judge's flat answers make most of its tests uninformative (J5 and J6 never move).

### Human review (J6)

- Neither judge auto-closed any trace. Jev's P(AUTO_CLOSE) was exactly 0.00 for all 150; the LLM chose HUMAN_REVIEW for all 150. So unsafe auto-close is 0 for both, and so is auto-close coverage, at every threshold from 0.70 to 0.95.
  The single clean trace (full policy) and the eight process-only clean traces were all sent to review: auto-close precision cannot be established (1 and 8 clean traces).
- Tier discrimination on the full policy (55 PRIORITY, 94 HUMAN, 1 AUTO): Jev tier accuracy 68.0%, macro F1 0.43; PRIORITY recall 50.9%, under-escalation 49.1%; PRIORITY-versus-rest AUC 0.71 [0.63, 0.80] (mean P(PRIORITY) 0.51 on PRIORITY
  traces and 0.39 on HUMAN traces). LLM: tier accuracy 62.7%, macro F1 0.26, PRIORITY recall 0%.
- The agent's own review flag as a gate: it would auto-close 95 of 150 traces (63%) and 94 of them (99%) are problematic under the policy; review recall on problematic traces 37%. An observable "any defect" rule reviews everything.
  So the judges' caution is worth more than the agent's self-assessment, but on this corpus it is indistinguishable from "always review".
- Caveat that qualifies the clean-trace result: the question tells the judge to weigh tool and contract problems, and every packet shows at least one invalid tool call and a repaired submission, while the policy deliberately does not count those
  universal defects. A careful reviewer could refuse to auto-close a trace with a hallucinated tool call, so "Jev cannot recognise a clean trace" is not established here; the corpus contains no trace that is clean by every reviewer standard.

### Correct-but-bad-process and wrong-but-reasonable (the 2x2)

| Cell (n) | Jev | LLM |
|---|---|---|
| A correct, good process (1) | judged not good (2 defects flagged); tier HUMAN_REVIEW | judged not good (3 flagged); HUMAN_REVIEW |
| B correct, bad process (15) | 0 of 15 judged good; 9 HUMAN, 6 PRIORITY; 3.2 defects flagged (reference 2.1) | 0 judged good; 15 HUMAN; 4.7 flagged |
| C wrong, good process (0) | not observable: the baseline agent never produces one | not observable |
| C proxy: wrong, at most one defect (33) | 5 of 33 judged good; 27 HUMAN, 6 PRIORITY; 2.1 defects flagged (reference 1.0) | 0 judged good; 33 HUMAN; 4.2 flagged |
| D wrong, bad process (134) | 6 of 134 judged good (4%); 92 HUMAN, 42 PRIORITY; 2.9 flagged (reference 2.1) | 0 judged good; 4.4 flagged |

Jev did not mistake a correct-looking answer for a good process: all 15 correct-but-bad-process traces were flagged. It also flags about one defect more than the reference everywhere, so it over-penalises even the least defective wrong
answers (proxy cell). Whether it recognises a genuinely good process cannot be measured with one good trace.

### Trace length, slices, failure taxonomy, cost

- **Length (terciles of packet size, 2,081 to 3,682 tokens).** No degradation with length for Jev: pooled accuracy 64%, 68%, 68% (short, medium, long), Brier 0.21, 0.20, 0.18, P50 latency 197, 196, 193 ms, cost per 1,000 judgments $0.16, $0.19, $0.21.
  The LLM's accuracy is flat at 44 to 46%.
- **Slices** (reported, not tuned; accuracy at a fixed 0.5 cut reflects prevalence per slice, so read them with the counts in the report): the dependency-root-cause archetype is the weakest for Jev (pooled 48%, n=10), vague the strongest (80%, n=16);
  high agent confidence is worse than low (59% against 72%, driven by J5 at 25%); insufficient-evidence cases show J2 at 50% and J1 at 38%.
- **Failure taxonomy, Jev (LLM).** False support 55 (26); false unsupported 1 (2); false missed-evidence alarm 32 (20); missed missed-evidence 4 (3); false anchoring alarm 60 (123); missed anchoring 2 (0); false premature alarm 13 (85);
  missed premature closure 9 (0); false inconsistency alarm 61 (133); missed final inconsistency 1 (0); unsafe auto-close 0 (0); unnecessary human review 1 (1); priority under-escalation 27 (55). Jev's errors are dominated by false alarms.
- **Cost, latency, contract (all 1,890 judgments per judge, 8-way concurrency).** Jev: $0.18 per 1,000 judgments (mean 4,351 input tokens), P50 193 ms, P95 284 ms, 0 errors, model `jev-1.13.0` on every call.
  LLM: $3.52 per 1,000 judgments at the assumed Turbo price, P50 873 ms, P95 2,001 ms; first-attempt valid 1,890 of 1,890, no repair, no unrecoverable failure. Jev is about 19 times cheaper and about 4.5 times faster at the median.
  Spend: judges $7.0 for the main run (Jev $0.35, LLM $6.65) plus about $0.6 for Stage A; agent traces about $4.3.

## Capability map (the pre-registered rubric, applied as written)

| Judgment | Category | Basis | Reading |
|---|---|---|---|
| J1 conclusion support | Better deterministic | rule AUC 1.00; Jev 0.70, LLM 0.75 | Code reproduces the lexical reference exactly (by construction). Neither judge is reliable here (8 positives, at the provisional bar). Not a Jev use case. |
| J2 missed critical evidence | Useful supporting signal | Jev 0.84 [0.77, 0.90]; LLM 0.77; rule 0.61 | Jev is the only approach that separates relevant from irrelevant unretrieved evidence (beats the rule by 0.23). Missed the Strong bar on direction consistency (77% against 80%). |
| J3 distractor anchoring | Useful supporting signal | Jev 0.85 [0.77, 0.92]; LLM 0.47; no natural rule | Real ranking signal on 23 positives, poorly calibrated, unresponsive to prominence. Supporting only. |
| J4 premature conclusion | Better deterministic | rule 0.94; Jev 0.93 [0.88, 0.96]; LLM 0.33 | Jev is excellent (and 100% direction consistent) but a three-line observable rule is as good. Prefer the rule. |
| J5 final-answer consistency | Better deterministic | rule 1.00 (control); Jev 0.85; LLM 0.50 | A deterministic checker is exact. Jev responds to a contradicted answer but over-alarms. Prefer code. |
| J6 human review | Useful supporting signal for escalation triage (provisional); not established as an auto-close gate | PRIORITY-vs-rest AUC 0.71 [0.63, 0.80]; 0 auto-closed; 1 clean trace | Safe by never auto-closing; cannot show it recognises clean traces. |

No judgment is classified Strong Jev and none Better LLM. The LLM judge, as prompted, is weak on J3 to J6 and comparable on J1 and J2. The rubric constants are in `analysis.py` and the pre-registration.

## Answers to the completion questions

1. **Can Jev identify unsupported conclusions?** Not reliably. AUC 0.70 on 8 positives, over-calls support, does not order supported / partial / unsupported; code does the lexical version exactly.
2. **Can it detect missed critical evidence?** Yes, moderately: AUC 0.84, 76% accuracy at 0.5 with 32 false alarms, clearly better than the observable rule; its response to removing one critical item is directionally right but small.
3. **Distractor anchoring?** It ranks anchoring well (AUC 0.85, 23 positives) but over-predicts it (60 false alarms) and does not react to a distractor being made prominent. Supporting signal only.
4. **Premature conclusions?** Yes (AUC 0.93; every truncation variant moved up), but a simple observable rule does the same.
5. **Final-answer inconsistency?** It reacts strongly to a contradicted final answer (30 of 30) but ranks the natural cases moderately (0.85) and over-alarms; use the deterministic checker.
6. **Which traces need human review?** It never auto-closes, so it is safe and uninformative as a gate on this corpus; it separates PRIORITY from HUMAN moderately (AUC 0.71, recall 51%). Auto-close precision cannot be established.
7. **Correct-but-bad-process versus good runs?** It flagged all 15 correct-but-bad-process traces and judged none good; recognising a genuinely good process cannot be tested (one good trace).
8. **Over-penalising wrong-but-reasonable?** The natural cell is empty. On the proxy (wrong, one defect) it flags about one extra defect per trace, so yes, it leans to over-penalising.
9. **Response to perturbations?** Correct and strong for removed evidence, truncation and a contradicted answer; stable under redundancy and identifier changes; no response to distractor prominence; weak magnitude for J2 under P1.
10. **Versus an LLM judge?** Better ranking on J3 to J5 and J2, worse or equal on J1; the LLM judge's near-constant answers on J3 to J6 (one shared prompt) make it the weaker comparator here; it is also about 19 times costlier and 4.5 times slower.
11. **Where deterministic checks are better.** J1 (lexical support), J4 (premature close) and J5 (final consistency). J2, J3 and J6 have no observable rule that matches.
12. **Latency and cost.** Jev $0.18 per 1,000 judgments, P50 193 ms, P95 284 ms, no length effect and no failed call; the LLM judge $3.52, 873 ms, 2,001 ms, 100% valid first attempts.

## Limitations and issues found

- **T8-1 The baseline agent is almost always defective.** 300 of 300 traces have an invalid tool call and a repaired submission; no ID field is ever filled; the causal signals are usually never retrieved. The corpus therefore has one good-process trace,
  one clean trace under the full policy (eight process-only), and 8 supported conclusions. Several categories are provisional or thin, cell C of the 2x2 is empty, and auto-close precision cannot be measured. Fixing the agent is out of scope (unchanged by design); a
  stronger agent is a precondition for evaluating a guardrail.
- **T8-2 Reference labels are deterministic proxies.** Phase 6's text matching under-counts correct answers (some "wrong" traces are semantically right, so the PRIORITY tier carries noise); J1 is lexical; J2 to J4 use the hidden critical and distractor sets;
  J5 is a function of the packet (a control). Labels were frozen before any judge call; several design decisions were made from reading the pool's traces before then and are listed in the reference-labels document.
- **T8-3 J6 question and policy differ on universal defects.** The question asks the judge to weigh tool and contract problems; every trace has them; the policy does not count them. This confounds the clean-trace result (above).
- **T8-4 One correction pass was used.** J5 was reworded once after Stage A (`_v2`), and the J6 perturbation scalar changed to the expected review level because P(AUTO_CLOSE) was 0 for every trace (Amendment 1 of the pre-registration). No other question, label, threshold or rubric constant changed after seeing results.
- **T8-5 P2's expectation is weak.** Making a distractor more prominent does not change the reference; the rubric scores the non-response as inconsistency. Read the J3 category with that in mind.
- **T8-6 Calibration.** Jev's probabilities are shifted on J1, J3 and J5 (ECE 0.34 to 0.43); nothing was recalibrated or thresholded (no tuning). Accuracy at 0.5 understates what the ranking supports.
- **T8-7 One run per judge per item, one prompt shared by both judges, an enriched corpus of 150 traces from 150 dev cases.** Intervals are wide where positives are few (J1 8, J3 23). This is an engineering capability study, not a benchmark: no validation or locked split was used, and none was opened.
- **T8-8 The trace shows the validated final answer.** The harness dropped the evidence citations the agent attempted (231 traces); judges and labels both see the validated view, as Phase 6 does.
- **T8-9 Latency** is under 8-way concurrency; the LLM price is an assumed rate carried from Phase 7.

## Reproduce

```bash
python3 -m agent.trace_eval_v2.corpus --build-pool            # 300 dev cases; no API call
python3 -m agent.trace_eval_v2.corpus --generate              # fresh Phase 5 runs for the missing cases (about 20 minutes, parallel)
python3 -m agent.trace_eval_v2.corpus --build-records         # review context + reference labels; no API call
python3 -m agent.trace_eval_v2.corpus --select-corpus         # the 150-trace corpus; no API call
python3 -m agent.trace_eval_v2.cli check --stage main         # build all 315 packets, run the leakage guard; no API call
python3 -m agent.trace_eval_v2.cli run --stage main           # 3,780 judge calls (about 5 minutes)
python3 -m agent.trace_eval_v2.cli analyze --jev <id> --llm <id>
python3 -m unittest agent.trace_eval_v2.test_trace_eval       # 45 offline tests
python3 -m agent.trace_eval_v2.validate_boundaries
```

Experiments: main `exp_trace_eval_dev_v1_jev_20260924T011354Z_c92ea332` and `exp_trace_eval_dev_v1_llm_20260924T011354Z_321f78cc`; Stage A `exp_trace_eval_smoke_v1_*` and `exp_trace_eval_smoke_v1b_*` (J5 re-check);
Phase 6 scoring of the corpus `exp_phase8_trace_corpus_v1_phase6_20260924T005609Z_52585a35`. Pre-registration sha256 (amended text) recorded on the main experiments.

## Phase 9 (not implemented here)

Runtime verification and guardrails: the agent proposes a conclusion or action, Jev (and deterministic checks) assess support and review need, and a deterministic policy continues, asks for evidence, or escalates.
Phase 8 suggests the design: deterministic code for support lexicon, premature close and consistency; Jev for relevance-sensitive judgments (missed evidence, anchoring) and for PRIORITY triage; and a stronger agent, since
this baseline gives a gate almost nothing to let through.
