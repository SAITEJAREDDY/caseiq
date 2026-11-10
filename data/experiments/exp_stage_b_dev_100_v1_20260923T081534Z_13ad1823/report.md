# Experiment: stage_b_dev_100_v1

- experiment_id: `exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:15:34.903490+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v1
- candidate_strategy_version: v1
- evaluator_version: v1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical'}

## issue_category (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 70.0%
- acceptable_match_rate: 70.0%
- accuracy 95% CI: 70.0% [60.0%, 79.0%] (n=100)
- Brier: 0.1795
- ECE: 0.0736
- false-confident rate (wrong AND conf>=0.9): 6.0% (n=100)
- macro F1: 0.567
- candidate recall: 100.0% (avg candidates: 18.0)
- end-to-end accuracy: 70.0% | conditional accuracy given candidate present: 70.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 65.0% | 83.1% | 16.9% |
| >= 0.8 | 56.0% | 83.9% | 16.1% |
| >= 0.85 | 47.0% | 85.1% | 14.9% |
| >= 0.9 | 40.0% | 85.0% | 15.0% |
| >= 0.95 | 34.0% | 88.2% | 11.8% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 10.0% | 10 |
| <=2% | 10.0% | 10 |
| <=1% | 10.0% | 10 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=71.7%, mean_confidence=80.9%
  - customer_misdiagnosis: n=13, accuracy=61.5%, mean_confidence=67.5%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=65.0%
  - multi_component_symptoms: n=6, accuracy=66.7%, mean_confidence=75.0%
  - vague: n=12, accuracy=75.0%, mean_confidence=72.4%
  - wrong_product_mentioned: n=6, accuracy=50.0%, mean_confidence=73.2%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=66.7%, mean_confidence=74.7%
  - sufficient: n=94, accuracy=70.2%, mean_confidence=77.0%

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 26.0%
- acceptable_match_rate: 26.0%
- accuracy 95% CI: 26.0% [18.0%, 34.0%] (n=100)
- Brier: 0.3796
- ECE: 0.4213
- false-confident rate (wrong AND conf>=0.9): 7.0% (n=100)
- macro F1: 0.228
- candidate recall: 68.0% (avg candidates: 12.0)
- end-to-end accuracy: 26.0% | conditional accuracy given candidate present: 38.2%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 52.0% | 30.8% | 69.2% |
| >= 0.8 | 33.0% | 39.4% | 60.6% |
| >= 0.85 | 19.0% | 47.4% | 52.6% |
| >= 0.9 | 12.0% | 41.7% | 58.3% |
| >= 0.95 | 4.0% | 50.0% | 50.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 1.0% | 1 |
| <=2% | 1.0% | 1 |
| <=1% | 1.0% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=21.7%, mean_confidence=67.7%
  - customer_misdiagnosis: n=13, accuracy=30.8%, mean_confidence=69.7%
  - dependency_root_cause: n=3, accuracy=33.3%, mean_confidence=72.0%
  - multi_component_symptoms: n=6, accuracy=16.7%, mean_confidence=68.8%
  - vague: n=12, accuracy=58.3%, mean_confidence=65.7%
  - wrong_product_mentioned: n=6, accuracy=0.0%, mean_confidence=71.8%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=80.2%
  - sufficient: n=94, accuracy=27.7%, mean_confidence=67.4%

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 86.0%
- acceptable_match_rate: 86.0%
- accuracy 95% CI: 86.0% [79.0%, 92.0%] (n=100)
- Brier: 0.1622
- ECE: 0.1638
- false-confident rate (wrong AND conf>=0.9): 5.0% (n=100)
- macro F1: 0.629
- candidate recall: 94.0% (avg candidates: 1.7)
- end-to-end accuracy: 86.0% | conditional accuracy given candidate present: 91.5%
- selected-is-newest-change rate: 48.2%
- accuracy when true causal change IS newest: 88.5% (n=26)
- accuracy when true causal change is OLDER than a distractor: 0.0% (n=2)

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 69.0% | 88.4% | 11.6% |
| >= 0.8 | 61.0% | 90.2% | 9.8% |
| >= 0.85 | 53.0% | 88.7% | 11.3% |
| >= 0.9 | 50.0% | 90.0% | 10.0% |
| >= 0.95 | 47.0% | 91.5% | 8.5% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=80.0%, mean_confidence=80.0%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=75.1%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=69.7%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=66.2%
  - vague: n=12, accuracy=100.0%, mean_confidence=82.0%
  - wrong_product_mentioned: n=6, accuracy=66.7%, mean_confidence=89.3%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=95.2%
  - sufficient: n=94, accuracy=85.1%, mean_confidence=78.0%

## owning_team (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 29.0%
- acceptable_match_rate: 38.0%
- accuracy 95% CI: 29.0% [20.0%, 38.0%] (n=100)
- Brier: 0.3878
- ECE: 0.3580
- false-confident rate (wrong AND conf>=0.9): 12.0% (n=100)
- macro F1: 0.187
- candidate recall: 61.0% (avg candidates: 6.4)
- end-to-end accuracy: 29.0% | conditional accuracy given candidate present: 62.3%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 46.0% | 23.9% | 76.1% |
| >= 0.8 | 29.0% | 24.1% | 75.9% |
| >= 0.85 | 22.0% | 31.8% | 68.2% |
| >= 0.9 | 17.0% | 29.4% | 70.6% |
| >= 0.95 | 11.0% | 27.3% | 72.7% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=23.3%, mean_confidence=61.9%
  - customer_misdiagnosis: n=13, accuracy=30.8%, mean_confidence=63.7%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=69.0%
  - multi_component_symptoms: n=6, accuracy=33.3%, mean_confidence=73.5%
  - vague: n=12, accuracy=50.0%, mean_confidence=70.0%
  - wrong_product_mentioned: n=6, accuracy=50.0%, mean_confidence=74.7%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=68.8%
  - sufficient: n=94, accuracy=30.9%, mean_confidence=64.5%

## evidence_sufficiency (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 2.0%
- acceptable_match_rate: 2.0%
- accuracy 95% CI: 2.0% [0.0%, 5.0%] (n=100)
- Brier: 0.4119
- ECE: 0.5927
- false-confident rate (wrong AND conf>=0.9): 4.0% (n=100)
- macro F1: 0.018
- candidate recall: 100.0% (avg candidates: 3.0)
- end-to-end accuracy: 2.0% | conditional accuracy given candidate present: 2.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 42.0% | 0.0% | 100.0% |
| >= 0.8 | 10.0% | 0.0% | 100.0% |
| >= 0.85 | 8.0% | 0.0% | 100.0% |
| >= 0.9 | 4.0% | 0.0% | 100.0% |
| >= 0.95 | 1.0% | 0.0% | 100.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=3.3%, mean_confidence=62.0%
  - customer_misdiagnosis: n=13, accuracy=0.0%, mean_confidence=55.0%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=57.7%
  - multi_component_symptoms: n=6, accuracy=0.0%, mean_confidence=56.5%
  - vague: n=12, accuracy=0.0%, mean_confidence=64.6%
  - wrong_product_mentioned: n=6, accuracy=0.0%, mean_confidence=67.5%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=16.7%, mean_confidence=77.8%
  - sufficient: n=94, accuracy=1.1%, mean_confidence=60.2%

## incident_relationship (noul)

- n_decisions: 17  (errors: 0, contract failures: 0)
- accuracy: 70.6%
- acceptable_match_rate: 70.6%
- accuracy 95% CI: 70.6% [47.1%, 88.2%] (n=17)
- Brier: 0.2014
- ECE: 0.2206
- false-confident rate (wrong AND conf>=0.9): 5.9% (n=17)
- Noul precision/recall/F1: 0.5/0.2/0.28571428571428575, FPR=8.3%, FNR=80.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 94.1% | 75.0% | 25.0% |
| >= 0.8 | 82.4% | 78.6% | 21.4% |
| >= 0.85 | 76.5% | 76.9% | 23.1% |
| >= 0.9 | 52.9% | 88.9% | 11.1% |
| >= 0.95 | 11.8% | 50.0% | 50.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 5.9% | 1 |
| <=2% | 5.9% | 1 |
| <=1% | 5.9% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=9, accuracy=77.8%, mean_confidence=83.9%
  - customer_misdiagnosis: n=2, accuracy=100.0%, mean_confidence=90.0%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=86.0%
  - multi_component_symptoms: n=1, accuracy=100.0%, mean_confidence=94.0%
  - vague: n=3, accuracy=66.7%, mean_confidence=87.0%
  - wrong_product_mentioned: n=1, accuracy=0.0%, mean_confidence=89.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=50.0%
  - sufficient: n=16, accuracy=75.0%, mean_confidence=88.4%
