# Experiment: rc_context_v2_v4_operational_100

- experiment_id: `exp_rc_context_v2_v4_operational_100_20260923T084026Z_e9fa26a3`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:40:26.967677+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: root_cause
- question_set_version: v2
- candidate_strategy_version: v2
- evaluator_version: v2
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v4_operational', 'comparison_baseline_experiment_id': 'exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823'}

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 45.0%
- acceptable_match_rate: 45.0%
- accuracy 95% CI: 45.0% [36.0%, 55.0%] (n=100)
- Brier: 0.2758
- ECE: 0.1928
- false-confident rate (wrong AND conf>=0.9): 3.0% (n=100)
- macro F1: 0.419
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 45.0% | conditional accuracy given candidate present: 45.0%
- failure decomposition: missing=0, present/jev-wrong=55, present/jev-correct=45, high-confidence-wrong=3

- efficiency: mean latency=165.24200000000002 ms; mean input/output tokens=1478.92/163.92; total input/output tokens=147892/16392

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 44.0% | 56.8% | 43.2% |
| >= 0.8 | 24.0% | 70.8% | 29.2% |
| >= 0.85 | 20.0% | 75.0% | 25.0% |
| >= 0.9 | 15.0% | 80.0% | 20.0% |
| >= 0.95 | 5.0% | 60.0% | 40.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 2.0% | 2 |
| <=2% | 2.0% | 2 |
| <=1% | 2.0% | 2 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=40.0%, mean_confidence=62.5%
  - customer_misdiagnosis: n=13, accuracy=53.8%, mean_confidence=64.5%
  - dependency_root_cause: n=3, accuracy=66.7%, mean_confidence=71.0%
  - multi_component_symptoms: n=6, accuracy=33.3%, mean_confidence=66.5%
  - vague: n=12, accuracy=50.0%, mean_confidence=71.0%
  - wrong_product_mentioned: n=6, accuracy=66.7%, mean_confidence=59.5%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=77.8%
  - sufficient: n=94, accuracy=47.9%, mean_confidence=63.2%
