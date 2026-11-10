# Experiment: rc_context_v2_v1_narrative_100_rerun

- experiment_id: `exp_rc_context_v2_v1_narrative_100_rerun_20260923T084336Z_0a7c0075`
- experiment_type: jev_primitive
- kind: engineering
- created_at: 2026-09-23T08:43:36.702622+00:00
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
- accuracy: 6.0%
- acceptable_match_rate: 6.0%
- accuracy 95% CI: 6.0% [2.0%, 11.0%] (n=100)
- Brier: 0.6294
- ECE: 0.7209
- false-confident rate (wrong AND conf>=0.9): 32.0% (n=100)
- macro F1: 0.062
- candidate recall: 100.0% (avg candidates: 15.9)
- candidate count distribution: median=16.0, P90=16
- end-to-end accuracy: 6.0% | conditional accuracy given candidate present: 6.0%
- failure decomposition: missing=0, present/jev-wrong=94, present/jev-correct=6, high-confidence-wrong=32

- efficiency: mean latency=165.418 ms; mean input/output tokens=674.68/163.92; total input/output tokens=67468/16392

Automation coverage:

| Threshold | Coverage | Accuracy among eligible | Error rate |
|---|---|---|---|
| >= 0.7 | 69.0% | 2.9% | 97.1% |
| >= 0.8 | 57.0% | 3.5% | 96.5% |
| >= 0.85 | 47.0% | 2.1% | 97.9% |
| >= 0.9 | 33.0% | 3.0% | 97.0% |
| >= 0.95 | 21.0% | 4.8% | 95.2% |

Target-error coverage:

| Target error | Max coverage | n |
|---|---|---|
| <=5% | 0.0% | 0 |
| <=2% | 0.0% | 0 |
| <=1% | 0.0% | 0 |

Slices:

- difficulty_archetype:
  - clear: n=60, accuracy=6.7%, mean_confidence=76.1%
  - customer_misdiagnosis: n=13, accuracy=0.0%, mean_confidence=67.7%
  - dependency_root_cause: n=3, accuracy=33.3%, mean_confidence=89.7%
  - multi_component_symptoms: n=6, accuracy=0.0%, mean_confidence=90.7%
  - vague: n=12, accuracy=0.0%, mean_confidence=90.2%
  - wrong_product_mentioned: n=6, accuracy=16.7%, mean_confidence=77.8%
- evidence_sufficiency:
  - partially_sufficient: n=6, accuracy=0.0%, mean_confidence=66.8%
  - sufficient: n=94, accuracy=6.4%, mean_confidence=78.8%
