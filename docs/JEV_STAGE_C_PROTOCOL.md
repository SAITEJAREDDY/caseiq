# Phase 7 — Stage C Validation Protocol (pre-registered)

Written before any validation-split call was made. The run records this
file's sha256 in the experiment config (`pre_registered_protocol`), so any
later edit is detectable. Stage C is a generalization benchmark, not a tuning
cycle: nothing below may be changed after the validation results are seen.

## Scope and rules

- Split: `validation` only (750 cases), through the existing guard
  (`--split validation --kind validation`). The locked test split is not
  opened for any purpose.
- Configuration: `stage_b_frozen_v1` exactly, run with `--frozen-config` and no
  overrides and without `--pre-freeze`, so the manifest is verified first
  (versions, source-file hashes, split file, Phase 1-3 digest, dev cohort).
  If verification fails the run stops and the drift is reported; the freeze is
  never regenerated.
- One run. No question, candidate, context, model or calibration change is
  made in response to validation results, and validation is not re-run after
  inspecting failures. An interrupted run may be **resumed** from its
  checkpoint (same frozen settings, the completed cases are not re-sent); a run
  is never discarded because of what its numbers look like.
- Failure listings are used only to count deterministic failure categories.
  Jev is never used to label its own failures.
- Orchestration: cases are dispatched concurrently (`parallel_runner.py`,
  8 workers) and each decision's input is built once and sent to both Jev and
  the LLM. This changes how cases are scheduled, not what is sent; on 24 dev
  cases it reproduced the stored sequential run's inputs 123/123 and Jev's
  answers 123/123.
- Dev reference values come from the stored experiments, not from prompts:
  Jev `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24`, LLM
  `exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff`; causal-change dev
  runs `exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8` and
  `exp_causal_change_v3_repeat_dev100_jev_20260923T174042Z_aee6568c`.

## Metric definitions

- **Accuracy**: correct / scored decisions. **Conditional accuracy**: among
  decisions whose true answer was offered. Owning team reports primary and
  acceptable variants of both. Confidence intervals: Phase 6's percentile
  bootstrap (2,000 resamples, fixed seed) for accuracies; Wilson score
  intervals for other proportions.
- **Macro F1 and class-level precision/recall** from the confusion matrix of
  predicted versus true value.
- **Calibration**: Phase 6 Brier, ECE, reliability buckets and false-confident
  rate (wrong at confidence >= 0.90), unchanged. Jev's confidence is the native
  probability of the typed primitive; the LLM's is a self-reported number; they
  are reported separately and never ranked against each other.
- **Automation coverage** at thresholds 0.70, 0.80, 0.85, 0.90, 0.95: share
  automated, accuracy and error among the automated subset, share deferred.
  **Target-error coverage** at <= 5%, 2%, 1%: maximum coverage, the decisions
  it contains, its observed error, and the Wilson 95% upper bound of that
  error. Offline simulation only.
- **Candidate metrics** for every Choice primitive: recall, average, median and
  P90 candidate count, and the number of cases where the true answer is
  absent. Owning team: primary and acceptable.
- **Causal-change groups** (evaluator v2.1): A true change is the newest
  candidate; B true change is older than at least one strictly later
  candidate; C no causal change exists; D two or more real change candidates
  were offered (cuts across A/B/C); E the true change was not offered. Equal
  timestamps count as A. Each group reports n, accuracy, conditional accuracy,
  high-confidence errors and the newest-change selection rate. If group B is
  empty on validation, that limitation is recorded and the dataset is not
  altered.
- **Failure categories** (mutually exclusive, first match): invalid output or
  API error; candidate missing; wrong with confidence >= 0.90; wrong at lower
  confidence; correct at confidence < 0.50; correct otherwise. Causal change
  additionally splits wrong answers into false positive on a no-change case,
  `none` chosen when a true change was offered, and a wrong real change chosen.
  Incident relationship splits into false attribution (by the incident's true
  relationship label, including coincidental overlap) and missed incident.
  Evidence sufficiency splits into under-called and over-called.
- **Difficulty slices** use the Phase 1 archetype names as stored. A slice
  is flagged "confidence does not track accuracy" when it has at least 30
  decisions and its (mean confidence minus accuracy) exceeds the overall value
  by at least 0.10. Slices under 30 decisions are marked small.
- **Candidate-set-size bins**: each distinct size when there are six or fewer
  distinct sizes, otherwise terciles of the validation distribution; a single
  size is reported as "no variation".
- **Dev versus validation**: difference (validation minus dev) with a Newcombe
  hybrid-score 95% interval for two independent proportions, and the
  validation/dev ratio with a bootstrap interval. Labels: *material
  degradation* when the whole interval is below 0; *improvement* when it is
  above 0; *plausible sampling variation* when it includes 0; *insufficient
  sample* when either side has fewer than 30 decisions. No fixed percentage
  threshold is used.
- **Jev versus LLM**: paired by (case, decision, incident) on identical
  inputs, verified by hashing state, options and decision time; exact McNemar
  test and paired bootstrap interval. The dev ranking is not assumed.
- **Latency and cost**: P50, P90 and P95 latency; cost from provider-returned
  token counts at the versioned prices in `config.py` (the LLM price stays an
  assumption while Together lists no Turbo row).

## Capability classification (pre-registered rubric)

Engineering triage, not a score. For each primitive, on validation only:

- **Baseline**: the accuracy of a rule that ignores the evidence: majority
  class; for causal change the better of "always `none`" and "newest change,
  else `none`"; for incident relationship "never related".
- **T1 beats baseline**: the lower 95% bound of Jev's accuracy exceeds the
  baseline accuracy.
- **T2 generalizes**: the dev-to-validation difference is not *material
  degradation*, and, for primitives with generated candidate sets, validation
  candidate recall is at least 0.95 (owning team judged on acceptable recall).
- **T3 strong**: accuracy at least 0.85 and false-confident rate at most 0.05.
- **T4 adequate sample**: at least 100 validation decisions, and for
  incident relationship at least 20 true-related decisions.

Classes, first match wins: **Insufficient sample** if T4 fails; **Weak /
deprioritize** if T1 fails; **Candidate for locked benchmark** if T1, T2 and T3
all pass; otherwise **Supporting-only**. The headline accuracy is: issue
category, root cause, causal change, evidence sufficiency and incident
relationship accuracy; owning team primary accuracy. The comparison with the
LLM is reported alongside but is not part of the rubric, and moving any
primitive to the locked benchmark remains a decision for the user.

## Expectations recorded in advance (not required conclusions)

Causal change stays strong and is the likeliest locked-benchmark candidate;
issue category is roughly stable; root cause and owning team keep a Jev lead
over the LLM at modest absolute accuracy; evidence sufficiency stays far below
its majority baseline; incident relationship needs the larger validation sample
before any judgement.
