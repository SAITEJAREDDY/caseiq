# Experiment: rc_context_v2_v2_domain_100

- experiment_id: `exp_rc_context_v2_v2_domain_100_20260923T083919Z_b9c24f64`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:39:19.364628+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: root_cause
- question_set_version: v2
- candidate_strategy_version: v2
- evaluator_version: v2
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v2_domain', 'comparison_baseline_experiment_id': 'exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823'}

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 5.0%
- acceptable_match_rate: 5.0%
- accuracy 95% CI: 5.0% [1.0%, 10.0%] (n=100)
- Brier: 0.6204
- ECE: 0.7342
- false-confident rate (wrong AND conf>=0.9): 31.0% (n=100)
- macro F1: 0.056
- candidate recall: 100.0% (avg candidates: 15.8)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 5.0% | conditional accuracy given candidate present: 5.0%
- failure decomposition: missing=0, present/jev-wrong=95, present/jev-correct=5, high-confidence-wrong=31

- efficiency: mean latency=150.516 ms; mean input/output tokens=984.33/163.38; total input/output tokens=98433/16338

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 69.0% | 4.3% | 95.7% |
| >= 0.8 | 57.0% | 1.8% | 98.2% |
| >= 0.85 | 50.0% | 2.0% | 98.0% |
| >= 0.9 | 32.0% | 3.1% | 96.9% |
| >= 0.95 | 20.0% | 5.0% | 95.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=5.0%, mean_confidence=77.2%
  - customer_misdiagnosis: n=13, accuracy=0.0%, mean_confidence=69.8%
  - dependency_root_cause: n=3, accuracy=33.3%, mean_confidence=87.3%
  - multi_component_symptoms: n=6, accuracy=0.0%, mean_confidence=82.7%
  - vague: n=12, accuracy=0.0%, mean_confidence=87.0%
  - wrong_product_mentioned: n=6, accuracy=16.7%, mean_confidence=83.3%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=74.2%
  - sufficient: n=94, accuracy=5.3%, mean_confidence=78.7%
