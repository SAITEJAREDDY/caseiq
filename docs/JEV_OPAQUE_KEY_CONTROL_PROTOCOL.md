# Opaque-key control (JEV-025): pre-registered protocol v1

Written before any control call was made. Its sha256 is recorded on the control experiments
(`config.pre_registered_protocol`) and this file must not be edited afterwards; the results are
reported in `docs/JEV_OPAQUE_KEY_CONTROL.md`.

## 1. Question and scope

Does causal-change performance depend on the canonical change or deployment ids (`CH030402` and
similar) that Stage C showed to the models as option keys?

- Why it matters: the generator numbered injected causal events after background events, so on
  validation every true change id (30402 to 31157, n=234) is larger than every other candidate id
  (93 to 30383, n=382), with zero overlap (JEV-025). A system could in principle answer from the number.
- Data: the 750 validation cases of the completed Stage C experiments, and only those. The locked
  test split is not read, counted or previewed. No dev case is run; dev results are historical context only.
- Decision: `causal_change` only, at the frozen settings (candidate_generation_v3, question
  `causal_change_v1`, context `v4_operational`, evaluator v2.1, Jev `jev-1.13.0`,
  `meta-llama/Llama-3.3-70B-Instruct-Turbo` at temperature 0.1).
- This is a methodological control. Nothing is tuned: no question, candidate rule, context,
  threshold or model setting changes, and nothing is re-fitted to these results.
- Reference: the authoritative Stage C canonical results are reused, not re-bought:
  Jev `exp_stage_c_validation_jev_20260923T184036Z_fa984004`,
  LLM `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a`. They are read, never written.

## 2. The single variable

The only intended difference is the option key shown to the model.

- Canonical arm: the stored Stage C inputs (keys `CH...`).
- Opaque arm: each real change or deployment key is replaced by `opt_` plus five characters derived
  from `sha256("opaque_key_control_v1|" + case_id + "|" + canonical_id + "|" + salt)`, written in a
  27-symbol alphabet with no vowels (so no accidental words). The salt is 0 unless two keys in one
  decision collide, in which case it is incremented deterministically.
  - The key depends only on the case and the canonical id, so it does not depend on the candidate's
    position, timestamp, event type, component, source projection, or whether it is the true cause.
  - It preserves neither the numeric order of the canonical ids nor the list order (rank correlations
    are measured and reported as integrity numbers).
  - All keys have the same shape and length, so the key format does not distinguish a deployment from a change.
  - The mapping is stored on the decision record (`candidate_meta.alias_to_id`), outside the model
    input, and the answer is mapped back to the canonical id before scoring.
- The `none` option keeps its key and text. Candidate order, count, membership, descriptions, the
  question text and the state are unchanged. The `none`-only decisions (no real candidate) contain no
  id, so their input is byte-identical in both arms.
- Deliberate difference from the JEV-025 dev control: that control used the aliases `option_1`,
  `option_2`, ... in list order. Those numbers encode the candidate's rank (the list is newest
  first), so it swapped one cue for another. The hashed keys remove the id number without adding a rank cue.
- Not tested: descriptions keep the event type, component and timestamp (legitimate observable
  evidence), so the second JEV-025 artifact (a visible deployment is the true cause in 68 of 110
  cases that offer one) is not removed by this control. Whether the request order of the options
  survives inside Jev's service is not observable.

## 3. Input-equivalence checks (before any API call, all 750 cases)

The run aborts before its first call unless every case passes:

1. The rebuilt canonical state, candidates (order included), candidate metadata and `as_of` equal the
   stored Stage C Jev and LLM records for that case (this is also what licenses reusing the stored results).
2. For both request bodies (the Jev payload and the LLM prompt), replacing each opaque key by its
   canonical id reproduces the canonical request byte for byte. So the two arms differ only in the keys.
3. No canonical change id occurs anywhere in an opaque request.
4. Opaque keys are distinct, well-formed, differ from `none`, and pass the runtime leakage guard.
5. Same key set size, same order, same `none` position, same descriptions.
6. The scored candidate recall of the control equals Stage C exactly (checked again after the run;
   a difference invalidates the control).

## 4. Populations and metrics

- ALL: all 750 decisions. P: non-trivial decisions, at least one real change offered (443 in Stage C).
  T: `none`-only decisions (307).
- Only P can show id dependence, so P is the primary population. T is a negative control: its input is
  identical, so any difference there is run-to-run noise. ALL is reported for comparability with the
  Stage C headline.
- Per system: accuracy (ALL and P); conditional accuracy (true change offered); candidate recall;
  detection rate (a true change exists); no-change false-positive rate (no true change, a real change
  chosen); distractor-selection rate; high-confidence errors (wrong at confidence >= 0.90, each system's
  own confidence, never compared across systems); semantic agreement (the same canonical choice under
  both arms, whatever its correctness); for the LLM, first-attempt validity, invalid option, repair,
  unrecoverable failure; tokens, latency, cost.
- Paired outcomes per system: correct/correct, correct/wrong, wrong/correct, wrong/wrong (canonical/opaque).
  Wrong includes an unanswered decision. Exact two-sided McNemar on the discordant pairs; paired
  percentile bootstrap (2,000 resamples, seed 20260923) for the accuracy difference; Wilson intervals
  for single rates.
- Recency groups are the evaluator's (v2.1): A true change newest; B true change older than a newer
  candidate; C no causal change; D two or more real candidates (overlaps A/B/C); E true change not
  offered. No other slice is a headline. Group B is reported case by case (candidate count, true
  candidate, the four selections, whether the answer changed).

## 5. Decision rules (fixed before the run; the same rules for both systems)

Notation, on P: b = correct under canonical and wrong under opaque; c = wrong under canonical and
correct under opaque; delta = (c - b) / |P| (opaque minus canonical).

M = 3.0 percentage points on P. This is a convention set before the run, not derived from these
results. It is about 1.8 points on ALL, the same scale as the "1 to 2 point fluctuation" the request
names as noise, and it is larger than the dev run-to-run noise (see 8).

- R1, accuracy.
  - DROP: b > c and exact McNemar p < 0.05.
  - MATERIAL DROP: DROP and delta <= -M.
  - PRESERVED: not DROP and the paired 95% CI lower bound of delta is above -M (a drop of M or more is excluded at 95%).
  - Otherwise UNRESOLVED.
- R2, prediction stability (semantic disagreement d = share of P decisions whose canonical choice differs between arms).
  - d = 0: STABLE.
  - d > 0 needs a noise floor, because Jev and the LLM are not perfectly repeatable (section 8). A canonical
    replicate of P is run for that system (section 6). d0 is its disagreement with the Stage C canonical
    answers. Excess = d - d0; exact McNemar on the paired indicators (disagrees under opaque, disagrees
    under the replicate).
  - SENSITIVE: excess >= M and p < 0.05 in the direction of more disagreement under opaque. STABLE otherwise.
- R3, concentration. If group B shows a net loss of at least 2 decisions (b_B - c_B >= 2), the verdict
  cannot be "no material ID dependence detected", whatever R1 and R2 say. Group B has about six
  decisions, so it cannot establish dependence by itself; the cap is a guard against a small confounded
  group hiding a loss.

Verdict for a system:

- MATERIAL ID DEPENDENCE DETECTED: MATERIAL DROP, or (SENSITIVE and b > c).
- NO MATERIAL ID DEPENDENCE DETECTED: PRESERVED and STABLE and R3 does not apply.
- POSSIBLE ID SENSITIVITY / INCONCLUSIVE: everything else (for example a statistically supported but
  sub-M drop, an unresolved interval, predictions that change without a net accuracy loss, or a
  concentrated group-B loss).

A system whose accuracy rises under opaque keys is not relying on the canonical ids; the verdict rules
still apply mechanically, and the report says in words when the direction is an improvement.

Jev is the gate (the question is whether the locked causal-change result can be trusted). The LLM
verdict is reported independently and is not a gate.

## 6. Canonical replicate (conditional, pre-registered)

Only if a system's d > 0 on P: rerun that system on the P decisions with the canonical keys, as a
separate control run (`stage_c_causal_canonical_replicate`), same settings, same concurrency. It is
never merged into the Stage C results and is used only for the R2 noise floor.

## 7. Consequences

- Jev verdict "no material ID dependence detected": JEV-025 is marked sufficiently controlled for
  Phase 7; `locked_benchmark_frozen_v1.json` and its manifest are not modified (their digests are
  re-verified); the locked benchmark is still not run and waits for explicit approval.
- Jev verdict "material ID dependence detected": the locked configuration is marked superseded before
  use and preserved historically; a methodological issue is opened; a configuration with opaque keys is
  proposed with the validation re-evaluation it needs; no new freeze is created automatically; the
  locked split stays closed.
- Jev verdict "possible ID sensitivity / inconclusive": treated as not passed. The locked configuration
  is not declared superseded (dependence is not shown) and the locked benchmark is not ready for
  approval until the user decides how to proceed. The report gives the options.

## 8. Context read before this was written (dev only, no validation result seen)

Stored dev-100 causal-change runs, 61 non-trivial decisions each:

| Comparison (same 100 cases) | Jev disagree / 61 | LLM disagree / 61 |
|---|---:|---:|
| identical canonical input, run twice (final vs repeat) | 1 | 3 |
| canonical vs position-coded `option_i` aliases (JEV-025 control) | 1 to 2 | 12 to 13 |

Dev accuracy: Jev 92, 92, 91 with ids and 91 with aliases; LLM 80 and 83 with ids and 87 with aliases.
So Jev's run-to-run noise is small but not zero, the LLM's is larger, and the LLM's dev disagreement
under aliases is well above its noise. Those aliases carried rank information, which is one reason the
validation control uses hashed keys. The replicate rule in section 6 exists because of these numbers.

## 9. Limits stated in advance

- One run per arm on one cohort: sampling variation is described by the intervals, not removed.
- Concurrency is 8 workers, as in Stage C, so latencies are comparable to Stage C but not to sequential runs.
- The control shows whether these two systems, at these settings, use the key identity. It does not
  show that no other artifact exists (section 2).
- The validation set has been seen by the project; this control adds no tuning on it, but it is not a
  fresh holdout.
- The Turbo pricing used for cost figures is an assumption carried from Stage B (`pricing_version 2026-09-23`).
