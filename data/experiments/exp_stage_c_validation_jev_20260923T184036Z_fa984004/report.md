# Experiment: stage_c_validation_jev

- experiment_id: `exp_stage_c_validation_jev_20260923T184036Z_fa984004`
- experiment_type: jev_primitive
- kind: validation
- created_at: 2026-09-23T18:40:36.581707+00:00
- dataset_split: validation
- num_cases: 750
- decision_types: issue_category, root_cause, causal_change, owning_team, evidence_sufficiency, incident_relationship
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v4_operational', 'candidate_generation_versions': {'issue_category': 'v1', 'root_cause': 'v2', 'causal_change': 'v3', 'owning_team': 'v2', 'evidence_sufficiency': 'v1', 'incident_relationship': 'v1'}, 'causal_key_mode': 'canonical', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': {'name': 'stage_b_frozen_v1', 'config_sha256': '0f72b8e2734b37b4bd0518bcc6dd9d376c1e39e9187b4470b3a95c32cc51d788', 'status': 'verified_against_manifest'}, 'pricing_version': '2026-09-23', 'orchestration': {'runner': 'parallel_v1', 'workers': 8, 'failed_cases': []}, 'case_ids_sha256': '6f89e2c8036213e41c2454031df1b79f0757413bf43e6f7667c238fc5c0c890a', 'pre_registered_protocol': {'path': 'docs/JEV_STAGE_C_PROTOCOL.md', 'sha256': '4c950c80104804ba37b4c8f5e9b06ea3e12437e4924b12319422a6f224cd95e2'}}

## issue_category (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 78.4%
- acceptable_match_rate: 78.4%
- accuracy 95% CI: 78.4% [75.3%, 81.3%] (n=750)
- Brier: 0.1282
- ECE: 0.0297
- false-confident rate (wrong AND conf>=0.9): 0.9% (n=750)
- macro F1: 0.706
- candidate recall: 100.0% (avg candidates: 18.0)
- candidate count distribution: median=18.0, P90=18
- end-to-end accuracy: 78.4% | conditional accuracy given candidate present: 78.4%
- failure decomposition: missing=0, present/jev-wrong=162, present/jev-correct=588, high-confidence-wrong=7
- strict first-attempt accuracy (contract failures count as wrong): 78.4%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (IC13)=17.2%

- efficiency: mean latency=391.6854666666666 ms (P50=193.85000000000002, P95=1169.6); mean input/output tokens=870.3226666666667/182.0; total input/output tokens=652742/136500
- cost (pricing 2026-09-23): total $0.0274; $0.037 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 66.0% | 91.7% | 8.3% |
| >= 0.8 | 54.3% | 95.3% | 4.7% |
| >= 0.85 | 49.1% | 95.7% | 4.3% |
| >= 0.9 | 42.0% | 97.8% | 2.2% |
| >= 0.95 | 32.1% | 99.2% | 0.8% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 56.4% | 423 |
| <=2% | 41.5% | 311 |
| <=1% | 35.7% | 268 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=80.7%, mean_confidence=80.0%
  - customer_misdiagnosis: n=99, accuracy=69.7%, mean_confidence=67.6%
  - dependency_root_cause: n=35, accuracy=77.1%, mean_confidence=74.9%
  - multi_component_symptoms: n=51, accuracy=80.4%, mean_confidence=81.8%
  - vague: n=88, accuracy=69.3%, mean_confidence=75.3%
  - wrong_product_mentioned: n=63, accuracy=88.9%, mean_confidence=79.2%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=84.6%, mean_confidence=74.2%
  - partially_sufficient: n=40, accuracy=60.0%, mean_confidence=68.2%
  - sufficient: n=697, accuracy=79.3%, mean_confidence=78.2%

## root_cause (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 37.2%
- acceptable_match_rate: 37.2%
- accuracy 95% CI: 37.2% [33.7%, 40.8%] (n=750)
- Brier: 0.2721
- ECE: 0.2464
- false-confident rate (wrong AND conf>=0.9): 2.9% (n=750)
- macro F1: 0.406
- candidate recall: 98.7% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 37.2% | conditional accuracy given candidate present: 37.7%
- failure decomposition: missing=10, present/jev-wrong=461, present/jev-correct=279, high-confidence-wrong=22
- strict first-attempt accuracy (contract failures count as wrong): 37.2%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (RC17)=10.4%

- efficiency: mean latency=385.1661333333333 ms (P50=188.8, P95=1103.5); mean input/output tokens=1444.4413333333334/164.244; total input/output tokens=1083331/123183
- cost (pricing 2026-09-23): total $0.0455; $0.061 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 36.5% | 54.4% | 45.6% |
| >= 0.8 | 25.2% | 61.9% | 38.1% |
| >= 0.85 | 17.9% | 64.9% | 35.1% |
| >= 0.9 | 11.2% | 73.8% | 26.2% |
| >= 0.95 | 4.8% | 83.3% | 16.7% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.9% | 7 |
| <=2% | 0.9% | 7 |
| <=1% | 0.9% | 7 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=35.7%, mean_confidence=61.4%
  - customer_misdiagnosis: n=99, accuracy=40.4%, mean_confidence=61.9%
  - dependency_root_cause: n=35, accuracy=40.0%, mean_confidence=60.8%
  - multi_component_symptoms: n=51, accuracy=47.1%, mean_confidence=64.6%
  - vague: n=88, accuracy=38.6%, mean_confidence=62.9%
  - wrong_product_mentioned: n=63, accuracy=30.2%, mean_confidence=61.7%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=0.0%, mean_confidence=65.8%
  - partially_sufficient: n=40, accuracy=0.0%, mean_confidence=65.0%
  - sufficient: n=697, accuracy=40.0%, mean_confidence=61.6%

## causal_change (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 89.3%
- acceptable_match_rate: 89.3%
- accuracy 95% CI: 89.3% [87.2%, 91.6%] (n=750)
- Brier: 0.1017
- ECE: 0.1058
- false-confident rate (wrong AND conf>=0.9): 0.4% (n=750)
- macro F1: 0.687
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 89.3% | conditional accuracy given candidate present: 89.3%
- failure decomposition: missing=0, present/jev-wrong=80, present/jev-correct=670, high-confidence-wrong=3
- strict first-attempt accuracy (contract failures count as wrong): 89.3%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (none)=68.8%; newest-change-else-none=71.3%
- recency A_true_is_newest: n=228, accuracy=75.9%, selected-newest=75.9%, selected-none=23.2%
- recency B_true_older_than_a_distractor: n=6, accuracy=100.0%, selected-newest=0.0%, selected-none=0.0%
- recency C_no_causal_change: n=516, accuracy=95.2%, selected-newest=3.7%, selected-none=95.2%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=143, accuracy=85.3%
- no-causal-change accuracy=95.2%; distractor-selection rate=3.6% of all decisions, 8.8% when a distractor was offered (n=306)
- selected-is-newest-change rate: 43.3%
- accuracy when true causal change IS newest: 75.9% (n=228)
- accuracy when true causal change is OLDER than a distractor: 100.0% (n=6)

- efficiency: mean latency=420.566 ms (P50=195.25, P95=1200.0); mean input/output tokens=1168.8693333333333/38.32533333333333; total input/output tokens=876652/28744
- cost (pricing 2026-09-23): total $0.0368; $0.049 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 70.5% | 97.5% | 2.5% |
| >= 0.8 | 64.5% | 98.3% | 1.7% |
| >= 0.85 | 59.2% | 98.9% | 1.1% |
| >= 0.9 | 53.3% | 99.2% | 0.8% |
| >= 0.95 | 46.4% | 99.4% | 0.6% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 82.4% | 618 |
| <=2% | 69.3% | 520 |
| <=1% | 58.7% | 440 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=89.4%, mean_confidence=79.1%
  - customer_misdiagnosis: n=99, accuracy=83.8%, mean_confidence=74.8%
  - dependency_root_cause: n=35, accuracy=94.3%, mean_confidence=85.1%
  - multi_component_symptoms: n=51, accuracy=92.2%, mean_confidence=75.2%
  - vague: n=88, accuracy=93.2%, mean_confidence=85.1%
  - wrong_product_mentioned: n=63, accuracy=87.3%, mean_confidence=75.2%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=92.3%, mean_confidence=82.5%
  - partially_sufficient: n=40, accuracy=95.0%, mean_confidence=89.8%
  - sufficient: n=697, accuracy=89.0%, mean_confidence=78.2%

## owning_team (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 37.6%
- acceptable_match_rate: 52.8%
- accuracy 95% CI: 37.6% [34.0%, 41.2%] (n=750)
- Brier: 0.2893
- ECE: 0.2388
- false-confident rate (wrong AND conf>=0.9): 5.3% (n=750)
- macro F1: 0.265
- candidate recall: 99.9% (avg candidates: 11.8)
- candidate count distribution: median=12.0, P90=12
- end-to-end accuracy: 37.6% | conditional accuracy given candidate present: 52.9%
- failure decomposition: missing=1, present/jev-wrong=467, present/jev-correct=282, high-confidence-wrong=40
- team candidate recall: primary=99.7%, acceptable=99.9%
- team accuracy: primary=37.6%, acceptable=52.8%; conditional primary=37.7%, conditional acceptable=52.9%
- strict first-attempt accuracy (contract failures count as wrong): 37.6%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (TM01)=15.6%

- efficiency: mean latency=418.15 ms (P50=196.0, P95=1173.4); mean input/output tokens=1254.284/127.416; total input/output tokens=940713/95562
- cost (pricing 2026-09-23): total $0.0395; $0.053 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 37.2% | 49.8% | 50.2% |
| >= 0.8 | 25.9% | 51.5% | 48.5% |
| >= 0.85 | 19.9% | 53.7% | 46.3% |
| >= 0.9 | 12.8% | 58.3% | 41.7% |
| >= 0.95 | 6.9% | 50.0% | 50.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.4% | 3 |
| <=2% | 0.4% | 3 |
| <=1% | 0.4% | 3 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=40.3%, mean_confidence=62.4%
  - customer_misdiagnosis: n=99, accuracy=32.3%, mean_confidence=57.2%
  - dependency_root_cause: n=35, accuracy=28.6%, mean_confidence=63.9%
  - multi_component_symptoms: n=51, accuracy=31.4%, mean_confidence=59.9%
  - vague: n=88, accuracy=30.7%, mean_confidence=61.6%
  - wrong_product_mentioned: n=63, accuracy=47.6%, mean_confidence=61.5%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=23.1%, mean_confidence=60.5%
  - partially_sufficient: n=40, accuracy=17.5%, mean_confidence=52.6%
  - sufficient: n=697, accuracy=39.0%, mean_confidence=62.0%

## evidence_sufficiency (choice)

- n_decisions: 750  (errors: 0, contract failures: 0)
- accuracy: 12.4%
- acceptable_match_rate: 12.4%
- accuracy 95% CI: 12.4% [10.1%, 14.8%] (n=750)
- Brier: 0.4656
- ECE: 0.5277
- false-confident rate (wrong AND conf>=0.9): 4.5% (n=750)
- macro F1: 0.135
- candidate recall: 100.0% (avg candidates: 3.0)
- candidate count distribution: median=3.0, P90=3
- end-to-end accuracy: 12.4% | conditional accuracy given candidate present: 12.4%
- failure decomposition: missing=0, present/jev-wrong=657, present/jev-correct=93, high-confidence-wrong=34
- strict first-attempt accuracy (contract failures count as wrong): 12.4%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (sufficient)=92.9%

- efficiency: mean latency=421.6521333333333 ms (P50=201.05, P95=1178.8); mean input/output tokens=1200.1106666666667/61.604; total input/output tokens=900083/46203
- cost (pricing 2026-09-23): total $0.0378; $0.050 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 50.3% | 4.8% | 95.2% |
| >= 0.8 | 30.8% | 3.9% | 96.1% |
| >= 0.85 | 17.6% | 3.8% | 96.2% |
| >= 0.9 | 4.9% | 8.1% | 91.9% |
| >= 0.95 | 1.1% | 25.0% | 75.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.1% | 1 |
| <=2% | 0.1% | 1 |
| <=1% | 0.1% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=414, accuracy=11.8%, mean_confidence=65.0%
  - customer_misdiagnosis: n=99, accuracy=16.2%, mean_confidence=63.2%
  - dependency_root_cause: n=35, accuracy=11.4%, mean_confidence=62.7%
  - multi_component_symptoms: n=51, accuracy=11.8%, mean_confidence=70.2%
  - vague: n=88, accuracy=14.8%, mean_confidence=64.9%
  - wrong_product_mentioned: n=63, accuracy=7.9%, mean_confidence=67.1%
- evidence_sufficiency:
  - insufficient: n=13, accuracy=30.8%, mean_confidence=60.7%
  - partially_sufficient: n=40, accuracy=65.0%, mean_confidence=61.7%
  - sufficient: n=697, accuracy=9.0%, mean_confidence=65.5%

## incident_relationship (noul)

- n_decisions: 132  (errors: 0, contract failures: 0)
- accuracy: 82.6%
- acceptable_match_rate: 82.6%
- accuracy 95% CI: 82.6% [76.5%, 88.6%] (n=132)
- Brier: 0.1461
- ECE: 0.0834
- false-confident rate (wrong AND conf>=0.9): 9.1% (n=132)
- failure decomposition: missing=0, present/jev-wrong=23, present/jev-correct=109, high-confidence-wrong=12
- Noul precision/recall/F1: 0.8/0.27586206896551724/0.4102564102564103, FPR=1.9%, FNR=72.4%
- strict first-attempt accuracy (contract failures count as wrong): 82.6%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (False)=78.0%

- efficiency: mean latency=417.7916666666667 ms (P50=201.55, P95=1230.5); mean input/output tokens=636.1818181818181/21.0; total input/output tokens=83976/2772
- cost (pricing 2026-09-23): total $0.0035; $0.027 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 89.4% | 83.9% | 16.1% |
| >= 0.8 | 78.0% | 84.5% | 15.5% |
| >= 0.85 | 70.5% | 84.9% | 15.1% |
| >= 0.9 | 59.8% | 84.8% | 15.2% |
| >= 0.95 | 37.1% | 87.8% | 12.2% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 3.0% | 4 |
| <=2% | 3.0% | 4 |
| <=1% | 3.0% | 4 |

Slices:

- difficulty_archetype:
  - clear: n=67, accuracy=88.1%, mean_confidence=85.7%
  - customer_misdiagnosis: n=29, accuracy=75.9%, mean_confidence=89.4%
  - dependency_root_cause: n=5, accuracy=60.0%, mean_confidence=95.6%
  - multi_component_symptoms: n=8, accuracy=87.5%, mean_confidence=86.4%
  - vague: n=16, accuracy=75.0%, mean_confidence=87.3%
  - wrong_product_mentioned: n=7, accuracy=85.7%, mean_confidence=84.7%
- evidence_sufficiency:
  - insufficient: n=2, accuracy=100.0%, mean_confidence=88.5%
  - partially_sufficient: n=9, accuracy=44.4%, mean_confidence=90.1%
  - sufficient: n=121, accuracy=85.1%, mean_confidence=86.8%
