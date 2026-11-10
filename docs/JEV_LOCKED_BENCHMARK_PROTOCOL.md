# Phase 7 — Locked benchmark protocol (pre-registered)

Written before the locked test split is opened. Its sha256 is pinned in the
manifest of `locked_benchmark_frozen_v1`, so an edit after sealing makes the
locked run refuse to start (and, once it has started, invalidates it as a
holdout). The locked report may contain only what section 7 lists.

## 1. Question

Do the Stage B and Stage C findings hold on data nothing has ever been
developed, selected or tuned on? The locked test split (751 cases) is measured
**once**, with the sealed configuration, whatever the result. A worse result is a
finding, not a reason to run again.

## 2. Scope: what is measured, and what is not

Inclusion in the locked test (measure once on the final holdout) is a separate
decision from runtime candidacy (does the primitive belong in the eventual
CaseIQ runtime).

| Primitive | In locked test | Stage C class | Runtime status | Reason |
|---|---|---|---|---|
| Causal change | **yes** | Candidate for locked benchmark | Runtime candidate, conditional on this result | Only primitive to clear the Stage C rubric. Two qualifiers travel with it: 41% of decisions are trivially determined by candidate generation (`JEV-028`) and the change-id artifact is unresolved on validation (`JEV-025`). |
| Issue category | **yes** | Supporting-only | Supporting signal | Stable and calibrated; a frozen automation threshold exists that has not met unseen data. |
| Root cause | **yes** | Supporting-only | Supporting-only (human review) | Scientific completeness: does the Jev lead over the LLM and the dev-to-validation drop repeat? Not a deployment claim. |
| Owning team | **yes** | Supporting-only | Supporting-only | Scientific completeness: candidate coverage and the Jev lead generalized on validation. |
| Evidence sufficiency | no | Weak / deprioritize | Deprioritize | 12.4% against a 92.9% majority baseline. Excluded so untouched data remain for a redesign. |
| Incident relationship | no | Weak / deprioritize | Deprioritize | Does not beat "never related"; Jev found 8 of 29 related incidents. Excluded to keep untouched data for a redesign with more true-related incidents. |

The two exclusions are reversible only **before** the run, by creating a new
freeze version; they cannot be added afterwards.

## 3. What is fixed

Everything in `data/eval/jev/locked_benchmark_frozen_v1.json`, derived from
`stage_b_frozen_v1` (which Stage C ran unmodified). In particular:

- Jev `jev-1.13.0`; LLM baseline `meta-llama/Llama-3.3-70B-Instruct-Turbo` at temperature 0.1, one repair re-prompt allowed; evaluator `v2.1`; pricing version `2026-09-23`.
- Question, candidate-generation and context versions exactly as frozen: root cause with candidate generation v2 and `v4_operational` context, causal change with candidate generation v3 and **canonical** change ids, owning team v2, issue category v1, evidence-sufficiency question v2 (not run).
- Decision time `as_of` = each case's own `created_date` (T0). The whole test split, in sorted case-id order; no subset, no `--n`.
- 8 concurrent workers, each decision's input built once and sent to both systems.
- Every project source file reachable by import from the run and analysis entry points, the split files, the Stage B freeze, the Stage C artifacts and this protocol, by sha256.
- The runtime graph must have 116,868 nodes and 325,539 relationships (checked live), and the environment must have `tenacity==8.5.0` and no `typesafe-sdk`.

Change ids stay canonical because that is the configuration that was validated;
switching to opaque keys would run an unvalidated configuration. If the opaque
control on validation later shows reliance on the ids, a new freeze version is
required before any locked run.

## 4. Metrics per included primitive

| Primitive | Primary | Co-primary | Secondary (all reported) |
|---|---|---|---|
| Causal change | accuracy | accuracy on non-trivial decisions (a real change was offered); detection rate (accuracy when a true change exists); no-change false-positive rate | conditional accuracy, recency groups A to E, distractor-selection rate, change-id artifact (descriptive), plus the common set below |
| Issue category | accuracy | none | macro F1, class-level precision and recall, plus the common set |
| Root cause | accuracy | conditional accuracy; committed accuracy (answers other than the `RC40` abstention) | `RC40` abstention share, root cause by evidence quality, macro F1, plus the common set |
| Owning team | acceptable-team accuracy | primary-team accuracy | conditional primary and acceptable accuracy, primary and acceptable candidate recall, high-confidence routing errors, plus the common set |

Common set, for every included primitive: candidate recall and candidate-count
distribution (average, median, P90, number absent), macro F1, class-level
precision and recall, false-confident rate (wrong at confidence 0.90 or more),
Brier, ECE, reliability buckets, automation grid (0.70, 0.80, 0.85, 0.90, 0.95),
target-error coverage (5%, 2%, 1%), the frozen thresholds (section 6),
difficulty-archetype slices, evidence-sufficiency slices, candidate-size bins,
deterministic failure categories, the paired Jev-versus-LLM test, latency (P50,
P90, P95), cost per decision and per 1,000, and contract failures.

For every accuracy-type metric: n, the point estimate and a 95% interval.

## 5. Reading rules

**Reference.** The comparison for "did it generalize" is the Stage C validation
experiment (not dev). Difference is locked minus validation with a Newcombe
hybrid-score 95% interval for independent proportions. Labels, without any fixed
percentage threshold: *material degradation* (whole interval below 0),
*improvement* (above 0), *plausible sampling variation* (includes 0),
*insufficient sample* (either side under 30). For lower-is-better metrics
(false-confident rate, false-positive rate) the direction is inverted; the `RC40`
abstention share is direction-neutral and is read only as higher, lower or no
material difference.

**Capability rubric** (the Stage C rubric, unchanged): T1 lower 95% bound of
accuracy above the best evidence-blind rule; T2 no material degradation against
validation and candidate recall at least 0.95 (owning team judged on acceptable
recall); T3 accuracy at least 0.85 and false-confident rate at most 0.05; T4 at
least 100 decisions. Owning team is read on **primary**-team accuracy, as in
Stage C, and acceptable accuracy is reported beside it. The classes are engineering
triage, not scores.

**Causal change, additional readings.** Non-trivial accuracy is read against the
better of "always `none`" and "newest change" on the same decisions (its lower
bound must exceed that rule) and against the validation value with the delta
labels above. Detection rate and the no-change false-positive rate are read the
same way. The T3 bar is applied to end-to-end accuracy as in Stage C; the
non-trivial accuracy is reported at equal prominence so the trivial decisions
cannot carry the result.

**Jev versus LLM.** Paired by (case, decision) on identical inputs (hash
verified). Reported: both correct, only Jev, only LLM, both wrong, exact
two-sided McNemar p-value, and the paired-bootstrap interval of the accuracy
difference. "Jev ahead" or "LLM ahead" only when that interval excludes 0. No
multiplicity adjustment is applied and marginal p-values are not interpreted.
Confidence is never ranked across systems (the semantics differ).

**What the result does not decide.** No deployment threshold is set here. Whether
any primitive belongs in the runtime is a separate decision made after the
report. The locked result is reported for every included primitive, including
poor ones, with the exclusions and their reasons stated.

## 6. Frozen thresholds

`threshold_policy_v1` was applied to Stage C validation decisions only and its
output is fixed in the configuration. Confidence is Jev's `confidence` field as
delivered (`JEV-032`). Grid: the project's 0.70, 0.80, 0.85, 0.90, 0.95. Two
tiers: standard (observed error at most 5% and Wilson 95% upper bound at most
10%) and strict (2% and 5%), each requiring at least 50 automated decisions; the
selected threshold is the lowest grid value that satisfies the tier, and the
policy never relaxes itself. For causal change the population is the decisions
that offered at least one real change (decisions offering only `none` need no
primitive call in any runtime use). The tiers and the factor of 2 are
engineering choices made before the selection was computed, not values fitted to
the data; the policy was written knowing the Stage C aggregate tables.

| Primitive | Standard (5%) | Strict (2%) |
|---|---|---|
| Issue category | 0.80 | 0.95 |
| Causal change (non-trivial decisions) | 0.80 | none selected |
| Root cause | none selected | none selected |
| Owning team | none selected | none selected |

On the locked run these thresholds are **evaluated, never re-selected**: for each
the report gives the automated count, coverage, errors, observed error and Wilson
upper bound, whether the policy would still be met, and the validation values
beside them. Because they were chosen on validation, some regression toward
worse values on unseen data is expected; the locked figures are the unbiased
estimate. Root cause and owning team are still reported on the whole grid.

## 7. Analyses (the complete list)

1. Overall metrics with confidence intervals (section 4).
2. Candidate recall, candidate-count distribution and the number of absent true answers.
3. Conditional accuracy where candidate recall applies.
4. Macro F1 and class-level precision and recall.
5. Paired Jev-versus-LLM comparison (section 5).
6. Difficulty-archetype slices (`clear`, `customer_misdiagnosis`, `dependency_root_cause`, `multi_component_symptoms`, `vague`, `wrong_product_mentioned`) with the flag "confidence does not track accuracy" as defined in Stage C.
7. Evidence-quality slices (`sufficient`, `partially_sufficient`, `insufficient`) for the four included primitives.
8. Causal recency groups A to E and the causal detail (false-positive rate, distractor-selection rate, detection, non-trivial accuracy).
9. Candidate-size bins (each distinct size when six or fewer, otherwise terciles; empty bins dropped).
10. Calibration: Brier, ECE, reliability buckets, false-confident rate, per system.
11. Automation grid and target-error coverage, with Wilson upper bounds.
12. The frozen thresholds (section 6).
13. Latency P50, P90, P95 and cost per decision and per 1,000 decisions, with the LLM price labelled an assumption.
14. Contract failures for both systems, reported separately from accuracy.
15. Deterministic failure categories (never assigned by Jev).
16. Root-cause abstention (`RC40`) share and committed accuracy.
17. The change-id artifact on the locked causal candidate sets, descriptive only.
18. The comparison of every included metric against Stage C validation (section 5).

Anything else is **exploratory**, must be labelled so, and may not be a headline.
The analysis code (`locked_report.py`, `stage_c_report.py`, `stage_c_posthoc.py`,
`threshold_policy.py`) is pinned by hash.

## 8. Execution rules

- One command, no overrides, whole split:
  `python3 -m agent.jev_v2.run_experiment --name locked_benchmark_run --kind locked_benchmark --split test --compare-llm --frozen-config locked_benchmark_frozen_v1`.
  `--check-only` verifies every guard without loading case ids, calling an API or writing a marker.
- Before the first call the run verifies the sealed configuration, the environment and the graph counts, then writes the run-state marker. After that only `--resume` of the same run under the same configuration is accepted, and only to finish cases that did not complete.
- A case that fails after its retries stops the run before anything is persisted; it is resumed, never restarted under another name and never dropped.
- The report is produced with `python3 -m agent.jev_v2.locked_report`, whose integrity checks must all pass.
- After the run: no change to any question, candidate generator, context, model setting or threshold is made in response to locked failures. Any follow-up is a new, separately versioned experiment on data that are still untouched, and it must not overwrite this result.

## 9. What invalidates the benchmark

Editing the sealed configuration or any pinned file after the run starts; a
second run of the holdout; a deviation from section 8. An invalid run may still be
reported, but only as a non-holdout re-run, and a changed benchmark needs a new
freeze version.

## 10. Limitations acknowledged before the run

- The change-id artifact (`JEV-025`): validation shows the id number separates true changes from other candidates perfectly. Canonical ids are kept because that is what was validated; the locked report describes the artifact but cannot separate reliance from reasoning.
- The older-than-newer-distractor group (B) is structurally rare (6 of 750 on validation); the locked split will probably hold only a handful, so the recency-versus-causality question stays underpowered.
- One run per system. Jev is not bit-deterministic (93% to 100% same answer on identical inputs in Stage B) and the LLM is unseeded, so single-run accuracies carry run-to-run noise beyond the sampling intervals.
- Jev's `confidence` is not the probability of its chosen option (`JEV-032`); the LLM's is coarse; neither is ranked against the other.
- The LLM price is an assumption (the pricing page lists no Turbo row). Latency is measured under 8-way concurrency.
- Inclusion decisions, thresholds and the root-cause context were informed by dev and validation, never by locked data. Validation-based selection makes validation figures mildly optimistic references.
- All 2,500 graph cases are synthetic, 10% of the generator's output.

## 11. Expectations recorded in advance (hypotheses, not required conclusions)

Point estimates are expected near the Stage C validation values; an expectation
is falsified for a metric if the locked point estimate falls outside the
validation 95% interval.

- Causal change: accuracy about 89% (validation interval 87.2 to 91.6), non-trivial accuracy about 82%, detection about 77%, no-change false-positive rate about 5%.
- Issue category: about 78%, tied with the LLM.
- Root cause: about 37%, Jev ahead of the LLM by roughly 15 points, `RC40` abstention near 40%.
- Owning team: about 38% primary and 53% acceptable, Jev far ahead of the LLM.
- Frozen thresholds: observed errors at least as high as on validation (selection effect); the issue-category standard tier is the likeliest to stay within its target.
