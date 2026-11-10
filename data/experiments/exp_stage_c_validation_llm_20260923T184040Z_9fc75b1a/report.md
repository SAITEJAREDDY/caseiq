# Experiment: stage_c_validation_llm

- experiment_id: `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`
- experiment_type: llm_primitive_baseline
- kind: validation
- created_at: 2026-09-23T18:40:40.090504+00:00
- dataset_split: validation
- num_cases: 750
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v4_operational', 'candidate_generation_versions': {'issue_category': 'v1', 'root_cause': 'v2', 'causal_change': 'v3', 'owning_team': 'v2', 'evidence_sufficiency': 'v1', 'incident_relationship': 'v1'}, 'causal_key_mode': 'canonical', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': {'name': 'stage_b_frozen_v1', 'config_sha256': '0f72b8e2734b37b4bd0518bcc6dd9d376c1e39e9187b4470b3a95c32cc51d788', 'status': 'verified_against_manifest'}, 'pricing_version': '2026-09-23', 'orchestration': {'runner': 'parallel_v1', 'workers': 8, 'failed_cases': []}, 'case_ids_sha256': '6f89e2c8036213e41c2454031df1b79f0757413bf43e6f7667c238fc5c0c890a', 'pre_registered_protocol': {'path': 'docs/JEV_STAGE_C_PROTOCOL.md', 'sha256': '4c950c80104804ba37b4c8f5e9b06ea3e12437e4924b12319422a6f224cd95e2'}, 'llm_model': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'llm_temperature': 0.1, 'llm_max_tokens': 400, 'llm_repair_max_attempts': 1, 'paired_jev_experiment_id': 'exp_stage_c_validation_jev_20260923T184036Z_fa984004'}

## issue_category (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 79.3%
- acceptable_match_rate: 79.3%
- accuracy 95% CI: 79.3% [76.3%, 82.4%] (n=750)
- Brier: 0.1590
- ECE: 0.0565
- false-confident rate (wrong AND conf>=0.9): 2.7% (n=750)
- macro F1: 0.748
- candidate recall: 100.0% (avg candidates: 18.0)
- candidate count distribution: median=18.0, P90=18
- end-to-end accuracy: 79.3% | conditional accuracy given candidate present: 79.3%
- failure decomposition: missing=0, present/jev-wrong=155, present/jev-correct=595, high-confidence-wrong=20
- strict first-attempt accuracy (contract failures count as wrong): 79.3%
- contract: first-attempt valid=750/750 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (IC13)=17.2%

- efficiency: mean latency=1384.8389333333332 ms (P50=1037.0500000000002, P95=3482.6); mean input/output tokens=534.3186666666667/16.0; total input/output tokens=400739/12000
- cost (pricing 2026-09-23): total $0.4292; $0.572 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 79.3% | 20.7% |
| >= 0.8 | 100.0% | 79.3% | 20.7% |
| >= 0.85 | 34.4% | 92.2% | 7.8% |
| >= 0.9 | 34.4% | 92.2% | 7.8% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 5.3% | 40 |
| <=2% | 4.0% | 30 |
| <=1% | 4.0% | 30 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=83.6%, mean_confidence=84.1%
  - customer_misdiagnosis: n=99, accuracy=60.6%, mean_confidence=82.8%
  - dependency_root_cause: n=35, accuracy=85.7%, mean_confidence=84.6%
  - multi_component_symptoms: n=51, accuracy=80.4%, mean_confidence=81.4%
  - vague: n=88, accuracy=77.3%, mean_confidence=81.8%
  - wrong_product_mentioned: n=63, accuracy=79.4%, mean_confidence=83.2%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=92.3%, mean_confidence=84.6%
  - partially_sufficient: n=40, accuracy=65.0%, mean_confidence=82.0%
  - sufficient: n=697, accuracy=79.9%, mean_confidence=83.5%

## root_cause (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 20.7%
- acceptable_match_rate: 20.7%
- accuracy 95% CI: 20.7% [18.0%, 23.5%] (n=750)
- Brier: 0.5000
- ECE: 0.5639
- false-confident rate (wrong AND conf>=0.9): 1.1% (n=750)
- macro F1: 0.245
- candidate recall: 98.7% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 20.7% | conditional accuracy given candidate present: 20.9%
- failure decomposition: missing=10, present/jev-wrong=585, present/jev-correct=155, high-confidence-wrong=8
- strict first-attempt accuracy (contract failures count as wrong): 20.7%
- contract: first-attempt valid=750/750 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (RC17)=10.4%

- efficiency: mean latency=1437.3798666666664 ms (P50=1005.8499999999999, P95=3909.7); mean input/output tokens=909.1226666666666/16.0; total input/output tokens=681842/12000
- cost (pricing 2026-09-23): total $0.7216; $0.962 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 90.7% | 18.1% | 81.9% |
| >= 0.8 | 79.5% | 15.8% | 84.2% |
| >= 0.85 | 1.1% | 0.0% | 100.0% |
| >= 0.9 | 1.1% | 0.0% | 100.0% |
| >= 0.95 | 0.8% | 0.0% | 100.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=21.7%, mean_confidence=77.0%
  - customer_misdiagnosis: n=99, accuracy=14.1%, mean_confidence=77.4%
  - dependency_root_cause: n=35, accuracy=34.3%, mean_confidence=76.9%
  - multi_component_symptoms: n=51, accuracy=17.6%, mean_confidence=76.5%
  - vague: n=88, accuracy=28.4%, mean_confidence=76.7%
  - wrong_product_mentioned: n=63, accuracy=7.9%, mean_confidence=77.9%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=0.0%, mean_confidence=80.0%
  - partially_sufficient: n=40, accuracy=0.0%, mean_confidence=80.0%
  - sufficient: n=697, accuracy=22.2%, mean_confidence=76.8%

## causal_change (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 84.8%
- acceptable_match_rate: 84.8%
- accuracy 95% CI: 84.8% [82.3%, 87.2%] (n=750)
- Brier: 0.1200
- ECE: 0.0355
- false-confident rate (wrong AND conf>=0.9): 0.7% (n=750)
- macro F1: 0.649
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 84.8% | conditional accuracy given candidate present: 84.8%
- failure decomposition: missing=0, present/jev-wrong=114, present/jev-correct=636, high-confidence-wrong=5
- strict first-attempt accuracy (contract failures count as wrong): 84.8%
- contract: first-attempt valid=750/750 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (none)=68.8%; newest-change-else-none=71.3%
- recency A_true_is_newest: n=228, accuracy=91.2%, selected-newest=91.2%, selected-none=7.9%
- recency B_true_older_than_a_distractor: n=6, accuracy=100.0%, selected-newest=0.0%, selected-none=0.0%
- recency C_no_causal_change: n=516, accuracy=81.8%, selected-newest=16.9%, selected-none=81.8%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=143, accuracy=78.3%
- no-causal-change accuracy=81.8%; distractor-selection rate=12.8% of all decisions, 31.4% when a distractor was offered (n=306)
- selected-is-newest-change rate: 66.6%
- accuracy when true causal change IS newest: 91.2% (n=228)
- accuracy when true causal change is OLDER than a distractor: 100.0% (n=6)

- efficiency: mean latency=1434.2310666666667 ms (P50=1002.45, P95=3691.3); mean input/output tokens=761.432/15.826666666666666; total input/output tokens=571074/11870
- cost (pricing 2026-09-23): total $0.6063; $0.808 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 97.3% | 86.2% | 13.8% |
| >= 0.8 | 96.5% | 86.9% | 13.1% |
| >= 0.85 | 39.2% | 98.3% | 1.7% |
| >= 0.9 | 39.2% | 98.3% | 1.7% |
| >= 0.95 | 39.2% | 98.3% | 1.7% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 46.7% | 350 |
| <=2% | 40.7% | 305 |
| <=1% | 3.7% | 28 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=83.8%, mean_confidence=86.9%
  - customer_misdiagnosis: n=99, accuracy=84.8%, mean_confidence=84.6%
  - dependency_root_cause: n=35, accuracy=97.1%, mean_confidence=90.3%
  - multi_component_symptoms: n=51, accuracy=80.4%, mean_confidence=85.7%
  - vague: n=88, accuracy=84.1%, mean_confidence=86.8%
  - wrong_product_mentioned: n=63, accuracy=88.9%, mean_confidence=88.1%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=69.2%, mean_confidence=93.8%
  - partially_sufficient: n=40, accuracy=82.5%, mean_confidence=93.5%
  - sufficient: n=697, accuracy=85.2%, mean_confidence=86.2%

## owning_team (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 14.5%
- acceptable_match_rate: 27.2%
- accuracy 95% CI: 14.5% [12.0%, 17.1%] (n=750)
- Brier: 0.5524
- ECE: 0.6545
- false-confident rate (wrong AND conf>=0.9): 0.3% (n=750)
- macro F1: 0.116
- candidate recall: 99.9% (avg candidates: 11.8)
- candidate count distribution: median=12.0, P90=12
- end-to-end accuracy: 14.5% | conditional accuracy given candidate present: 27.2%
- failure decomposition: missing=1, present/jev-wrong=640, present/jev-correct=109, high-confidence-wrong=2
- team candidate recall: primary=99.7%, acceptable=99.9%
- team accuracy: primary=14.5%, acceptable=27.2%; conditional primary=14.6%, conditional acceptable=27.2%
- strict first-attempt accuracy (contract failures count as wrong): 14.5%
- contract: first-attempt valid=750/750 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (TM01)=15.6%

- efficiency: mean latency=1316.1218666666666 ms (P50=992.9, P95=3148.4); mean input/output tokens=785.2066666666667/16.0; total input/output tokens=588905/12000
- cost (pricing 2026-09-23): total $0.6249; $0.833 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 99.9% | 14.6% | 85.4% |
| >= 0.8 | 99.6% | 14.6% | 85.4% |
| >= 0.85 | 0.4% | 33.3% | 66.7% |
| >= 0.9 | 0.4% | 33.3% | 66.7% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=15.9%, mean_confidence=80.0%
  - customer_misdiagnosis: n=99, accuracy=8.1%, mean_confidence=80.1%
  - dependency_root_cause: n=35, accuracy=11.4%, mean_confidence=80.0%
  - multi_component_symptoms: n=51, accuracy=17.6%, mean_confidence=79.8%
  - vague: n=88, accuracy=17.0%, mean_confidence=80.0%
  - wrong_product_mentioned: n=63, accuracy=11.1%, mean_confidence=80.2%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=23.1%, mean_confidence=80.0%
  - partially_sufficient: n=40, accuracy=12.5%, mean_confidence=80.0%
  - sufficient: n=697, accuracy=14.5%, mean_confidence=80.0%

## evidence_sufficiency (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 41.9%
- acceptable_match_rate: 41.9%
- accuracy 95% CI: 41.9% [38.5%, 45.2%] (n=750)
- Brier: 0.2953
- ECE: 0.4403
- false-confident rate (wrong AND conf>=0.9): 0.1% (n=750)
- macro F1: 0.419
- candidate recall: 100.0% (avg candidates: 3.0)
- candidate count distribution: median=3.0, P90=3
- end-to-end accuracy: 41.9% | conditional accuracy given candidate present: 41.9%
- failure decomposition: missing=0, present/jev-wrong=436, present/jev-correct=314, high-confidence-wrong=1
- strict first-attempt accuracy (contract failures count as wrong): 41.9%
- contract: first-attempt valid=750/750 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (sufficient)=92.9%

- efficiency: mean latency=1398.6228 ms (P50=999.45, P95=3680.2); mean input/output tokens=812.6426666666666/17.234666666666666; total input/output tokens=609482/12926
- cost (pricing 2026-09-23): total $0.6473; $0.863 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 88.8% | 44.3% | 55.7% |
| >= 0.8 | 38.3% | 97.6% | 2.4% |
| >= 0.85 | 2.5% | 94.7% | 5.3% |
| >= 0.9 | 2.5% | 94.7% | 5.3% |
| >= 0.95 | 0.0% | n/a | n/a |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 39.2% | 294 |
| <=2% | 6.9% | 52 |
| <=1% | 1.6% | 12 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=42.5%, mean_confidence=72.9%
  - customer_misdiagnosis: n=99, accuracy=44.4%, mean_confidence=73.0%
  - dependency_root_cause: n=35, accuracy=54.3%, mean_confidence=74.3%
  - multi_component_symptoms: n=51, accuracy=29.4%, mean_confidence=71.6%
  - vague: n=88, accuracy=50.0%, mean_confidence=74.5%
  - wrong_product_mentioned: n=63, accuracy=25.4%, mean_confidence=71.7%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=53.8%, mean_confidence=73.8%
  - partially_sufficient: n=40, accuracy=85.0%, mean_confidence=66.8%
  - sufficient: n=697, accuracy=39.2%, mean_confidence=73.3%

## incident_relationship (noul)

- n_decisions: 132  (errors: 0, contract failures: 0)
- accuracy: 78.8%
- acceptable_match_rate: 78.8%
- accuracy 95% CI: 78.8% [72.0%, 85.6%] (n=132)
- Brier: 0.1752
- ECE: 0.1394
- false-confident rate (wrong AND conf>=0.9): 8.3% (n=132)
- failure decomposition: missing=0, present/jev-wrong=28, present/jev-correct=104, high-confidence-wrong=11
- Noul precision/recall/F1: 0.5714285714285714/0.13793103448275862/0.2222222222222222, FPR=2.9%, FNR=86.2%
- strict first-attempt accuracy (contract failures count as wrong): 78.8%
- contract: first-attempt valid=132/132 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (False)=78.0%

- efficiency: mean latency=1154.7181818181816 ms (P50=864.25, P95=2953.7); mean input/output tokens=403.65909090909093/9.0; total input/output tokens=53283/1188
- cost (pricing 2026-09-23): total $0.0566; $0.429 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 78.8% | 21.2% |
| >= 0.8 | 100.0% | 78.8% | 21.2% |
| >= 0.85 | 63.6% | 86.9% | 13.1% |
| >= 0.9 | 63.6% | 86.9% | 13.1% |
| >= 0.95 | 63.6% | 86.9% | 13.1% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 1.5% | 2 |
| <=2% | 1.5% | 2 |
| <=1% | 1.5% | 2 |

Slices:

- difficulty_archetype:
  - clear: n=67, accuracy=82.1%, mean_confidence=92.2%
  - customer_misdiagnosis: n=29, accuracy=75.9%, mean_confidence=94.5%
  - dependency_root_cause: n=5, accuracy=60.0%, mean_confidence=100.0%
  - multi_component_symptoms: n=8, accuracy=75.0%, mean_confidence=87.5%
  - vague: n=16, accuracy=75.0%, mean_confidence=91.2%
  - wrong_product_mentioned: n=7, accuracy=85.7%, mean_confidence=94.3%
- evidence_sufficiency:
  - insufficient: n=2, accuracy=100.0%, mean_confidence=100.0%
  - partially_sufficient: n=9, accuracy=44.4%, mean_confidence=91.1%
  - sufficient: n=121, accuracy=81.0%, mean_confidence=92.7%
