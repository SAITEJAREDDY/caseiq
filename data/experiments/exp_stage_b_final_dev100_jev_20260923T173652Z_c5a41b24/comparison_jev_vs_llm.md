# Jev vs LLM primitive baseline (JEV-018)

- Jev: `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24`  (jev-1.13.0)
- LLM: `exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff`  (meta-llama/Llama-3.3-70B-Instruct-Turbo, temperature 0.1, one repair re-prompt allowed)
- cohort: 100 `dev` cases; candidate versions {'issue_category': 'v1', 'root_cause': 'v2', 'causal_change': 'v3', 'owning_team': 'v2', 'evidence_sufficiency': 'v1', 'incident_relationship': 'v1'}; root-cause context v4_operational
- evaluator v2.1; pricing 2026-09-23 (token counts are provider-returned; prices are versioned assumptions)
- Single run per system (LLM temperature 0.1, no seed): no run-to-run variance is measured for the LLM.
- **Confidence is not comparable.** Jev's is a native probability from the typed primitive; the LLM's is a number it was asked to write. Shown side by side for transparency, never ranked against each other.

## causal_change

- n = 100 paired decisions; input parity (identical state, candidates, decision time): 100/100
- trivial baseline: always `none` = 68.0%; newest-change-else-none = 71.0%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 1.8 | 1.8 |
| Accuracy (as scored) | 92.0% [87.0%, 97.0%] | 80.0% [72.0%, 87.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 92.0% | 80.0% |
| Conditional accuracy (true answer offered) | 92.0% | 80.0% |
| Macro F1 | 0.782 | 0.597 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 0 / 44 | 0 / 39 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.128 / 0.162 | 0.139 / 0.074 |
| First-attempt valid output | 100/100 (native typed) | 100/100 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 169 / 302 | 783 / 1722 |
| Mean input / output tokens | 1202 / 38 | 783 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000050 / 0.0505 | 0.000831 / 0.8308 |
| No-causal-change accuracy | 94.1% | 75.0% |
| Distractor-selection rate (a distractor was offered) | 10.0% | 42.5% |
| Recency A true is newest (n = 32) | 87.5% | 90.6% |
| Recency B true older than a distractor (n = 0) | n/a | n/a |
| Recency C no causal change (n = 68) | 94.1% | 75.0% |
| Recency D multiple recent changes (n = 17) | 88.2% | 58.8% |
| Recency E true change not offered (n = 0) | n/a | n/a |

Paired outcomes: both correct 78, only Jev 14, only LLM 2, neither 6; exact McNemar p = 0.004.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.120 [+0.050, +0.200]; against the LLM's strict first-attempt outcomes: +0.120 [+0.050, +0.200].

## evidence_sufficiency

- n = 100 paired decisions; input parity (identical state, candidates, decision time): 100/100
- trivial baseline: always `sufficient` = 94.0%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 3.0 | 3.0 |
| Accuracy (as scored) | 14.0% [8.0%, 21.0%] | 43.0% [33.0%, 53.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 14.0% | 43.0% |
| Conditional accuracy (true answer offered) | 14.0% | 43.0% |
| Macro F1 | 0.093 | 0.369 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 2 / 2 | 0 / 5 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.453 / 0.505 | 0.285 / 0.434 |
| First-attempt valid output | 100/100 (native typed) | 100/100 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 171 / 315 | 789 / 1699 |
| Mean input / output tokens | 1224 / 62 | 830 / 17 |
| Cost per decision / per 1,000 decisions (USD) | 0.000051 / 0.0514 | 0.000881 / 0.8807 |

Paired outcomes: both correct 13, only Jev 1, only LLM 30, neither 56; exact McNemar p = 0.000.
Jev minus LLM accuracy (paired bootstrap 95% CI): -0.290 [-0.390, -0.200]; against the LLM's strict first-attempt outcomes: -0.290 [-0.390, -0.200].

## incident_relationship

- n = 17 paired decisions; input parity (identical state, candidates, decision time): 17/17
- trivial baseline: always `False` = 70.6%

| Metric | Jev | LLM |
|---|---:|---:|
| Accuracy (as scored) | 70.6% [47.1%, 88.2%] | 82.4% [64.7%, 100.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 70.6% | 82.4% |
| AUC of raw P(related) | 0.692 | 0.675 |
| Brier of raw P(related) | 0.203 | 0.172 |
| TP / FP / FN / TN at 0.5 | 1/1/4/11 | 2/0/3/12 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 1 / 8 | 2 / 9 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.203 / 0.208 | 0.172 / 0.153 |
| First-attempt valid output | 17/17 (native typed) | 17/17 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 156 / 296 | 649 / 2942 |
| Mean input / output tokens | 640 / 21 | 407 / 9 |
| Cost per decision / per 1,000 decisions (USD) | 0.000027 / 0.0269 | 0.000433 / 0.4329 |

Paired outcomes: both correct 12, only Jev 0, only LLM 2, neither 3; exact McNemar p = 0.500.
Jev minus LLM accuracy (paired bootstrap 95% CI): -0.118 [-0.294, +0.000]; against the LLM's strict first-attempt outcomes: -0.118 [-0.294, +0.000].

## issue_category

- n = 100 paired decisions; input parity (identical state, candidates, decision time): 100/100
- trivial baseline: always `IC13` = 18.0%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 18.0 | 18.0 |
| Accuracy (as scored) | 73.0% [64.0%, 82.0%] | 76.0% [68.0%, 84.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 73.0% | 76.0% |
| Conditional accuracy (true answer offered) | 73.0% | 76.0% |
| Macro F1 | 0.587 | 0.645 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 6 / 42 | 4 / 29 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.189 / 0.094 | 0.183 / 0.069 |
| First-attempt valid output | 100/100 (native typed) | 100/100 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 166 / 413 | 808 / 1347 |
| Mean input / output tokens | 876 / 182 | 539 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000037 / 0.0368 | 0.000577 / 0.5772 |

Paired outcomes: both correct 67, only Jev 6, only LLM 9, neither 18; exact McNemar p = 0.607.
Jev minus LLM accuracy (paired bootstrap 95% CI): -0.030 [-0.110, +0.040]; against the LLM's strict first-attempt outcomes: -0.030 [-0.110, +0.040].

## owning_team

- n = 100 paired decisions; input parity (identical state, candidates, decision time): 100/100
- trivial baseline: always `TM08` = 16.0%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 11.9 | 11.9 |
| Accuracy (as scored) | 36.0% [27.0%, 45.0%] | 11.0% [5.0%, 17.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 36.0% | 11.0% |
| Conditional accuracy (true answer offered) | 49.0% | 22.0% |
| Primary-team accuracy / acceptable-team accuracy | 36.0% / 49.0% | 11.0% / 22.0% |
| Macro F1 | 0.262 | 0.059 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 5 / 8 | 0 / 0 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.329 / 0.245 | 0.574 / 0.690 |
| First-attempt valid output | 100/100 (native typed) | 100/100 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 174 / 288 | 801 / 1579 |
| Mean input / output tokens | 1290 / 128 | 809 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000054 / 0.0542 | 0.000858 / 0.8576 |

Paired outcomes: both correct 4, only Jev 32, only LLM 7, neither 57; exact McNemar p = 0.000.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.250 [+0.140, +0.360]; against the LLM's strict first-attempt outcomes: +0.250 [+0.140, +0.360].

## root_cause

- n = 100 paired decisions; input parity (identical state, candidates, decision time): 100/100
- trivial baseline: always `RC14` = 10.0%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 15.9 | 15.9 |
| Accuracy (as scored) | 48.0% [38.0%, 58.0%] | 24.0% [16.0%, 32.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 48.0% | 24.0% |
| Conditional accuracy (true answer offered) | 48.0% | 24.0% |
| Macro F1 | 0.445 | 0.194 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 3 / 13 | 0 / 0 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.292 / 0.240 | 0.485 / 0.541 |
| First-attempt valid output | 100/100 (native typed) | 100/100 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 173 / 468 | 816 / 1374 |
| Mean input / output tokens | 1479 / 164 | 932 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000062 / 0.0621 | 0.000986 / 0.9860 |

Paired outcomes: both correct 22, only Jev 26, only LLM 2, neither 50; exact McNemar p = 0.000.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.240 [+0.150, +0.330]; against the LLM's strict first-attempt outcomes: +0.240 [+0.150, +0.330].

