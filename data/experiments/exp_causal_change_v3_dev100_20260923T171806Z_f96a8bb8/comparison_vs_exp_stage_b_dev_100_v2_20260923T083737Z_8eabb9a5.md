# Causal change: v2 (Stage B v2) vs v3 (rerun)

- v2 (Stage B v2): `exp_stage_b_dev_100_v2_20260923T083737Z_8eabb9a5`
- v3 (rerun): `exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8`
- 100 identical ordered dev cases; both sides re-aggregated with evaluator v2.1 (stored files untouched).
- trivial baselines on these cases: always `none` = 68.0%; newest-change-else-none = 71.0%

| Metric | v2 (Stage B v2) | v3 (rerun) |
|---|---:|---:|
| Candidate recall | 94.0% | 100.0% |
| Cases with no true candidate | 6 | 0 |
| Avg candidates (incl. `none`) | 1.73 | 1.80 |
| Median / P90 candidates | 2.0 / 3 | 2.0 / 3 |
| End-to-end accuracy | 87.0% | 92.0% |
| Conditional accuracy (true change offered) | 92.6% | 92.0% |
| Macro F1 | 0.646 | 0.782 |
| False-confident rate (wrong at conf >= 0.90) | 5.0% (5) | 0.0% (0) |
| No-causal-change accuracy | 94.1% | 94.1% |
| Distractor-selection rate (all decisions) | 4.0% | 4.0% |
| Distractor-selection rate (a distractor was offered) | 10.3% (n=39) | 10.0% (n=40) |
| Latency P50 / P95 (ms) | 157 / 273 | 181 / 438 |
| Mean input tokens | 1198 | 1202 |
| Cost per 1,000 decisions (USD) | 0.0503 | 0.0505 |

## Recency and distractor groups

A = true change is the newest candidate; B = true change is older than at least one distractor; C = no causal change; D = two or more real change candidates were offered (overlaps A/B/C); E = the true change was not offered at all.

| Group | v2 (Stage B v2) n | v2 (Stage B v2) accuracy | v3 (rerun) n | v3 (rerun) accuracy |
|---|---:|---:|---:|---:|
| A_true_is_newest | 26 | 88.5% | 32 | 87.5% |
| B_true_older_than_a_distractor | 0 | n/a | 0 | n/a |
| C_no_causal_change | 68 | 94.1% | 68 | 94.1% |
| D_multiple_recent_changes | 15 | 86.7% | 17 | 88.2% |
| E_true_change_not_offered | 6 | 0.0% | 0 | n/a |

**Group B is empty**: no case in this cohort has a visible true cause older than a visible distractor, so this run cannot test recency-vs-causality.

## Paired outcome changes

- wrong under v2 (Stage B v2), right under v3 (rerun): 5 (CS00001, CS00006, CS00122, CS00145, CS00165)
- right under v2 (Stage B v2), wrong under v3 (rerun): 0 (none)
- exact McNemar p on those discordant pairs: 0.062
- paired accuracy difference (v3 (rerun) minus v2 (Stage B v2)): {"n": 100, "diff": 0.05, "ci_low": 0.01, "ci_high": 0.1}

## Same inputs, same model: how repeatable is Jev?

- 93 of 100 cases had byte-identical state and candidate sets on both sides; Jev gave the same answer on 93 of them.
- Differences on those cases are Jev run-to-run variability, not a candidate-set effect.

## The 7 cases whose candidate set differs

| case | truth | v2 (Stage B v2) predicted | v3 (rerun) predicted | v3 (rerun) confidence | v3 (rerun) correct |
|---|---|---|---|---:|---|
| CS00001 | CH030400 | none | CH030400 | 0.78 | True |
| CS00006 | CH030403 | none | CH030403 | 0.92 | True |
| CS00075 | CH030424 | none | none | 0.77 | False |
| CS00122 | CH030439 | none | CH030439 | 0.31 | True |
| CS00145 | CH030446 | none | CH030446 | 0.55 | True |
| CS00165 | CH030455 | none | CH030455 | 0.25 | True |
| CS00213 | none | none | none | 0.67 | True |

