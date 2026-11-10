# Experiment: stage_b_final_dev100_llm

- experiment_id: `exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff`
- experiment_type: llm_primitive_baseline
- kind: engineering
- created_at: 2026-09-23T17:36:53.262439+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v4_operational', 'candidate_generation_versions': {'issue_category': 'v1', 'root_cause': 'v2', 'causal_change': 'v3', 'owning_team': 'v2', 'evidence_sufficiency': 'v1', 'incident_relationship': 'v1'}, 'causal_key_mode': 'canonical', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': {'name': 'stage_b_frozen_v1', 'config_sha256': '0f72b8e2734b37b4bd0518bcc6dd9d376c1e39e9187b4470b3a95c32cc51d788', 'status': 'pre_freeze_versions_only'}, 'pricing_version': '2026-09-23', 'llm_model': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'llm_temperature': 0.1, 'llm_max_tokens': 400, 'llm_repair_max_attempts': 1, 'paired_jev_experiment_id': 'exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24'}

## issue_category (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 76.0%
- acceptable_match_rate: 76.0%
- accuracy 95% CI: 76.0% [68.0%, 84.0%] (n=100)
- Brier: 0.1833
- ECE: 0.0690
- false-confident rate (wrong AND conf>=0.9): 4.0% (n=100)
- macro F1: 0.645
- candidate recall: 100.0% (avg candidates: 18.0)
- candidate count distribution: median=18.0, P90=18
- end-to-end accuracy: 76.0% | conditional accuracy given candidate present: 76.0%
- failure decomposition: missing=0, present/jev-wrong=24, present/jev-correct=76, high-confidence-wrong=4
- strict first-attempt accuracy (contract failures count as wrong): 76.0%
- contract: first-attempt valid=100/100 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (IC13)=18.0%

- efficiency: mean latency=856.285 ms (P50=808.35, P95=1346.7); mean input/output tokens=538.97/16.0; total input/output tokens=53897/1600
- cost (pricing 2026-09-23): total $0.0577; $0.577 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 76.0% | 24.0% |
| >= 0.8 | 100.0% | 76.0% | 24.0% |
| >= 0.85 | 29.0% | 86.2% | 13.8% |
| >= 0.9 | 29.0% | 86.2% | 13.8% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 5.0% | 5 |
| <=2% | 5.0% | 5 |
| <=1% | 5.0% | 5 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=80.0%, mean_confidence=83.8%
  - customer_misdiagnosis: n=13, accuracy=61.5%, mean_confidence=81.5%
  - dependency_root_cause: n=3, accuracy=66.7%, mean_confidence=83.3%
  - multi_component_symptoms: n=6, accuracy=66.7%, mean_confidence=80.0%
  - vague: n=12, accuracy=75.0%, mean_confidence=81.7%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=81.7%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=83.3%, mean_confidence=83.3%
  - sufficient: n=94, accuracy=75.5%, mean_confidence=82.9%

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 24.0%
- acceptable_match_rate: 24.0%
- accuracy 95% CI: 24.0% [16.0%, 32.0%] (n=100)
- Brier: 0.4845
- ECE: 0.5410
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.194
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 24.0% | conditional accuracy given candidate present: 24.0%
- failure decomposition: missing=0, present/jev-wrong=76, present/jev-correct=24, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 24.0%
- contract: first-attempt valid=100/100 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (RC14)=10.0%

- efficiency: mean latency=910.454 ms (P50=815.85, P95=1374.2); mean input/output tokens=932.1/16.0; total input/output tokens=93210/1600
- cost (pricing 2026-09-23): total $0.0986; $0.986 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 95.0% | 24.2% | 75.8% |
| >= 0.8 | 86.0% | 19.8% | 80.2% |
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
  - clear: n=60, accuracy=26.7%, mean_confidence=77.5%
  - customer_misdiagnosis: n=13, accuracy=7.7%, mean_confidence=80.0%
  - dependency_root_cause: n=3, accuracy=33.3%, mean_confidence=70.0%
  - multi_component_symptoms: n=6, accuracy=33.3%, mean_confidence=78.3%
  - vague: n=12, accuracy=33.3%, mean_confidence=80.0%
  - wrong_product_mentioned: n=6, accuracy=0.0%, mean_confidence=80.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=80.0%
  - sufficient: n=94, accuracy=25.5%, mean_confidence=78.0%

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 80.0%
- acceptable_match_rate: 80.0%
- accuracy 95% CI: 80.0% [72.0%, 87.0%] (n=100)
- Brier: 0.1386
- ECE: 0.0740
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.597
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 80.0% | conditional accuracy given candidate present: 80.0%
- failure decomposition: missing=0, present/jev-wrong=20, present/jev-correct=80, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 80.0%
- contract: first-attempt valid=100/100 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (none)=68.0%; newest-change-else-none=71.0%
- recency A_true_is_newest: n=32, accuracy=90.6%, selected-newest=90.6%, selected-none=9.4%
- recency B_true_older_than_a_distractor: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency C_no_causal_change: n=68, accuracy=75.0%, selected-newest=22.1%, selected-none=75.0%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=17, accuracy=58.8%
- no-causal-change accuracy=75.0%; distractor-selection rate=17.0% of all decisions, 42.5% when a distractor was offered (n=40)
- selected-is-newest-change rate: 72.1%
- accuracy when true causal change IS newest: 90.6% (n=32)
- accuracy when true causal change is OLDER than a distractor: n/a (n=0)

- efficiency: mean latency=948.909 ms (P50=783.3, P95=1722.0); mean input/output tokens=782.96/15.92; total input/output tokens=78296/1592
- cost (pricing 2026-09-23): total $0.0831; $0.831 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 99.0% | 80.8% | 19.2% |
| >= 0.8 | 97.0% | 82.5% | 17.5% |
| >= 0.85 | 39.0% | 100.0% | 0.0% |
| >= 0.9 | 39.0% | 100.0% | 0.0% |
| >= 0.95 | 39.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 54.0% | 54 |
| <=2% | 46.0% | 46 |
| <=1% | 46.0% | 46 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=76.7%, mean_confidence=87.2%
  - customer_misdiagnosis: n=13, accuracy=92.3%, mean_confidence=88.5%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=86.7%
  - multi_component_symptoms: n=6, accuracy=66.7%, mean_confidence=83.3%
  - vague: n=12, accuracy=83.3%, mean_confidence=88.3%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=90.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=93.3%
  - sufficient: n=94, accuracy=78.7%, mean_confidence=87.0%

## owning_team (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 11.0%
- acceptable_match_rate: 22.0%
- accuracy 95% CI: 11.0% [5.0%, 17.0%] (n=100)
- Brier: 0.5740
- ECE: 0.6900
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.059
- candidate recall: 100.0% (avg candidates: 11.9)
- candidate count distribution: median=12.0, P90=12
- end-to-end accuracy: 11.0% | conditional accuracy given candidate present: 22.0%
- failure decomposition: missing=0, present/jev-wrong=89, present/jev-correct=11, high-confidence-wrong=0
- team candidate recall: primary=99.0%, acceptable=100.0%
- team accuracy: primary=11.0%, acceptable=22.0%; conditional primary=11.1%, conditional acceptable=22.0%
- strict first-attempt accuracy (contract failures count as wrong): 11.0%
- contract: first-attempt valid=100/100 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (TM08)=16.0%

- efficiency: mean latency=915.8810000000001 ms (P50=801.25, P95=1579.2); mean input/output tokens=808.59/16.0; total input/output tokens=80859/1600
- cost (pricing 2026-09-23): total $0.0858; $0.858 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 11.0% | 89.0% |
| >= 0.8 | 100.0% | 11.0% | 89.0% |
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
  - clear: n=60, accuracy=11.7%, mean_confidence=80.0%
  - customer_misdiagnosis: n=13, accuracy=15.4%, mean_confidence=80.0%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=80.0%
  - multi_component_symptoms: n=6, accuracy=0.0%, mean_confidence=80.0%
  - vague: n=12, accuracy=16.7%, mean_confidence=80.0%
  - wrong_product_mentioned: n=6, accuracy=0.0%, mean_confidence=80.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=16.7%, mean_confidence=80.0%
  - sufficient: n=94, accuracy=10.6%, mean_confidence=80.0%

## evidence_sufficiency (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 43.0%
- acceptable_match_rate: 43.0%
- accuracy 95% CI: 43.0% [33.0%, 53.0%] (n=100)
- Brier: 0.2852
- ECE: 0.4340
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.369
- candidate recall: 100.0% (avg candidates: 3.0)
- candidate count distribution: median=3.0, P90=3
- end-to-end accuracy: 43.0% | conditional accuracy given candidate present: 43.0%
- failure decomposition: missing=0, present/jev-wrong=57, present/jev-correct=43, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 43.0%
- contract: first-attempt valid=100/100 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (sufficient)=94.0%

- efficiency: mean latency=976.8689999999999 ms (P50=789.0, P95=1698.7); mean input/output tokens=829.59/17.26; total input/output tokens=82959/1726
- cost (pricing 2026-09-23): total $0.0881; $0.881 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 84.0% | 46.4% | 53.6% |
| >= 0.8 | 37.0% | 100.0% | 0.0% |
| >= 0.85 | 5.0% | 100.0% | 0.0% |
| >= 0.9 | 5.0% | 100.0% | 0.0% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 40.0% | 40 |
| <=2% | 37.0% | 37 |
| <=1% | 37.0% | 37 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=41.7%, mean_confidence=72.5%
  - customer_misdiagnosis: n=13, accuracy=53.8%, mean_confidence=73.8%
  - dependency_root_cause: n=3, accuracy=66.7%, mean_confidence=73.3%
  - multi_component_symptoms: n=6, accuracy=16.7%, mean_confidence=70.0%
  - vague: n=12, accuracy=50.0%, mean_confidence=73.3%
  - wrong_product_mentioned: n=6, accuracy=33.3%, mean_confidence=71.7%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=63.3%
  - sufficient: n=94, accuracy=39.4%, mean_confidence=73.2%

## incident_relationship (noul)

- n_decisions: 17  (errors: 0, contract failures: 0)
- accuracy: 82.4%
- acceptable_match_rate: 82.4%
- accuracy 95% CI: 82.4% [64.7%, 100.0%] (n=17)
- Brier: 0.1718
- ECE: 0.1529
- false-confident rate (wrong AND conf>=0.9): 11.8% (n=17)
- failure decomposition: missing=0, present/jev-wrong=3, present/jev-correct=14, high-confidence-wrong=2
- Noul precision/recall/F1: 1.0/0.4/0.5714285714285715, FPR=0.0%, FNR=60.0%
- strict first-attempt accuracy (contract failures count as wrong): 82.4%
- contract: first-attempt valid=17/17 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (False)=70.6%

- efficiency: mean latency=879.1058823529411 ms (P50=649.4, P95=2941.5); mean input/output tokens=407.29411764705884/9.0; total input/output tokens=6924/153
- cost (pricing 2026-09-23): total $0.0074; $0.433 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 82.4% | 17.6% |
| >= 0.8 | 100.0% | 82.4% | 17.6% |
| >= 0.85 | 52.9% | 77.8% | 22.2% |
| >= 0.9 | 52.9% | 77.8% | 22.2% |
| >= 0.95 | 52.9% | 77.8% | 22.2% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 29.4% | 5 |
| <=2% | 29.4% | 5 |
| <=1% | 29.4% | 5 |

Slices:

- difficulty_archetype:
  - clear: n=9, accuracy=88.9%, mean_confidence=91.1%
  - customer_misdiagnosis: n=2, accuracy=100.0%, mean_confidence=90.0%
  - dependency_root_cause: n=1, accuracy=0.0%, mean_confidence=100.0%
  - multi_component_symptoms: n=1, accuracy=100.0%, mean_confidence=80.0%
  - vague: n=3, accuracy=100.0%, mean_confidence=93.3%
  - wrong_product_mentioned: n=1, accuracy=0.0%, mean_confidence=80.0%
- evidence_sufficiency:
  - partially_sufficient: n=1, accuracy=100.0%, mean_confidence=80.0%
  - sufficient: n=16, accuracy=81.2%, mean_confidence=91.2%
