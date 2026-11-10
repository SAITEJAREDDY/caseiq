# Stage B v1 vs v2

- v1: `exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823`
- v2: `exp_stage_b_dev_100_v2_20260923T083737Z_8eabb9a5`
- Both experiments use the same ordered development case IDs; v1 source records remain unchanged.

## root_cause

| Metric | v1 | v2 |
|---|---:|---:|
| candidate recall | 68.0% | 100.0% |
| avg candidates | 12.0 | 15.9 |
| median / P90 candidates | 12.0 / 12 | 16.0 / 16 |
| conditional accuracy | 38.2% | 32.0% |
| end-to-end accuracy | 26.0% | 32.0% |
| macro F1 | 0.228 | 0.266 |
| false-confident rate | 7.0% | 2.0% |

Failure-source decomposition:

| Source | v1 | v2 |
|---|---:|---:|
| Candidate missing | 32 | 0 |
| Candidate present / Jev wrong | 42 | 68 |
| Candidate present / Jev correct | 26 | 32 |
| Jev wrong with high confidence | 7 | 2 |

## owning_team

| Metric | v1 | v2 |
|---|---:|---:|
| candidate recall | 61.0% | 100.0% |
| avg candidates | 6.4 | 11.9 |
| median / P90 candidates | 6.5 / 9 | 12.0 / 12 |
| conditional accuracy | 62.3% | 49.0% |
| end-to-end accuracy | 29.0% | 36.0% |
| macro F1 | 0.187 | 0.257 |
| false-confident rate | 12.0% | 5.0% |

Failure-source decomposition:

| Source | v1 | v2 |
|---|---:|---:|
| Candidate missing | 39 | 0 |
| Candidate present / Jev wrong | 32 | 64 |
| Candidate present / Jev correct | 29 | 36 |
| Jev wrong with high confidence | 12 | 5 |

## owning-team primary and acceptable routing

| Metric | v1 | v2 |
|---|---:|---:|
| primary candidate recall | 53.0% | 99.0% |
| acceptable candidate recall | 61.0% | 100.0% |
| primary accuracy | 29.0% | 36.0% |
| acceptable accuracy | 38.0% | 49.0% |
| conditional primary accuracy | 54.7% | 36.4% |
| conditional acceptable accuracy | 62.3% | 49.0% |

## Evidence sufficiency

| Metric | v1 | v2 |
|---|---:|---:|
| Accuracy | 2.0% | 14.0% |
| Question version | evidence_sufficiency_v1 | evidence_sufficiency_v2 |

v2 uses a time-gated observable telemetry summary and a versioned operational definition; the v1 2% score is retained as a measurement of its earlier, semantically incomplete state projection.

## Unchanged primitives

| Decision | v1 accuracy | v2 accuracy |
|---|---:|---:|
| issue_category | 70.0% | 72.0% |
| causal_change | 86.0% | 87.0% |
| incident_relationship | 70.6% | 70.6% |
