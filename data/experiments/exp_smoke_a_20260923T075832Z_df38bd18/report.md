# Experiment: smoke_a

- experiment_id: `exp_smoke_a_20260923T075832Z_df38bd18`
- experiment_type: jev_primitive
- kind: smoke
- created_at: 2026-09-23T07:58:32.656101+00:00
- dataset_split: dev
- num_cases: 5
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v1
- candidate_strategy_version: v1
- evaluator_version: v1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical'}

## issue_category (choice)

- n_decisions: 5  (errors: 0, contract failures: 0)
- accuracy: 80.0%
- acceptable_match_rate: 80.0%
- accuracy 95% CI: 80.0% [40.0%, 100.0%] (n=5)
- Brier: 0.1056
- ECE: 0.1780
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=5)
- macro F1: 0.733
- candidate recall: 100.0% (avg candidates: 18.0)
- end-to-end accuracy: 80.0% | conditional accuracy given candidate present: 80.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 80.0% | 20.0% |
| >= 0.8 | 80.0% | 100.0% | 0.0% |
| >= 0.85 | 80.0% | 100.0% | 0.0% |
| >= 0.9 | 80.0% | 100.0% | 0.0% |
| >= 0.95 | 60.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 80.0% | 4 |
| <=2% | 80.0% | 4 |
| <=1% | 80.0% | 4 |

Slices:

- difficulty_archetype:
  - clear: n=3, accuracy=100.0%, mean_confidence=95.7%
  - customer_misdiagnosis: n=1, accuracy=0.0%, mean_confidence=72.0%
  - vague: n=1, accuracy=100.0%, mean_confidence=96.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=100.0%, mean_confidence=96.0%
  - sufficient: n=4, accuracy=75.0%, mean_confidence=89.8%

## root_cause (choice)

- n_decisions: 5  (errors: 0, contract failures: 0)
- accuracy: 20.0%
- acceptable_match_rate: 20.0%
- accuracy 95% CI: 20.0% [0.0%, 60.0%] (n=5)
- Brier: 0.4118
- ECE: 0.6040
- false-confident rate (wrong AND conf>=0.9): 20.0% (n=5)
- macro F1: 0.167
- candidate recall: 80.0% (avg candidates: 12.0)
- end-to-end accuracy: 20.0% | conditional accuracy given candidate present: 25.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 40.0% | 50.0% | 50.0% |
| >= 0.8 | 20.0% | 0.0% | 100.0% |
| >= 0.85 | 20.0% | 0.0% | 100.0% |
| >= 0.9 | 20.0% | 0.0% | 100.0% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=3, accuracy=33.3%, mean_confidence=72.7%
  - customer_misdiagnosis: n=1, accuracy=0.0%, mean_confidence=68.0%
  - vague: n=1, accuracy=0.0%, mean_confidence=66.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=91.0%
  - sufficient: n=4, accuracy=25.0%, mean_confidence=65.3%

## causal_change (choice)

- n_decisions: 5  (errors: 0, contract failures: 0)
- accuracy: 60.0%
- acceptable_match_rate: 60.0%
- accuracy 95% CI: 60.0% [20.0%, 100.0%] (n=5)
- Brier: 0.3788
- ECE: 0.4380
- false-confident rate (wrong AND conf>=0.9): 40.0% (n=5)
- macro F1: 0.417
- candidate recall: 60.0% (avg candidates: 1.6)
- end-to-end accuracy: 60.0% | conditional accuracy given candidate present: 100.0%
- selected-is-newest-change rate: 50.0%
- accuracy when true causal change IS newest: 100.0% (n=1)
- accuracy when true causal change is OLDER than a distractor: 0.0% (n=1)

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 60.0% | 40.0% |
| >= 0.8 | 80.0% | 50.0% | 50.0% |
| >= 0.85 | 80.0% | 50.0% | 50.0% |
| >= 0.9 | 80.0% | 50.0% | 50.0% |
| >= 0.95 | 60.0% | 66.7% | 33.3% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=3, accuracy=33.3%, mean_confidence=96.7%
  - customer_misdiagnosis: n=1, accuracy=100.0%, mean_confidence=71.0%
  - vague: n=1, accuracy=100.0%, mean_confidence=100.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=100.0%, mean_confidence=100.0%
  - sufficient: n=4, accuracy=50.0%, mean_confidence=90.2%

## owning_team (choice)

- n_decisions: 5  (errors: 0, contract failures: 0)
- accuracy: 60.0%
- acceptable_match_rate: 60.0%
- accuracy 95% CI: 60.0% [20.0%, 100.0%] (n=5)
- Brier: 0.3487
- ECE: 0.4920
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=5)
- macro F1: 0.467
- candidate recall: 60.0% (avg candidates: 6.0)
- end-to-end accuracy: 60.0% | conditional accuracy given candidate present: 100.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 80.0% | 50.0% | 50.0% |
| >= 0.8 | 60.0% | 33.3% | 66.7% |
| >= 0.85 | 40.0% | 50.0% | 50.0% |
| >= 0.9 | 20.0% | 100.0% | 0.0% |
| >= 0.95 | 20.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 20.0% | 1 |
| <=2% | 20.0% | 1 |
| <=1% | 20.0% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=3, accuracy=66.7%, mean_confidence=76.3%
  - customer_misdiagnosis: n=1, accuracy=0.0%, mean_confidence=88.0%
  - vague: n=1, accuracy=100.0%, mean_confidence=75.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=81.0%
  - sufficient: n=4, accuracy=75.0%, mean_confidence=77.8%

## evidence_sufficiency (choice)

- n_decisions: 5  (errors: 0, contract failures: 0)
- accuracy: 0.0%
- acceptable_match_rate: 0.0%
- accuracy 95% CI: 0.0% [0.0%, 0.0%] (n=5)
- Brier: 0.5282
- ECE: 0.7240
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=5)
- macro F1: 0.000
- candidate recall: 100.0% (avg candidates: 3.0)
- end-to-end accuracy: 0.0% | conditional accuracy given candidate present: 0.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 60.0% | 0.0% | 100.0% |
| >= 0.8 | 20.0% | 0.0% | 100.0% |
| >= 0.85 | 0.0% | n/a | n/a |
| >= 0.9 | 0.0% | n/a | n/a |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=3, accuracy=0.0%, mean_confidence=76.3%
  - customer_misdiagnosis: n=1, accuracy=0.0%, mean_confidence=69.0%
  - vague: n=1, accuracy=0.0%, mean_confidence=64.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=70.0%
  - sufficient: n=4, accuracy=0.0%, mean_confidence=73.0%
