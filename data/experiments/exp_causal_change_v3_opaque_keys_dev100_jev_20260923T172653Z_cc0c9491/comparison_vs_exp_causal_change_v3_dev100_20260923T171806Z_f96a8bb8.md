# Causal change: Jev canonical ids vs Jev opaque keys

- Jev canonical ids: `exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8`
- Jev opaque keys: `exp_causal_change_v3_opaque_keys_dev100_jev_20260923T172653Z_cc0c9491`
- 100 identical ordered dev cases; both sides re-aggregated with evaluator v2.1 (stored files untouched).
- trivial baselines on these cases: always `none` = 68.0%; newest-change-else-none = 71.0%

| Metric | Jev canonical ids | Jev opaque keys |
|---|---:|---:|
| Candidate recall | 100.0% | 100.0% |
| Cases with no true candidate | 0 | 0 |
| Avg candidates (incl. `none`) | 1.80 | 1.80 |
| Median / P90 candidates | 2.0 / 3 | 2.0 / 3 |
| End-to-end accuracy | 92.0% | 91.0% |
| Conditional accuracy (true change offered) | 92.0% | 91.0% |
| Macro F1 | 0.782 | 0.755 |
| False-confident rate (wrong at conf >= 0.90) | 0.0% (0) | 0.0% (0) |
| No-causal-change accuracy | 94.1% | 94.1% |
| Distractor-selection rate (all decisions) | 4.0% | 4.0% |
| Distractor-selection rate (a distractor was offered) | 10.0% (n=40) | 10.0% (n=40) |
| Latency P50 / P95 (ms) | 181 / 438 | 180 / 555 |
| Mean input tokens | 1202 | 1199 |
| Cost per 1,000 decisions (USD) | 0.0505 | 0.0503 |

## Recency and distractor groups

A = true change is the newest candidate; B = true change is older than at least one distractor; C = no causal change; D = two or more real change candidates were offered (overlaps A/B/C); E = the true change was not offered at all.

| Group | Jev canonical ids n | Jev canonical ids accuracy | Jev opaque keys n | Jev opaque keys accuracy |
|---|---:|---:|---:|---:|
| A_true_is_newest | 32 | 87.5% | 32 | 84.4% |
| B_true_older_than_a_distractor | 0 | n/a | 0 | n/a |
| C_no_causal_change | 68 | 94.1% | 68 | 94.1% |
| D_multiple_recent_changes | 17 | 88.2% | 17 | 88.2% |
| E_true_change_not_offered | 0 | n/a | 0 | n/a |

**Group B is empty**: no case in this cohort has a visible true cause older than a visible distractor, so this run cannot test recency-vs-causality.

## Paired outcome changes

- wrong under Jev canonical ids, right under Jev opaque keys: 0 (none)
- right under Jev canonical ids, wrong under Jev opaque keys: 1 (CS00152)
- exact McNemar p on those discordant pairs: 1.000
- paired accuracy difference (Jev opaque keys minus Jev canonical ids): {"n": 100, "diff": -0.01, "ci_low": -0.03, "ci_high": 0.0}

## Same inputs, same model: how repeatable is Jev?

- 100 of 100 cases had byte-identical state and candidate sets on both sides; Jev gave the same answer on 99 of them (differed on CS00152).
- Differences on those cases are Jev run-to-run variability, not a candidate-set effect.

## The 0 cases whose candidate set differs

| case | truth | Jev canonical ids predicted | Jev opaque keys predicted | Jev opaque keys confidence | Jev opaque keys correct |
|---|---|---|---|---:|---|

