# Experiment: causal_change_v3_dev100

- experiment_id: `exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T17:18:06.432376+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: causal_change
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical', 'candidate_generation_versions': {'causal_change': 'v3'}, 'causal_key_mode': 'canonical', 'jev_model_requested': 'jev-latest', 'frozen_config': None, 'pricing_version': '2026-09-23', 'comparison_baseline_experiment_id': 'exp_stage_b_dev_100_v2_20260923T083737Z_8eabb9a5'}

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 92.0%
- acceptable_match_rate: 92.0%
- accuracy 95% CI: 92.0% [87.0%, 97.0%] (n=100)
- Brier: 0.1349
- ECE: 0.1920
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

- efficiency: mean latency=206.368 ms (P50=180.75, P95=437.7); mean input/output tokens=1201.97/38.32; total input/output tokens=120197/3832
- cost (pricing 2026-09-23): total $0.0050; $0.050 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 64.0% | 95.3% | 4.7% |
| >= 0.8 | 58.0% | 100.0% | 0.0% |
| >= 0.85 | 46.0% | 100.0% | 0.0% |
| >= 0.9 | 45.0% | 100.0% | 0.0% |
| >= 0.95 | 42.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 84.0% | 84 |
| <=2% | 61.0% | 61 |
| <=1% | 59.0% | 59 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=88.3%, mean_confidence=75.5%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=73.6%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=66.7%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=65.8%
  - vague: n=12, accuracy=100.0%, mean_confidence=81.2%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=83.7%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=94.2%
  - sufficient: n=94, accuracy=91.5%, mean_confidence=74.4%
