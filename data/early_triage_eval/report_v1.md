# Early triage: dev comparison (35 of 36 cases)

Cases: the first 36 of the 72-case frozen list (every case of the dev verify100 cohort that has a stored LLM + Graph baseline run under the baseline tag, sorted by case id; no outcome was consulted; fixed before any early-triage run). Missing: ['CS00182']. One run per case per arm; dev only.

## Issue-category accuracy (exact id)

| Arm | Correct | 95% CI (Wilson) | Wrong | No category |
|---|---|---|---|---|
| LLM + Graph baseline (stored) | 14/35 (40%) | 26%–56% | 7 | 14 |
| Early triage + agent, first answer | 21/35 (60%) | 44%–74% | 8 | 6 |
| LLM + Graph + Jev, final (after late verification) | 19/35 (54%) | 38%–70% | 8 | 8 |

Paired baseline vs early-triage first answer: both correct 10, only early 11, only baseline 4, neither 10; exact McNemar p = 0.1185.

## Early Jev alone

Statuses: {'hint': 35}. A hint was given on 35/35 cases.
Accuracy when a hint was given: 27/35 (77%, CI 61%–88%).
Top-1 if it were always forced: 27/35 (77%).
By probability: 0.40-0.70: 3/5; 0.70-1.00: 24/30. Latency mean 0.1341s, p95 0.169s.

## What the agent did with the hint

Hint correct (n=27): confirmed 21, changed away 0, dropped 6; the baseline was correct on 11 of these.
Hint wrong (n=8): adopted the wrong hint 8, reached the true category 0, another wrong category 0, dropped 0; the baseline was correct on 3 and chose that same wrong category on 0.

## Evidence retrieval (critical evidence, Phase 6 definition)

| Arm | Cases with critical evidence | Mean critical recall | All critical retrieved | Mean evidence items seen |
|---|---|---|---|---|
| Baseline | 25 | 59% | 11 | 7.2 |
| Early triage, first answer | 25 | 81% | 18 | 9.6 |
| Full, final | 25 | 85% | 20 | 11.0857 |

## Cost and latency (means)

Model tool calls: baseline 8.1429, early-triage first answer 8.2, full 11.4.
Agent tokens: baseline 22007.0857, full 39310.0571 (cases with no extra round, n=7: 21170.8571 vs 24236.4286).
Model seconds: baseline 153.9719, full 258.4186; added Jev seconds: early triage 0.1341, late verifier 1.6948. Est. cost per case: baseline $0.0194, full $0.0361. Runs with an extra investigation round: 28.

## Final disposition

Baseline agent status: {'DIAGNOSIS_PROPOSED': 20, 'INSUFFICIENT_EVIDENCE': 15}; answered without a review flag: {'n': 20, 'correct': 13, 'wrong': 7, 'abstain': 0}.
LLM + Graph + Jev: first policy decision {'ACCEPT': 1, 'CONTINUE_INVESTIGATION': 28, 'PRIORITY_REVIEW': 5, 'HUMAN_REVIEW': 1}; final {'ACCEPT': 2, 'HUMAN_REVIEW': 21, 'PRIORITY_REVIEW': 12}; agent status {'DIAGNOSIS_PROPOSED': 23, 'CONTRACT_FAILURE': 3, 'INSUFFICIENT_EVIDENCE': 9}; contract failures 3.
Accepted: {'n': 2, 'correct': 1, 'wrong': 1, 'abstain': 0}. Sent to review: 33, of which the category was correct in 18.

## Limitations

- One run per case per arm at temperature 0.1: run-to-run model noise is not separated from any effect. The baseline runs were made earlier with the same agent code and no triage.
- N = 35 dev cases; the intervals above are wide. Nothing here supports a claim of improvement or of no effect.
- Early Jev sees ticket text only (no signals) and has an abstain option, so its accuracy is not comparable to the Phase 7 issue-category figure.
- The hint wording, the 0.30 minimum probability, the uncertainty bands and the advisory tool map are hand-set and unvalidated; nothing was tuned on these results.
- Category is one of five diagnostic fields and the only one Jev is asked about early; root cause, component and team were not evaluated here.