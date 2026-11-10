# Jev vs LLM primitive baseline (JEV-018)

- Jev: `exp_causal_change_v3_opaque_keys_dev100_jev_20260923T172653Z_cc0c9491`  (jev-1.13.0)
- LLM: `exp_causal_change_v3_opaque_keys_dev100_llm_20260923T172653Z_9076cf7d`  (meta-llama/Llama-3.3-70B-Instruct-Turbo, temperature 0.1, one repair re-prompt allowed)
- cohort: 100 `dev` cases; candidate versions {'causal_change': 'v3'}; root-cause context v3_technical
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
| Accuracy (as scored) | 91.0% [85.0%, 96.0%] | 87.0% [80.0%, 93.0%] |
| Accuracy, strict first attempt (contract failures = wrong) | 91.0% | 87.0% |
| Conditional accuracy (true answer offered) | 91.0% | 87.0% |
| Macro F1 | 0.755 | 0.665 |
| High-confidence (>= 0.9) wrong / high-confidence predictions | 0 / 44 | 0 / 40 |
| Brier / ECE on the answer's confidence (see confidence note) | 0.120 / 0.140 | 0.112 / 0.022 |
| First-attempt valid output | 100/100 (native typed) | 100/100 |
| Repair required / succeeded / unrecoverable | n/a | 0 / 0 / 0 |
| API/request errors | 0 | 0 |
| Latency P50 / P95 (ms) | 180 / 555 | 803 / 1600 |
| Mean input / output tokens | 1199 / 34 | 783 / 16 |
| Cost per decision / per 1,000 decisions (USD) | 0.000050 / 0.0503 | 0.000831 / 0.8306 |
| No-causal-change accuracy | 94.1% | 88.2% |
| Distractor-selection rate (a distractor was offered) | 10.0% | 22.5% |
| Recency A true is newest (n = 32) | 84.4% | 84.4% |
| Recency B true older than a distractor (n = 0) | n/a | n/a |
| Recency C no causal change (n = 68) | 94.1% | 88.2% |
| Recency D multiple recent changes (n = 17) | 88.2% | 64.7% |
| Recency E true change not offered (n = 0) | n/a | n/a |

Paired outcomes: both correct 84, only Jev 7, only LLM 3, neither 6; exact McNemar p = 0.344.
Jev minus LLM accuracy (paired bootstrap 95% CI): +0.040 [-0.020, +0.100]; against the LLM's strict first-attempt outcomes: +0.040 [-0.020, +0.100].

