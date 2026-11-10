# Experiment: stage_b_dev_100_v2

- experiment_id: `exp_stage_b_dev_100_v2_20260923T083737Z_8eabb9a5`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:37:37.201357+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v2
- candidate_strategy_version: v2
- evaluator_version: v2
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical', 'comparison_baseline_experiment_id': 'exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823'}

## issue_category (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 72.0%
- acceptable_match_rate: 72.0%
- accuracy 95% CI: 72.0% [63.0%, 81.0%] (n=100)
- Brier: 0.1872
- ECE: 0.1179
- false-confident rate (wrong AND conf>=0.9): 6.0% (n=100)
- macro F1: 0.583
- candidate recall: 100.0% (avg candidates: 18.0)
- candidate count distribution: median=18.0, P90=18
- end-to-end accuracy: 72.0% | conditional accuracy given candidate present: 72.0%
- failure decomposition: missing=0, present/jev-wrong=28, present/jev-correct=72, high-confidence-wrong=6

- efficiency: mean latency=174.422 ms; mean input/output tokens=876.38/182.0; total input/output tokens=87638/18200

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 63.0% | 82.5% | 17.5% |
| >= 0.8 | 55.0% | 83.6% | 16.4% |
| >= 0.85 | 48.0% | 85.4% | 14.6% |
| >= 0.9 | 41.0% | 85.4% | 14.6% |
| >= 0.95 | 33.0% | 87.9% | 12.1% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 10.0% | 10 |
| <=2% | 10.0% | 10 |
| <=1% | 10.0% | 10 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=76.7%, mean_confidence=80.9%
  - customer_misdiagnosis: n=13, accuracy=61.5%, mean_confidence=68.8%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=63.7%
  - multi_component_symptoms: n=6, accuracy=66.7%, mean_confidence=74.8%
  - vague: n=12, accuracy=66.7%, mean_confidence=73.5%
  - wrong_product_mentioned: n=6, accuracy=50.0%, mean_confidence=72.5%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=66.7%, mean_confidence=75.3%
  - sufficient: n=94, accuracy=72.3%, mean_confidence=77.2%

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 32.0%
- acceptable_match_rate: 32.0%
- accuracy 95% CI: 32.0% [23.0%, 41.0%] (n=100)
- Brier: 0.2923
- ECE: 0.3250
- false-confident rate (wrong AND conf>=0.9): 2.0% (n=100)
- macro F1: 0.266
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 32.0% | conditional accuracy given candidate present: 32.0%
- failure decomposition: missing=0, present/jev-wrong=68, present/jev-correct=32, high-confidence-wrong=2

- efficiency: mean latency=165.946 ms; mean input/output tokens=1376.75/163.92; total input/output tokens=137675/16392

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 44.0% | 47.7% | 52.3% |
| >= 0.8 | 26.0% | 61.5% | 38.5% |
| >= 0.85 | 19.0% | 68.4% | 31.6% |
| >= 0.9 | 14.0% | 85.7% | 14.3% |
| >= 0.95 | 4.0% | 75.0% | 25.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 1.0% | 1 |
| <=2% | 1.0% | 1 |
| <=1% | 1.0% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=26.7%, mean_confidence=63.2%
  - customer_misdiagnosis: n=13, accuracy=38.5%, mean_confidence=65.9%
  - dependency_root_cause: n=3, accuracy=33.3%, mean_confidence=75.0%
  - multi_component_symptoms: n=6, accuracy=16.7%, mean_confidence=63.0%
  - vague: n=12, accuracy=58.3%, mean_confidence=66.6%
  - wrong_product_mentioned: n=6, accuracy=33.3%, mean_confidence=67.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=77.8%
  - sufficient: n=94, accuracy=34.0%, mean_confidence=63.6%

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 87.0%
- acceptable_match_rate: 87.0%
- accuracy 95% CI: 87.0% [80.0%, 93.0%] (n=100)
- Brier: 0.1743
- ECE: 0.1866
- false-confident rate (wrong AND conf>=0.9): 5.0% (n=100)
- macro F1: 0.646
- candidate recall: 94.0% (avg candidates: 1.7)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 87.0% | conditional accuracy given candidate present: 92.6%
- failure decomposition: missing=6, present/jev-wrong=7, present/jev-correct=87, high-confidence-wrong=5
- selected-is-newest-change rate: 46.4%
- accuracy when true causal change IS newest: 88.5% (n=26)
- accuracy when true causal change is OLDER than a distractor: 0.0% (n=2)

- efficiency: mean latency=175.137 ms; mean input/output tokens=1197.77/37.11; total input/output tokens=119777/3711

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 67.0% | 88.1% | 11.9% |
| >= 0.8 | 60.0% | 90.0% | 10.0% |
| >= 0.85 | 56.0% | 89.3% | 10.7% |
| >= 0.9 | 50.0% | 90.0% | 10.0% |
| >= 0.95 | 46.0% | 91.3% | 8.7% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=81.7%, mean_confidence=79.2%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=73.8%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=61.3%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=64.5%
  - vague: n=12, accuracy=100.0%, mean_confidence=83.7%
  - wrong_product_mentioned: n=6, accuracy=66.7%, mean_confidence=90.3%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=95.3%
  - sufficient: n=94, accuracy=86.2%, mean_confidence=77.2%

## owning_team (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 36.0%
- acceptable_match_rate: 49.0%
- accuracy 95% CI: 36.0% [26.0%, 45.0%] (n=100)
- Brier: 0.3224
- ECE: 0.2287
- false-confident rate (wrong AND conf>=0.9): 5.0% (n=100)
- macro F1: 0.257
- candidate recall: 100.0% (avg candidates: 11.9)
- candidate count distribution: median=12.0, P90=12
- end-to-end accuracy: 36.0% | conditional accuracy given candidate present: 49.0%
- failure decomposition: missing=0, present/jev-wrong=64, present/jev-correct=36, high-confidence-wrong=5
- team candidate recall: primary=99.0%, acceptable=100.0%
- team accuracy: primary=36.0%, acceptable=49.0%; conditional primary=36.4%, conditional acceptable=49.0%

- efficiency: mean latency=167.915 ms; mean input/output tokens=1290.02/127.83; total input/output tokens=129002/12783

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 34.0% | 32.4% | 67.6% |
| >= 0.8 | 21.0% | 33.3% | 66.7% |
| >= 0.85 | 11.0% | 36.4% | 63.6% |
| >= 0.9 | 8.0% | 37.5% | 62.5% |
| >= 0.95 | 6.0% | 33.3% | 66.7% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=33.3%, mean_confidence=56.8%
  - customer_misdiagnosis: n=13, accuracy=30.8%, mean_confidence=54.9%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=48.7%
  - multi_component_symptoms: n=6, accuracy=33.3%, mean_confidence=62.3%
  - vague: n=12, accuracy=50.0%, mean_confidence=62.0%
  - wrong_product_mentioned: n=6, accuracy=66.7%, mean_confidence=69.3%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=33.3%, mean_confidence=63.0%
  - sufficient: n=94, accuracy=36.2%, mean_confidence=57.7%

## evidence_sufficiency (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 14.0%
- acceptable_match_rate: 14.0%
- accuracy 95% CI: 14.0% [8.0%, 21.0%] (n=100)
- Brier: 0.4492
- ECE: 0.4929
- false-confident rate (wrong AND conf>=0.9): 2.0% (n=100)
- macro F1: 0.093
- candidate recall: 100.0% (avg candidates: 3.0)
- candidate count distribution: median=3.0, P90=3
- end-to-end accuracy: 14.0% | conditional accuracy given candidate present: 14.0%
- failure decomposition: missing=0, present/jev-wrong=86, present/jev-correct=14, high-confidence-wrong=2

- efficiency: mean latency=254.083 ms; mean input/output tokens=1223.79/61.61; total input/output tokens=122379/6161

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 53.0% | 5.7% | 94.3% |
| >= 0.8 | 24.0% | 0.0% | 100.0% |
| >= 0.85 | 12.0% | 0.0% | 100.0% |
| >= 0.9 | 2.0% | 0.0% | 100.0% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=15.0%, mean_confidence=60.8%
  - customer_misdiagnosis: n=13, accuracy=7.7%, mean_confidence=66.4%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=66.3%
  - multi_component_symptoms: n=6, accuracy=16.7%, mean_confidence=77.2%
  - vague: n=12, accuracy=16.7%, mean_confidence=61.5%
  - wrong_product_mentioned: n=6, accuracy=16.7%, mean_confidence=69.5%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=66.7%, mean_confidence=58.8%
  - sufficient: n=94, accuracy=10.6%, mean_confidence=63.6%

## incident_relationship (noul)

- n_decisions: 17  (errors: 0, contract failures: 0)
- accuracy: 70.6%
- acceptable_match_rate: 70.6%
- accuracy 95% CI: 70.6% [47.1%, 88.2%] (n=17)
- Brier: 0.2044
- ECE: 0.2200
- false-confident rate (wrong AND conf>=0.9): 5.9% (n=17)
- failure decomposition: missing=0, present/jev-wrong=5, present/jev-correct=12, high-confidence-wrong=1
- Noul precision/recall/F1: 0.5/0.2/0.28571428571428575, FPR=8.3%, FNR=80.0%

- efficiency: mean latency=159.98235294117646 ms; mean input/output tokens=639.8235294117648/21.0; total input/output tokens=10877/357

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 94.1% | 75.0% | 25.0% |
| >= 0.8 | 76.5% | 76.9% | 23.1% |
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
  - clear: n=9, accuracy=77.8%, mean_confidence=83.4%
  - customer_misdiagnosis: n=2, accuracy=100.0%, mean_confidence=89.5%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=86.0%
  - multi_component_symptoms: n=1, accuracy=100.0%, mean_confidence=94.0%
  - vague: n=3, accuracy=66.7%, mean_confidence=87.3%
  - wrong_product_mentioned: n=1, accuracy=0.0%, mean_confidence=88.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=51.0%
  - sufficient: n=16, accuracy=75.0%, mean_confidence=88.1%
