# Experiment: causal_change_v3_repeat_dev100_jev

- experiment_id: `exp_causal_change_v3_repeat_dev100_jev_20260923T174042Z_aee6568c`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T17:40:42.496320+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: causal_change
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical', 'candidate_generation_versions': {'causal_change': 'v3'}, 'causal_key_mode': 'canonical', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': None, 'pricing_version': '2026-09-23'}

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 91.0%
- acceptable_match_rate: 91.0%
- accuracy 95% CI: 91.0% [86.0%, 96.0%] (n=100)
- Brier: 0.1332
- ECE: 0.1550
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.761
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 91.0% | conditional accuracy given candidate present: 91.0%
- failure decomposition: missing=0, present/jev-wrong=9, present/jev-correct=91, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 91.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (none)=68.0%; newest-change-else-none=71.0%
- recency A_true_is_newest: n=32, accuracy=87.5%, selected-newest=87.5%, selected-none=12.5%
- recency B_true_older_than_a_distractor: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency C_no_causal_change: n=68, accuracy=92.6%, selected-newest=5.9%, selected-none=92.6%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=17, accuracy=82.4%
- no-causal-change accuracy=92.6%; distractor-selection rate=5.0% of all decisions, 12.5% when a distractor was offered (n=40)
- selected-is-newest-change rate: 52.5%
- accuracy when true causal change IS newest: 87.5% (n=32)
- accuracy when true causal change is OLDER than a distractor: n/a (n=0)

- efficiency: mean latency=171.74099999999999 ms (P50=169.39999999999998, P95=223.0); mean input/output tokens=1201.97/38.38; total input/output tokens=120197/3838
- cost (pricing 2026-09-23): total $0.0050; $0.050 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 64.0% | 95.3% | 4.7% |
| >= 0.8 | 57.0% | 98.2% | 1.8% |
| >= 0.85 | 48.0% | 100.0% | 0.0% |
| >= 0.9 | 44.0% | 100.0% | 0.0% |
| >= 0.95 | 42.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 84.0% | 84 |
| <=2% | 60.0% | 60 |
| <=1% | 55.0% | 55 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=86.7%, mean_confidence=75.8%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=74.5%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=66.3%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=66.3%
  - vague: n=12, accuracy=100.0%, mean_confidence=81.4%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=83.8%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=94.8%
  - sufficient: n=94, accuracy=90.4%, mean_confidence=74.7%
