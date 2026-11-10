# Experiment: causal_change_v3_opaque_keys_dev100_jev

- experiment_id: `exp_causal_change_v3_opaque_keys_dev100_jev_20260923T172653Z_cc0c9491`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T17:26:53.573310+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: causal_change
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical', 'candidate_generation_versions': {'causal_change': 'v3'}, 'causal_key_mode': 'opaque', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': None, 'pricing_version': '2026-09-23'}

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 91.0%
- acceptable_match_rate: 91.0%
- accuracy 95% CI: 91.0% [85.0%, 96.0%] (n=100)
- Brier: 0.1204
- ECE: 0.1402
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.755
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 91.0% | conditional accuracy given candidate present: 91.0%
- failure decomposition: missing=0, present/jev-wrong=9, present/jev-correct=91, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 91.0%
- contract: native typed output; transport/API errors=0
- trivial baselines: always-majority (none)=68.0%; newest-change-else-none=71.0%
- recency A_true_is_newest: n=32, accuracy=84.4%, selected-newest=84.4%, selected-none=15.6%
- recency B_true_older_than_a_distractor: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency C_no_causal_change: n=68, accuracy=94.1%, selected-newest=4.4%, selected-none=94.1%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=17, accuracy=88.2%
- no-causal-change accuracy=94.1%; distractor-selection rate=4.0% of all decisions, 10.0% when a distractor was offered (n=40)
- selected-is-newest-change rate: 49.2%
- accuracy when true causal change IS newest: 84.4% (n=32)
- accuracy when true causal change is OLDER than a distractor: n/a (n=0)

- efficiency: mean latency=255.41400000000002 ms (P50=180.1, P95=554.6); mean input/output tokens=1198.77/33.82; total input/output tokens=119877/3382
- cost (pricing 2026-09-23): total $0.0050; $0.050 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 68.0% | 97.1% | 2.9% |
| >= 0.8 | 53.0% | 98.1% | 1.9% |
| >= 0.85 | 50.0% | 100.0% | 0.0% |
| >= 0.9 | 44.0% | 100.0% | 0.0% |
| >= 0.95 | 42.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 72.0% | 72 |
| <=2% | 63.0% | 63 |
| <=1% | 51.0% | 51 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=86.7%, mean_confidence=77.0%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=76.5%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=67.3%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=63.8%
  - vague: n=12, accuracy=100.0%, mean_confidence=84.0%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=81.5%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=95.8%
  - sufficient: n=94, accuracy=90.4%, mean_confidence=75.8%
