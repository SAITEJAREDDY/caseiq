# Phase 7 — Stage C review and pre-locked benchmark plan

Reviewed and frozen on 2026-09-23. This is the last checkpoint before the locked
test split. **The locked split has not been opened, sampled, counted, previewed or
run.** The locked-benchmark configuration is sealed and the benchmark itself is
waiting for explicit approval.

The Stage C results are unchanged. This review selects and freezes; it tunes
nothing. Detailed Stage C tables are in [JEV_STAGE_C_VALIDATION.md](JEV_STAGE_C_VALIDATION.md);
machine-generated audit and comparison tables are in
`data/eval/jev/analysis/stage_c_review/` (`stage_c_review.md` / `.json`).

## Decisions at a glance

| Primitive | Capability class | In the locked test | Runtime status | Primary metric |
|---|---|---|---|---|
| Causal change | **A. Locked-benchmark candidate** | **yes** | Runtime candidate, conditional on the locked result | accuracy (co-primary: non-trivial accuracy, detection rate, no-change false-positive rate) |
| Issue category | B. Supporting-only | **yes** | Supporting signal | accuracy |
| Root cause | B. Supporting-only | **yes** (scientific completeness) | Supporting-only, human review | accuracy (co-primary: conditional, committed) |
| Owning team | B. Supporting-only | **yes** (scientific completeness) | Supporting-only | acceptable-team accuracy (co-primary: primary-team) |
| Evidence sufficiency | C. Weak / deprioritize | no | Deprioritize | macro F1 (if ever measured) |
| Incident relationship | C. Weak / deprioritize | no | Deprioritize | balanced accuracy (if ever measured) |

Inclusion in the locked test and runtime candidacy are separate decisions and are
recorded separately in the frozen configuration.

## 1. Stage C validation integrity

The authoritative experiments are the two runs `exp_stage_c_validation_jev_20260923T184036Z_fa984004`
and `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`. `stage_c_audit.py`
checks them against the frozen configuration field by field: **33 of 33 checks
pass.**

| Verified | Result |
|---|---|
| Split, kind, case count | `validation` / `validation`, 750 cases, exactly the validation split in the same order; case-id digest `6f89e2c8…c890a`; the checkpoint holds the same ids |
| Frozen configuration | ran under `stage_b_frozen_v1`, status `verified_against_manifest`, not `--pre-freeze`; recorded digest `0f72b8e2…d788` equals both the config file and its manifest |
| Versions | candidate versions issue v1 / root cause v2 / causal v3 / team v2 / sufficiency v1 / incident v1; context `v4_operational`; canonical change ids; evaluator `v2.1`; question set `v2`; candidate bundle `v3`; pricing `2026-09-23`. Every stored record carries the frozen question and candidate-generation version of its decision |
| Models | Jev requested `jev-1.13.0` and every one of 3,882 decisions resolved to it; LLM `meta-llama/Llama-3.3-70B-Instruct-Turbo`, temperature 0.1, 400 max tokens, one repair allowed |
| Run | 0 failed cases, 3,882 decisions per system, protocol digest on the run matches the pre-registered file |
| Immutability | the Stage C experiments, report and protocol are byte-identical to what the locked freeze pinned |

**No locked access during Stage C.** Evidence, from metadata only: the registry
has 23 experiments and none carries `dataset_split` `test` or kind
`locked_benchmark`; every case id used by all 23 experiments (Phase 6 smoke runs
and the regression suite included) is in the dev or validation split; the
Stage C checkpoint holds exactly the validation ids; no run-state marker exists;
and the CLI guards refuse the test split (Phase 7 validator checks [8] to [10]).
The split loader keeps no access log, so there is none to consult. Membership was
checked against the dev and validation lists only: the existing loader parses the
whole split file, but the test entries are dropped at once and never selected,
counted or printed. The pre-run guard check (validator check [10]) requested only
the dev split's ids.

## 2. Dev versus validation (authoritative)

Values are the ones stored in the experiment reports (all 11 equal the values
Stage C recomputed from the decision records). Difference is validation minus dev
with a Newcombe 95% interval; the ratio is validation over dev with a bootstrap
interval. No fixed percentage threshold is used.

| Primitive | Dev | Validation [95% CI] | Delta (pts) [95% CI] | Ratio | Reading |
|---|---:|---:|---:|---:|---|
| Issue category | 73.0% (73/100) | 78.4% (588/750) [75.3, 81.3] | +5.4 [−2.9, +15.2] | 1.07 | stable within uncertainty |
| Root cause | 48.0% (48/100) | 37.2% (279/750) [33.7, 40.8] | −10.8 [−21.1, −0.6] | 0.78 | **likely degradation** |
| Causal change | 92.0% (92/100; other dev runs 92%, 91%) | 89.3% (670/750) [87.2, 91.6] | −2.7 [−7.2, +4.6] | 0.97 | stable within uncertainty |
| Owning team, primary | 36.0% (36/100) | 37.6% (282/750) [34.0, 41.2] | +1.6 [−8.7, +11.0] | 1.04 | stable within uncertainty |
| Owning team, acceptable | 49.0% (49/100) | 52.8% (396/750) [49.2, 56.4] | +3.8 [−6.5, +14.0] | 1.08 | stable within uncertainty |
| Evidence sufficiency | 14.0% (14/100) | 12.4% (93/750) [10.1, 14.8] | −1.6 [−10.0, +4.4] | 0.89 | stable within uncertainty |
| Incident relationship | 70.6% (12/17) | 82.6% (109/132) [76.5, 88.6] | +12.0 [−5.7, +36.3] | 1.17 | inconclusive (dev n=17) |

"Stable within uncertainty" means indistinguishable, not equal: the dev intervals
are wide, so a moderate change could hide in them.

### 2.1 Root cause: advance, support, or deprioritize?

**Supporting-only; included in the locked test for completeness.**
- Candidate recall 98.7% (10 of 750 absent). End-to-end 37.2%, conditional 37.7%, macro F1 0.406, false-confident 22 of 750 (2.9%), ECE 0.246.
- The dev-to-validation drop is likely real: the interval's upper edge is −0.6, and the LLM on identical inputs barely moved (24.0% to 20.7%). The v4 context and candidate cutoffs were selected on those same 100 dev cases, so this is what dev optimism looks like.
- 303 of 750 answers (40.4%) are the `RC40` abstention, which is never the true answer (0 of 750). When Jev commits to a specific root cause it is right 62.4% [57.8, 66.8] (dev 84.2%, n=57). Accuracy is 0% on the 53 cases with partial or insufficient evidence, at mean confidence about 65% (`JEV-027`).
- Candidate-size sensitivity is not informative: 691 of 750 decisions have 16 candidates, 58 have 15 (43.1%), one has 11.
- Against the LLM: +16.5 points [+13.1, +20.1] (dev +24.0); Jev-only correct 159, LLM-only 35, McNemar p < 0.001. The lead generalized, at a lower level.
- Context stays `v4_operational`; v5 is not reconsidered, and nothing was rerun.
- It fails T3 (accuracy below 0.85) whatever T2 says, so it cannot be a locked-benchmark candidate.

### 2.2 Causal change

**Locked-benchmark candidate**, with qualifiers.
- Recall 100% (750/750), 1.8 candidates on average (median 2, P90 3). End-to-end 89.3% [87.2, 91.6] against a 71.3% evidence-blind rule; conditional accuracy equals it (recall is 100%). Macro F1 0.687, false-confident 3 of 750 (0.4%).
- No-change false-positive rate 4.8% (25 of 516, Wilson 3.3 to 7.1%; dev 5.9%). Distractor-selection rate 8.8%. Failure kinds: 25 false positives, 53 `none` chosen when a true change was offered, 2 wrong real change.
- **Trivial decisions.** 307 of 750 (41%) offered only `none`. On the 443 non-trivial decisions Jev scores 81.9% [78.1, 85.2] against 51.5% for the best evidence-blind rule, and the LLM scores 74.3%. When a true change exists Jev finds it 76.5% of the time (LLM 91.5%); its lead over the LLM comes from no-change cases (95.2% against 81.8%) (`JEV-028`). The T3 bar is met end to end (89.3%) but not on the non-trivial decisions (81.9%). The locked protocol therefore makes non-trivial accuracy co-primary.
- Against the LLM: +4.5 points [+1.9, +7.2] (dev +12.0), Jev-only 73, LLM-only 39, McNemar p = 0.002.
- Latency P50/P95 195/1,200 ms against 1,002/3,691 ms; $0.049 against $0.808 per 1,000 decisions.

**Recency groups.**

| Group | n | Accuracy | Newest-change selection | High-confidence errors |
|---|---:|---:|---:|---:|
| A true is newest | 228 | 75.9% | 75.9% | 2 |
| B true older than a newer distractor | 6 | 100% (6/6) | 0.0% | 0 |
| C no causal change | 516 | 95.2% | 3.7% | 1 |
| D multiple recent changes | 143 | 85.3% | 54.5% | 2 |

**Does Jev show causal discrimination beyond picking the newest event? Not
established.** Group B finally has examples (dev had none) but only six. Jev
chose the older true change in all six and never the newest, which a pure recency
rule would not do, but two things stop this from being evidence of causal
reasoning: the Wilson lower bound for 6/6 is 61%, and in the synthetic data the
change-id number separates every true change from every other candidate (true ids
30402 to 31157, all others 93 to 30383, zero overlap on validation), so an
id-keyed rule would also get all six right. The older-than-distractor gap is
therefore **not resolved** (`JEV-014`, `JEV-025`); it is a limitation of the
dataset and it is carried into the locked benchmark unchanged.

### 2.3 Issue category

**Supporting-only; included.** Stable (73.0% to 78.4%), well calibrated (ECE
0.094 on dev to 0.030), recall 100% over a fixed set of 18. False-confident 7 of
750 (0.9%), 7 of 315 predictions at 0.90 or more are wrong. Macro F1 0.706; class
recall is uneven (IC11 0.31 and IC12 0.39 at precision 0.93 and 0.94). Against the
LLM: −0.9 points [−3.7, +1.9], McNemar p = 0.569 (a tie); the LLM makes 20 wrong
answers among its 258 predictions at 0.90 or more. Its value is cost, latency and
calibrated deferral, not accuracy. It fails only T3 (78.4% is below 0.85).

### 2.4 Owning team

**Supporting-only; included for completeness.** Do not confuse coverage with
routing accuracy: acceptable-team candidate recall is 99.9% (749/750) and primary
99.7% (748/750), but primary accuracy is 37.6% and acceptable accuracy 52.8%
(conditional 37.7% and 52.9%). At confidence 0.90 or more 40 of 96 routing
predictions are wrong (58.3% right), false-confident 5.3%, ECE 0.239; the archetype
`dependency_root_cause` is flagged (accuracy 28.6% at confidence 63.9%). Recall by
team is very uneven (TM01 0.84, TM04 and TM07 about 0.03). The Jev lead over the
LLM generalized: +23.1 points [+18.9, +27.2] (dev +25.0), Jev-only 234, LLM-only 61,
p < 0.001.

### 2.5 Evidence sufficiency

**Weak / deprioritize; not in the locked test.** 12.4% against a 92.9% majority
baseline (697 sufficient, 40 partial, 13 insufficient). Jev answers "partially
sufficient" on 651 of 750 decisions (86.8%): per-class recall sufficient 9.0%,
partial 65.0%, insufficient 30.8%; macro F1 0.135; false-confident 34 of 750;
confidence spread 182 / 191 / 340 / 37 decisions across the 0.0-0.5, 0.5-0.7,
0.7-0.9 and 0.9-1.0 bands. The LLM (41.9%, macro F1 0.419) is also below the
baseline and beats Jev by 29.5 points (p < 0.001). Nothing was redesigned.

### 2.6 Incident relationship

**Weak / deprioritize by the pre-registered rubric; not in the locked test.** The
sample is now interpretable (132 decisions from 132 distinct cases, 29
true-related; dev had 17 and 5). Sensitivity (TPR) 27.6% [14.7, 45.7], specificity
98.1% (FPR 1.9% [0.5, 6.8]), balanced accuracy 62.8% (LLM 55.4%), AUC 0.697. False
attributions 2 (both coincidental overlap; 69 coincidental cases in the sample, 97.1%
correct), missed incidents 21 (`directly_caused`: 8 of 27 found; `partially_influenced`:
0 of 2), and all 12 of Jev's high-confidence errors are misses. Accuracy 82.6% [76.5, 88.6]
does not clear the 78.0% "never related" baseline. It sits between "weak" and
"insufficient evidence": the sample is large enough to show Jev misses most related
incidents, but not to show it is worse than the baseline. Against the LLM the paired
bootstrap gives +3.8 points [+0.8, +6.8] but the exact test does not reach 0.05
(p = 0.062, five discordant pairs all favouring Jev): fragile.

## 3. Candidate-generation generalization (JEV-019)

| Decision | Dev recall | Validation recall [Wilson 95%] | Candidates avg / median / P90 (validation) | Absent (validation) |
|---|---:|---:|---:|---:|
| Issue category | 100.0% | 100.0% [99.5, 100] | 18.0 / 18 / 18 | 0 |
| Root cause | 100.0% | 98.7% [97.6, 99.3] | 15.9 / 16 / 16 | 10 |
| Causal change | 100.0% | 100.0% [99.5, 100] | 1.8 / 2 / 3 | 0 |
| Owning team, acceptable | 100.0% | 99.9% [99.2, 100] | 11.8 / 12 / 12 | 1 |
| Owning team, primary | 99.0% | 99.7% [99.0, 99.9] | 11.8 / 12 / 12 | 2 |

**The strategies generalized beyond the 100-case dev cohort.** Every recall is at
least 0.95, none of the dev-to-validation differences is material, and candidate
counts match dev. The 10 root-cause misses are spread over seven root causes and
cap root-cause accuracy at 98.7%. **JEV-019 stays closed.** No generator was
changed.

## 4. Jev versus LLM on validation

Paired on identical inputs (hash-verified 750/750 and 132/132). Both systems had 0
contract failures.

| Primitive | Jev | LLM | Difference (paired 95% CI) | Both / only Jev / only LLM / neither | McNemar p | Reading vs dev |
|---|---:|---:|---:|---|---:|---|
| Issue category | 78.4% | 79.3% | −0.9 [−3.7, +1.9] | 536 / 52 / 59 / 103 | 0.569 | same (tie) |
| Root cause | 37.2% | 20.7% | +16.5 [+13.1, +20.1] | 120 / 159 / 35 / 436 | <0.001 | same (Jev ahead), narrower |
| Causal change | 89.3% | 84.8% | +4.5 [+1.9, +7.2] | 597 / 73 / 39 / 41 | 0.002 | same (Jev ahead), narrower |
| Owning team | 37.6% | 14.5% | +23.1 [+18.9, +27.2] | 48 / 234 / 61 / 407 | <0.001 | same (Jev ahead) |
| Evidence sufficiency | 12.4% | 41.9% | −29.5 [−32.9, −25.9] | 85 / 8 / 229 / 428 | <0.001 | same (LLM ahead) |
| Incident relationship | 82.6% | 78.8% | +3.8 [+0.8, +6.8] | 104 / 5 / 0 / 23 | 0.062 | changed, on thin evidence |

**What generalized:** the Jev lead on root cause, causal change and owning team;
the tie on issue category; the LLM lead on evidence sufficiency. **What did not:**
the size of the root-cause and causal-change leads (+24.0 to +16.5, +12.0 to +4.5),
and the incident reading. High-confidence errors (Jev / LLM, confidence 0.90 or
more): issue 7 of 315 / 20 of 258; root cause 22 of 84 / 8 of 8; causal 3 of 400 /
5 of 294; team 40 of 96 / 2 of 3; sufficiency 34 of 37 / 1 of 19; incident 12 of 79 /
11 of 84.

### 4.1 Cost and latency, Stage B versus Stage C

| | Dev, sequential (Jev / LLM) | Validation, 8 workers (Jev / LLM) |
|---|---:|---:|
| P50 latency, ms (range over decisions) | 156–174 / 649–816 | 189–202 / 864–1,037 |
| P90 | 201–309 / 1,247–1,568 | 920–1,043 / 2,014–2,381 |
| P95 | 288–468 / 1,347–2,942 | 1,104–1,230 / 2,954–3,910 |
| Cost per 1,000 decisions | $0.027–0.062 / $0.433–0.986 | $0.027–0.061 / $0.429–0.962 |

The advantages persisted: median latency 4.3× to 5.4× lower (dev 4.2× to 4.9×) and
cost 15.7× to 17.1× lower, $0.19 against $3.09 for the 3,882 validation decisions.
**Caveat:** the two stages are not comparable at the tail. Jev's P95 rose from
about 0.3 to 0.5 s to about 1.1 to 1.2 s and the LLM's from about 1.3 to 2.9 s to
about 3.0 to 3.9 s when Stage C ran under 8-way concurrency, so only within-stage
ratios are fair (`JEV-034`). The locked run uses the same 8 workers as Stage C.
The LLM price ($1.04 per million tokens) remains an **assumption**: Together's page
lists no separate Turbo row.

### 4.2 Contract reliability

Stage B (517 decisions per system): Jev 0 API or typed-output errors; LLM 0 contract
failures. Stage C (3,882 per system): Jev 0 API errors and typed output on every
call; LLM first attempt valid on 3,882 of 3,882, 0 repairs, 0 unrecoverable. The
zero-failure result held at 7.5 times the scale.

## 5. Calibration and false confidence

Jev's `confidence` is the API field as delivered; it is not the probability of the
chosen option (`JEV-032`) and the LLM's is a coarse self-reported number (2 to 7
distinct values per decision type), so they are reported side by side and never
ranked.

| Primitive | Dev Brier / ECE / false-confident | Validation Brier / ECE / false-confident |
|---|---|---|
| Issue category | 0.189 / 0.094 / 6 of 100 | 0.128 / 0.030 / 7 of 750 |
| Root cause | 0.292 / 0.240 / 3 of 100 | 0.272 / 0.246 / 22 of 750 |
| Causal change | 0.128 / 0.162 / 0 of 100 | 0.102 / 0.106 / 3 of 750 |
| Owning team | 0.329 / 0.245 / 5 of 100 | 0.289 / 0.239 / 40 of 750 |
| Evidence sufficiency | 0.453 / 0.505 / 2 of 100 | 0.466 / 0.528 / 34 of 750 |
| Incident relationship | 0.203 / 0.208 / 1 of 17 | 0.146 / 0.083 / 12 of 132 |

Issue category is the only well-calibrated decision (ECE 0.030). Root cause and
owning team are overconfident by about 24 points at every level of evidence, and
sufficiency by about 50. The one archetype flagged as "confidence does not track
accuracy" is owning team on `dependency_root_cause` (n=35).

## 6. Automation coverage and target-error coverage

Offline simulation on validation only (the locked report evaluates the thresholds
below, it does not choose any).

| Threshold | Issue category | Root cause | Causal change | Owning team |
|---|---:|---:|---:|---:|
| ≥ 0.70 | 66.0% at 91.7% | 36.5% at 54.4% | 70.5% at 97.5% | 37.2% at 49.8% |
| ≥ 0.80 | 54.3% at 95.3% | 25.2% at 61.9% | 64.5% at 98.3% | 25.9% at 51.5% |
| ≥ 0.85 | 49.1% at 95.7% | 17.9% at 64.9% | 59.2% at 98.9% | 19.9% at 53.7% |
| ≥ 0.90 | 42.0% at 97.8% | 11.2% at 73.8% | 53.3% at 99.2% | 12.8% at 58.3% |
| ≥ 0.95 | 32.1% at 99.2% | 4.8% at 83.3% | 46.4% at 99.4% | 6.9% at 50.0% |

(coverage at accuracy of the automated subset; the deferral fraction is one minus
coverage.) Maximum coverage at observed error of 5% / 2% / 1%: issue category
56.4% / 41.5% / 35.7% (Wilson upper bounds 7.5 / 4.1 / 2.7%); causal change
82.4% / 69.3% / 58.7% (6.8 / 3.5 / 2.3%); root cause 0.9%; owning team 0.4%. These
are not production guarantees: the cutoffs are chosen on the same data. Causal
coverage is mostly the 307 trivial decisions: of Jev's 400 decisions at 0.90 or
more, 307 are trivial, and the 93 non-trivial ones have 3 errors (3.2%, Wilson
1.1 to 9.1%).

## 7. Capability map

| Primitive | Class | Measured reasoning |
|---|---|---|
| Causal change | **A. Locked-benchmark candidate** | Passes the pre-registered rubric (T1 to T4): 89.3% (lower bound 87.2) against 71.3%, stable against dev, 0.4% false-confident, recall 100%. Not proven: 81.9% on non-trivial decisions, 76.5% detection, group B underpowered and id-confounded. |
| Issue category | B. Supporting-only | Stable and calibrated, but 78.4% is below 0.85 and the LLM ties it. |
| Root cause | B. Supporting-only | Beats a 10.4% baseline and beats the LLM, but degraded from dev, 37.2% absolute, 40% abstentions. |
| Owning team | B. Supporting-only | Generalizes and far ahead of the LLM, but 37.6% primary and 5.3% false-confident. |
| Evidence sufficiency | C. Weak / deprioritize | 12.4% against 92.9%; below the LLM. |
| Incident relationship | C. Weak / deprioritize | Not above "never related"; 8 of 29 related incidents found. Borderline insufficient evidence. |

## 8. Proposed locked benchmark

Frozen in `data/eval/jev/locked_benchmark_frozen_v1.json` and pre-registered in
[JEV_LOCKED_BENCHMARK_PROTOCOL.md](JEV_LOCKED_BENCHMARK_PROTOCOL.md).

```text
causal_change
  include_in_locked_test: yes
  reason: only primitive to clear the pre-registered Stage C rubric
  runtime_status: runtime candidate, conditional on the locked result (qualifiers JEV-028, JEV-025)
  primary_metric: accuracy
  co-primary: accuracy on non-trivial decisions; detection rate; no-change false-positive rate
  secondary_metrics: conditional accuracy; recency groups A-E; distractor rate; change-id artifact (descriptive); common set

issue_category
  include_in_locked_test: yes
  reason: generalization confirmed; a frozen automation threshold exists that has not met unseen data
  runtime_status: supporting signal
  primary_metric: accuracy
  secondary_metrics: macro F1; class-level precision/recall; common set

root_cause
  include_in_locked_test: yes
  reason: scientific completeness: does the Jev lead over the LLM and the dev-to-validation drop repeat
  runtime_status: supporting-only (human review)
  primary_metric: accuracy
  co-primary: conditional accuracy; committed accuracy (answers other than RC40)
  secondary_metrics: RC40 abstention share; root cause by evidence quality; macro F1; common set

owning_team
  include_in_locked_test: yes
  reason: scientific completeness: candidate coverage and the Jev lead generalized on validation
  runtime_status: supporting-only
  primary_metric: acceptable-team accuracy
  co-primary: primary-team accuracy
  secondary_metrics: conditional primary/acceptable accuracy; primary/acceptable recall; high-confidence routing errors; common set

evidence_sufficiency
  include_in_locked_test: no
  reason: weak; untouched data kept for any redesign
  runtime_status: deprioritize

incident_relationship
  include_in_locked_test: no
  reason: does not beat "never related"; untouched data kept for a redesign with more true-related incidents
  runtime_status: deprioritize
```

The two exclusions are reversible only before the run, by a new freeze version.

**Common set:** candidate recall and counts, macro F1, class-level precision and
recall, false-confident rate, Brier, ECE, reliability buckets, automation grid,
target-error coverage, difficulty-archetype and evidence-quality slices,
candidate-size bins, failure categories, paired Jev-versus-LLM test, latency, cost
and contract failures.

**Frozen thresholds** (`threshold_policy_v1`, chosen on validation only; evaluated,
never re-selected):

| Primitive | Standard (error at most 5%, Wilson upper at most 10%) | Strict (2% and 5%) | Selected on validation |
|---|---|---|---|
| Issue category | ≥ 0.80 | ≥ 0.95 | 54.3% at 4.7% error; 32.1% at 0.8% error |
| Causal change (non-trivial decisions) | ≥ 0.80 | none | 40.0% of 443 at 4.5% error |
| Root cause | none | none | no grid value came close |
| Owning team | none | none | no grid value came close |

The policy takes the lowest grid threshold that meets a tier with at least 50
automated decisions, and never relaxes itself; the tiers and the factor of 2 were
fixed before the selection was computed. Because they were chosen on validation, the
locked figures are the unbiased estimate and some regression to worse values is
expected.

**Predefined slices:** the six Phase 1 difficulty archetypes (`clear`,
`customer_misdiagnosis`, `dependency_root_cause`, `multi_component_symptoms`,
`vague`, `wrong_product_mentioned`) and the three evidence-quality classes;
causal recency groups A to E; candidate-size bins.

**Statistical tests:** Phase 6 percentile bootstrap (2,000 resamples, seed
20260923) for accuracy intervals; Wilson for proportions; Newcombe for locked
minus validation; exact McNemar and paired bootstrap for Jev versus LLM; no
multiplicity adjustment.

**Expected cost and time** at Stage C rates: about $0.15 for Jev and about $2.4 for
the LLM over 751 cases and four decisions, about 15 minutes.

## 9. The frozen artifact

| Item | Value |
|---|---|
| Configuration | `data/eval/jev/locked_benchmark_frozen_v1.json`, sha256 `27236d36b17844f1e7bf95b58fcd9f488e5f1eafc69abae9486e4f454103b82d` |
| Manifest | `data/eval/jev/locked_benchmark_frozen_v1_manifest.json`, sha256 `138c12f6c0bbe2f39fe3c58e451ffa727e189da79b574521ba662d584788684a` |
| Derived from | `stage_b_frozen_v1` (config digest `0f72b8e2…d788`) plus the selection above |
| Pinned | 44 project source files (the import closure of the run and analysis code, including scoring, candidates, tools, splits and the analysis modules), the split file and split manifest, the pre-registered protocol, the Stage B freeze, the Stage C experiments, decisions, report and protocol, and the Phase 1-3 digest |
| Fixed settings | Jev `jev-1.13.0`; LLM Llama-3.3-70B-Instruct-Turbo at temperature 0.1; evaluator `v2.1`; all question, candidate, context and projection versions; canonical change ids; 8 workers; T0; whole split (751 cases from the split manifest); graph 116,868 / 325,539; `tenacity==8.5.0`, no `typesafe-sdk` |
| Run command | `python3 -m agent.jev_v2.run_experiment --name locked_benchmark_run --kind locked_benchmark --split test --compare-llm --frozen-config locked_benchmark_frozen_v1` |

**Guards.** `--split test` or `--kind locked_benchmark` is refused without the
sealed locked configuration; the locked configuration is refused on any other
split, with `--n`, `--decision-types`, any override, `--pre-freeze`, a different
`--name` or without `--compare-llm`; explicit `--case-ids` and the regression suite
are refused unless every id is in dev or validation (this closes a previous path
around the split guard). The run first verifies the manifest, the environment and
the live graph counts, then writes `locked_benchmark_run_state.json` before its
first call; afterwards only `--resume` of that run under the same configuration is
accepted, and any change to the configuration or a pinned file invalidates the
benchmark as a holdout. `--check-only` runs every guard and prints the plan without
loading case ids, calling an API or writing a marker; it passes today.

**Rehearsal.** The pre-registered locked report was run end to end on stored
validation data (dev as reference), including the frozen thresholds, which
reproduce their validation statistics exactly. Its code is pinned, so the analysis
cannot change after the run starts.

**Limits of the seal.** It is tamper-evident, not tamper-proof: enforcement is
verification, the manifest and the marker, not file permissions. One pinned
module has a harmless `ResourceWarning` (an unclosed file) that was left as is
because fixing it would mean unsealing an immutable freeze.

## 10. Unresolved limitations

- **Recency versus causality (`JEV-014`, `JEV-025`):** six group-B cases, and the change-id number separates true from other candidates perfectly, so neither validation nor the locked test can separate causal reasoning from an id shortcut. The dev control found no reliance; it was not repeated on validation.
- **Root cause:** dev optimism (48.0% to 37.2%) and 40% abstention; `v4` was chosen on dev.
- **Evidence sufficiency:** weak on both systems; the primitive as defined may need a redesign.
- **Incident relationship:** interpretable but below or at the baseline; 29 true-related cases.
- **Causal change:** 41% trivial decisions; detection 76.5% against the LLM's 91.5%.
- **LLM price:** an assumption for the Turbo model id.
- **Tail latency:** measured under concurrency; not comparable with dev (`JEV-034`).
- **Confidence:** Jev's field is not the chosen option's probability (`JEV-032`); the LLM's is coarse.
- **One run per system:** Jev is not bit-deterministic and the LLM is unseeded.
- **Selection on validation:** inclusion decisions, thresholds and this review used validation, so validation figures are mildly optimistic references.

## Decisions needed from you

1. **The inclusion set.** Amending it (for example adding the two weak primitives) means a new freeze version, before any run.
2. **The change-id question (`JEV-025`).** Canonical ids are frozen because that is what was validated. An opaque-key control on validation (about $0.04 for Jev and $0.6 for the LLM, causal change only) would show whether Jev relies on the ids; it re-uses validation, so it needs your approval, and if it showed reliance a new freeze version would be needed. I recommend running it before the locked run.
3. **Explicit approval to run the locked benchmark.** Nothing runs without it.
