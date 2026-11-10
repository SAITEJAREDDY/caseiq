# Stage C review: audit and authoritative tables (machine-generated)

Stage C: Jev `exp_stage_c_validation_jev_20260923T184036Z_fa984004`, LLM `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`. Dev reference: Jev `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24`, LLM `exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff`.

## Audit

| Check | Passed | Detail |
|---|---|---|
| registry holds exactly one validation Jev experiment and one validation LLM experiment | True | ['exp_stage_c_validation_jev_20260923T184036Z_fa984004', 'exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a |
| Jev: split is validation and kind is validation | True | validation/validation |
| Jev: ran under stage_b_frozen_v1, verified against its manifest (not --pre-freeze) | True | {'name': 'stage_b_frozen_v1', 'config_sha256': '0f72b8e2734b37b4bd0518bcc6dd9d376c1e39e9187b4470b3a95c32cc51d7 |
| Jev: recorded config digest equals the Stage B config file and its manifest | True | 0f72b8e2734b37b4 |
| Jev: candidate-generation versions equal the frozen ones | True |  |
| Jev: root-cause context is the frozen v4_operational | True |  |
| Jev: causal key mode is the frozen canonical | True |  |
| Jev: evaluator, question-set, candidate bundle and pricing versions equal the frozen ones | True | v2.1/v2/v3/2026-09-23 |
| Jev: orchestration completed with no failed cases | True | {'runner': 'parallel_v1', 'workers': 8, 'failed_cases': []} |
| LLM: split is validation and kind is validation | True | validation/validation |
| LLM: ran under stage_b_frozen_v1, verified against its manifest (not --pre-freeze) | True | {'name': 'stage_b_frozen_v1', 'config_sha256': '0f72b8e2734b37b4bd0518bcc6dd9d376c1e39e9187b4470b3a95c32cc51d7 |
| LLM: recorded config digest equals the Stage B config file and its manifest | True | 0f72b8e2734b37b4 |
| LLM: candidate-generation versions equal the frozen ones | True |  |
| LLM: root-cause context is the frozen v4_operational | True |  |
| LLM: causal key mode is the frozen canonical | True |  |
| LLM: evaluator, question-set, candidate bundle and pricing versions equal the frozen ones | True | v2.1/v2/v3/2026-09-23 |
| LLM: orchestration completed with no failed cases | True | {'runner': 'parallel_v1', 'workers': 8, 'failed_cases': []} |
| Jev: requested model is the frozen jev-1.13.0 | True | jev-1.13.0 |
| LLM: model, temperature, max tokens and repair allowance equal the frozen ones | True |  |
| Jev: every decision resolved to the frozen model version | True | {'jev-1.13.0': 3882} |
| Jev: every record carries the frozen question and candidate-generation version of its decision | True | [('causal_change', 'causal_change_v1', 'v3'), ('evidence_sufficiency', 'evidence_sufficiency_v2', 'v1'), ('inc |
| LLM: every record carries the frozen question and candidate-generation version of its decision | True | [('causal_change', 'causal_change_v1', 'v3'), ('evidence_sufficiency', 'evidence_sufficiency_v2', 'v1'), ('inc |
| Jev and LLM experiments contain exactly the validation split (750 cases, same order) | True | 750 |
| case-id digest recorded on the run equals the digest of the validation ids | True | 6f89e2c8036213e4 |
| decision files contain no case outside the experiment's case list | True |  |
| decision counts: 750 per choice decision, incident decisions equal for both systems | True | {'issue_category': 750, 'root_cause': 750, 'causal_change': 750, 'owning_team': 750, 'evidence_sufficiency': 7 |
| pre-registered Stage C protocol digest recorded on the run matches the file today | True | 4c950c80104804ba |
| Stage C experiments, report and protocol are byte-identical to what the locked freeze pinned (immutable) | True |  |
| registry: no experiment carries dataset_split 'test' or kind 'locked_benchmark' | True | {('regression_suite', 'smoke'): 2, ('dev', 'smoke'): 2, ('explicit_case_ids', 'smoke'): 2, ('dev', 'engineerin |
| registry: every case id used by all 23 registered experiments is in the dev or validation split | True | 0 outside |
| Stage C checkpoint holds exactly the validation case ids | True | 750 |
| no locked run-state marker exists (the locked holdout has not started) | True |  |
| no access log exists to consult (none is kept by the split loader); the evidence is the registry, the marker and the guard checks | True | the split loader keeps no log; see Phase 7 boundary validator checks [8], [9], [10] |

## Dev versus validation (stored registry values)

| Metric | Dev | Validation | Delta pts [95% CI] | Val/dev ratio | Reading |
|---|---:|---:|---:|---:|---|
| Issue category accuracy | 73.0% (73/100) | 78.4% (588/750) | +5.4 [-2.9, +15.2] | 1.07 [0.96, 1.24] | plausible sampling variation |
| Root cause accuracy | 48.0% (48/100) | 37.2% (279/750) | -10.8 [-21.1, -0.6] | 0.78 [0.63, 1.00] | material degradation |
| Causal change accuracy | 92.0% (92/100) | 89.3% (670/750) | -2.7 [-7.2, +4.6] | 0.97 [0.92, 1.04] | plausible sampling variation |
| Owning team primary accuracy | 36.0% (36/100) | 37.6% (282/750) | +1.6 [-8.7, +11.0] | 1.04 [0.81, 1.45] | plausible sampling variation |
| Owning team acceptable accuracy | 49.0% (49/100) | 52.8% (396/750) | +3.8 [-6.5, +14.0] | 1.08 [0.89, 1.37] | plausible sampling variation |
| Evidence sufficiency accuracy | 14.0% (14/100) | 12.4% (93/750) | -1.6 [-10.0, +4.4] | 0.89 [0.56, 1.63] | plausible sampling variation |
| Incident relationship accuracy | 70.6% (12/17) | 82.6% (109/132) | +12.0 [-5.7, +36.3] | 1.17 [0.90, 1.79] | insufficient sample |
| Issue category candidate recall | 100.0% (100/100) | 100.0% (750/750) | +0.0 [-0.5, +3.7] | 1.00 [1.00, 1.00] | plausible sampling variation |
| Root cause candidate recall | 100.0% (100/100) | 98.7% (740/750) | -1.3 [-2.4, +2.4] | 0.99 [0.98, 0.99] | plausible sampling variation |
| Causal change candidate recall | 100.0% (100/100) | 100.0% (750/750) | +0.0 [-0.5, +3.7] | 1.00 [1.00, 1.00] | plausible sampling variation |
| Owning team primary candidate recall | 99.0% (99/100) | 99.7% (748/750) | +0.7 [-0.3, +5.2] | 1.01 [0.99, 1.03] | plausible sampling variation |
| Owning team acceptable candidate recall | 100.0% (100/100) | 99.9% (749/750) | -0.1 [-0.8, +3.6] | 1.00 [1.00, 1.00] | plausible sampling variation |

Dev causal-change runs (stored): {'causal v3 run': {'accuracy': 0.92, 'n': 100}, 'causal v3 repeat run': {'accuracy': 0.91, 'n': 100}, 'final dev comparison run': {'accuracy': 0.92, 'n': 100}}

Stored values equal the recomputed Stage C values for 11/11 metrics.

## Operations, dev versus validation (Jev / LLM)

| Stage | Decision | Jev P50/P90/P95 ms | LLM P50/P90/P95 ms | Jev $ per 1k | LLM $ per 1k | LLM first-attempt valid | Jev API errors |
|---|---|---:|---:|---:|---:|---:|---:|
| dev (sequential) | issue_category | 166/264/413 | 808/1260/1347 | 0.037 | 0.577 | 100/100 | 0 |
| dev (sequential) | root_cause | 173/309/468 | 816/1247/1374 | 0.062 | 0.986 | 100/100 | 0 |
| dev (sequential) | causal_change | 169/265/302 | 783/1568/1722 | 0.050 | 0.831 | 100/100 | 0 |
| dev (sequential) | owning_team | 174/235/288 | 801/1303/1579 | 0.054 | 0.858 | 100/100 | 0 |
| dev (sequential) | evidence_sufficiency | 171/270/315 | 789/1304/1699 | 0.051 | 0.881 | 100/100 | 0 |
| dev (sequential) | incident_relationship | 156/201/296 | 649/1358/2942 | 0.027 | 0.433 | 17/17 | 0 |
| validation (8 workers) | issue_category | 194/1005/1170 | 1037/2161/3483 | 0.037 | 0.572 | 750/750 | 0 |
| validation (8 workers) | root_cause | 189/956/1104 | 1006/2381/3910 | 0.061 | 0.962 | 750/750 | 0 |
| validation (8 workers) | causal_change | 195/1043/1200 | 1002/2372/3691 | 0.049 | 0.808 | 750/750 | 0 |
| validation (8 workers) | owning_team | 196/1021/1173 | 993/2103/3148 | 0.053 | 0.833 | 750/750 | 0 |
| validation (8 workers) | evidence_sufficiency | 201/1013/1179 | 999/2332/3680 | 0.050 | 0.863 | 750/750 | 0 |
| validation (8 workers) | incident_relationship | 202/920/1230 | 864/2014/2954 | 0.027 | 0.429 | 132/132 | 0 |

## Paired outcomes

| Split | Decision | Both correct | Only Jev | Only LLM | Both wrong | McNemar p |
|---|---|---:|---:|---:|---:|---:|
| dev | issue_category | 67 | 6 | 9 | 18 | 0.607 |
| dev | root_cause | 22 | 26 | 2 | 50 | 0.000 |
| dev | causal_change | 78 | 14 | 2 | 6 | 0.004 |
| dev | owning_team | 4 | 32 | 7 | 57 | 0.000 |
| dev | evidence_sufficiency | 13 | 1 | 30 | 56 | 0.000 |
| dev | incident_relationship | 12 | 0 | 2 | 3 | 0.500 |
| validation | issue_category | 536 | 52 | 59 | 103 | 0.569 |
| validation | root_cause | 120 | 159 | 35 | 436 | 0.000 |
| validation | causal_change | 597 | 73 | 39 | 41 | 0.002 |
| validation | owning_team | 48 | 234 | 61 | 407 | 0.000 |
| validation | evidence_sufficiency | 85 | 8 | 229 | 428 | 0.000 |
| validation | incident_relationship | 104 | 5 | 0 | 23 | 0.062 |
