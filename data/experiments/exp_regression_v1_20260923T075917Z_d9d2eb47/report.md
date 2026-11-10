# Experiment: regression_v1

- experiment_id: `exp_regression_v1_20260923T075917Z_d9d2eb47`
- experiment_type: jev_primitive
- kind: smoke
- created_at: 2026-09-23T07:59:17.505977+00:00
- dataset_split: regression_suite
- num_cases: 9
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v1
- candidate_strategy_version: v1
- evaluator_version: v1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical'}

## issue_category (choice)

- n_decisions: 9  (errors: 0, contract failures: 0)
- accuracy: 77.8%
- acceptable_match_rate: 77.8%
- accuracy 95% CI: 77.8% [44.4%, 100.0%] (n=9)
- Brier: 0.1236
- ECE: 0.2044
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=9)
- macro F1: 0.607
- candidate recall: 100.0% (avg candidates: 18.0)
- end-to-end accuracy: 77.8% | conditional accuracy given candidate present: 77.8%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 88.9% | 87.5% | 12.5% |
| >= 0.8 | 77.8% | 100.0% | 0.0% |
| >= 0.85 | 66.7% | 100.0% | 0.0% |
| >= 0.9 | 66.7% | 100.0% | 0.0% |
| >= 0.95 | 44.4% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 77.8% | 7 |
| <=2% | 77.8% | 7 |
| <=1% | 77.8% | 7 |

Slices:

- difficulty_archetype:
  - clear: n=5, accuracy=100.0%, mean_confidence=94.2%
  - customer_misdiagnosis: n=2, accuracy=0.0%, mean_confidence=72.5%
  - dependency_root_cause: n=1, accuracy=100.0%, mean_confidence=91.0%
  - multi_component_symptoms: n=1, accuracy=100.0%, mean_confidence=99.0%
- evidence_sufficiency:
  - insufficient: n=1, accuracy=100.0%, mean_confidence=100.0%
  - partially_sufficient: n=1, accuracy=100.0%, mean_confidence=92.0%
  - sufficient: n=7, accuracy=71.4%, mean_confidence=87.7%

## root_cause (choice)

- n_decisions: 9  (errors: 0, contract failures: 0)
- accuracy: 0.0%
- acceptable_match_rate: 0.0%
- accuracy 95% CI: 0.0% [0.0%, 0.0%] (n=9)
- Brier: 0.4389
- ECE: 0.6322
- false-confident rate (wrong AND conf>=0.9): 11.1% (n=9)
- macro F1: 0.000
- candidate recall: 66.7% (avg candidates: 12.0)
- end-to-end accuracy: 0.0% | conditional accuracy given candidate present: 0.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 33.3% | 0.0% | 100.0% |
| >= 0.8 | 33.3% | 0.0% | 100.0% |
| >= 0.85 | 11.1% | 0.0% | 100.0% |
| >= 0.9 | 11.1% | 0.0% | 100.0% |
| >= 0.95 | 11.1% | 0.0% | 100.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=5, accuracy=0.0%, mean_confidence=68.2%
  - customer_misdiagnosis: n=2, accuracy=0.0%, mean_confidence=55.5%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=50.0%
  - multi_component_symptoms: n=1, accuracy=0.0%, mean_confidence=67.0%
- evidence_sufficiency:
  - insufficient: n=1, accuracy=0.0%, mean_confidence=98.0%
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=81.0%
  - sufficient: n=7, accuracy=0.0%, mean_confidence=55.7%

## causal_change (choice)

- n_decisions: 9  (errors: 0, contract failures: 0)
- accuracy: 77.8%
- acceptable_match_rate: 77.8%
- accuracy 95% CI: 77.8% [55.6%, 100.0%] (n=9)
- Brier: 0.2216
- ECE: 0.2267
- false-confident rate (wrong AND conf>=0.9): 11.1% (n=9)
- macro F1: 0.679
- candidate recall: 88.9% (avg candidates: 2.2)
- end-to-end accuracy: 77.8% | conditional accuracy given candidate present: 87.5%
- selected-is-newest-change rate: 66.7%
- accuracy when true causal change IS newest: 100.0% (n=4)
- accuracy when true causal change is OLDER than a distractor: n/a (n=0)

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 77.8% | 71.4% | 28.6% |
| >= 0.8 | 44.4% | 75.0% | 25.0% |
| >= 0.85 | 44.4% | 75.0% | 25.0% |
| >= 0.9 | 44.4% | 75.0% | 25.0% |
| >= 0.95 | 44.4% | 75.0% | 25.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=5, accuracy=60.0%, mean_confidence=76.8%
  - customer_misdiagnosis: n=2, accuracy=100.0%, mean_confidence=85.0%
  - dependency_root_cause: n=1, accuracy=100.0%, mean_confidence=79.0%
  - multi_component_symptoms: n=1, accuracy=100.0%, mean_confidence=99.0%
- evidence_sufficiency:
  - insufficient: n=1, accuracy=100.0%, mean_confidence=58.0%
  - partially_sufficient: n=1, accuracy=100.0%, mean_confidence=100.0%
  - sufficient: n=7, accuracy=71.4%, mean_confidence=82.0%

## owning_team (choice)

- n_decisions: 9  (errors: 0, contract failures: 0)
- accuracy: 11.1%
- acceptable_match_rate: 11.1%
- accuracy 95% CI: 11.1% [0.0%, 33.3%] (n=9)
- Brier: 0.3747
- ECE: 0.5589
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=9)
- macro F1: 0.028
- candidate recall: 44.4% (avg candidates: 6.3)
- end-to-end accuracy: 11.1% | conditional accuracy given candidate present: 25.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 44.4% | 25.0% | 75.0% |
| >= 0.8 | 33.3% | 33.3% | 66.7% |
| >= 0.85 | 22.2% | 50.0% | 50.0% |
| >= 0.9 | 11.1% | 100.0% | 0.0% |
| >= 0.95 | 11.1% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 11.1% | 1 |
| <=2% | 11.1% | 1 |
| <=1% | 11.1% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=5, accuracy=20.0%, mean_confidence=71.2%
  - customer_misdiagnosis: n=2, accuracy=0.0%, mean_confidence=58.5%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=81.0%
  - multi_component_symptoms: n=1, accuracy=0.0%, mean_confidence=43.0%
- evidence_sufficiency:
  - insufficient: n=1, accuracy=0.0%, mean_confidence=65.0%
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=60.0%
  - sufficient: n=7, accuracy=14.3%, mean_confidence=67.4%

## evidence_sufficiency (choice)

- n_decisions: 9  (errors: 0, contract failures: 0)
- accuracy: 11.1%
- acceptable_match_rate: 11.1%
- accuracy 95% CI: 11.1% [0.0%, 33.3%] (n=9)
- Brier: 0.4139
- ECE: 0.5222
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=9)
- macro F1: 0.222
- candidate recall: 100.0% (avg candidates: 3.0)
- end-to-end accuracy: 11.1% | conditional accuracy given candidate present: 11.1%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 44.4% | 0.0% | 100.0% |
| >= 0.8 | 22.2% | 0.0% | 100.0% |
| >= 0.85 | 11.1% | 0.0% | 100.0% |
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
  - clear: n=5, accuracy=20.0%, mean_confidence=66.8%
  - customer_misdiagnosis: n=2, accuracy=0.0%, mean_confidence=61.5%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=71.0%
  - multi_component_symptoms: n=1, accuracy=0.0%, mean_confidence=42.0%
- evidence_sufficiency:
  - insufficient: n=1, accuracy=100.0%, mean_confidence=55.0%
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=75.0%
  - sufficient: n=7, accuracy=0.0%, mean_confidence=62.9%

## incident_relationship (noul)

- n_decisions: 3  (errors: 0, contract failures: 0)
- accuracy: 33.3%
- acceptable_match_rate: 33.3%
- accuracy 95% CI: 33.3% [n/a, n/a] (n=3)
- Brier: 0.3255
- ECE: 0.5133
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=3)
- Noul precision/recall/F1: 0.5/0.5/0.5, FPR=100.0%, FNR=50.0%

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 66.7% | 50.0% | 50.0% |
| >= 0.8 | 33.3% | 0.0% | 100.0% |
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
  - clear: n=3, accuracy=33.3%, mean_confidence=70.7%
- evidence_sufficiency:
  - insufficient: n=1, accuracy=0.0%, mean_confidence=82.0%
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=51.0%
  - sufficient: n=1, accuracy=100.0%, mean_confidence=79.0%
