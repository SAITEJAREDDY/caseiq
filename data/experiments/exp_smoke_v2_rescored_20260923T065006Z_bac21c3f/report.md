# Experiment: smoke_v2_rescored

- experiment_id: `exp_smoke_v2_rescored_20260923T065006Z_bac21c3f`
- kind: smoke
- created_at: 2026-09-23T06:50:06.694713+00:00
- dataset_split: explicit_case_ids (split_version v1)
- num_cases: 12
- run_mode: evaluate_existing
- evaluator_version: v1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- agent: {'model_provider': 'together', 'model_name': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'temperature': 0.1, 'prompt_version': 'v1', 'toolset_version': 'v1', 'output_schema_version': 'v1', 'agent_loop_version': 'v1', 'repair_layer_version': 'v1', 'graph_version': 'phase4-2500case-2026-09-22', 'homogeneous': True}

## Outcome correctness

| Field | Accuracy (scored/total, prediction_rate) |
|---|---|
| product | n/a (n=0/12, prediction_rate=0.0%) |
| component | n/a (n=0/12, prediction_rate=0.0%) |
| issue_category | n/a (n=0/12, prediction_rate=0.0%) |
| issue_subcategory | n/a (n=0/12, prediction_rate=0.0%) |
| root_cause_exact | n/a (n=0/12, prediction_rate=0.0%) |
| root_cause_containment | n/a (n=0/12, prediction_rate=0.0%) |
| causal_change | n/a (n=0/12, prediction_rate=0.0%) |
| severity_exact | n/a (n=0/12, prediction_rate=0.0%) |
| severity_within_one | n/a (n=0/12, prediction_rate=0.0%) |
| team_primary | n/a (n=0/12, prediction_rate=0.0%) |
| team_acceptable | n/a (n=0/12, prediction_rate=0.0%) |
| evidence_sufficiency | 16.7% (n=12/12, prediction_rate=100.0%) |
| human_review_agreement | 25.0% (n=12/12, prediction_rate=100.0%) |

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
| >= 0.7 | 8.3% | 0.0% | 100.0% | 81.8% |
| >= 0.8 | 8.3% | 0.0% | 100.0% | 81.8% |
| >= 0.85 | 0.0% | n/a | n/a | 75.0% |
| >= 0.9 | 0.0% | n/a | n/a | 75.0% |
| >= 0.95 | 0.0% | n/a | n/a | 75.0% |

## Evidence

- critical_all_retrieved_rate: 11.1%
- critical_all_cited_rate: 0.0%
- distractor_selected_as_causal_change_rate: 0.0%

## Process / contract compliance

- mean_tool_calls: 7.25
- p95_tool_calls: 9.0
- redundant_call_rate: 0.0%
- tool_error_rate: 100.0%
- unknown_tool_call_rate: 100.0%
- unsupported_evidence_rate: 0.0%
- budget_exhaustion_rate: 0.0%
- clean_run_rate: 0.0%
- n_repair_status_unknown: 0
- root_cause_accuracy_among_clean_runs: n/a (n=0/0, prediction_rate=n/a)
- root_cause_accuracy_among_repaired_runs: n/a (n=0/12, prediction_rate=0.0%)

## Efficiency

- mean_tokens: 14336.083333333334
- mean_cost_usd: 0.0014335833333333334
- total_cost_usd: 0.017203
- mean_llm_latency_ms: 10161.525
- p95_llm_latency_ms: 13471.789999999999
- cost_per_correct_root_cause_diagnosis: None

## Failure taxonomy

- % cases with at least one failure tag: 100.0%

| Tag | Count | Rate |
|---|---|---|
| contract_schema_problem | 12 | 100.0% |
| tool_failure | 9 | 75.0% |
| critical_evidence_missed | 8 | 66.7% |
| wrong_causal_change | 4 | 33.3% |

## Slices

### difficulty_archetype

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| clear | 7 | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | 37.1% |
| customer_misdiagnosis | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |
| multi_component_symptoms | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| vague | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 50.0% |
| wrong_product_mentioned | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |

### issue_category_id

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| IC01 | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 40.0% |
| IC04 | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 45.0% |
| IC05 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |
| IC09 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| IC11 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |
| IC12 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |
| IC13 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |
| IC14 | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 40.0% |
| IC17 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |

### evidence_sufficiency

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| partially_sufficient | 3 | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | 36.7% |
| sufficient | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 45.6% |

### incident_relationship

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| none | 12 | n/a (n=0/12, prediction_rate=0.0%) | n/a (n=0/12, prediction_rate=0.0%) | n/a (n=0/12, prediction_rate=0.0%) | 43.3% |

### dependency_driven

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 47.8% |
| True | 3 | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | 30.0% |

### customer_misdiagnosis

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 11 | n/a (n=0/11, prediction_rate=0.0%) | n/a (n=0/11, prediction_rate=0.0%) | n/a (n=0/11, prediction_rate=0.0%) | 42.7% |
| True | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |

### multi_component

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 11 | n/a (n=0/11, prediction_rate=0.0%) | n/a (n=0/11, prediction_rate=0.0%) | n/a (n=0/11, prediction_rate=0.0%) | 40.0% |
| True | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |

### ambiguous

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 43.3% |
| True | 3 | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | 43.3% |

### low_evidence

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 12 | n/a (n=0/12, prediction_rate=0.0%) | n/a (n=0/12, prediction_rate=0.0%) | n/a (n=0/12, prediction_rate=0.0%) | 43.3% |

### reopened

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 12 | n/a (n=0/12, prediction_rate=0.0%) | n/a (n=0/12, prediction_rate=0.0%) | n/a (n=0/12, prediction_rate=0.0%) | 43.3% |

### escalated

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 10 | n/a (n=0/10, prediction_rate=0.0%) | n/a (n=0/10, prediction_rate=0.0%) | n/a (n=0/10, prediction_rate=0.0%) | 41.0% |
| True | 2 | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | n/a (n=0/2, prediction_rate=0.0%) | 55.0% |
