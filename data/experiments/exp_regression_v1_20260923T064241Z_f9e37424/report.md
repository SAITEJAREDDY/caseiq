# Experiment: regression_v1

- experiment_id: `exp_regression_v1_20260923T064241Z_f9e37424`
- kind: smoke
- created_at: 2026-09-23T06:42:41.394228+00:00
- dataset_split: regression_suite (split_version v1)
- num_cases: 9
- run_mode: run_and_evaluate
- evaluator_version: v1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- agent: {'model_provider': 'together', 'model_name': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'temperature': 0.1, 'prompt_version': 'v1', 'toolset_version': 'v1', 'output_schema_version': 'v1', 'agent_loop_version': 'v1', 'repair_layer_version': 'v1', 'graph_version': 'phase4-2500case-2026-09-22', 'homogeneous': True}

## Outcome correctness

| Field | Accuracy (scored/total, prediction_rate) |
|---|---|
| product | n/a (n=0/9, prediction_rate=0.0%) |
| component | n/a (n=0/9, prediction_rate=0.0%) |
| issue_category | n/a (n=0/9, prediction_rate=0.0%) |
| issue_subcategory | n/a (n=0/9, prediction_rate=0.0%) |
| root_cause_exact | n/a (n=0/9, prediction_rate=0.0%) |
| root_cause_containment | n/a (n=0/9, prediction_rate=0.0%) |
| causal_change | 0.0% (n=5/9, prediction_rate=55.6%) |
| severity_exact | n/a (n=0/9, prediction_rate=0.0%) |
| severity_within_one | n/a (n=0/9, prediction_rate=0.0%) |
| team_primary | n/a (n=0/9, prediction_rate=0.0%) |
| team_acceptable | n/a (n=0/9, prediction_rate=0.0%) |
| evidence_sufficiency | 22.2% (n=9/9, prediction_rate=100.0%) |
| human_review_agreement | 55.6% (n=9/9, prediction_rate=100.0%) |

## Bootstrap 95% CIs (headline metrics)

| Metric | Point estimate | CI low | CI high | n scored |
|---|---|---|---|---|
| root_cause_containment | n/a | n/a | n/a | 0 |
| component | n/a | n/a | n/a | 0 |
| team_acceptable | n/a | n/a | n/a | 0 |
| issue_category | n/a | n/a | n/a | 0 |

## Confidence / calibration (chosen-answer, not full-distribution)

### product
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

### component
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

### root_cause
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

### causal_change
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

### team
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

### severity
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

### overall
- Brier score: n/a
- ECE: n/a
- False-confident rate (wrong AND conf>=0.9): n/a (n=0)

| Bucket | n | mean conf | observed accuracy |
|---|---|---|---|
| 0.00-0.50 | 0 | n/a | n/a |
| 0.50-0.60 | 0 | n/a | n/a |
| 0.60-0.70 | 0 | n/a | n/a |
| 0.70-0.80 | 0 | n/a | n/a |
| 0.80-0.90 | 0 | n/a | n/a |
| 0.90-0.95 | 0 | n/a | n/a |
| 0.95-1.00 | 0 | n/a | n/a |

## False-confident root-cause rate by scenario

- insufficient_evidence: n/a (n=0)
- ambiguous: n/a (n=0)
- customer_misdiagnosis: n/a (n=0)

## Automation-coverage simulation (evaluation only)

| Threshold | % eligible | accuracy among eligible | wrong-auto-action rate | human-review % below |
|---|---|---|---|---|
| >= 0.7 | 44.4% | 0.0% | 100.0% | 80.0% |
| >= 0.8 | 44.4% | 0.0% | 100.0% | 80.0% |
| >= 0.85 | 0.0% | n/a | n/a | 44.4% |
| >= 0.9 | 0.0% | n/a | n/a | 44.4% |
| >= 0.95 | 0.0% | n/a | n/a | 44.4% |

## Evidence

- critical_all_retrieved_rate: 0.0%
- critical_all_cited_rate: 0.0%
- distractor_selected_as_causal_change_rate: 0.0%

## Process / contract compliance

- mean_tool_calls: 7.111111111111111
- p95_tool_calls: 8.0
- redundant_call_rate: 0.0%
- tool_error_rate: 100.0%
- unknown_tool_call_rate: 100.0%
- unsupported_evidence_rate: 0.0%
- budget_exhaustion_rate: 0.0%
- clean_run_rate: 0.0%
- n_repair_status_unknown: 0
- root_cause_accuracy_among_clean_runs: n/a (n=0/0, prediction_rate=n/a)
- root_cause_accuracy_among_repaired_runs: n/a (n=0/9, prediction_rate=0.0%)

## Efficiency

- mean_tokens: 14486.222222222223
- mean_cost_usd: 0.0014486666666666667
- total_cost_usd: 0.013038
- mean_llm_latency_ms: 11970.533333333333
- p95_llm_latency_ms: 14321.34
- cost_per_correct_root_cause_diagnosis: None

## Failure taxonomy

- % cases with at least one failure tag: 100.0%

| Tag | Count | Rate |
|---|---|---|
| contract_schema_problem | 9 | 100.0% |
| critical_evidence_missed | 7 | 77.8% |
| tool_failure | 6 | 66.7% |
| wrong_causal_change | 5 | 55.6% |
| missed_incident | 2 | 22.2% |

## Slices

### difficulty_archetype

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| clear | 5 | n/a (n=0/5, prediction_rate=0.0%) | n/a (n=0/5, prediction_rate=0.0%) | n/a (n=0/5, prediction_rate=0.0%) | 46.0% |
| customer_misdiagnosis | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 65.0% |
| dependency_root_cause | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| multi_component_symptoms | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |

### issue_category_id

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| IC01 | 3 | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | 46.7% |
| IC02 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 60.0% |
| IC05 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |
| IC07 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| IC08 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| IC09 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| IC11 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |

### evidence_sufficiency

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| insufficient | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |
| partially_sufficient | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |
| sufficient | 7 | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | 65.7% |

### incident_relationship

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| coincidental_unrelated | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |
| directly_caused | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 30.0% |
| none | 6 | n/a (n=0/6, prediction_rate=0.0%) | n/a (n=0/6, prediction_rate=0.0%) | n/a (n=0/6, prediction_rate=0.0%) | 71.7% |

### dependency_driven

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 61.3% |
| True | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |

### customer_misdiagnosis

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 7 | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | 55.7% |
| True | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 65.0% |

### multi_component

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 55.0% |
| True | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |

### ambiguous

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 57.8% |

### low_evidence

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 61.3% |
| True | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |

### reopened

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 57.8% |

### escalated

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 58.8% |
| True | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |
