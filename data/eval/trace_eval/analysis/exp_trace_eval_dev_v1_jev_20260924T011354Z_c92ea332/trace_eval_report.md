# Phase 8 trace evaluation: measured results (generated)

Jev experiment `exp_trace_eval_dev_v1_jev_20260924T011354Z_c92ea332`, LLM experiment `exp_trace_eval_dev_v1_llm_20260924T011354Z_321f78cc`.

## Corpus

150 original traces (150 cases) and 165 synthetic variants {'P1': 30, 'P2': 25, 'P3': 30, 'P4': 30, 'P5': 25, 'P6': 25}.

Outcome {'CORRECT': 16, 'WRONG': 108, 'UNANSWERED': 26}; quadrant {'A': 1, 'D': 134, 'B': 15}; archetype {'multi_component_symptoms': 8, 'vague': 16, 'clear': 81, 'dependency_root_cause': 10, 'customer_misdiagnosis': 24, 'wrong_product_mentioned': 11}.

Reference labels:

- support: {'SUPPORTED': 8, 'UNSUPPORTED': 104, 'PARTIALLY_SUPPORTED': 38}
- missed_evidence: {'False': 45, 'True': 105}
- distractor_anchor: {'False': 127, 'True': 23}
- premature_close: {'False': 85, 'True': 65}
- final_consistency: {'True': 134, 'False': 16}
- human_review: {'AUTO_CLOSE': 1, 'HUMAN_REVIEW': 94, 'PRIORITY_REVIEW': 55}
- human_review_process_only: {'AUTO_CLOSE': 8, 'HUMAN_REVIEW': 142}

## Performance on original traces (Jev / LLM / observable-only rule)

| Judgment | n (pos) | Judge | Accuracy | F1 | Precision | Recall | ROC-AUC [95% CI] | PR-AUC | Brier | ECE | False-confident |
|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| J1 support | 112 (8) | jev | 50.0% | 0.20 | 0.11 | 0.88 | 0.70 [0.53, 0.86] | 0.29 | 0.27 | 0.43 | 0/2 |
| J1 support | 112 (8) | llm | 75.0% | 0.30 | 0.19 | 0.75 | 0.75 [0.55, 0.92] | 0.20 | 0.17 | 0.21 | 3/72 |
| J1 support | 112 (8) | det | 100.0% | 1.00 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00 | 0.00 | 0.00 | 0/112 |
| J2 missed_evidence | 150 (105) | jev | 76.0% | 0.85 | 0.76 | 0.96 | 0.84 [0.77, 0.90] | 0.92 | 0.16 | 0.09 | 6/70 |
| J2 missed_evidence | 150 (105) | llm | 84.7% | 0.90 | 0.84 | 0.97 | 0.77 [0.69, 0.85] | 0.84 | 0.13 | 0.04 | 4/41 |
| J2 missed_evidence | 150 (105) | det | 76.7% | 0.86 | 0.75 | 1.00 | 0.61 [0.55, 0.68] | 0.75 | 0.23 | 0.23 | 35/150 |
| J3 distractor_anchor | 150 (23) | jev | 58.7% | 0.40 | 0.26 | 0.91 | 0.85 [0.77, 0.92] | 0.57 | 0.23 | 0.34 | 0/7 |
| J3 distractor_anchor | 150 (23) | llm | 18.0% | 0.27 | 0.16 | 1.00 | 0.47 [0.44, 0.50] | 0.16 | 0.55 | 0.64 | 12/12 |
| J3 distractor_anchor | 150 (23) | det | 84.7% | n/a | n/a | 0.00 | 0.50 [0.50, 0.50] | 0.15 | 0.15 | 0.15 | 23/150 |
| J4 premature_close | 150 (65) | jev | 85.3% | 0.84 | 0.81 | 0.86 | 0.93 [0.88, 0.96] | 0.86 | 0.12 | 0.12 | 0/6 |
| J4 premature_close | 150 (65) | llm | 43.3% | 0.60 | 0.43 | 1.00 | 0.33 [0.26, 0.40] | 0.39 | 0.43 | 0.41 | 46/59 |
| J4 premature_close | 150 (65) | det | 93.3% | 0.93 | 0.87 | 1.00 | 0.94 [0.91, 0.97] | 0.87 | 0.07 | 0.07 | 10/150 |
| J5 final_consistency | 150 (134) | jev | 58.7% | 0.70 | 0.99 | 0.54 | 0.85 [0.77, 0.93] | 0.98 | 0.22 | 0.37 | 0/4 |
| J5 final_consistency | 150 (134) | llm | 11.3% | 0.01 | 1.00 | 0.01 | 0.50 [0.50, 0.51] | 0.89 | 0.89 | 0.89 | 133/150 |
| J5 final_consistency | 150 (134) | det | 100.0% | 1.00 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00 | 0.00 | 0.00 | 0/150 |

## Jev versus the LLM judge (paired, exact McNemar on correct-at-0.5; AUC difference by paired bootstrap)

| Judgment | Only Jev right | Only LLM right | McNemar p | AUC Jev - LLM [95% CI] | AUC Jev - rule [95% CI] |
|---|---:|---:|---:|---|---|
| J1 support | 11 | 39 | 0.000 | -0.05 [-0.23, 0.12] | -0.30 [-0.47, -0.14] |
| J2 missed_evidence | 6 | 19 | 0.015 | 0.07 [-0.03, 0.17] | 0.23 [0.12, 0.32] |
| J3 distractor_anchor | 66 | 5 | 0.000 | 0.38 [0.29, 0.45] | 0.35 [0.27, 0.42] |
| J4 premature_close | 72 | 9 | 0.000 | 0.60 [0.51, 0.68] | -0.01 [-0.05, 0.02] |
| J5 final_consistency | 72 | 1 | 0.000 | 0.35 [0.26, 0.42] | -0.15 [-0.23, -0.07] |

## Perturbations (direction each judgment should move; share of variants that moved that way)

| Perturbation | Judgment | Expected | n | Jev consistent | Jev material (>=0.05) | Jev mean delta | LLM consistent | LLM mean delta |
|---|---|---|---:|---|---:|---:|---|---:|
| P1 remove one critical evidence item from the trace's tool resu | human_review | up | 30 | 29/30 (97%) | 15 | 0.056 | 0/30 | 0.000 |
| P1 remove one critical evidence item from the trace's tool resu | missed_evidence | up | 30 | 23/30 (77%) | 5 | 0.028 | 5/30 | 0.063 |
| P1 remove one critical evidence item from the trace's tool resu | support | down | 30 | 29/30 (97%) | 26 | -0.254 | 15/30 | -0.313 |
| P2 move the step that returned a known distractor to just befor | distractor_anchor | up | 25 | 13/25 (52%) | 0 | 0.004 | 1/25 | 0.004 |
| P3 truncate the trace before the first retrieval of critical ev | human_review | up | 30 | 29/30 (97%) | 25 | 0.104 | 0/30 | 0.000 |
| P3 truncate the trace before the first retrieval of critical ev | premature_close | up | 30 | 30/30 (100%) | 28 | 0.134 | 27/30 | 0.090 |
| P3 truncate the trace before the first retrieval of critical ev | support | down | 30 | 30/30 (100%) | 28 | -0.408 | 21/30 | -0.543 |
| P4 replace the final top hypothesis with an alternative the tra | final_consistency | down | 30 | 30/30 (100%) | 30 | -0.526 | 0/30 | 0.000 |
| P4 replace the final top hypothesis with an alternative the tra | human_review | up | 30 | 30/30 (100%) | 30 | 0.200 | 0/30 | 0.000 |
| P5 remove one duplicate tool call (5 natural cases), else inser | distractor_anchor | stable | 25 | 25/25 (100%) | n/a | -0.002 | 25/25 | 0.000 |
| P5 remove one duplicate tool call (5 natural cases), else inser | final_consistency | stable | 25 | 23/25 (92%) | n/a | -0.000 | 25/25 | 0.000 |
| P5 remove one duplicate tool call (5 natural cases), else inser | human_review | stable | 25 | 25/25 (100%) | n/a | 0.004 | 25/25 | 0.000 |
| P5 remove one duplicate tool call (5 natural cases), else inser | missed_evidence | stable | 25 | 25/25 (100%) | n/a | 0.000 | 25/25 | 0.000 |
| P5 remove one duplicate tool call (5 natural cases), else inser | premature_close | stable | 25 | 25/25 (100%) | n/a | 0.004 | 25/25 | 0.020 |
| P5 remove one duplicate tool call (5 natural cases), else inser | support | stable | 25 | 25/25 (100%) | n/a | -0.003 | 22/25 | -0.076 |
| P6 re-alias every model-facing identifier with a different mapp | distractor_anchor | stable | 25 | 25/25 (100%) | n/a | 0.000 | 25/25 | 0.004 |
| P6 re-alias every model-facing identifier with a different mapp | final_consistency | stable | 25 | 25/25 (100%) | n/a | 0.003 | 25/25 | 0.000 |
| P6 re-alias every model-facing identifier with a different mapp | human_review | stable | 25 | 25/25 (100%) | n/a | -0.001 | 25/25 | 0.000 |
| P6 re-alias every model-facing identifier with a different mapp | missed_evidence | stable | 25 | 25/25 (100%) | n/a | 0.000 | 24/25 | -0.032 |
| P6 re-alias every model-facing identifier with a different mapp | premature_close | stable | 25 | 25/25 (100%) | n/a | 0.006 | 25/25 | 0.000 |
| P6 re-alias every model-facing identifier with a different mapp | support | stable | 25 | 25/25 (100%) | n/a | -0.000 | 22/25 | -0.064 |

## Capability map (pre-registered rubric)

| Judgment | Category | Jev AUC | LLM AUC | Rule AUC | Reasons |
|---|---|---:|---:|---:|---|
| J1 support | **Better deterministic** | 0.70 | 0.75 | 1.00 | an observable-only rule reaches AUC 1.00 against Jev 0.70 and the LLM 0.75 |
| J2 missed_evidence | **Useful supporting signal** | 0.84 | 0.77 | 0.61 | Jev AUC 0.84 (lower bound 0.77) clears the signal bar but not every Strong condition (directional ok: False, stable ok: True, ECE 0.08593333333333336) |
| J3 distractor_anchor | **Useful supporting signal** | 0.85 | 0.47 | 0.50 | Jev AUC 0.85 (lower bound 0.77) clears the signal bar but not every Strong condition (directional ok: False, stable ok: True, ECE 0.33786666666666665) |
| J4 premature_close | **Better deterministic** | 0.93 | 0.33 | 0.94 | an observable-only rule reaches AUC 0.94 against Jev 0.93 and the LLM 0.33 |
| J5 final_consistency | **Better deterministic** | 0.85 | 0.50 | 1.00 | an observable-only rule reaches AUC 1.00 against Jev 0.85 and the LLM 0.50 |
| J6 human_review | **Useful supporting signal (provisional: thin class)** | n/a | n/a | n/a | only 1 clean traces in the corpus: auto-close precision cannot be established; Jev auto-closed 0 traces, 0 unsafe; the LLM auto-closed 0, 0 unsafe; PRIORITY vs rest AUC: Jev 0.7147368421052631, LLM 0.5 |
