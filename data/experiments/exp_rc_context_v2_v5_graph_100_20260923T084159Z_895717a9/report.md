# Experiment: rc_context_v2_v5_graph_100

- experiment_id: `exp_rc_context_v2_v5_graph_100_20260923T084159Z_895717a9`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:41:59.152444+00:00
- dataset_split: dev
- num_cases: 100
- decision_types: root_cause
- question_set_version: v2
- candidate_strategy_version: v2
- evaluator_version: v2
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- config: {'context_version': 'v5_graph', 'comparison_baseline_experiment_id': 'exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823'}

## root_cause (choice)

- n_decisions: 100  (errors: 0, contract failures: 0)
- accuracy: 46.0%
- acceptable_match_rate: 46.0%
- accuracy 95% CI: 46.0% [37.0%, 55.0%] (n=100)
- Brier: 0.2824
- ECE: 0.1831
- false-confident rate (wrong AND conf>=0.9): 4.0% (n=100)
- macro F1: 0.433
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 46.0% | conditional accuracy given candidate present: 46.0%
- failure decomposition: missing=0, present/jev-wrong=54, present/jev-correct=46, high-confidence-wrong=4

- efficiency: mean latency=175.657 ms; mean input/output tokens=1806.84/163.92; total input/output tokens=180684/16392

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 42.0% | 54.8% | 45.2% |
| >= 0.8 | 26.0% | 69.2% | 30.8% |
| >= 0.85 | 21.0% | 76.2% | 23.8% |
| >= 0.9 | 13.0% | 69.2% | 30.8% |
| >= 0.95 | 5.0% | 80.0% | 20.0% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 1.0% | 1 |
| <=2% | 1.0% | 1 |
| <=1% | 1.0% | 1 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=43.3%, mean_confidence=61.9%
  - customer_misdiagnosis: n=13, accuracy=53.8%, mean_confidence=64.8%
  - dependency_root_cause: n=3, accuracy=66.7%, mean_confidence=72.0%
  - multi_component_symptoms: n=6, accuracy=33.3%, mean_confidence=65.8%
  - vague: n=12, accuracy=50.0%, mean_confidence=69.2%
  - wrong_product_mentioned: n=6, accuracy=50.0%, mean_confidence=62.0%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=78.0%
  - sufficient: n=94, accuracy=48.9%, mean_confidence=62.8%
