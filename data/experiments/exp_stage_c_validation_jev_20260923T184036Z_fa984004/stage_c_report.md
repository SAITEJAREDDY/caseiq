# Stage C validation report (machine-generated tables)

- Jev validation: `exp_stage_c_validation_jev_20260923T184036Z_fa984004`
- LLM validation: `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`
- dev references: Jev `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24`, LLM `exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff`
- validation cases: 750; protocol sha256 `4c950c80104804ba37b4c8f5e9b06ea3e12437e4924b12319422a6f224cd95e2`

## Candidate generalization

| Decision | Recall dev | Recall validation | Avg cands dev / val | Median / P90 val | Absent (val) |
|---|---:|---:|---:|---:|---:|
| issue_category | 100.0% | 100.0% | 18.0 / 18.0 | 18.0 / 18 | 0 of 750 |
| root_cause | 100.0% | 98.7% | 15.9 / 15.9 | 16.0 / 16 | 10 of 750 |
| causal_change | 100.0% | 100.0% | 1.8 / 1.8 | 2.0 / 3 | 0 of 750 |
| owning_team (acceptable) | 100.0% | 99.9% | 11.9 / 11.8 | 12.0 / 12 | 1 of 750 |

Owning team primary recall: validation 99.7% (2 absent).

## Dev versus validation

| Metric | Dev | Validation | Delta (pts) [95% CI] | Val/dev ratio [95% CI] | Reading |
|---|---:|---:|---:|---:|---|
| Issue category accuracy | 73.0% (73/100) | 78.4% (588/750) | +5.4 [-2.9, +15.2] | 1.07 [0.96, 1.24] | plausible sampling variation |
| Root cause accuracy | 48.0% (48/100) | 37.2% (279/750) | -10.8 [-21.1, -0.6] | 0.78 [0.63, 1.00] | material degradation |
| Causal change accuracy | 92.0% (92/100) | 89.3% (670/750) | -2.7 [-7.2, +4.6] | 0.97 [0.92, 1.04] | plausible sampling variation |
| Owning team primary accuracy | 36.0% (36/100) | 37.6% (282/750) | +1.6 [-8.7, +11.0] | 1.04 [0.81, 1.45] | plausible sampling variation |
| Owning team acceptable accuracy | 49.0% (49/100) | 52.8% (396/750) | +3.8 [-6.5, +14.0] | 1.08 [0.89, 1.37] | plausible sampling variation |
| Evidence sufficiency accuracy | 14.0% (14/100) | 12.4% (93/750) | -1.6 [-10.0, +4.4] | 0.89 [0.56, 1.63] | plausible sampling variation |
| Incident relationship accuracy | 70.6% (12/17) | 82.6% (109/132) | +12.0 [-5.7, +36.3] | 1.17 [0.90, 1.79] | insufficient sample |
| Root cause candidate recall | 100.0% (100/100) | 98.7% (740/750) | -1.3 [-2.4, +2.4] | 0.99 [0.98, 0.99] | plausible sampling variation |
| Causal change candidate recall | 100.0% (100/100) | 100.0% (750/750) | +0.0 [-0.5, +3.7] | 1.00 [1.00, 1.00] | plausible sampling variation |
| Owning team primary candidate recall | 99.0% (99/100) | 99.7% (748/750) | +0.7 [-0.3, +5.2] | 1.01 [0.99, 1.03] | plausible sampling variation |
| Owning team acceptable candidate recall | 100.0% (100/100) | 99.9% (749/750) | -0.1 [-0.8, +3.6] | 1.00 [1.00, 1.00] | plausible sampling variation |
| issue_category false-confident rate (lower is better) | 6.0% (6/100) | 0.9% (7/750) | -5.1 [-11.6, -1.7] | 0.16 [0.04, 0.53] | improvement |
| root_cause false-confident rate (lower is better) | 3.0% (3/100) | 2.9% (22/750) | -0.1 [-5.6, +2.4] | 0.98 [0.37, 3.47] | plausible sampling variation |
| causal_change false-confident rate (lower is better) | 0.0% (0/100) | 0.4% (3/750) | +0.4 [-3.3, +1.2] | n/a | plausible sampling variation |
| owning_team false-confident rate (lower is better) | 5.0% (5/100) | 5.3% (40/750) | +0.3 [-6.0, +3.7] | 1.07 [0.50, 4.00] | plausible sampling variation |
| evidence_sufficiency false-confident rate (lower is better) | 2.0% (2/100) | 4.5% (34/750) | +2.5 [-2.6, +4.8] | 2.27 [0.77, 5.60] | plausible sampling variation |
| incident_relationship false-confident rate (lower is better) | 5.9% (1/17) | 9.1% (12/132) | +3.2 [-18.2, +11.0] | 1.55 [0.34, 2.19] | insufficient sample |

## issue_category

- n = 750; accuracy 78.4% [75.3%, 81.3%]; macro F1 0.706
- trivial baselines: {'majority_class': 'IC13', 'majority_class_accuracy': 0.172, 'n': 750}
- Brier 0.128, ECE 0.030; false-confident 7/750 (0.9%)
- contract: {'n_decisions': 750, 'request_or_api_errors': 0, 'native_typed_output': True, 'first_attempt_valid': 750, 'first_attempt_valid_rate': 1.0, 'repair_required': 0, 'repair_succeeded': 0, 'unrecoverable_failures': 0, 'first_attempt_failure_kinds': {}}
- failure categories: {'correct': 544, 'wrong_lower_confidence': 155, 'correct_low_confidence': 44, 'wrong_high_confidence': 7}
- conditional accuracy (true answer offered): 78.4% [75.3%, 81.3%] (n=750)

Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):

- clear: n=414, acc 80.7%, conf 80.0%, hc-err 1.0%
- customer_misdiagnosis: n=99, acc 69.7%, conf 67.6%, hc-err 1.0%
- dependency_root_cause: n=35, acc 77.1%, conf 74.9%, hc-err 0.0%
- multi_component_symptoms: n=51, acc 80.4%, conf 81.8%, hc-err 0.0%
- vague: n=88, acc 69.3%, conf 75.3%, hc-err 2.3%
- wrong_product_mentioned: n=63, acc 88.9%, conf 79.2%, hc-err 0.0%

Evidence-quality slices:

- insufficient: n=13 (small), acc 84.6%, conf 74.2%, hc-err 0.0%
- partially_sufficient: n=40, acc 60.0%, conf 68.2%, hc-err 2.5%
- sufficient: n=697, acc 79.3%, conf 78.2%, hc-err 0.9%

| Threshold | Automated | Accuracy automated | Error | Deferred |
|---|---:|---:|---:|---:|
| >= 0.7 | 66.0% (495) | 91.7% | 8.3% | 34.0% |
| >= 0.8 | 54.3% (407) | 95.3% | 4.7% | 45.7% |
| >= 0.85 | 49.1% (368) | 95.7% | 4.3% | 50.9% |
| >= 0.9 | 42.0% (315) | 97.8% | 2.2% | 58.0% |
| >= 0.95 | 32.1% (241) | 99.2% | 0.8% | 67.9% |

| Target error | Max coverage | Decisions | Observed error | Upper 95% error |
|---|---:|---:|---:|---:|
| <= 5% | 56.4% | 423 | 5.0% | 7.5% |
| <= 2% | 41.5% | 311 | 1.9% | 4.1% |
| <= 1% | 35.7% | 268 | 0.7% | 2.7% |

## root_cause

- n = 750; accuracy 37.2% [33.7%, 40.8%]; macro F1 0.406
- trivial baselines: {'majority_class': 'RC17', 'majority_class_accuracy': 0.104, 'n': 750}
- Brier 0.272, ECE 0.246; false-confident 22/750 (2.9%)
- contract: {'n_decisions': 750, 'request_or_api_errors': 0, 'native_typed_output': True, 'first_attempt_valid': 750, 'first_attempt_valid_rate': 1.0, 'repair_required': 0, 'repair_succeeded': 0, 'unrecoverable_failures': 0, 'first_attempt_failure_kinds': {}}
- failure categories: {'correct': 219, 'wrong_lower_confidence': 440, 'wrong_high_confidence': 21, 'correct_low_confidence': 60, 'candidate_missing': 10}
- conditional accuracy (true answer offered): 37.7% [34.3%, 41.2%] (n=740)
- accuracy by candidate-set size: {'11': (1, '0.0%', '0.0%'), '15': (58, '43.1%', '43.9%'), '16': (691, '36.8%', '37.2%')}

Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):

- clear: n=414, acc 35.7%, conf 61.4%, hc-err 2.9%
- customer_misdiagnosis: n=99, acc 40.4%, conf 61.9%, hc-err 3.0%
- dependency_root_cause: n=35, acc 40.0%, conf 60.8%, hc-err 2.9%
- multi_component_symptoms: n=51, acc 47.1%, conf 64.6%, hc-err 3.9%
- vague: n=88, acc 38.6%, conf 62.9%, hc-err 2.3%
- wrong_product_mentioned: n=63, acc 30.2%, conf 61.7%, hc-err 3.2%

Evidence-quality slices:

- insufficient: n=13 (small), acc 0.0%, conf 65.8%, hc-err 15.4%
- partially_sufficient: n=40, acc 0.0%, conf 65.0%, hc-err 15.0%
- sufficient: n=697, acc 40.0%, conf 61.6%, hc-err 2.0%

| Threshold | Automated | Accuracy automated | Error | Deferred |
|---|---:|---:|---:|---:|
| >= 0.7 | 36.5% (274) | 54.4% | 45.6% | 63.5% |
| >= 0.8 | 25.2% (189) | 61.9% | 38.1% | 74.8% |
| >= 0.85 | 17.9% (134) | 64.9% | 35.1% | 82.1% |
| >= 0.9 | 11.2% (84) | 73.8% | 26.2% | 88.8% |
| >= 0.95 | 4.8% (36) | 83.3% | 16.7% | 95.2% |

| Target error | Max coverage | Decisions | Observed error | Upper 95% error |
|---|---:|---:|---:|---:|
| <= 5% | 0.9% | 7 | 0.0% | 35.4% |
| <= 2% | 0.9% | 7 | 0.0% | 35.4% |
| <= 1% | 0.9% | 7 | 0.0% | 35.4% |

## causal_change

- n = 750; accuracy 89.3% [87.2%, 91.6%]; macro F1 0.687
- trivial baselines: {'majority_class': 'none', 'majority_class_accuracy': 0.688, 'n': 750, 'newest_change_else_none_accuracy': 0.7133333333333334}
- Brier 0.102, ECE 0.106; false-confident 3/750 (0.4%)
- contract: {'n_decisions': 750, 'request_or_api_errors': 0, 'native_typed_output': True, 'first_attempt_valid': 750, 'first_attempt_valid_rate': 1.0, 'repair_required': 0, 'repair_succeeded': 0, 'unrecoverable_failures': 0, 'first_attempt_failure_kinds': {}}
- failure categories: {'correct': 588, 'wrong_lower_confidence': 77, 'causal__none_chosen_when_true_change_offered': 53, 'correct_low_confidence': 82, 'causal__false_positive_on_no_change_case': 25, 'wrong_high_confidence': 3, 'causal__wrong_real_change_chosen': 2}
- conditional accuracy (true answer offered): 89.3% [87.2%, 91.6%] (n=750)

| Group | n | Accuracy | Conditional accuracy | High-conf errors | Newest-change selection |
|---|---:|---:|---:|---:|---:|
| A true is newest | 228 | 75.9% | 75.9% | 2 | 75.9% |
| B true older than a newer distractor | 6 | 100.0% | 100.0% | 0 | 0.0% |
| C no causal change | 516 | 95.2% | 95.2% | 1 | 3.7% |
| D multiple recent changes | 143 | 85.3% | 85.3% | 2 | 54.5% |
| E true change not offered | 0 | n/a | n/a | 0 | n/a |

- false-positive rate on no-change cases 4.8%; distractor-selection rate when a distractor was offered 8.8%
- accuracy by candidate-set size: {'1': (307, '100.0%', '100.0%'), '2': (300, '80.3%', '80.3%'), '3': (115, '85.2%', '85.2%'), '4': (26, '84.6%', '84.6%'), '5': (2, '100.0%', '100.0%')}

Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):

- clear: n=414, acc 89.4%, conf 79.1%, hc-err 0.2%
- customer_misdiagnosis: n=99, acc 83.8%, conf 74.8%, hc-err 0.0%
- dependency_root_cause: n=35, acc 94.3%, conf 85.1%, hc-err 0.0%
- multi_component_symptoms: n=51, acc 92.2%, conf 75.2%, hc-err 0.0%
- vague: n=88, acc 93.2%, conf 85.1%, hc-err 1.1%
- wrong_product_mentioned: n=63, acc 87.3%, conf 75.2%, hc-err 1.6%

Evidence-quality slices:

- insufficient: n=13 (small), acc 92.3%, conf 82.5%, hc-err 0.0%
- partially_sufficient: n=40, acc 95.0%, conf 89.8%, hc-err 0.0%
- sufficient: n=697, acc 89.0%, conf 78.2%, hc-err 0.4%

| Threshold | Automated | Accuracy automated | Error | Deferred |
|---|---:|---:|---:|---:|
| >= 0.7 | 70.5% (529) | 97.5% | 2.5% | 29.5% |
| >= 0.8 | 64.5% (484) | 98.3% | 1.7% | 35.5% |
| >= 0.85 | 59.2% (444) | 98.9% | 1.1% | 40.8% |
| >= 0.9 | 53.3% (400) | 99.2% | 0.8% | 46.7% |
| >= 0.95 | 46.4% (348) | 99.4% | 0.6% | 53.6% |

| Target error | Max coverage | Decisions | Observed error | Upper 95% error |
|---|---:|---:|---:|---:|
| <= 5% | 82.4% | 618 | 4.9% | 6.8% |
| <= 2% | 69.3% | 520 | 1.9% | 3.5% |
| <= 1% | 58.7% | 440 | 0.9% | 2.3% |

## owning_team

- n = 750; accuracy 37.6% [34.0%, 41.2%]; macro F1 0.265
- trivial baselines: {'majority_class': 'TM01', 'majority_class_accuracy': 0.156, 'n': 750}
- Brier 0.289, ECE 0.239; false-confident 40/750 (5.3%)
- contract: {'n_decisions': 750, 'request_or_api_errors': 0, 'native_typed_output': True, 'first_attempt_valid': 750, 'first_attempt_valid_rate': 1.0, 'repair_required': 0, 'repair_succeeded': 0, 'unrecoverable_failures': 0, 'first_attempt_failure_kinds': {}}
- failure categories: {'wrong_lower_confidence': 427, 'correct_low_confidence': 68, 'correct': 214, 'wrong_high_confidence': 40, 'candidate_missing': 1}
- conditional accuracy (true answer offered): 37.7% [34.4%, 41.3%] (n=749)
- primary 37.6% [34.0%, 41.2%] (n=750); acceptable 52.8% [49.2%, 56.4%] (n=750); conditional_primary 37.7% [34.4%, 41.3%] (n=748); conditional_acceptable 52.9% [49.5%, 56.3%] (n=749)
- accuracy by candidate-set size: candidate-set size is effectively constant (sizes 5-12; one dominant size)

Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):

- clear: n=414, acc 40.3%, conf 62.4%, hc-err 6.3%
- customer_misdiagnosis: n=99, acc 32.3%, conf 57.2%, hc-err 3.0%
- dependency_root_cause: n=35, acc 28.6%, conf 63.9%, hc-err 5.7% **FLAG: confidence does not track accuracy**
- multi_component_symptoms: n=51, acc 31.4%, conf 59.9%, hc-err 3.9%
- vague: n=88, acc 30.7%, conf 61.6%, hc-err 6.8%
- wrong_product_mentioned: n=63, acc 47.6%, conf 61.5%, hc-err 1.6%

Evidence-quality slices:

- insufficient: n=13 (small), acc 23.1%, conf 60.5%, hc-err 0.0%
- partially_sufficient: n=40, acc 17.5%, conf 52.6%, hc-err 2.5%
- sufficient: n=697, acc 39.0%, conf 62.0%, hc-err 5.6%

| Threshold | Automated | Accuracy automated | Error | Deferred |
|---|---:|---:|---:|---:|
| >= 0.7 | 37.2% (279) | 49.8% | 50.2% | 62.8% |
| >= 0.8 | 25.9% (194) | 51.5% | 48.5% | 74.1% |
| >= 0.85 | 19.9% (149) | 53.7% | 46.3% | 80.1% |
| >= 0.9 | 12.8% (96) | 58.3% | 41.7% | 87.2% |
| >= 0.95 | 6.9% (52) | 50.0% | 50.0% | 93.1% |

| Target error | Max coverage | Decisions | Observed error | Upper 95% error |
|---|---:|---:|---:|---:|
| <= 5% | 0.4% | 3 | 0.0% | 56.2% |
| <= 2% | 0.4% | 3 | 0.0% | 56.2% |
| <= 1% | 0.4% | 3 | 0.0% | 56.2% |

## evidence_sufficiency

- n = 750; accuracy 12.4% [10.1%, 14.8%]; macro F1 0.135
- trivial baselines: {'majority_class': 'sufficient', 'majority_class_accuracy': 0.9293333333333333, 'n': 750}
- Brier 0.466, ECE 0.528; false-confident 34/750 (4.5%)
- contract: {'n_decisions': 750, 'request_or_api_errors': 0, 'native_typed_output': True, 'first_attempt_valid': 750, 'first_attempt_valid_rate': 1.0, 'repair_required': 0, 'repair_succeeded': 0, 'unrecoverable_failures': 0, 'first_attempt_failure_kinds': {}}
- failure categories: {'wrong_lower_confidence': 623, 'evidence__under_called': 648, 'correct_low_confidence': 53, 'wrong_high_confidence': 34, 'correct': 40, 'evidence__over_called': 9}
- conditional accuracy (true answer offered): 12.4% [10.1%, 14.8%] (n=750)
- truth distribution {'sufficient': 697, 'partially_sufficient': 40, 'insufficient': 13}; majority baseline 92.9% (sufficient)
- per-class accuracy {'insufficient': {'n': 13, 'recall': 0.3076923076923077}, 'partially_sufficient': {'n': 40, 'recall': 0.65}, 'sufficient': {'n': 697, 'recall': 0.09038737446197992}}
- confusion {'insufficient->insufficient': 4, 'insufficient->partially_sufficient': 9, 'partially_sufficient->insufficient': 14, 'partially_sufficient->partially_sufficient': 26, 'sufficient->insufficient': 18, 'sufficient->partially_sufficient': 616, 'sufficient->sufficient': 63}
- confidence distribution {'0.0-0.5': 182, '0.5-0.7': 191, '0.7-0.9': 340, '0.9-1.0': 37}

Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):

- clear: n=414, acc 11.8%, conf 65.0%, hc-err 4.6%
- customer_misdiagnosis: n=99, acc 16.2%, conf 63.2%, hc-err 0.0%
- dependency_root_cause: n=35, acc 11.4%, conf 62.7%, hc-err 2.9%
- multi_component_symptoms: n=51, acc 11.8%, conf 70.2%, hc-err 17.6%
- vague: n=88, acc 14.8%, conf 64.9%, hc-err 3.4%
- wrong_product_mentioned: n=63, acc 7.9%, conf 67.1%, hc-err 3.2%

| Threshold | Automated | Accuracy automated | Error | Deferred |
|---|---:|---:|---:|---:|
| >= 0.7 | 50.3% (377) | 4.8% | 95.2% | 49.7% |
| >= 0.8 | 30.8% (231) | 3.9% | 96.1% | 69.2% |
| >= 0.85 | 17.6% (132) | 3.8% | 96.2% | 82.4% |
| >= 0.9 | 4.9% (37) | 8.1% | 91.9% | 95.1% |
| >= 0.95 | 1.1% (8) | 25.0% | 75.0% | 98.9% |

| Target error | Max coverage | Decisions | Observed error | Upper 95% error |
|---|---:|---:|---:|---:|
| <= 5% | 0.1% | 1 | 0.0% | 79.3% |
| <= 2% | 0.1% | 1 | 0.0% | 79.3% |
| <= 1% | 0.1% | 1 | 0.0% | 79.3% |

## incident_relationship

- n = 132; accuracy 82.6% [76.5%, 88.6%]; macro F1 None
- trivial baselines: {'majority_class': 'False', 'majority_class_accuracy': 0.7803030303030303, 'n': 132}
- Brier 0.146, ECE 0.083; false-confident 12/132 (9.1%)
- contract: {'n_decisions': 132, 'request_or_api_errors': 0, 'native_typed_output': True, 'first_attempt_valid': 132, 'first_attempt_valid_rate': 1.0, 'repair_required': 0, 'repair_succeeded': 0, 'unrecoverable_failures': 0, 'first_attempt_failure_kinds': {}}
- failure categories: {'correct': 109, 'missed_incident': 21, 'wrong_high_confidence': 12, 'false_attribution__coincidental_unrelated': 2}
- eligible decisions 132; true-related 29, not related 103; TPR 27.6%, FPR 1.9%; false attributions 2, missed 21; AUC 0.6965182457315032
- by true relationship: {'coincidental_unrelated': {'n': 69, 'accuracy': 0.9710144927536232, 'predicted_related': 2, 'false_attributions': 2}, 'customer_assumed_incorrectly': {'n': 34, 'accuracy': 1.0, 'predicted_related': 0, 'false_attributions': 0}, 'directly_caused': {'n': 27, 'accuracy': 0.2962962962962963, 'predicted_related': 8, 'false_attributions': 0}, 'partially_influenced': {'n': 2, 'accuracy': 0.0, 'predicted_related': 0, 'false_attributions': 0}}

Difficulty slices (n, accuracy, mean confidence, high-conf error rate, flag):

- clear: n=67, acc 88.1%, conf 85.7%, hc-err 3.0%
- customer_misdiagnosis: n=29 (small), acc 75.9%, conf 89.4%, hc-err 13.8%
- dependency_root_cause: n=5 (small), acc 60.0%, conf 95.6%, hc-err 40.0%
- multi_component_symptoms: n=8 (small), acc 87.5%, conf 86.4%, hc-err 12.5%
- vague: n=16 (small), acc 75.0%, conf 87.3%, hc-err 12.5%
- wrong_product_mentioned: n=7 (small), acc 85.7%, conf 84.7%, hc-err 14.3%

| Threshold | Automated | Accuracy automated | Error | Deferred |
|---|---:|---:|---:|---:|
| >= 0.7 | 89.4% (118) | 83.9% | 16.1% | 10.6% |
| >= 0.8 | 78.0% (103) | 84.5% | 15.5% | 22.0% |
| >= 0.85 | 70.5% (93) | 84.9% | 15.1% | 29.5% |
| >= 0.9 | 59.8% (79) | 84.8% | 15.2% | 40.2% |
| >= 0.95 | 37.1% (49) | 87.8% | 12.2% | 62.9% |

| Target error | Max coverage | Decisions | Observed error | Upper 95% error |
|---|---:|---:|---:|---:|
| <= 5% | 3.0% | 4 | 0.0% | 49.0% |
| <= 2% | 3.0% | 4 | 0.0% | 49.0% |
| <= 1% | 3.0% | 4 | 0.0% | 49.0% |

## Jev vs LLM (validation)

| Decision | Jev acc | LLM acc | Jev minus LLM (paired CI) | McNemar p | Jev P50/P90/P95 ms | LLM P50/P90/P95 ms | $/1k Jev | $/1k LLM | LLM first-attempt valid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| issue_category | 78.4% | 79.3% | -0.9 [-3.7, +1.9] | 0.569 | 194/1005/1170 | 1037/2161/3483 | 0.037 | 0.572 | 750/750 |
| root_cause | 37.2% | 20.7% | +16.5 [+13.1, +20.1] | 0.000 | 189/956/1104 | 1006/2381/3910 | 0.061 | 0.962 | 750/750 |
| causal_change | 89.3% | 84.8% | +4.5 [+1.9, +7.2] | 0.002 | 195/1043/1200 | 1002/2372/3691 | 0.049 | 0.808 | 750/750 |
| owning_team | 37.6% | 14.5% | +23.1 [+18.9, +27.2] | 0.000 | 196/1021/1173 | 993/2103/3148 | 0.053 | 0.833 | 750/750 |
| evidence_sufficiency | 12.4% | 41.9% | -29.5 [-32.9, -25.9] | 0.000 | 201/1013/1179 | 999/2332/3680 | 0.050 | 0.863 | 750/750 |
| incident_relationship | 82.6% | 78.8% | +3.8 [+0.8, +6.8] | 0.062 | 202/920/1230 | 864/2014/2954 | 0.027 | 0.429 | 132/132 |

Does the ranking generalize?

| Decision | Dev Jev minus LLM | Dev reading | Validation Jev minus LLM | Validation reading | Same reading |
|---|---:|---|---:|---|---|
| issue_category | -3.0 [-11.0, +4.0] | no clear difference | -0.9 [-3.7, +1.9] | no clear difference | True |
| root_cause | +24.0 [+15.0, +33.0] | Jev ahead | +16.5 [+13.1, +20.1] | Jev ahead | True |
| causal_change | +12.0 [+5.0, +20.0] | Jev ahead | +4.5 [+1.9, +7.2] | Jev ahead | True |
| owning_team | +25.0 [+14.0, +36.0] | Jev ahead | +23.1 [+18.9, +27.2] | Jev ahead | True |
| evidence_sufficiency | -29.0 [-39.0, -20.0] | LLM ahead | -29.5 [-32.9, -25.9] | LLM ahead | True |
| incident_relationship | -11.8 [-29.4, +0.0] | no clear difference | +3.8 [+0.8, +6.8] | Jev ahead | False |

## Capability classification (pre-registered rubric)

| Primitive | Class | T1 beats baseline | T2 generalizes | T3 strong | T4 sample | Accuracy [CI] | Baseline | False-confident |
|---|---|---|---|---|---|---:|---:|---:|
| issue_category | **supporting-only** | True | True | False | True | 78.4% [75.3%, 81.3%] | 17.2% | 0.9% |
| root_cause | **supporting-only** | True | False | False | True | 37.2% [33.7%, 40.8%] | 10.4% | 2.9% |
| causal_change | **candidate for locked benchmark** | True | True | True | True | 89.3% [87.2%, 91.6%] | 71.3% | 0.4% |
| owning_team | **supporting-only** | True | True | False | True | 37.6% [34.0%, 41.2%] | 15.6% | 5.3% |
| evidence_sufficiency | **weak / deprioritize** | False | True | False | True | 12.4% [10.1%, 14.8%] | 92.9% | 4.5% |
| incident_relationship | **weak / deprioritize** | False | True | False | True | 82.6% [76.5%, 88.6%] | 78.0% | 9.1% |
