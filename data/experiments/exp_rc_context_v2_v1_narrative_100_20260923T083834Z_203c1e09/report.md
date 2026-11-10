# Experiment: rc_context_v2_v1_narrative_100

- experiment_id: `exp_rc_context_v2_v1_narrative_100_20260923T083834Z_203c1e09`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:38:34.336115+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: root_cause
- question_set_version: v2
- candidate_strategy_version: v2
- evaluator_version: v2
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v1_narrative', 'comparison_baseline_experiment_id': 'exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823'}

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 0.0%
- acceptable_match_rate: 0.0%
- accuracy 95% CI: 0.0% [0.0%, 0.0%] (n=100)
- Brier: 1.0000
- ECE: 1.0000
- false-confident rate (wrong AND conf>=0.9): 100.0% (n=100)
- macro F1: 0.000
- candidate recall: 0.0% (avg candidates: 1.0)
- candidate count distribution: median=1.0, P90=1
- end-to-end accuracy: 0.0% | conditional accuracy given candidate present: n/a
- failure decomposition: missing=100, present/jev-wrong=0, present/jev-correct=0, high-confidence-wrong=100

- efficiency: mean latency=164.8 ms; mean input/output tokens=431.63/30.0; total input/output tokens=43163/3000

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 100.0% | 0.0% | 100.0% |
| >= 0.8 | 100.0% | 0.0% | 100.0% |
| >= 0.85 | 100.0% | 0.0% | 100.0% |
| >= 0.9 | 100.0% | 0.0% | 100.0% |
| >= 0.95 | 100.0% | 0.0% | 100.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=0.0%, mean_confidence=100.0%
  - customer_misdiagnosis: n=13, accuracy=0.0%, mean_confidence=100.0%
  - dependency_root_cause: n=3, accuracy=0.0%, mean_confidence=100.0%
  - multi_component_symptoms: n=6, accuracy=0.0%, mean_confidence=100.0%
  - vague: n=12, accuracy=0.0%, mean_confidence=100.0%
  - wrong_product_mentioned: n=6, accuracy=0.0%, mean_confidence=100.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=100.0%
  - sufficient: n=94, accuracy=0.0%, mean_confidence=100.0%
