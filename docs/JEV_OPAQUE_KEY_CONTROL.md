# Opaque-key control for causal change (JEV-025): results and decision

Run 2026-09-23 on the Stage C validation cohort only. The locked test split was not opened, counted or previewed.
Pre-registered protocol: [JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md](JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md)
(sha256 `214e46688e4a6042f3fe6091fc58eea23b35beea218619288b6d94b1d2dfc4ac`, recorded on every run).
Generated tables: `data/eval/jev/analysis/opaque_control/opaque_control.md` and `.json`.

**Outcome.** By the pre-registered rule, Jev's verdict is **material ID dependence detected**, so
`locked_benchmark_frozen_v1` is recorded as superseded before use and the locked benchmark is **not ready to run**.
The finding is narrower than the label suggests: Jev's accuracy did not fall, but its answers moved in one
direction when the ids were removed. Section 6 says what the control does and does not show.

## 1. Why the control was run

Stage C found that the synthetic generator numbered injected causal events after background events: every true
change id (30402 to 31157, n=234) is larger than every other candidate id (93 to 30383, n=382), with no overlap
(JEV-025). A system could answer from the number. The dev control (100 cases) saw no accuracy effect, but it was
small and it used position-coded aliases (`option_1`, `option_2`, ... in newest-first order), which encode recency
rank. Causal change is the primary locked-benchmark candidate, so the control was repeated on validation before the
one-shot holdout was spent.

## 2. Method

- One variable: the option key. Cases, state, candidates, order, descriptions, question text, the `none` option, model
  versions and settings are the Stage C inputs. The canonical arm is the stored Stage C result (read, not re-bought).
- Opaque keys: `opt_` plus five characters from a 27-symbol alphabet, derived from
  `sha256(seed | case id | canonical id | salt)`. A key does not depend on position, time, type, component or truth.
  Measured over 205 within-decision pairs: Kendall tau between key order and id number +0.005, between key order and
  list position +0.054 (no order carried). The mapping is stored on each record outside the model input.
- Checks before any call, all 750 cases: the rebuilt canonical inputs equal the stored Stage C records for Jev and the
  LLM (state, candidates and order, metadata, `as_of`); replacing each opaque key by its canonical id reproduces the
  canonical request byte for byte, for both the Jev body and the LLM prompt; no canonical id appears in an opaque
  request; keys are distinct and well formed. 616 keys were issued (443 non-trivial decisions). After the run the
  candidate recall was identical to Stage C for every case.
- A conditional canonical replicate (protocol s.6) was run because both systems showed disagreement: the 443
  non-trivial decisions again with canonical keys, as separate experiments, for the run-to-run noise floor.

| Role | Experiment |
|---|---|
| Stage C canonical (reference) | `exp_stage_c_validation_jev_20260923T184036Z_fa984004`, `exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a` |
| Opaque control | `exp_stage_c_causal_opaque_control_jev_20260923T233920Z_e3b82da8`, `exp_stage_c_causal_opaque_control_llm_20260923T233921Z_cbd00df9` |
| Canonical replicate (443 decisions) | `exp_stage_c_causal_canonical_replicate_jev_20260923T234310Z_1c65a600`, `exp_stage_c_causal_canonical_replicate_llm_20260923T234310Z_6c94f589` |

750 decisions per system, 0 failures, the same model versions as Stage C (`jev-1.13.0`, Llama-3.3-70B-Instruct-Turbo at
temperature 0.1). 27 integrity checks pass (the generated report lists them).

## 3. Jev

P = the 443 non-trivial decisions (a real change was offered), the only decisions whose input differs between arms.
The 307 `none`-only decisions are byte-identical in both arms and served as a negative control: the same choice in 307
of 307.

| Metric (P, n=443) | Canonical ids | Opaque keys | Delta |
|---|---:|---:|---:|
| Accuracy | 81.9% | 81.5% | -0.5 pp [-2.3, +1.1] |
| Candidate recall | 100.0% | 100.0% | identical |
| Detection rate (a true change exists, n=234) | 76.5% | 72.6% | -3.8 pp |
| No-change false-positive rate (n=209) | 12.0% | 8.6% | -3.3 pp |
| High-confidence errors (wrong at 0.90 or more) | 3 | 5 | +2 |
| Semantic agreement (same choice in both arms) | | 96.4% [94.2, 97.8] | 16 of 443 differ |
| Share of decisions answered `none` | 53.5% | 57.1% | +3.6 pp (canonical replicate 53.0%) |

All 750 decisions: accuracy 89.3% to 89.1% (-0.3 pp [-1.3, +0.8]); the semantic agreement is 97.9%.

- Paired outcomes on P (canonical / opaque): correct/correct 354, correct/wrong 9, wrong/correct 7, wrong/wrong 73;
  exact McNemar p = 0.80.
- **Every one of the 16 changed answers moved from a real change to `none`.** The canonical replicate changed 2 of 443
  (0.5%), both in the opposite direction (`none` to a real change). Excess disagreement +3.2 pp; disagrees only under
  opaque 16, only under the replicate 2; exact McNemar p = 0.0013.
- What changed: 9 true-change detections were lost and 7 false positives were avoided, so accuracy nets to about zero.
  Jev's probability on the true change fell by 0.035 on average when it was offered (median absolute shift 0.03;
  3.8% of decisions moved by more than 0.10; maximum 0.15).
- Pre-registered rules: R1 (accuracy) **preserved**; R2 (prediction stability) **sensitive**; R3 (group B
  concentration) does not apply (net loss 1). Verdict: **material ID dependence detected** (sensitive, and more
  correct-to-wrong than wrong-to-correct flips: 9 against 7).

The margin is thin and should be read as such: the excess disagreement is 3.16 points against the pre-registered 3.0,
and the accuracy leg (9 against 7) is not significant on its own. The margin was fixed before the run and the rule was
applied as written. The existence of a one-directional shift does not depend on the margin (16 against 2, p = 0.0013);
only the word "material" does.

## 4. LLM baseline (reported independently, not a gate)

| Metric (P, n=443) | Canonical ids | Opaque keys | Delta |
|---|---:|---:|---:|
| Accuracy | 74.3% | 80.1% | +5.9 pp [+2.9, +8.6] |
| Detection rate | 91.5% | 88.9% | -2.6 pp |
| No-change false-positive rate | 45.0% | 29.7% | -15.3 pp |
| Semantic agreement | | 90.1% [86.9, 92.5] | 44 of 443 differ |
| Share answered `none` | 30.0% | 38.1% | +8.1 pp (canonical replicate 30.0%) |

- Paired outcomes: correct/wrong 8, wrong/correct 34, exact McNemar p < 0.0001. All 750 decisions: 84.8% to 88.3%
  (+3.5 pp [+1.9, +5.2]).
- Of the 44 changed answers, 38 went from a real change to `none`, 4 to a different real change, 2 from `none` to a
  real change. The replicate changed 9 (2.0%): 4, 1 and 4 respectively. Excess +7.9 pp, 40 against 5, p < 0.0001.
- Contract: first-attempt valid 750 of 750 in both arms, no repair, no unrecoverable failure.
- Verdict by the same rules: **possible ID sensitivity / inconclusive** (R1 preserved because accuracy rose, R2
  sensitive, but more wrong-to-correct than correct-to-wrong flips). The LLM's accuracy improved without the ids.

## 5. Recency groups and group B

| Group | n | Jev canonical | Jev opaque | Jev flips b/c | LLM canonical | LLM opaque | LLM flips b/c |
|---|---:|---:|---:|---:|---:|---:|---:|
| A true change newest | 228 | 75.9% | 72.4% | 8/0 | 91.2% | 88.6% | 8/2 |
| B true change older than a newer candidate | 6 | 100% | 83.3% | 1/0 | 100% | 100% | 0/0 |
| C no causal change | 516 | 95.2% | 96.5% | 0/7 | 81.8% | 88.0% | 0/32 |
| D two or more real candidates (overlaps) | 143 | 85.3% | 82.5% | 4/0 | 78.3% | 78.3% | 2/2 |
| E true change not offered | 0 | | | | | | |

b = correct under canonical and wrong under opaque; c = the reverse. For Jev the shift goes the same way in every group:
group A and D decisions lose detections, and group C decisions lose false positives.

Group B (6 decisions, so this cannot establish or exclude anything): in 5 of 6 both systems still choose the true
older change with the ids removed. The one change is Jev on CS02173 (true `CH031066`, now `none`). In all six the true
change also has the highest id number, so the confound recorded in JEV-014 is not removed by this sample.

## 6. What the control does and does not show

- It does **not** show that Jev's accuracy comes from the id numbers: accuracy is the same without them.
- It **does** show that Jev's answers are not invariant to the option key. Removing canonical ids makes Jev more
  willing to answer `none`, on both true-change decisions (a loss) and no-change decisions (a gain). The noise floor
  (2 of 443 changed answers, in the other direction) does not explain 16 changes in one direction.
- It cannot separate two explanations, because opaque keys change both at once: (a) the **id number** carries
  information Jev uses (the true id is always the highest in its decision: 97 of 97 where a true change sits next to
  another real candidate); (b) the **key format** (`CH0304xx` reads like a change record; `opt_x7k2` does not) changes how
  willing a model is to commit. The LLM moves the same way, four to five times as strongly, which fits (b) at least in
  part. The seven avoided false positives are candidates with low ids, which a pure "largest number is the cause"
  shortcut would not pick (my inference, not tested).
- Untested exposure elsewhere (JEV-039): the root-cause (`v4_operational`) and evidence-sufficiency states also contain
  canonical `change_id`s, in 443 of 750 decisions each. This control did not touch them.

## 7. Consequence for the Jev-versus-LLM causal-change result (exploratory)

| Keys | Population | Jev | LLM | Jev - LLM | Only Jev right / only LLM right | McNemar p |
|---|---|---:|---:|---:|---:|---:|
| canonical | all 750 | 89.3% | 84.8% | +4.5 pp [+1.9, +7.2] | 73 / 39 | 0.002 |
| canonical | P | 81.9% | 74.3% | +7.7 pp [+3.2, +12.2] | 73 / 39 | 0.002 |
| opaque | all 750 | 89.1% | 88.3% | +0.8 pp [-1.7, +3.3] | 50 / 44 | 0.61 |
| opaque | P | 81.5% | 80.1% | +1.4 pp [-3.2, +5.4] | 50 / 44 | 0.61 |

The Stage C causal-change lead came mostly from the LLM's false positives on canonical ids (45% of no-change
decisions in P). Without them the two systems are not distinguishable on this decision. This is not a pre-registered
analysis; it is reported because it changes how Stage C's causal result should be read.

## 8. Decision

**DO NOT RUN the v1 locked benchmark.** `locked_benchmark_frozen_v1` is recorded as superseded before use
(`data/eval/jev/locked_benchmark_frozen_v1_superseded.json`). The configuration and manifest are byte-identical to what
was sealed (config sha256 `27236d36b17844f1e7bf95b58fcd9f488e5f1eafc69abae9486e4f454103b82d`, manifest
`138c12f6c0bbe2f39fe3c58e451ffa727e189da79b574521ba662d584788684a`) and stay in place as history. No new freeze was
created.

**The supersession is a record, not an enforcement.** The sealed runner does not read it, so the v1 command would still
be accepted (JEV-038). Making `locked_benchmark.verify()` refuse a superseded freeze means editing a sealed source
(`locked_benchmark.py`), which was blocked in this session and is left as a decision for the owner.

## 9. Proposed replacement configuration (not created)

`locked_benchmark_frozen_v2`, derived from v1:

1. Causal-change option keys are `hashed_opaque_v1` for both systems (the scheme in `opaque_control.py`, parameters
   pinned). Nothing else changes.
2. Decide how the change ids inside the root-cause and evidence-sufficiency states are treated (JEV-039): alias them
   with the same per-case mapping, or run a validation control for them first. Until then a locked root-cause result
   carries an untested exposure.
3. Validation evidence: the opaque control is already a validation-split run of the v2 causal decision (750 decisions,
   pre-registered). It can serve as the validation record if the v2 runner is shown to send byte-identical requests for
   the same 750 decisions, which can be checked offline with no API call. If not identical, causal change needs a new
   validation run.
4. Thresholds: the causal-change automation threshold (v1: 0.80 on non-trivial decisions) was chosen from canonical
   validation records. Under v2 it must be re-derived by `threshold_policy_v1` from the opaque records, a pure function
   with no discretion. Issue category, root cause and owning team keep their thresholds (none for the last two).
5. Pre-registration: a v2 protocol, with the expectation for causal change restated (parity with the LLM, not a
   lead), then a rehearsal on stored validation data and a new seal. The v2 runner can refuse v1 by name, which would
   also close JEV-038.
6. Scope: causal change stays a locked-benchmark candidate on its absolute performance (Jev 89.1% on all decisions,
   81.5% on non-trivial, opaque keys); the "Jev leads" reading no longer holds (section 7).

Options for the owner, in the order I would take them: (i) build v2 as above; (ii) first run a second validation control
with canonical-format keys drawn at random (`CH` plus six random digits, unordered), which separates the id-number
explanation from the key-format one and decides which scheme v2 should use (about $0.04 for Jev and $0.6 for the LLM);
(iii) keep v1, which requires deleting the supersession record with a logged reason and reading the causal result as
specific to canonical keys (not recommended).

## 10. Limitations

- One run per arm on one cohort; the intervals describe sampling variation. The validation set has been seen by the
  project; the control adds no tuning on it but it is not a fresh holdout.
- The margin M (3 points) is a convention chosen before the run; the verdict is at the margin (3.16 points).
- Latencies (P50 195 to 227 ms Jev, 1.0 s LLM) are from a run with one call per case at 8 workers, unlike Stage C's six
  calls per case, so they are not comparable with Stage C's tail figures.
- Whether Jev's service reorders the request's options is not observable; requests preserved the candidate order.
- The second JEV-025 artifact (a visible deployment is the true cause in 68 of 110 cases that offer one) is in the
  descriptions, which the control deliberately kept; it is untouched.
- Spend: Jev $0.037 (opaque) + $0.022 (replicate); LLM $0.608 + $0.367 at the assumed Turbo price; about $1.03 in all.
  Runs took 3.4 and 1.9 minutes.

## 11. Reproduce

```
python3 -m agent.jev_v2.opaque_control --prepare            # every input check, no API call
python3 -m agent.jev_v2.opaque_control --run                # opaque arm, Jev + LLM, 750 cases
python3 -m agent.jev_v2.opaque_control --replicate jev llm  # canonical replicate of the 443 non-trivial decisions
python3 -m agent.jev_v2.opaque_control_report --control-jev <id> --control-llm <id> --replicate-jev <id> --replicate-llm <id>
python3 -m agent.jev_v2.supersede_locked_benchmark          # writes the supersession record (refuses unless the verdict is material)
```
