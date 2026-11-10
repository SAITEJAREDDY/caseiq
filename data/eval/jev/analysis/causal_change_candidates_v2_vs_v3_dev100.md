# Causal-change candidate generation: v2 vs v3 (dev-100, no Jev call)

- cohort: `exp_stage_b_dev_100_v2_20260923T083737Z_8eabb9a5` (100 dev cases, same ordered ids)
- v2 reproduces the stored Stage B v2 candidate keys for 100/100 cases

| Metric | v2 | v3 |
|---|---:|---:|
| Candidate recall | 94.0% | 100.0% |
| Cases with no true candidate | 6 | 0 |
| Avg candidates (incl. `none`) | 1.73 | 1.80 |
| Median candidates | 2.0 | 2.0 |
| P90 candidates | 3 | 3 |
| Avg real (non-`none`) candidates | 0.73 | 0.80 |
| Cases with zero real candidates | 44 | 39 |
| Cases with a deployment-type candidate | 0 (0.0%) | 7 (7.0%) |
| Cases with duplicate suppression | n/a | 0 (total suppressed 0) |
| Future events dropped by the defensive gate | n/a | 0 |

v2 misses: CS00001, CS00006, CS00075, CS00122, CS00145, CS00165

v3 misses: none

## Structural properties of the v3 candidate sets (read before interpreting Jev's accuracy)

- true causal-change id numbers span [30400, 30469]; every other visible candidate spans [1302, 27899]. The id number alone separates them perfectly: True.
- 7 cases have a visible deployment; in 6 of them that deployment is the true cause.

These are properties of how the synthetic data was generated, observable in the candidate ids, not hidden fields. They mean a system could in principle exploit the id number; the opaque-key control run measures whether Jev/the LLM do.
