# Experiment: phase8_trace_corpus_v1_phase6

- experiment_id: `exp_phase8_trace_corpus_v1_phase6_20260924T005609Z_52585a35`
- kind: engineering
- created_at: 2026-09-24T00:56:09.105952+00:00
- dataset_split: dev (split_version v1)
- num_cases: 150
- run_mode: evaluate_existing
- evaluator_version: v1
- dataset_checksum_digest: `51e4d7d3ff9f9645`
- agent: {'model_provider': 'together', 'model_name': 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 'temperature': 0.1, 'prompt_version': 'v1', 'toolset_version': 'v1', 'output_schema_version': 'v1', 'agent_loop_version': 'v1', 'repair_layer_version': 'v1', 'graph_version': 'phase4-2500case-2026-09-22', 'homogeneous': True}

## Outcome correctness

| Field | Accuracy (scored/total, prediction_rate) |
|---|---|
| product | n/a (n=0/150, prediction_rate=0.0%) |
| component | n/a (n=0/150, prediction_rate=0.0%) |
| issue_category | n/a (n=0/150, prediction_rate=0.0%) |
| issue_subcategory | n/a (n=0/150, prediction_rate=0.0%) |
| root_cause_exact | n/a (n=0/150, prediction_rate=0.0%) |
| root_cause_containment | n/a (n=0/150, prediction_rate=0.0%) |
| causal_change | n/a (n=0/150, prediction_rate=0.0%) |
| severity_exact | n/a (n=0/150, prediction_rate=0.0%) |
| severity_within_one | n/a (n=0/150, prediction_rate=0.0%) |
| team_primary | n/a (n=0/150, prediction_rate=0.0%) |
| team_acceptable | n/a (n=0/150, prediction_rate=0.0%) |
| evidence_sufficiency | 14.0% (n=150/150, prediction_rate=100.0%) |
| human_review_agreement | 65.3% (n=150/150, prediction_rate=100.0%) |

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
| >= 0.7 | 43.3% | 0.0% | 100.0% | 50.6% |
| >= 0.8 | 40.7% | 0.0% | 100.0% | 48.3% |
| >= 0.85 | 6.7% | 0.0% | 100.0% | 38.6% |
| >= 0.9 | 6.7% | 0.0% | 100.0% | 38.6% |
| >= 0.95 | 0.7% | 0.0% | 100.0% | 36.2% |

## Evidence

- critical_all_retrieved_rate: 7.1%
- critical_all_cited_rate: 0.0%
- distractor_selected_as_causal_change_rate: 0.0%

## Process / contract compliance

- mean_tool_calls: 6.88
- p95_tool_calls: 8.0
- redundant_call_rate: 0.0%
- tool_error_rate: 100.0%
- unknown_tool_call_rate: 100.0%
- unsupported_evidence_rate: 2.7%
- budget_exhaustion_rate: 0.0%
- clean_run_rate: 0.0%
- n_repair_status_unknown: 0
- root_cause_accuracy_among_clean_runs: n/a (n=0/0, prediction_rate=n/a)
- root_cause_accuracy_among_repaired_runs: n/a (n=0/150, prediction_rate=0.0%)

## Efficiency

- mean_tokens: 14117.093333333334
- mean_cost_usd: 0.00141172
- total_cost_usd: 0.211758
- mean_llm_latency_ms: 18578.807333333334
- p95_llm_latency_ms: 32648.254999999983
- cost_per_correct_root_cause_diagnosis: None

## Failure taxonomy

- % cases with at least one failure tag: 100.0%

| Tag | Count | Rate |
|---|---|---|
| contract_schema_problem | 150 | 100.0% |
| critical_evidence_missed | 105 | 70.0% |
| tool_failure | 81 | 54.0% |
| wrong_causal_change | 64 | 42.7% |
| missed_incident | 6 | 4.0% |

## Slices

### difficulty_archetype

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| clear | 81 | n/a (n=0/81, prediction_rate=0.0%) | n/a (n=0/81, prediction_rate=0.0%) | n/a (n=0/81, prediction_rate=0.0%) | 59.1% |
| customer_misdiagnosis | 24 | n/a (n=0/24, prediction_rate=0.0%) | n/a (n=0/24, prediction_rate=0.0%) | n/a (n=0/24, prediction_rate=0.0%) | 70.0% |
| dependency_root_cause | 10 | n/a (n=0/10, prediction_rate=0.0%) | n/a (n=0/10, prediction_rate=0.0%) | n/a (n=0/10, prediction_rate=0.0%) | 67.0% |
| multi_component_symptoms | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 51.2% |
| vague | 16 | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | 49.4% |
| wrong_product_mentioned | 11 | n/a (n=0/11, prediction_rate=0.0%) | n/a (n=0/11, prediction_rate=0.0%) | n/a (n=0/11, prediction_rate=0.0%) | 62.7% |

### issue_category_id

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| IC01 | 14 | n/a (n=0/14, prediction_rate=0.0%) | n/a (n=0/14, prediction_rate=0.0%) | n/a (n=0/14, prediction_rate=0.0%) | 52.1% |
| IC02 | 4 | n/a (n=0/4, prediction_rate=0.0%) | n/a (n=0/4, prediction_rate=0.0%) | n/a (n=0/4, prediction_rate=0.0%) | 70.0% |
| IC03 | 3 | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | 50.0% |
| IC04 | 6 | n/a (n=0/6, prediction_rate=0.0%) | n/a (n=0/6, prediction_rate=0.0%) | n/a (n=0/6, prediction_rate=0.0%) | 63.3% |
| IC05 | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 52.2% |
| IC06 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 50.0% |
| IC07 | 7 | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | 70.0% |
| IC08 | 7 | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | n/a (n=0/7, prediction_rate=0.0%) | 58.6% |
| IC09 | 21 | n/a (n=0/21, prediction_rate=0.0%) | n/a (n=0/21, prediction_rate=0.0%) | n/a (n=0/21, prediction_rate=0.0%) | 64.8% |
| IC10 | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 61.3% |
| IC11 | 14 | n/a (n=0/14, prediction_rate=0.0%) | n/a (n=0/14, prediction_rate=0.0%) | n/a (n=0/14, prediction_rate=0.0%) | 61.4% |
| IC12 | 15 | n/a (n=0/15, prediction_rate=0.0%) | n/a (n=0/15, prediction_rate=0.0%) | n/a (n=0/15, prediction_rate=0.0%) | 54.7% |
| IC13 | 17 | n/a (n=0/17, prediction_rate=0.0%) | n/a (n=0/17, prediction_rate=0.0%) | n/a (n=0/17, prediction_rate=0.0%) | 65.3% |
| IC14 | 13 | n/a (n=0/13, prediction_rate=0.0%) | n/a (n=0/13, prediction_rate=0.0%) | n/a (n=0/13, prediction_rate=0.0%) | 58.5% |
| IC15 | 4 | n/a (n=0/4, prediction_rate=0.0%) | n/a (n=0/4, prediction_rate=0.0%) | n/a (n=0/4, prediction_rate=0.0%) | 75.0% |
| IC16 | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 80.0% |
| IC17 | 6 | n/a (n=0/6, prediction_rate=0.0%) | n/a (n=0/6, prediction_rate=0.0%) | n/a (n=0/6, prediction_rate=0.0%) | 48.3% |

### evidence_sufficiency

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| insufficient | 16 | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | 41.9% |
| partially_sufficient | 17 | n/a (n=0/17, prediction_rate=0.0%) | n/a (n=0/17, prediction_rate=0.0%) | n/a (n=0/17, prediction_rate=0.0%) | 59.4% |
| sufficient | 117 | n/a (n=0/117, prediction_rate=0.0%) | n/a (n=0/117, prediction_rate=0.0%) | n/a (n=0/117, prediction_rate=0.0%) | 62.8% |

### incident_relationship

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| coincidental_unrelated | 16 | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | 61.3% |
| customer_assumed_incorrectly | 9 | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | n/a (n=0/9, prediction_rate=0.0%) | 61.1% |
| directly_caused | 5 | n/a (n=0/5, prediction_rate=0.0%) | n/a (n=0/5, prediction_rate=0.0%) | n/a (n=0/5, prediction_rate=0.0%) | 36.0% |
| none | 119 | n/a (n=0/119, prediction_rate=0.0%) | n/a (n=0/119, prediction_rate=0.0%) | n/a (n=0/119, prediction_rate=0.0%) | 61.3% |
| partially_influenced | 1 | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | n/a (n=0/1, prediction_rate=0.0%) | 30.0% |

### dependency_driven

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 134 | n/a (n=0/134, prediction_rate=0.0%) | n/a (n=0/134, prediction_rate=0.0%) | n/a (n=0/134, prediction_rate=0.0%) | 60.6% |
| True | 16 | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | 56.9% |

### customer_misdiagnosis

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 126 | n/a (n=0/126, prediction_rate=0.0%) | n/a (n=0/126, prediction_rate=0.0%) | n/a (n=0/126, prediction_rate=0.0%) | 58.3% |
| True | 24 | n/a (n=0/24, prediction_rate=0.0%) | n/a (n=0/24, prediction_rate=0.0%) | n/a (n=0/24, prediction_rate=0.0%) | 70.0% |

### multi_component

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 142 | n/a (n=0/142, prediction_rate=0.0%) | n/a (n=0/142, prediction_rate=0.0%) | n/a (n=0/142, prediction_rate=0.0%) | 60.7% |
| True | 8 | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | n/a (n=0/8, prediction_rate=0.0%) | 51.2% |

### ambiguous

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 123 | n/a (n=0/123, prediction_rate=0.0%) | n/a (n=0/123, prediction_rate=0.0%) | n/a (n=0/123, prediction_rate=0.0%) | 61.4% |
| True | 27 | n/a (n=0/27, prediction_rate=0.0%) | n/a (n=0/27, prediction_rate=0.0%) | n/a (n=0/27, prediction_rate=0.0%) | 54.8% |

### low_evidence

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 134 | n/a (n=0/134, prediction_rate=0.0%) | n/a (n=0/134, prediction_rate=0.0%) | n/a (n=0/134, prediction_rate=0.0%) | 62.4% |
| True | 16 | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | n/a (n=0/16, prediction_rate=0.0%) | 41.9% |

### reopened

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 147 | n/a (n=0/147, prediction_rate=0.0%) | n/a (n=0/147, prediction_rate=0.0%) | n/a (n=0/147, prediction_rate=0.0%) | 59.9% |
| True | 3 | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | n/a (n=0/3, prediction_rate=0.0%) | 73.3% |

### escalated

| value | n | root_cause_containment | component | team_acceptable | mean confidence |
|---|---|---|---|---|---|
| False | 129 | n/a (n=0/129, prediction_rate=0.0%) | n/a (n=0/129, prediction_rate=0.0%) | n/a (n=0/129, prediction_rate=0.0%) | 60.9% |
| True | 21 | n/a (n=0/21, prediction_rate=0.0%) | n/a (n=0/21, prediction_rate=0.0%) | n/a (n=0/21, prediction_rate=0.0%) | 55.7% |
