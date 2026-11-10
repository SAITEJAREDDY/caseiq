# Experiment: causal_change_v3_opaque_keys_dev100_llm

- experiment_id: `exp_causal_change_v3_opaque_keys_dev100_llm_20260923T172653Z_9076cf7d`
- experiment_type: llm_primitive_baseline
- kind: engineering
- created_at: 2026-09-23T17:26:53.826993+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: causal_change
- question_set_version: v2
- candidate_strategy_version: v3
- evaluator_version: v2.1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v3_technical', 'candidate_generation_versions': {'causal_change': 'v3'}, 'causal_key_mode': 'opaque', 'jev_model_requested': 'jev-1.13.0', 'frozen_config': None, 'pricing_version': '2026-09-23', 'llm_model': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'llm_temperature': 0.1, 'llm_max_tokens': 400, 'llm_repair_max_attempts': 1, 'paired_jev_experiment_id': 'exp_causal_change_v3_opaque_keys_dev100_jev_20260923T172653Z_cc0c9491'}

## causal_change (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 87.0%
- acceptable_match_rate: 87.0%
- accuracy 95% CI: 87.0% [80.0%, 93.0%] (n=100)
- Brier: 0.1116
- ECE: 0.0220
- false-confident rate (wrong AND conf>=0.9): 0.0% (n=100)
- macro F1: 0.665
- candidate recall: 100.0% (avg candidates: 1.8)
- candidate count distribution: median=2.0, P90=3
- end-to-end accuracy: 87.0% | conditional accuracy given candidate present: 87.0%
- failure decomposition: missing=0, present/jev-wrong=13, present/jev-correct=87, high-confidence-wrong=0
- strict first-attempt accuracy (contract failures count as wrong): 87.0%
- contract: first-attempt valid=100/100 (100.0%), repair required=0, repair succeeded=0, unrecoverable=0, request errors=0, first-attempt failure kinds={}
- trivial baselines: always-majority (none)=68.0%; newest-change-else-none=71.0%
- recency A_true_is_newest: n=32, accuracy=84.4%, selected-newest=84.4%, selected-none=12.5%
- recency B_true_older_than_a_distractor: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency C_no_causal_change: n=68, accuracy=88.2%, selected-newest=8.8%, selected-none=88.2%
- recency E_true_change_not_offered: n=0, accuracy=n/a, selected-newest=n/a, selected-none=n/a
- recency D_multiple_recent_changes: n=17, accuracy=64.7%
- no-causal-change accuracy=88.2%; distractor-selection rate=9.0% of all decisions, 22.5% when a distractor was offered (n=40)
- selected-is-newest-change rate: 54.1%
- accuracy when true causal change IS newest: 84.4% (n=32)
- accuracy when true causal change is OLDER than a distractor: n/a (n=0)

- efficiency: mean latency=921.846 ms (P50=802.75, P95=1600.4); mean input/output tokens=782.96/15.72; total input/output tokens=78296/1572
- cost (pricing 2026-09-23): total $0.0831; $0.831 per 1,000 decisions

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 99.0% | 86.9% | 13.1% |
| >= 0.8 | 99.0% | 86.9% | 13.1% |
| >= 0.85 | 40.0% | 100.0% | 0.0% |
| >= 0.9 | 40.0% | 100.0% | 0.0% |
| >= 0.95 | 40.0% | 100.0% | 0.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 53.0% | 53 |
| <=2% | 46.0% | 46 |
| <=1% | 46.0% | 46 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=80.0%, mean_confidence=86.7%
  - customer_misdiagnosis: n=13, accuracy=100.0%, mean_confidence=87.7%
  - dependency_root_cause: n=3, accuracy=100.0%, mean_confidence=86.7%
  - multi_component_symptoms: n=6, accuracy=100.0%, mean_confidence=83.3%
  - vague: n=12, accuracy=100.0%, mean_confidence=90.0%
  - wrong_product_mentioned: n=6, accuracy=83.3%, mean_confidence=90.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=100.0%, mean_confidence=96.7%
  - sufficient: n=94, accuracy=86.2%, mean_confidence=86.6%
