# Jev vs LLM primitive baseline (JEV-018)

- Jev: `exp_stage_c_validation_jev_20260923T184036Z_fa984004`  (jev-1.13.0)
- LLM: `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`  (meta-llama/Llama-3.3-70B-Instruct-Turbo, temperature 0.1, one repair re-prompt allowed)
- cohort: 750 `validation` cases; candidate versions {'issue_category': 'v1', 'root_cause': 'v2', 'causal_change': 'v3', 'owning_team': 'v2', 'evidence_sufficiency': 'v1', 'incident_relationship': 'v1'}; root-cause context v4_operational
- evaluator v2.1; pricing 2026-09-23 (token counts are provider-returned; prices are versioned assumptions)
- Single run per system (LLM temperature 0.1, no seed): no run-to-run variance is measured for the LLM.
- **Confidence is not comparable.** Jev's is a native probability from the typed primitive; the LLM's is a number it was asked to write. Shown side by side for transparency, never ranked against each other.

## causal_change

- n = 750 paired decisions; input parity (identical state, candidates, decision time): 750/750
- trivial baseline: always `none` = 68.8%; newest-change-else-none = 71.3%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 1.8 | 1.8 |
| Accuracy (as scored) | 89.3% [87.2%, 91.6%] | 84.8% [82.3%, 87.2%] |
| Accuracy, strict first attempt (contract failures = wrong) | 89.3% | 84.8% |
| Conditional accuracy (true answer offered) | 89.3% | 84.8% |
| Macro F1 | 0.687 | 0.649 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 3 / 400 | 5 / 294 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.102 / 0.106 | 0.120 / 0.035 |
| First-attempt valid output | 750/750 (native typed) | 750/750 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 195 / 1200 | 1002 / 3691 |
| Mean input / output tokens | 1169 / 38 | 761 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000049 / 0.0491 | 0.000808 / 0.8083 |
| No-causal-change accuracy | 95.2% | 81.8% |
| Distractor-selection rate (a distractor was offered) | 8.8% | 31.4% |
| Recency A true is newest (n = 228) | 75.9% | 91.2% |
| Recency B true older than a distractor (n = 6) | 100.0% | 100.0% |
| Recency C no causal change (n = 516) | 95.2% | 81.8% |
| Recency D multiple recent changes (n = 143) | 85.3% | 78.3% |
| Recency E true change not offered (n = 0) | n/a | n/a |

Paired outcomes: both correct 597, only Jev 73, only LLM 39, neither 41; exact McNemar p = 0.002.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.045 [+0.019, +0.072]; against the LLM's strict first-attempt outcomes: +0.045 [+0.019, +0.072].

## evidence_sufficiency

- n = 750 paired decisions; input parity (identical state, candidates, decision time): 750/750
- trivial baseline: always `sufficient` = 92.9%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 3.0 | 3.0 |
| Accuracy (as scored) | 12.4% [10.1%, 14.8%] | 41.9% [38.5%, 45.2%] |
| Accuracy, strict first attempt (contract failures = wrong) | 12.4% | 41.9% |
| Conditional accuracy (true answer offered) | 12.4% | 41.9% |
| Macro F1 | 0.135 | 0.419 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 34 / 37 | 1 / 19 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.466 / 0.528 | 0.295 / 0.440 |
| First-attempt valid output | 750/750 (native typed) | 750/750 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 201 / 1179 | 999 / 3680 |
| Mean input / output tokens | 1200 / 62 | 813 / 17 |
| Cost per decision / per 1,000 decisions (USD) | 0.000050 / 0.0504 | 0.000863 / 0.8631 |

Paired outcomes: both correct 85, only Jev 8, only LLM 229, neither 428; exact McNemar p = 0.000.
Jev minus LLM accuracy (paired bootstrap 95% CI): -0.295 [-0.329, -0.259]; against the LLM's strict first-attempt outcomes: -0.295 [-0.329, -0.259].

## incident_relationship

- n = 132 paired decisions; input parity (identical state, candidates, decision time): 132/132
- trivial baseline: always `False` = 78.0%

| Metric | Jev | LLM |
|---|---:|---:|
| Accuracy (as scored) | 82.6% [76.5%, 88.6%] | 78.8% [72.0%, 85.6%] |
| Accuracy, strict first attempt (contract failures = wrong) | 82.6% | 78.8% |
| AUC of raw P(related) | 0.697 | 0.676 |
| Brier of raw P(related) | 0.146 | 0.175 |
| TP / FP / FN / TN at 0.5 | 8/2/21/101 | 4/3/25/100 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 12 / 79 | 11 / 84 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.146 / 0.083 | 0.175 / 0.139 |
| First-attempt valid output | 132/132 (native typed) | 132/132 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 202 / 1230 | 864 / 2954 |
| Mean input / output tokens | 636 / 21 | 404 / 9 |
| Cost per decision / per 1,000 decisions (USD) | 0.000027 / 0.0267 | 0.000429 / 0.4292 |

Paired outcomes: both correct 104, only Jev 5, only LLM 0, neither 23; exact McNemar p = 0.062.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.038 [+0.008, +0.068]; against the LLM's strict first-attempt outcomes: +0.038 [+0.008, +0.068].

## issue_category

- n = 750 paired decisions; input parity (identical state, candidates, decision time): 750/750
- trivial baseline: always `IC13` = 17.2%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 100.0% | 100.0% |
| Avg candidates | 18.0 | 18.0 |
| Accuracy (as scored) | 78.4% [75.3%, 81.3%] | 79.3% [76.3%, 82.4%] |
| Accuracy, strict first attempt (contract failures = wrong) | 78.4% | 79.3% |
| Conditional accuracy (true answer offered) | 78.4% | 79.3% |
| Macro F1 | 0.706 | 0.748 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 7 / 315 | 20 / 258 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.128 / 0.030 | 0.159 / 0.057 |
| First-attempt valid output | 750/750 (native typed) | 750/750 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 194 / 1170 | 1037 / 3483 |
| Mean input / output tokens | 870 / 182 | 534 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000037 / 0.0366 | 0.000572 / 0.5723 |

Paired outcomes: both correct 536, only Jev 52, only LLM 59, neither 103; exact McNemar p = 0.569.
Jev minus LLM accuracy (paired bootstrap 95% CI): -0.009 [-0.037, +0.019]; against the LLM's strict first-attempt outcomes: -0.009 [-0.037, +0.019].

## owning_team

- n = 750 paired decisions; input parity (identical state, candidates, decision time): 750/750
- trivial baseline: always `TM01` = 15.6%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 99.9% | 99.9% |
| Avg candidates | 11.8 | 11.8 |
| Accuracy (as scored) | 37.6% [34.0%, 41.2%] | 14.5% [12.0%, 17.1%] |
| Accuracy, strict first attempt (contract failures = wrong) | 37.6% | 14.5% |
| Conditional accuracy (true answer offered) | 52.9% | 27.2% |
| Primary-team accuracy / acceptable-team accuracy | 37.6% / 52.8% | 14.5% / 27.2% |
| Macro F1 | 0.265 | 0.116 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 40 / 96 | 2 / 3 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.289 / 0.239 | 0.552 / 0.655 |
| First-attempt valid output | 750/750 (native typed) | 750/750 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 196 / 1173 | 993 / 3148 |
| Mean input / output tokens | 1254 / 127 | 785 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000053 / 0.0527 | 0.000833 / 0.8333 |

Paired outcomes: both correct 48, only Jev 234, only LLM 61, neither 407; exact McNemar p = 0.000.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.231 [+0.189, +0.272]; against the LLM's strict first-attempt outcomes: +0.231 [+0.189, +0.272].

## root_cause

- n = 750 paired decisions; input parity (identical state, candidates, decision time): 750/750
- trivial baseline: always `RC17` = 10.4%

| Metric | Jev | LLM |
|---|---:|---:|
| Candidate recall (same set for both) | 98.7% | 98.7% |
| Avg candidates | 15.9 | 15.9 |
| Accuracy (as scored) | 37.2% [33.7%, 40.8%] | 20.7% [18.0%, 23.5%] |
| Accuracy, strict first attempt (contract failures = wrong) | 37.2% | 20.7% |
| Conditional accuracy (true answer offered) | 37.7% | 20.9% |
| Macro F1 | 0.406 | 0.245 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 22 / 84 | 8 / 8 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.272 / 0.246 | 0.500 / 0.564 |
| First-attempt valid output | 750/750 (native typed) | 750/750 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 189 / 1104 | 1006 / 3910 |
| Mean input / output tokens | 1444 / 164 | 909 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000061 / 0.0607 | 0.000962 / 0.9621 |

Paired outcomes: both correct 120, only Jev 159, only LLM 35, neither 436; exact McNemar p = 0.000.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.165 [+0.131, +0.201]; against the LLM's strict first-attempt outcomes: +0.165 [+0.131, +0.201].

