# Experiment: stage_b_final_dev100_jev

- experiment_id: `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T17:36:52.848899+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v4_operational', 'candidate_generation_versions': {'issue_category': 'v1', 'root_cause': 'v2', 'causal_change': 'v3', 'owning_team': 'v2', 'evidence_sufficiency': 'v1', 'incident_relationship': 'v1'}, 'causal_key_mode': 'canonical', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': {'name': 'stage_b_frozen_v1', 'config_sha256': '0f72b8e2734b37b4bd0518bcc6dd9d376c1e39e9187b4470b3a95c32cc51d788', 'status': 'pre_freeze_versions_only'}, 'pricing_version': '2026-09-23'}

## issue_category (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 73.0%
- acceptable_match_rate: 73.0%
- accuracy 95% CI: 73.0% [64.0%, 82.0%] (n=100)
- Brier: 0.1892
- ECE: 0.0941
- false-confident rate (wrong AND conf>=0.9): 6.0% (n=100)
- macro F1: 0.587
- candidate recall: 100.0% (avg candidates: 18.0)
- candidate count distribution: median=18.0, P90=18
- end-to-end accuracy: 73.0% | conditional accuracy given candidate present: 73.0%
- failure decomposition: missing=0, present/jev-wrong=27, present/jev-correct=73, high-confidence-wrong=6
- strict first-attempt accuracy (contract failures count as wrong): 73.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (IC13)=18.0%

- efficiency: mean latency=198.523 ms (P50=165.60000000000002, P95=412.8); mean input/output tokens=876.38/182.0; total input/output tokens=87638/18200
- cost (pricing 2026-09-23): total $0.0037; $0.037 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 66.0% | 81.8% | 18.2% |
| >= 0.8 | 56.0% | 83.9% | 16.1% |
| >= 0.85 | 49.0% | 83.7% | 16.3% |
| >= 0.9 | 42.0% | 85.7% | 14.3% |
| >= 0.95 | 33.0% | 87.9% | 12.1% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 10.0% | 10 |
| <=2% | 10.0% | 10 |
| <=1% | 10.0% | 10 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=76.7%, mean_confidence=81.5%
  - customer_misdiagnosis: n=13, accuracy=61.5%, mean_confidence=67.8%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=62.7%
  - multi_component_symptoms: n=6, accuracy=66.7%, mean_confidence=74.8%
  - vague: n=12, accuracy=75.0%, mean_confidence=72.2%
  - wrong_product_mentioned: n=6, accuracy=50.0%, mean_confidence=73.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=66.7%, mean_confidence=73.8%
  - sufficient: n=94, accuracy=73.4%, mean_confidence=77.3%

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 48.0%
- acceptable_match_rate: 48.0%
- accuracy 95% CI: 48.0% [38.0%, 58.0%] (n=100)
- Brier: 0.2920
- ECE: 0.2405
- false-confident rate (wrong AND conf>=0.9): 3.0% (n=100)
- macro F1: 0.445
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 48.0% | conditional accuracy given candidate present: 48.0%
- failure decomposition: missing=0, present/jev-wrong=52, present/jev-correct=48, high-confidence-wrong=3
- strict first-attempt accuracy (contract failures count as wrong): 48.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (RC14)=10.0%

- efficiency: mean latency=213.52900000000002 ms (P50=173.3, P95=468.2); mean input/output tokens=1478.92/163.92; total input/output tokens=147892/16392
- cost (pricing 2026-09-23): total $0.0062; $0.062 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 42.0% | 57.1% | 42.9% |
| >= 0.8 | 25.0% | 68.0% | 32.0% |
| >= 0.85 | 21.0% | 71.4% | 28.6% |
| >= 0.9 | 13.0% | 76.9% | 23.1% |
| >= 0.95 | 6.0% | 66.7% | 33.3% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 2.0% | 2 |
| <=2% | 2.0% | 2 |
| <=1% | 2.0% | 2 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=43.3%, mean_confidence=62.0%
  - customer_misdiagnosis: n=13, accuracy=53.8%, mean_confidence=65.4%
  - dependency_root_cause: n=3, accuracy=66.7%, mean_confidence=70.7%
  - multi_component_symptoms: n=6, accuracy=50.0%, mean_confidence=66.8%
  - vague: n=12, accuracy=50.0%, mean_confidence=71.7%
  - wrong_product_mentioned: n=6, accuracy=66.7%, mean_confidence=60.2%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=78.3%
  - sufficient: n=94, accuracy=51.1%, mean_confidence=63.1%

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 92.0%
- acceptable_match_rate: 92.0%
- accuracy 95% CI: 92.0% [87.0%, 97.0%] (n=100)
- Brier: 0.1283
- ECE: 0.1622
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.782
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 92.0% | conditional accuracy given candidate present: 92.0%
- failure decomposition: missing=0, present/jev-wrong=8, present/jev-correct=92, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 92.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (none)=68.0%; newest-change-else-none=71.0%
- recency A_true_is_newest: n=32, accuracy=87.5%, selected-newest=87.5%, selected-none=12.5%
- recency B_true_older_than_a_distractor: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency C_no_causal_change: n=68, accuracy=94.1%, selected-newest=4.4%, selected-none=94.1%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=17, accuracy=88.2%
- no-causal-change accuracy=94.1%; distractor-selection rate=4.0% of all decisions, 10.0% when a distractor was offered (n=40)
- selected-is-newest-change rate: 50.8%
- accuracy when true causal change IS newest: 87.5% (n=32)
- accuracy when true causal change is OLDER than a distractor: n/a (n=0)

- efficiency: mean latency=191.895 ms (P50=168.85, P95=302.3); mean input/output tokens=1201.97/38.32; total input/output tokens=120197/3832
- cost (pricing 2026-09-23): total $0.0050; $0.050 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 63.0% | 96.8% | 3.2% |
| >= 0.8 | 56.0% | 100.0% | 0.0% |
| >= 0.85 | 48.0% | 100.0% | 0.0% |
| >= 0.9 | 44.0% | 100.0% | 0.0% |
| >= 0.95 | 42.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 87.0% | 87 |
| <=2% | 61.0% | 61 |
| <=1% | 60.0% | 60 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=88.3%, mean_confidence=75.6%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=77.0%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=67.7%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=67.2%
  - vague: n=12, accuracy=100.0%, mean_confidence=81.7%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=83.5%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=95.3%
  - sufficient: n=94, accuracy=91.5%, mean_confidence=75.0%

## owning_team (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 36.0%
- acceptable_match_rate: 49.0%
- accuracy 95% CI: 36.0% [27.0%, 45.0%] (n=100)
- Brier: 0.3295
- ECE: 0.2452
- false-confident rate (wrong AND conf>=0.9): 5.0% (n=100)
- macro F1: 0.262
- candidate recall: 100.0% (avg candidates: 11.9)
- candidate count distribution: median=12.0, P90=12
- end-to-end accuracy: 36.0% | conditional accuracy given candidate present: 49.0%
- failure decomposition: missing=0, present/jev-wrong=64, present/jev-correct=36, high-confidence-wrong=5
- team candidate recall: primary=99.0%, acceptable=100.0%
- team accuracy: primary=36.0%, acceptable=49.0%; conditional primary=36.4%, conditional acceptable=49.0%
- strict first-attempt accuracy (contract failures count as wrong): 36.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (TM08)=16.0%

- efficiency: mean latency=215.19400000000002 ms (P50=173.85, P95=287.5); mean input/output tokens=1290.02/127.83; total input/output tokens=129002/12783
- cost (pricing 2026-09-23): total $0.0054; $0.054 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 34.0% | 32.4% | 67.6% |
| >= 0.8 | 24.0% | 29.2% | 70.8% |
| >= 0.85 | 12.0% | 33.3% | 66.7% |
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
  - clear: n=60, accuracy=33.3%, mean_confidence=57.8%
  - customer_misdiagnosis: n=13, accuracy=30.8%, mean_confidence=54.4%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=49.7%
  - multi_component_symptoms: n=6, accuracy=33.3%, mean_confidence=62.7%
  - vague: n=12, accuracy=50.0%, mean_confidence=62.1%
  - wrong_product_mentioned: n=6, accuracy=66.7%, mean_confidence=68.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=33.3%, mean_confidence=63.3%
  - sufficient: n=94, accuracy=36.2%, mean_confidence=58.2%

## evidence_sufficiency (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 14.0%
- acceptable_match_rate: 14.0%
- accuracy 95% CI: 14.0% [8.0%, 21.0%] (n=100)
- Brier: 0.4533
- ECE: 0.5045
- false-confident rate (wrong AND conf>=0.9): 2.0% (n=100)
- macro F1: 0.093
- candidate recall: 100.0% (avg candidates: 3.0)
- candidate count distribution: median=3.0, P90=3
- end-to-end accuracy: 14.0% | conditional accuracy given candidate present: 14.0%
- failure decomposition: missing=0, present/jev-wrong=86, present/jev-correct=14, high-confidence-wrong=2
- strict first-attempt accuracy (contract failures count as wrong): 14.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (sufficient)=94.0%

- efficiency: mean latency=210.32299999999998 ms (P50=171.3, P95=314.9); mean input/output tokens=1223.79/61.58; total input/output tokens=122379/6158
- cost (pricing 2026-09-23): total $0.0051; $0.051 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 48.0% | 4.2% | 95.8% |
| >= 0.8 | 27.0% | 0.0% | 100.0% |
| >= 0.85 | 13.0% | 0.0% | 100.0% |
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
  - customer_misdiagnosis: n=13, accuracy=7.7%, mean_confidence=66.8%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=67.3%
  - multi_component_symptoms: n=6, accuracy=16.7%, mean_confidence=76.0%
  - vague: n=12, accuracy=16.7%, mean_confidence=62.2%
  - wrong_product_mentioned: n=6, accuracy=16.7%, mean_confidence=69.7%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=66.7%, mean_confidence=58.7%
  - sufficient: n=94, accuracy=10.6%, mean_confidence=63.7%

## incident_relationship (noul)

- n_decisions: 17  (errors: 0, contract failures: 0)
- accuracy: 70.6%
- acceptable_match_rate: 70.6%
- accuracy 95% CI: 70.6% [47.1%, 88.2%] (n=17)
- Brier: 0.2034
- ECE: 0.2076
- false-confident rate (wrong AND conf>=0.9): 5.9% (n=17)
- failure decomposition: missing=0, present/jev-wrong=5, present/jev-correct=12, high-confidence-wrong=1
- Noul precision/recall/F1: 0.5/0.2/0.28571428571428575, FPR=8.3%, FNR=80.0%
- strict first-attempt accuracy (contract failures count as wrong): 70.6%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (False)=70.6%

- efficiency: mean latency=166.77647058823527 ms (P50=156.0, P95=296.5); mean input/output tokens=639.8235294117648/21.0; total input/output tokens=10877/357
- cost (pricing 2026-09-23): total $0.0005; $0.027 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 94.1% | 75.0% | 25.0% |
| >= 0.8 | 76.5% | 76.9% | 23.1% |
| >= 0.85 | 76.5% | 76.9% | 23.1% |
| >= 0.9 | 47.1% | 87.5% | 12.5% |
| >= 0.95 | 11.8% | 50.0% | 50.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 5.9% | 1 |
| <=2% | 5.9% | 1 |
| <=1% | 5.9% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=9, accuracy=77.8%, mean_confidence=83.7%
  - customer_misdiagnosis: n=2, accuracy=100.0%, mean_confidence=89.5%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=87.0%
  - multi_component_symptoms: n=1, accuracy=100.0%, mean_confidence=94.0%
  - vague: n=3, accuracy=66.7%, mean_confidence=86.3%
  - wrong_product_mentioned: n=1, accuracy=0.0%, mean_confidence=87.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=0.0%, mean_confidence=54.0%
  - sufficient: n=16, accuracy=75.0%, mean_confidence=87.8%
