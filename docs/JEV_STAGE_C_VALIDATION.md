# Phase 7 — Stage C validation report

Run on 2026-09-23 with the frozen Stage B configuration (`stage_b_frozen_v1`) on
the **validation split only** (750 cases). One run, no tuning. The locked test
split was not opened. The pre-registered plan and rubric are in
[JEV_STAGE_C_PROTOCOL.md](JEV_STAGE_C_PROTOCOL.md) (written before the first
validation call).

- Jev experiment: `exp_stage_c_validation_jev_20260923T184036Z_fa984004`
- LLM experiment: `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`
- Machine-generated tables: `stage_c_report.md` / `.json` and the labelled
  post-hoc analysis `stage_c_posthoc.md` / `.json`, in the Jev experiment folder
- Issue log entries: `JEV-014`, `-015`, `-016`, `-017`, `-019`, `-023`, `-025`,
  `-026` (updated) and `JEV-027` to `JEV-033` (new) in [JEV_ISSUE_LOG.md](JEV_ISSUE_LOG.md)

## Summary

| Primitive | Validation accuracy [95% CI] | Best rule that ignores the evidence | Class (pre-registered rubric) |
|---|---:|---:|---|
| Causal change | 89.3% [87.2, 91.6] | 71.3% | **Candidate for locked benchmark** |
| Issue category | 78.4% [75.3, 81.3] | 17.2% | Supporting-only |
| Root cause | 37.2% [33.7, 40.8] | 10.4% | Supporting-only |
| Owning team (primary) | 37.6% [34.0, 41.2] | 15.6% | Supporting-only |
| Evidence sufficiency | 12.4% [10.1, 14.8] | 92.9% | Weak / deprioritize |
| Incident relationship | 82.6% [76.5, 88.6] | 78.0% | Weak / deprioritize |

What the run showed, in order of consequence:

1. **The candidate generators generalize.** Recall on 750 unseen cases is 98.7% to 100%, above the 0.95 bar, so the in-sample worry behind `JEV-019` is resolved.
2. **Causal change is the only primitive that clears the rubric, but its headline accuracy needs two qualifiers.** 41% of its decisions offer only `none` and are trivially correct; on the 443 non-trivial decisions Jev scores 81.9%, below the 0.85 bar. And when a true change exists Jev finds it 76.5% of the time against the LLM's 91.5%. Jev's advantage comes from the no-change cases (95.2% against 81.8%).
3. **Root cause is the one primitive that degraded** (48.0% on dev to 37.2%, interval just below zero) while the LLM stayed put (24.0% to 20.7%). That is what dev optimism looks like, since the root-cause context was chosen on dev. 40% of Jev's root-cause answers are the `RC40` abstention, which is never the true answer.
4. **The Jev-versus-LLM ranking generalizes** on five of six decisions, and the latency and cost advantages persist (about 5× faster at the median, about 16× cheaper).
5. **Evidence sufficiency and incident relationship are weak** and neither beats the trivial rule that ignores the evidence.
6. **Only two primitives have a usable automation region** (issue category and causal change).

Recommendation: advance **causal change** to the locked benchmark, with three
conditions set before that run (see "Recommendation"). Do not spend the locked
split on evidence sufficiency or incident relationship. Everything else is the
user's call.

## A. Validation integrity

| Item | Result |
|---|---|
| Split and kind | `validation` / `validation`, through the guarded CLI |
| Cases | 750, exactly the validation split (experiment, decision file and checkpoint case ids all equal it); case-id digest `6f89e2c8…c890a` |
| Decisions | 3,882 per system (750 × 5 choice decisions + 132 incident decisions) |
| Frozen configuration | `stage_b_frozen_v1`, sha256 `0f72b8e2…d788`, status `verified_against_manifest`, no overrides, not `--pre-freeze`; `frozen_config.verify` returns no problems after the run |
| Models | Jev `jev-1.13.0` on all 3,882 decisions; LLM `meta-llama/Llama-3.3-70B-Instruct-Turbo`, temperature 0.1, one repair re-prompt allowed |
| Versions | context `v4_operational`; candidates issue category v1, root cause v2, causal change v3 (canonical keys), owning team v2, evidence sufficiency v1, incident v1; evaluator v2.1 |
| Pre-registration | protocol sha256 `4c950c80…cd95e2` recorded in the experiment and still matches the file |
| Failures | 0 failed cases; 0 Jev API or request errors; LLM first-attempt valid on 3,882 of 3,882 decisions (no repairs) |
| Input parity | Jev and the LLM received identical state, options and decision time on 750/750 per choice decision and 132/132 incident decisions (hash-verified) |
| Locked test split | Not opened, not loaded, not run. Case-id membership was checked against the validation ids only. |
| Boundary validators | Phase 7 (all 8 checks, including 11,005 stored inputs re-scanned clean and the frozen-config check), Phase 6, Phase 5 and Phase 4 all pass |
| Frozen data and graph | Phase 1–3 checksums: 88 files, 0 mismatches. Graph: 116,868 nodes and 325,539 relationships. |
| Environment | `pip check` clean; `tenacity==8.5.0`; `langchain==0.2.16`, `langchain-core==0.2.43`, `langchain-community==0.2.16`, `streamlit==1.35.0`; no `typesafe-sdk` |
| Offline tests | 27 pass (22 before Stage C, plus 5 for the analysis helpers) |

**Orchestration.** A sequential run would have taken about 6 hours. Cases were
dispatched by `parallel_runner.py` (8 workers, 17.1 minutes wall clock). It
changes how cases are scheduled, not what is sent: on 24 dev cases it reproduced
the stored sequential run's inputs 123/123 and Jev's answers 123/123. Latencies
below were therefore measured under 8-way concurrency for both systems (the dev
figures were sequential). See `JEV-030`.

## B. Candidate generalization

| Decision | Dev recall (n=100) | Validation recall | Wilson 95% | Avg / median / P90 candidates (val) | True answer absent |
|---|---:|---:|---:|---:|---:|
| Issue category | 100.0% | 100.0% | 99.5–100 | 18.0 / 18 / 18 | 0 |
| Root cause | 100.0% | 98.7% | 97.6–99.3 | 15.9 / 16 / 16 | 10 |
| Causal change | 100.0% | 100.0% | 99.5–100 | 1.8 / 2 / 3 | 0 |
| Owning team, acceptable | 100.0% | 99.9% | 99.2–100 | 11.8 / 12 / 12 | 1 |
| Owning team, primary | 99.0% | 99.7% | 99.0–99.9 | 11.8 / 12 / 12 | 2 |

Every strategy clears the pre-registered 0.95 bar and none of the dev-to-validation
differences is material. Candidate-set sizes on validation match dev, so nothing
about the validation cases is structurally different. The 10 root-cause misses
are spread over seven root causes (RC24 three times, RC20 twice, RC15, RC17,
RC32, RC33 and RC38 once each) with no single pattern; they cap root-cause
accuracy at 98.7%. No generator was changed in response.

Two facts about the candidate sets matter for reading accuracy: 307 of 750
causal-change decisions (41%) offer only `none` because no change was visible,
and owning-team and issue-category sizes barely vary, so size-versus-accuracy
analysis is informative only for causal change and (weakly) root cause.
**`JEV-019` is closed on this evidence.**

## C. Jev generalization

Difference is validation minus dev with a Newcombe 95% interval; the ratio is
validation over dev with a bootstrap interval. The labels follow the protocol
(no fixed percentage threshold).

| Metric | Dev (n=100) | Validation | Difference (pts) | Ratio | Reading |
|---|---:|---:|---:|---:|---|
| Issue category accuracy | 73.0% | 78.4% (588/750) | +5.4 [−2.9, +15.2] | 1.07 [0.96, 1.24] | sampling variation |
| Root cause accuracy | 48.0% | 37.2% (279/750) | −10.8 [−21.1, −0.6] | 0.78 [0.63, 1.00] | **material degradation** |
| Causal change accuracy | 92.0% | 89.3% (670/750) | −2.7 [−7.2, +4.6] | 0.97 [0.92, 1.04] | sampling variation |
| Owning team, primary | 36.0% | 37.6% (282/750) | +1.6 [−8.7, +11.0] | 1.04 [0.81, 1.45] | sampling variation |
| Owning team, acceptable | 49.0% | 52.8% (396/750) | +3.8 [−6.5, +14.0] | 1.08 [0.89, 1.37] | sampling variation |
| Evidence sufficiency accuracy | 14.0% | 12.4% (93/750) | −1.6 [−10.0, +4.4] | 0.89 [0.56, 1.63] | sampling variation |
| Incident relationship accuracy | 70.6% (12/17) | 82.6% (109/132) | +12.0 [−5.7, +36.3] | 1.17 [0.90, 1.79] | insufficient sample (dev n=17) |

False-confident rate (wrong at confidence ≥ 0.90) moved from 6.0% to 0.9% for
issue category (an improvement; the first machine-generated table labelled it
"material degradation" because of a direction bug, fixed in `JEV-029`), and
stayed within sampling variation for the others (root cause 3.0% to 2.9%, causal
change 0.0% to 0.4%, team 5.0% to 5.3%, evidence sufficiency 2.0% to 4.5%).

**Reading by primitive.**

- **Issue category** is stable and well calibrated (ECE 0.030). Accuracy varies
  by archetype from 69% (vague, customer misdiagnosis) to 89% (wrong product
  mentioned), and confidence broadly follows it (no slice flagged). Recall is
  uneven by class: IC11 and IC12 have precision of 0.93 and 0.94 but recall of
  0.31 and 0.39, so Jev under-uses them.
- **Root cause** degraded, and only its interval's upper edge (−0.6) reaches
  zero, so the size of the drop is uncertain. Two things point to dev
  optimism and not to bad luck: the LLM on identical inputs barely moved
  (24.0% to 20.7%), and the v4 context and the candidate cutoffs were selected on
  the same 100 dev cases. Accuracy is flat across archetypes (30% to 47%) while
  mean confidence sits at 61% to 65% everywhere (ECE 0.246): confidence does not
  track accuracy. Accuracy is 0% on the 53 cases with partial or insufficient
  evidence (mostly `RC40` abstentions, see `JEV-027`). Seven of 37 root causes
  are never predicted correctly.
- **Owning team** generalized (dev and validation differences within variation).
  The archetype `dependency_root_cause` (n=35) is flagged: accuracy 28.6% with
  confidence 63.9%. Recall is 0.84 for TM01 and near zero for TM04 and TM07.
- **Evidence sufficiency** is flat at 8% to 16% in every archetype slice.
- **Incident relationship** cannot be compared with dev (n=17), but stands on its
  own now (section E and `JEV-031`).

## D. Causal change

Groups follow evaluator v2.1 (A: true change is the newest candidate; B: true
change is visible and strictly older than another candidate; C: no causal
change; D: two or more real candidates offered, cutting across A/B/C; E: true
change not offered).

| Group | n | Accuracy | High-confidence errors | Newest-change selection |
|---|---:|---:|---:|---:|
| A true is newest | 228 | 75.9% | 2 | 75.9% |
| **B true older than a newer candidate** | **6** | **100.0%** (6/6) | 0 | **0.0%** |
| C no causal change | 516 | 95.2% | 1 | 3.7% |
| D multiple real candidates | 143 | 85.3% | 2 | 54.5% |
| E true change not offered | 0 | n/a | 0 | n/a |

- **False-positive rate on no-change cases: 4.8%** (25/516, Wilson 3.3–7.1%; dev
  5.9%). The LLM's is 18.2% (94/516).
- **Distractor-selection rate** when a distractor was offered: 8.8% (LLM 31.4%).
- **Failure kinds** (750 decisions): 25 false positives on no-change cases, 53
  `none` chosen when the true change was offered, 2 wrong real change chosen.
  Nearly every error is a call of "no change" or "some change" and almost none
  is a mix-up between two real changes.
- **Group B (question 5).** Six cases exist in 750 (0.8%). Jev and the LLM both
  got all six, with newest-selection 0%, so neither simply picked the newest
  change. With n=6 the Wilson lower bound is 61%: this is a first measurement,
  not evidence that the recency-versus-causality question is settled
  (`JEV-014` stays open). The cell is structurally rare in this dataset, so a
  larger split of the same kind will not fix it.
- **Candidate-set size.** Size 1 (only `none`): 307 decisions, 100%. Size 2: 300,
  80.3%. Size 3: 115, 85.2%. Size 4: 26, 84.6%. Size 5: 2.

Post-hoc reading (descriptive, not pre-registered, from `stage_c_posthoc.md`;
these do not change the classification):

| | Jev | LLM |
|---|---:|---:|
| Accuracy when a true change exists (n=234) | 76.5% [70.7, 81.5] | 91.5% [87.2, 94.4] |
| Answered `none` when a true change existed | 53 (22.6%) | 18 (7.7%) |
| Accuracy on no-change cases (n=516) | 95.2% | 81.8% |
| Accuracy on the 443 non-trivial decisions (a real change offered) | **81.9% [78.1, 85.2]** | 74.3% [70.0, 78.1] |
| Best evidence-blind rule on those 443 (always `none` / newest change) | 47.2% / 51.5% | same |

- Jev's overall lead over the LLM (+4.5 points) is a trade: it misses more true
  changes and raises far fewer false alarms. Which is preferable depends on the
  cost of a missed cause against a false one, which this evaluation does not
  set (`JEV-028`).
- Of Jev's 400 decisions at confidence ≥ 0.90, 307 are the trivial only-`none`
  decisions and 93 are non-trivial (3 wrong, 3.2% [1.1, 9.1]). The headline
  causal automation coverage below is mostly the trivial decisions.
- **Change-id artifact (`JEV-025`).** The structural artifact seen on dev
  replicates on validation: the numeric id of the true change ranges 30402 to
  31157 (n=234) while every other candidate is 93 to 30383 (n=382), with zero
  overlap; a visible deployment is the true cause in 68 of 110 cases that offer
  one (dev: 6 of 7). This is a property of the data, not a measured reliance by
  Jev, and the opaque-key control was not rerun. My inference is that Jev's error
  pattern (it misses true changes but picked a wrong real change in only 2 of
  the 234 cases that had a true one) is not what a model keying on the id
  number would produce, but validation cannot prove it.

## E. Jev versus LLM

Paired on identical inputs. Accuracy difference has a paired bootstrap 95%
interval; the p-value is exact McNemar. Confidence is **not** ranked: Jev's is
an API field and the LLM's is a number it was asked to write (it takes only 2 to
7 distinct values per decision type).

| Decision | Jev | LLM | Jev minus LLM (pts) | McNemar p | Dev reading | Validation reading |
|---|---:|---:|---:|---:|---|---|
| Issue category | 78.4% | 79.3% | −0.9 [−3.7, +1.9] | 0.569 | no clear difference | no clear difference |
| Root cause | 37.2% | 20.7% | +16.5 [+13.1, +20.1] | <0.001 | Jev ahead (+24.0) | Jev ahead |
| Causal change | 89.3% | 84.8% | +4.5 [+1.9, +7.2] | 0.002 | Jev ahead (+12.0) | Jev ahead |
| Owning team (primary) | 37.6% | 14.5% | +23.1 [+18.9, +27.2] | <0.001 | Jev ahead (+25.0) | Jev ahead |
| Evidence sufficiency | 12.4% | 41.9% | −29.5 [−32.9, −25.9] | <0.001 | LLM ahead (−29.0) | LLM ahead |
| Incident relationship | 82.6% | 78.8% | +3.8 [+0.8, +6.8] | 0.062 | no clear difference (n=17) | Jev ahead, fragile |

Five of six readings are unchanged. Root-cause and causal-change leads narrowed
(+24.0 to +16.5 and +12.0 to +4.5). The incident reading changed, but it rests on
five discordant pairs that all favour Jev, the exact test does not reach 0.05,
and neither system clearly beats the "never related" rule (`JEV-031`).

**Latency and cost** (validation, both systems under 8-way concurrency; LLM
price is an assumption because the pricing page lists no Turbo row, `JEV-026`):

| Decision | Jev P50 / P90 / P95 (ms) | LLM P50 / P90 / P95 (ms) | Jev / LLM $ per 1,000 |
|---|---:|---:|---:|
| Issue category | 194 / 1005 / 1170 | 1037 / 2161 / 3483 | 0.037 / 0.572 |
| Root cause | 189 / 956 / 1104 | 1006 / 2381 / 3910 | 0.061 / 0.962 |
| Causal change | 195 / 1043 / 1200 | 1002 / 2372 / 3691 | 0.049 / 0.808 |
| Owning team | 196 / 1021 / 1173 | 993 / 2103 / 3148 | 0.053 / 0.833 |
| Evidence sufficiency | 201 / 1013 / 1179 | 999 / 2332 / 3680 | 0.050 / 0.863 |
| Incident relationship | 202 / 920 / 1230 | 864 / 2014 / 2954 | 0.027 / 0.429 |

The dev claims hold: median latency is 4.3× to 5.4× lower (2.4× to 3.5× lower at
P95, where Jev's tail is proportionally heavier) and cost is 15.7× to 17.1× lower
per decision type (16.2× overall). Total for the 3,882 decisions: $0.19 (Jev)
against $3.09 (LLM).
Contract reliability: Jev returned typed output on every call; the LLM's first
attempt was valid on 3,882 of 3,882, with no repairs. Contract failures are
tracked separately from accuracy and were zero.

## F. Calibration and automation

Offline simulation on the validation data. Jev's `confidence` is the API field
as delivered (see `JEV-032`: it is not the probability of the chosen option, and
it is lower than that probability on 74% of choice answers).

| Primitive | Brier | ECE | False-confident (≥ 0.90 and wrong) |
|---|---:|---:|---:|
| Issue category | 0.128 | 0.030 | 7/750 (0.9%) |
| Root cause | 0.272 | 0.246 | 22/750 (2.9%) |
| Causal change | 0.102 | 0.106 | 3/750 (0.4%) |
| Owning team | 0.289 | 0.239 | 40/750 (5.3%) |
| Evidence sufficiency | 0.466 | 0.528 | 34/750 (4.5%) |
| Incident relationship | 0.146 | 0.083 | 12/132 (9.1%) |

Automation coverage: share of decisions automated at or above the threshold,
with the accuracy of that automated subset.

| Threshold | Issue category | Root cause | Causal change | Owning team | Evidence suff. | Incident |
|---|---:|---:|---:|---:|---:|---:|
| ≥ 0.70 | 66.0% at 91.7% | 36.5% at 54.4% | 70.5% at 97.5% | 37.2% at 49.8% | 50.3% at 4.8% | 89.4% at 83.9% |
| ≥ 0.80 | 54.3% at 95.3% | 25.2% at 61.9% | 64.5% at 98.3% | 25.9% at 51.5% | 30.8% at 3.9% | 78.0% at 84.5% |
| ≥ 0.85 | 49.1% at 95.7% | 17.9% at 64.9% | 59.2% at 98.9% | 19.9% at 53.7% | 17.6% at 3.8% | 70.5% at 84.9% |
| ≥ 0.90 | 42.0% at 97.8% | 11.2% at 73.8% | 53.3% at 99.2% | 12.8% at 58.3% | 4.9% at 8.1% | 59.8% at 84.8% |
| ≥ 0.95 | 32.1% at 99.2% | 4.8% at 83.3% | 46.4% at 99.4% | 6.9% at 50.0% | 1.1% at 25.0% | 37.1% at 87.8% |

Target-error coverage: the largest share that can be automated while the
observed error in the automated subset stays at or below the target (Wilson 95%
upper bound of that error in brackets).

| Target | Issue category | Root cause | Causal change | Owning team | Evidence suff. | Incident |
|---|---:|---:|---:|---:|---:|---:|
| ≤ 5% | 56.4% [7.5] | 0.9% [35.4] | 82.4% [6.8] | 0.4% [56.2] | 0.1% [79.3] | 3.0% [49.0] |
| ≤ 2% | 41.5% [4.1] | 0.9% [35.4] | 69.3% [3.5] | 0.4% [56.2] | 0.1% [79.3] | 3.0% [49.0] |
| ≤ 1% | 35.7% [2.7] | 0.9% [35.4] | 58.7% [2.3] | 0.4% [56.2] | 0.1% [79.3] | 3.0% [49.0] |

Caveats. The cutoffs are chosen after the fact on the same data, so these
coverages are optimistic and are not a pre-committed operating point; a locked
run would need the threshold fixed beforehand. The causal-change coverage is
mostly the 307 trivial decisions. Only issue category and causal change have an
automation region worth the name. For owning team, 40 of Jev's 96 predictions at
confidence ≥ 0.90 are wrong; for root cause, 22 of 84 (`JEV-033`).

## G. Capability map

Pre-registered rubric: T1 lower 95% bound above the best evidence-blind rule; T2
no material dev-to-validation degradation and candidate recall ≥ 0.95; T3
accuracy ≥ 0.85 and false-confident ≤ 0.05; T4 adequate sample. First match wins.

| Primitive | T1 | T2 | T3 | T4 | Class | Measured reasoning |
|---|:-:|:-:|:-:|:-:|---|---|
| Causal change | pass | pass | pass | pass | **Candidate for locked benchmark** | 89.3% (lower bound 87.2) against 71.3%; stable; 0.4% false-confident; recall 100%. Qualifiers above: 41% trivial decisions (81.9% on the rest, below 0.85), 76.5% detection when a change exists, group B n=6. |
| Issue category | pass | pass | fail | pass | Supporting-only | Stable and calibrated, but 78.4% is below 0.85 and the LLM ties it. Value is cost, latency and a 42% automation region at 2.2% error. |
| Root cause | pass | **fail** | fail | pass | Supporting-only | Beats a 10.4% baseline, but degraded on validation and fails T3 in any case (37.2%). 62.4% accurate when it commits, 40% abstentions. |
| Owning team | pass | pass | fail | pass | Supporting-only | Generalizes and is far ahead of the LLM (+23.1), but 37.6% absolute and 5.3% false-confident. Acceptable-team accuracy is 52.8%. |
| Evidence sufficiency | fail | pass | fail | pass | Weak / deprioritize | 12.4% against a 92.9% baseline; the LLM (41.9%) is also below it. Jev answers "partially sufficient" on 87% of decisions. |
| Incident relationship | fail | pass | fail | pass | Weak / deprioritize | 82.6% [76.5, 88.6] does not clear the 78.0% "never related" baseline. Finds 8 of 29 related incidents; all 12 of its high-confidence errors are misses. |

These are engineering triage classes, not scores. The LLM comparison is shown
next to them and is not part of the rubric.

## The twelve success questions

1. **Do the candidate strategies generalize?** Yes. Recall 98.7% (root cause), 100% (causal change), 99.9% acceptable / 99.7% primary (team), 100% (issue category), all above 0.95.
2. **Does issue-category performance generalize?** Yes: 73.0% to 78.4% (sampling variation), calibrated (ECE 0.030), tied with the LLM.
3. **Does root-cause performance generalize?** No, not fully. 48.0% to 37.2% is a material degradation by the protocol (interval upper edge −0.6); the LLM stayed flat, which points to dev optimism. The Jev lead over the LLM persists (+16.5).
4. **Does causal-change accuracy remain strong?** Yes overall (89.3%, 92.0% on dev). Read it with the trivial-decision share and the 76.5% detection rate.
5. **Can we measure Jev when the true event is older than a newer candidate?** Barely. Six cases; all correct, none by picking the newest. Too few to settle the question.
6. **Does Jev keep a low false-positive rate on no-change cases?** Yes: 4.8% (dev 5.9%), against 18.2% for the LLM.
7. **Does owning-team performance generalize?** Yes (36.0% to 37.6%; acceptable 49.0% to 52.8%; recall ≥ 99.7%), at a modest absolute level.
8. **Does evidence sufficiency remain weak?** Yes: 12.4% against 92.9% for always answering "sufficient"; the LLM is also below it.
9. **Is the incident sample now large enough to interpret?** Yes: 132 decisions from 132 distinct cases, 29 true-related (dev had 17 and 5). It reads negatively: not above the "never related" baseline.
10. **Does the Jev-versus-LLM ranking generalize?** Five of six decisions, with narrower leads on root cause and causal change. Incident changed reading, on thin evidence.
11. **Do latency and cost advantages persist?** Yes: median 4.3× to 5.4× faster (2.4× to 3.5× at P95), about 16× cheaper per decision. The LLM price remains an assumption.
12. **Which primitives are strong enough for the locked benchmark?** Causal change alone under the pre-registered rubric.

## Recommendation for the locked benchmark

This is a recommendation; nothing has been run and the decision is yours.

**Advance: causal change.** Before the locked run, three things should be settled
and written into a new pre-registration (they cannot be decided after seeing test
results):

1. Report accuracy on the non-trivial decisions (a real change offered) as a
   co-primary metric next to the headline, together with detection rate and
   no-change accuracy, so the trivial 41% cannot carry the result.
2. Decide the change-id question (`JEV-025`). The artifact replicates on
   validation. Options: keep canonical ids for comparability, or use opaque
   keys. A cheap opaque-key control on validation (about $0.04 for Jev and about
   $0.6 for the LLM) would tell you whether Jev relies on the ids. It needs your
   approval because it re-uses validation.
3. Accept that group B will stay near-empty on the test split too, and decide
   whether that matters for the claim you want to make.

**Optional, report-only: issue category, root cause, owning team.** They failed
the pre-registered bar (T3, plus T2 for root cause) but their Jev-over-LLM
ranking generalized and running them costs cents. If you include them, treat them
as descriptive supporting results, not pass/fail claims.

**Do not spend the locked split on evidence sufficiency or incident
relationship.** Both are weak. Any redesign (a different label or question for
sufficiency; a sample with more genuinely related incidents) would need untouched
data, and the test split is the only untouched data left.

**Any change after Stage C is a new, separately versioned experiment.** It cannot
be validated on the same 750 cases without turning them into a development set,
and it must not overwrite this result.

## Changes made after seeing results

None to the frozen configuration, questions, candidates, contexts, models or
protocol. Three additions, all analysis-side:

1. **Label fix (`JEV-029`).** The pre-registered "material degradation" wording was applied to lower-is-better rows without inverting direction, and an empty size bin was printed. Fixed in `stage_c_report.py` and the report regenerated; the diff is two lines, no number changed, and no classification changed (the rubric reads only accuracy and recall rows).
2. **Post-hoc analysis** (`stage_c_posthoc.py`): the causal split, non-trivial decisions, `RC40` abstention, id artifact, sufficiency prediction mix, incident structure and totals. Labelled post-hoc, never used for the classes above.
3. **Five offline tests** for the fixed label logic and the post-hoc helpers.

## Limits of this evidence

- One run per system. Jev is not bit-deterministic (93% to 100% same answer on identical inputs in Stage B), so single-run accuracies carry run-to-run noise beyond the sampling intervals; no repeat run was made on validation.
- All 2,500 graph cases are synthetic and 10% of the generator's output (`P4-003`).
- The dev cohort (100 cases) was small, so dev-to-validation intervals are wide; "sampling variation" means "not distinguishable", not "equal".
- The LLM run is single, unseeded, with an assumed price.
- Automation coverage and target-error figures are post-hoc optimal cutoffs.
- Confidence is not comparable across systems and is a non-standard field for Jev (`JEV-032`); the protocol's phrase "native probability" was loose and the protocol file was not edited.
