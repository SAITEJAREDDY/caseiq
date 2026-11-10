# Opaque-key control: measured results (generated)

Protocol `docs/JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md` (sha256 `214e46688e4a6042f3fe6091fc58eea23b35beea218619288b6d94b1d2dfc4ac`), M = 3 pp, alpha = 0.05.

| Role | Experiment |
|---|---|
| reference_jev | `exp_stage_c_validation_jev_20260923T184036Z_fa984004` |
| reference_llm | `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a` |
| control_jev | `exp_stage_c_causal_opaque_control_jev_20260923T233920Z_e3b82da8` |
| control_llm | `exp_stage_c_causal_opaque_control_llm_20260923T233921Z_cbd00df9` |
| replicate_jev | `exp_stage_c_causal_canonical_replicate_jev_20260923T234310Z_1c65a600` |
| replicate_llm | `exp_stage_c_causal_canonical_replicate_llm_20260923T234310Z_6c94f589` |

## A. Control integrity

| Check | Result |
|---|---|
| Jev opaque: kind validation_control on the validation split, 750 cases in the Stage C order | pass |
| Jev opaque: option keys are the pre-registered hashed opaque scheme | pass |
| Jev opaque: pre-registered protocol digest recorded on the run equals the file today | pass |
| Jev opaque: input checks passed for all cases before any call (reference equality, only-the-keys-differ, no canonical id in an opaque request) | pass |
| Jev opaque: locked config and manifest digests at run time equal today's (and the run state was empty) | pass |
| LLM opaque: kind validation_control on the validation split, 750 cases in the Stage C order | pass |
| LLM opaque: option keys are the pre-registered hashed opaque scheme | pass |
| LLM opaque: pre-registered protocol digest recorded on the run equals the file today | pass |
| LLM opaque: input checks passed for all cases before any call (reference equality, only-the-keys-differ, no canonical id in an opaque request) | pass |
| LLM opaque: locked config and manifest digests at run time equal today's (and the run state was empty) | pass |
| Jev opaque: exactly one causal-change decision per case, all status ok | pass |
| Jev opaque: candidates, candidate metadata and candidate recall identical to Stage C for every case (else the control is invalid) | pass |
| Jev opaque: every non-trivial decision carries the alias map and every answer maps back into that decision's canonical candidates | pass |
| LLM opaque: exactly one causal-change decision per case, all status ok | pass |
| LLM opaque: candidates, candidate metadata and candidate recall identical to Stage C for every case (else the control is invalid) | pass |
| LLM opaque: every non-trivial decision carries the alias map and every answer maps back into that decision's canonical candidates | pass |
| Jev: every control decision resolved to the model version Stage C used | pass |
| LLM: same model, temperature as Stage C | pass |
| Jev replicate: kind validation_control, validation split, exactly the non-trivial (P) decisions, canonical keys, protocol digest matches | pass |
| Jev replicate: one decision per case, all status ok, inputs identical to Stage C (candidates, order, candidate metadata) | pass |
| LLM replicate: kind validation_control, validation split, exactly the non-trivial (P) decisions, canonical keys, protocol digest matches | pass |
| LLM replicate: one decision per case, all status ok, inputs identical to Stage C (candidates, order, candidate metadata) | pass |
| Stage C experiments and decisions are byte-identical to the digests the locked freeze pinned | pass |
| locked benchmark verification is clean (config, manifest, 44 pinned sources, protocol, split files unchanged) | pass |
| no locked run-state marker exists | pass |
| registry: no experiment carries dataset_split 'test' or kind 'locked_benchmark' | pass |
| every control case id is in the validation split | pass |

Stage C causal-change accuracy recomputed here equals the stored registry value: True (Jev 0.8933, LLM 0.8480).

## B. Jev

Decisions: 750 (P non-trivial 443, T none-only 307).

### Primary population P (a real change was offered)

| Metric | Canonical ids | Opaque keys | Delta (opaque - canonical) |
|---|---:|---:|---:|
| Accuracy | 81.9% | 81.5% | -0.5 pp [-2.3, 1.1] |
| Conditional accuracy (true change offered) | 81.9% | 81.5% | -0.5 |
| Candidate recall | 100.0% | 100.0% | identical |
| Detection rate (a true change exists) | 76.5% (n=234) | 72.6% | -3.8 |
| No-change false-positive rate | 12.0% (n=209) | 8.6% | -3.3 |
| Distractor-selection rate | 0.5% | 0.5% | +0.0 |
| High-confidence errors (wrong at conf >= 0.90) | 3 | 5 | +2 |
| Semantic agreement (same choice in both arms) |  | 96.4% [94.2, 97.8] | 16 of 443 differ |

Paired outcomes (canonical / opaque): correct/correct 354, correct/wrong 9, wrong/correct 7, wrong/wrong 73 (of which a different wrong choice: 0). Exact McNemar p = 0.804.

### All decisions (comparable to the Stage C headline)

| Metric | Canonical ids | Opaque keys | Delta (opaque - canonical) |
|---|---:|---:|---:|
| Accuracy | 89.3% | 89.1% | -0.3 pp [-1.3, 0.8] |
| Conditional accuracy (true change offered) | 89.3% | 89.1% | -0.3 |
| Candidate recall | 100.0% | 100.0% | identical |
| Detection rate (a true change exists) | 76.5% (n=234) | 72.6% | -3.8 |
| No-change false-positive rate | 4.8% (n=516) | 3.5% | -1.4 |
| Distractor-selection rate | 0.3% | 0.3% | +0.0 |
| High-confidence errors (wrong at conf >= 0.90) | 3 | 5 | +2 |
| Semantic agreement (same choice in both arms) |  | 97.9% [96.6, 98.7] | 16 of 750 differ |

Paired outcomes (canonical / opaque): correct/correct 661, correct/wrong 9, wrong/correct 7, wrong/wrong 73 (of which a different wrong choice: 0). Exact McNemar p = 0.804.

Negative control T (none-only decisions, byte-identical input): the same choice in 307 of 307; correct/wrong 0, wrong/correct 0.

### Pre-registered rules

- R1 accuracy on P: **PRESERVED** (b=9, c=7, McNemar p=0.804, delta -0.5 pp, 95% CI lower bound -2.3 pp; M = 3 pp).
- R2 prediction stability on P: **SENSITIVE** (disagreements 16 of 443 = 3.6%; replicate: run; replicate disagreement 2 of 443 = 0.5%, excess +3.2 pp, only-under-opaque 16 vs only-under-replicate 2, McNemar p=0.001).
- R3 concentration: group B n=6, net loss 1, cap does not apply.
- **Verdict: MATERIAL ID DEPENDENCE DETECTED.**

Exploratory (no decision role): share of P decisions answered `none` 53.5% canonical, 57.1% opaque, 53.0% canonical replicate. What the changed answers changed to (canonical -> opaque): {'real change -> none': 16}; canonical -> replicate: {'none -> real change': 2}.

Canonical replicate on P (443 decisions): accuracy 81.9% against 81.9% in Stage C and 81.5% under opaque keys; the replicate differs from Stage C on 2 decisions (correct/wrong 1, wrong/correct 1). Opaque against the replicate: 18 different choices.

## C. LLM baseline

Decisions: 750 (P non-trivial 443, T none-only 307).

### Primary population P (a real change was offered)

| Metric | Canonical ids | Opaque keys | Delta (opaque - canonical) |
|---|---:|---:|---:|
| Accuracy | 74.3% | 80.1% | +5.9 pp [2.9, 8.6] |
| Conditional accuracy (true change offered) | 74.3% | 80.1% | +5.9 |
| Candidate recall | 100.0% | 100.0% | identical |
| Detection rate (a true change exists) | 91.5% (n=234) | 88.9% | -2.6 |
| No-change false-positive rate | 45.0% (n=209) | 29.7% | -15.3 |
| Distractor-selection rate | 0.5% | 0.9% | +0.5 |
| High-confidence errors (wrong at conf >= 0.90) | 5 | 6 | +1 |
| Semantic agreement (same choice in both arms) |  | 90.1% [86.9, 92.5] | 44 of 443 differ |

Paired outcomes (canonical / opaque): correct/correct 321, correct/wrong 8, wrong/correct 34, wrong/wrong 80 (of which a different wrong choice: 2). Exact McNemar p = 0.000.

### All decisions (comparable to the Stage C headline)

| Metric | Canonical ids | Opaque keys | Delta (opaque - canonical) |
|---|---:|---:|---:|
| Accuracy | 84.8% | 88.3% | +3.5 pp [1.9, 5.2] |
| Conditional accuracy (true change offered) | 84.8% | 88.3% | +3.5 |
| Candidate recall | 100.0% | 100.0% | identical |
| Detection rate (a true change exists) | 91.5% (n=234) | 88.9% | -2.6 |
| No-change false-positive rate | 18.2% (n=516) | 12.0% | -6.2 |
| Distractor-selection rate | 0.3% | 0.5% | +0.3 |
| High-confidence errors (wrong at conf >= 0.90) | 5 | 6 | +1 |
| Semantic agreement (same choice in both arms) |  | 94.1% [92.2, 95.6] | 44 of 750 differ |

Paired outcomes (canonical / opaque): correct/correct 628, correct/wrong 8, wrong/correct 34, wrong/wrong 80 (of which a different wrong choice: 2). Exact McNemar p = 0.000.

Negative control T (none-only decisions, byte-identical input): the same choice in 307 of 307; correct/wrong 0, wrong/correct 0.

Contract (all decisions): first-attempt valid 750 of 750 canonical vs 750 of 750 opaque; repair required 0 vs 0; unrecoverable 0 vs 0; first-attempt failures canonical {} vs opaque {}; strict first-attempt correct 636 vs 662.

### Pre-registered rules

- R1 accuracy on P: **PRESERVED** (b=8, c=34, McNemar p=0.000, delta +5.9 pp, 95% CI lower bound +2.9 pp; M = 3 pp).
- R2 prediction stability on P: **SENSITIVE** (disagreements 44 of 443 = 9.9%; replicate: run; replicate disagreement 9 of 443 = 2.0%, excess +7.9 pp, only-under-opaque 40 vs only-under-replicate 5, McNemar p=0.000).
- R3 concentration: group B n=6, net loss 0, cap does not apply.
- **Verdict: POSSIBLE ID SENSITIVITY / INCONCLUSIVE.**

Exploratory (no decision role): share of P decisions answered `none` 30.0% canonical, 38.1% opaque, 30.0% canonical replicate. What the changed answers changed to (canonical -> opaque): {'real change -> real change (different real change)': 4, 'real change -> none': 38, 'none -> real change': 2}; canonical -> replicate: {'real change -> none': 4, 'none -> real change': 4, 'real change -> real change (different real change)': 1}.

Canonical replicate on P (443 decisions): accuracy 74.5% against 74.3% in Stage C and 80.1% under opaque keys; the replicate differs from Stage C on 9 decisions (correct/wrong 4, wrong/correct 5). Opaque against the replicate: 45 different choices.

## D. Recency groups (canonical accuracy / opaque accuracy; b = correct-to-wrong, c = wrong-to-correct flips; differ = different choice)

| Group | n | Jev canonical | Jev opaque | Jev b/c | Jev differ | LLM canonical | LLM opaque | LLM b/c | LLM differ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A true change is the newest | 228 | 75.9% | 72.4% | 8/0 | 8 | 91.2% | 88.6% | 8/2 | 10 |
| B true change older than a newer candidate | 6 | 100.0% | 83.3% | 1/0 | 1 | 100.0% | 100.0% | 0/0 | 0 |
| C no causal change | 516 | 95.2% | 96.5% | 0/7 | 7 | 81.8% | 88.0% | 0/32 | 34 |
| D two or more real candidates (overlaps) | 143 | 85.3% | 82.5% | 4/0 | 4 | 78.3% | 78.3% | 2/2 | 6 |
| E true change not offered | 0 | n/a | n/a | 0/0 | 0 | n/a | n/a | 0/0 | 0 |

### Group B audit (small sample: this cannot establish or exclude dependence by itself)

| Case | Candidates (incl. none) | True | True has highest id | Jev canonical | Jev opaque | LLM canonical | LLM opaque | Jev changed | LLM changed |
|---|---:|---|---|---|---|---|---|---|---|
| CS00405 | 4 | CH030527 | yes | CH030527 | CH030527 | CH030527 | CH030527 | no | no |
| CS00606 | 4 | CH030585 | yes | CH030585 | CH030585 | CH030585 | CH030585 | no | no |
| CS01028 | 3 | CH030713 | yes | CH030713 | CH030713 | CH030713 | CH030713 | no | no |
| CS01393 | 3 | CH030822 | yes | CH030822 | CH030822 | CH030822 | CH030822 | no | no |
| CS02173 | 3 | CH031066 | yes | CH031066 | none | CH031066 | CH031066 | yes | no |
| CS02460 | 4 | CH031145 | yes | CH031145 | CH031145 | CH031145 | CH031145 | no | no |

## E. Pre-registered verdicts (mechanical)

- Jev (the gate): **MATERIAL ID DEPENDENCE DETECTED**
- LLM (informative, not a gate): **POSSIBLE ID SENSITIVITY / INCONCLUSIVE**

## Exploratory (labelled, no decision role)

- Jev versus the LLM, paired by decision, under each key scheme (Jev minus LLM accuracy with a paired 95% interval; exact McNemar on decisions only one of them got right):

| Keys | Population | n | Jev | LLM | Jev - LLM | only Jev right / only LLM right | McNemar p |
|---|---|---:|---:|---:|---:|---:|---:|
| canonical | ALL | 750 | 89.3% | 84.8% | +4.5 pp [1.9, 7.2] | 73 / 39 | 0.002 |
| canonical | P | 443 | 81.9% | 74.3% | +7.7 pp [3.2, 12.2] | 73 / 39 | 0.002 |
| opaque | ALL | 750 | 89.1% | 88.3% | +0.8 pp [-1.7, 3.3] | 50 / 44 | 0.606 |
| opaque | P | 443 | 81.5% | 80.1% | +1.4 pp [-3.2, 5.4] | 50 / 44 | 0.606 |

- Jev: absolute change in the probability given to the true change, over decisions where it was offered: {"n": 234, "mean_abs_shift": 0.04034188034188034, "median_abs_shift": 0.030000000000000027, "mean_signed_shift_opaque_minus_canonical": -0.03504273504273504, "share_over_0.10": 0.038461538461538464, "max_abs_shift": 0.15000000000000002}.
- Context: when the true change was offered next to another real candidate (97 decisions), its id number was the highest in 97.

## Cost and latency (8 workers, as in Stage C)

| System | Arm | Decisions | Cost (USD) | Mean input tokens | P50 latency (ms) | P95 latency (ms) |
|---|---|---:|---:|---:|---:|---:|
| Jev | canonical (all decisions) | 750 | 0.0368 | 1169 | 195 | 1200 |
| Jev | opaque (all decisions) | 750 | 0.0368 | 1167 | 227 | 403 |
| LLM | canonical (all decisions) | 750 | 0.6063 | 761 | 1002 | 3691 |
| LLM | opaque (all decisions) | 750 | 0.6080 | 763 | 1026 | 3521 |

Control cost (this run only): Jev $0.0368, LLM $0.6080; Turbo pricing is a versioned assumption.
