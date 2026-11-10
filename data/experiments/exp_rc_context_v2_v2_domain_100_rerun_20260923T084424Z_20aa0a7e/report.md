# Experiment: rc_context_v2_v2_domain_100_rerun

- experiment_id: `exp_rc_context_v2_v2_domain_100_rerun_20260923T084424Z_20aa0a7e`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:44:24.027499+00:00
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
- Brier: 0.6105
- ECE: 0.7235
- false-confident rate (wrong AND conf>=0.9): 32.0% (n=100)
- macro F1: 0.056
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 5.0% | conditional accuracy given candidate present: 5.0%
- failure decomposition: missing=0, present/jev-wrong=95, present/jev-correct=5, high-confidence-wrong=32

- efficiency: mean latency=151.36700000000002 ms; mean input/output tokens=984.72/163.92; total input/output tokens=98472/16392

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 70.0% | 2.9% | 97.1% |
| >= 0.8 | 53.0% | 1.9% | 98.1% |
| >= 0.85 | 46.0% | 2.2% | 97.8% |
| >= 0.9 | 33.0% | 3.0% | 97.0% |
| >= 0.95 | 18.0% | 5.6% | 94.4% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=5.0%, mean_confidence=76.3%
  - customer_misdiagnosis: n=13, accuracy=0.0%, mean_confidence=63.1%
  - dependency_root_cause: n=3, accuracy=33.3%, mean_confidence=90.7%
  - multi_component_symptoms: n=6, accuracy=0.0%, mean_confidence=85.5%
  - vague: n=12, accuracy=0.0%, mean_confidence=88.0%
  - wrong_product_mentioned: n=6, accuracy=16.7%, mean_confidence=82.8%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=63.5%
  - sufficient: n=94, accuracy=5.3%, mean_confidence=78.2%
