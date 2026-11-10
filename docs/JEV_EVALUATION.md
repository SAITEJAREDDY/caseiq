# Phase 7 — Running Jev Primitive Experiments

## Prerequisites

`TYPESAFE_API_KEY` in `.env` (for real Jev calls) and `TOGETHER_API_KEY`
(already present, for `--compare-llm`). Same `NEO4J_V2_*` credentials
Phase 4/5/6 use. `data/eval/splits/case_splits_v1.json` must already exist
(it does — Phase 6 generated it).

## CLI

```bash
# Stage A smoke test: all six decisions over a handful of dev cases
python3 -m agent.jev_v2.run_experiment --name smoke_a --kind smoke --split dev --n 5

# the permanent regression suite (9 fixed cases, reused from Phase 6)
python3 -m agent.jev_v2.run_experiment --name regression_v1 --kind smoke --regression-suite

# one decision type only
python3 -m agent.jev_v2.run_experiment --name rc_only --kind engineering --split dev --n 50 --decision-types root_cause

# root-cause context ablation (spec section 24) -- run once per context version, compare reports
python3 -m agent.jev_v2.run_experiment --name rc_v1 --kind engineering --split dev --n 50 --decision-types root_cause --context-version v1_narrative
python3 -m agent.jev_v2.run_experiment --name rc_v3 --kind engineering --split dev --n 50 --decision-types root_cause --context-version v3_technical
python3 -m agent.jev_v2.run_experiment --name rc_v5 --kind engineering --split dev --n 50 --decision-types root_cause --context-version v5_graph

# head-to-head against the LLM primitive baseline (writes two experiments + a comparison doc)
python3 -m agent.jev_v2.run_experiment --name compare_v1 --kind engineering --split dev --n 30 --compare-llm

# the locked test split -- requires an explicit --kind locked_benchmark
python3 -m agent.jev_v2.run_experiment --name locked_v1 --kind locked_benchmark --split test
```

Every decision uses `as_of = the case's own created_date` — a T0, "ticket
just arrived" investigation point (spec section 4's "decision timestamp
where relevant"). Multi-timepoint accumulation (spec sections 66-69,
T0→T1→T2→T3 using Phase 3's own historical `diagnostic_hypotheses.csv`/
`evidence_queries.csv` timestamps as natural snapshot boundaries) is real,
available infrastructure (`agent/agent_v2/time_gate.py`-style `as_of`
gating already threads through every state-builder function) but is
explicitly deferred past this first tranche, per spec section 22.

## Output

Same `data/experiments/<experiment_id>/` layout Phase 6 uses:
`experiment.json` (full config + per-decision-type report),
`decisions.jsonl`/`decisions.csv` (one row per decision, spec section 54),
`report.md`. `--compare-llm` additionally writes `comparison_vs_llm.md`
next to the Jev experiment's report. `experiment_type` distinguishes
`"jev_primitive"` from `"llm_primitive_baseline"` in the shared
`data/experiments/registry.jsonl`.

## What has actually been run (Stage A)

Two runs, both against the `dev` split, `jev-1.13.0`, `question_set_version
v1`, `candidate_strategy_version v1`, default `context_version
v3_technical`:

- **`smoke_a`** (5 fresh dev cases, all six decisions): 25 decisions, **zero
  errors, zero contract failures**.
- **`regression_v1`** (the permanent 9-case regression suite): 48 decisions
  (`incident_relationship` only fires for cases with a candidate incident —
  3 of the 9 had one), zero errors, zero contract failures.

**Two real bugs were found and fixed live against the actual API**, not
caught by any offline test, because they only manifest once the real
payload shape hits the leakage guard or the confusion-matrix code:

1. **A leakage-guard false positive.** The `causal_change` question
   legitimately asks whether a change is "causally related" to an incident
   — ordinary English for exactly what spec section 13 asks to be tested —
   but `BANNED_SUBSTRINGS` includes the bare word `causal` (meant to catch a
   hidden field like `causal_component_id`). A second, related false
   positive: the internal decision-type identifier `"causal_change"` itself
   (used as the `questions` dict's own key) also matched. Fixed in two
   parts (`client.py`): (a) value-scanning now uses a narrower
   `VALUE_BANNED_SUBSTRINGS` list excluding words that are legitimate
   domain vocabulary (`causal`, `distractor`, `optimal`, `mistake`,
   `misleading`, `efficiency`, `_relevant`) while keeping the full list for
   key-scanning (an actual field name leaking in as a *key* is the real
   risk spec section 65 describes); (b) the leakage scan no longer inspects
   the outer `questions` dict's own key names (Phase 7's own hand-written
   decision-type identifiers), only `state` and each question's `body`.
   This is the same class of self-referential false positive Phase 5/6 hit
   for their own output-schema field names — documented here rather than
   silently patched away.
2. **`owning_team`'s `ground_truth_value` was a list**, not a scalar
   (support for multiple legitimate primary teams), which crashed the
   confusion-matrix builder (`unhashable type: 'list'`) the first time a
   real experiment tried to build one. Fixed (`scoring.py::score_owning_team`)
   to report a single scalar `ground_truth_value` (the primary team, or the
   sole acceptable team if none is marked primary) while keeping the full
   acceptable set in a separate `acceptable_teams` field.

## Very-early signal (n=9, not a real benchmark yet)

The regression suite's numbers are far too small a sample to draw
conclusions from (several categories show 0/1 or 1/1 outcomes, and the
report's own bootstrap CIs are correspondingly wide or undefined) — they
are reported here only to show the harness surfaces real, differentiated
signal, not identical numbers everywhere:

| Decision | Accuracy (n=9, except incident n=3) | Candidate recall |
|---|---|---|
| issue_category | 77.8% | 100% |
| root_cause | 0.0% | 66.7% |
| causal_change | 77.8% | 88.9% |
| owning_team | 11.1% | 44.4% |
| evidence_sufficiency | 11.1% | 100% |
| incident_relationship | 33.3% | n/a (Noul) |

Notable, worth a closer look once sample size grows: `owning_team`'s
candidate recall is only 44.4% — nearly half the time the true team wasn't
even offered as an option, a candidate-generation issue, not necessarily a
Jev weakness (`candidates.py::owning_team_candidates`'s
component-topology-based strategy may need revisiting before it's fair to
judge Jev's own routing accuracy). `causal_change`'s recency breakdown
confirms the mechanism works: 100% accuracy when the true causal change
happens to be the newest one (n=4), with zero regression-suite cases yet
where the true cause is *older* than a distractor — a larger sample is
needed to see that specific, most-important cell.

## Staged progression

Per spec sections 50/79, Stage B (100-300 dev cases), Stage C (validation
split), and Stage D (locked benchmark) are deliberate checkpoints, not
automatic next steps. Stage B and Stage C have been run (Stage C: 750
validation cases, one run on the frozen configuration; see the last section and
`JEV_STAGE_C_VALIDATION.md`), and reviewed (`JEV_STAGE_C_REVIEW.md`). Stage D (the
locked benchmark) was frozen in `data/eval/jev/locked_benchmark_frozen_v1.json`
with a pre-registered protocol (`JEV_LOCKED_BENCHMARK_PROTOCOL.md`); it has not
been run, and the freeze is now recorded as superseded before use (opaque-key
control, `JEV_OPAQUE_KEY_CONTROL.md`). Any locked run needs a replacement freeze and explicit approval. `--split test` is refused unless
`--kind locked_benchmark` is passed explicitly (mirroring Phase 6's own
`test`-split guardrail).

## Reproducibility

Every experiment records `dataset_checksum_digest` (Phase 1-3's frozen-
baseline manifest hash, via `agent.eval_v2.registry.dataset_checksum_digest`,
reused directly), `question_set_version`, `candidate_strategy_version`, and
`evaluator_version`. Jev's own `model` field (the resolved `jev-1.13.0`,
not just the `jev-latest` alias requested) is stored per decision record.
Scoring (`scoring.py::score_decision`) is a pure function — re-scoring a
stored decision twice is byte-identical (`validate_boundaries.py` check 4).
Jev's own token sampling is not claimed to be bit-reproducible; everything
else in the pipeline is.

## Stage B v2 — candidate generation and evidence-sufficiency correction

Stage B v2 is a controlled development-only follow-up to Stage B v1.  It
uses the same ordered 100-case `dev` cohort and records
`exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823` as its immutable
comparison baseline.  No validation or locked-test case was read, previewed,
or evaluated.

### Evidence sufficiency: why v1 was 2.0%

This was **not** a Choice-key mapping or scorer inversion.  Inspection of the
100 raw v1 decisions found 94 `sufficient`, 6 `partially_sufficient`, and no
`insufficient` truth rows in this particular fixed cohort.  A 20-record
diagnostic sample included all six partial rows and fourteen sufficient rows
(an insufficient example cannot be selected from this cohort).  The raw API
answer is already one of the exact canonical keys and `scoring.py` compares
it directly to `phase2_ground_truth.evidence_sufficiency`:

| v1 truth | Jev sufficient | Jev partially sufficient | Jev insufficient |
|---|---:|---:|---:|
| sufficient (n=94) | 1 | 53 | 40 |
| partially sufficient (n=6) | 0 | 1 | 5 |

The Phase 2 generator defines the hidden label mechanically: insufficient
means no clear telemetry anomaly, at most one total signal, and no causal
change; sufficient means a causal signal, causal change, or clear telemetry
anomaly; partial is the remainder.  Its causal-signal/change membership is
intentionally hidden.  v1 gave Jev signal messages and change metadata but
only a list of telemetry *categories*, not the observable abnormal telemetry
findings that the label itself partly relies on.  Thus v1 asked whether the
visible evidence supported a diagnosis while grading against a label partly
defined by hidden relevance and omitted observable anomaly detail.  Case T0
was otherwise aligned: signals and causal changes are generated before the
case timestamp; post-case configuration snapshots are correctly excluded.

This is a **semantic/state-projection mismatch**, not a scorer bug,
normalization bug, or time-leakage issue.  `evidence_sufficiency_v2` adds a
time-gated observable telemetry summary (finding count, abnormal finding
count, metric/component/direction) and versioned operational instructions.
It does not expose causal labels or change the truth label/scorer.  The
corrected v2 result rises from 2.0% to 14.0%, confirming that the omitted
observable telemetry mattered but also that Jev remains poor on this noisy
three-way primitive under the retained Phase 2 target.

### Frozen `candidate_generation_v2`

Both v2 algorithms use only reference/taxonomy tables and the same
time-gated observable evidence that the Phase 5 tool layer uses.  They do not
read `eval_store`, Phase 1 `gt_*` columns, or Phase 3 labels.

- **Owning team:** aggregate component support across *all* deployed
  components (weight 1), product-team support (2), observed signal-component
  support (3), and reported-symptom -> subcategory -> team support (2 times
  the two public relationship weights).  Rank deterministically by descending
  support then team id; keep top 12.  This replaces v1's order-dependent
  `component_ids[:8]` slice.
- **Root cause:** aggregate product-component topology support (1),
  observed signal-component support (4), and reported-symptom -> subcategory
  -> root-cause support (4 times the two public relationship weights).  Rank
  deterministically by descending support then root-cause id; keep top 15
  plus `RC40`.  `RC40` is the canonical taxonomy entry "insufficient
  information to determine root cause", so it is retained as the explicit
  abstention option rather than injected as a plausible concrete diagnosis.

The prior seven team misses left after considering every deployed and signal
component were all recoverable through the public symptom -> subcategory ->
team relation (five `TM12`, one `TM22`, and one `TM17/TM22` acceptable pair).
All eight root causes absent from product topology were surfaced by public
signal and/or symptom taxonomy links.  Candidate strategy v2 therefore has
no remaining observable-coverage miss on this engineering cohort; that is not
a claim of future validation/test recall.

Before the model rerun, v2 root-cause cutoff analysis on the stored v1 inputs
measured 97% recall for top 11 + RC40 and 100% for top 15 + RC40 (average
candidate counts 12.0 and 15.9 respectively).  Top 15 was frozen as the
smallest tested bound with complete development recall.  Team v2's selected
top-12 bound averages 11.9 candidates (median/P90 both 12).

### Controlled Stage B comparison

| Metric | Root cause v1 | Root cause v2 | Owning team v1 | Owning team v2 |
|---|---:|---:|---:|---:|
| Candidate recall | 68.0% | 100.0% | 61.0% acceptable | 100.0% acceptable |
| Average candidates | 12.0 | 15.9 | 6.4 | 11.9 |
| Conditional accuracy | 38.2% | 32.0% | 62.3% acceptable | 49.0% acceptable |
| End-to-end / primary accuracy | 26.0% | 32.0% | 29.0% | 36.0% |
| Acceptable-team accuracy | n/a | n/a | 38.0% | 49.0% |
| Macro F1 | 0.228 | 0.266 | 0.187 | 0.257 |
| False-confident rate | 7.0% | 2.0% | 12.0% | 5.0% |

Candidate expansion improves end-to-end accuracy for both decisions even
though conditional Choice accuracy declines as the option set grows.  The
v2 failure decomposition makes the tradeoff explicit: root cause changes
from 32 missing / 42 present-but-wrong / 26 present-and-correct to 0 / 68 /
32; owning team changes from 39 / 32 / 29 to 0 / 64 / 36.  For team routing,
primary candidate recall is 53.0% -> 99.0%, while acceptable recall is 61.0%
-> 100.0%; primary/acceptable accuracy is 29.0%/38.0% -> 36.0%/49.0%.

The independently unchanged primitives provide a control: issue category is
70.0% -> 72.0%, causal change 86.0% -> 87.0%, and incident relationship
70.6% -> 70.6%.  The full machine-generated comparison is stored beside the
v2 experiment as `comparison_vs_exp_stage_b_dev_100_v1_20260923T081534Z_13ad1823.md`.

### Root-cause context ablation with v2 candidates

The candidate state is deliberately independent of the question-state
ablation: every arm uses the same reported product, reported symptoms, and
T0-visible signals to construct its candidate set.  The technical point is
the controlled Stage B v2 root-cause record; all other levels are separate
100-case dev-only experiments.

| Context | Recall | Avg candidates | Conditional / end-to-end accuracy | Brier / ECE | False-confident | Mean latency ms | Mean input/output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| v1 narrative | 100.0% | 15.9 | 6.0% / 6.0% | 0.6294 / 0.7209 | 32.0% | 165.4 | 674.7 / 163.9 |
| v2 domain | 100.0% | 15.9 | 5.0% / 5.0% | 0.6105 / 0.7235 | 32.0% | 151.4 | 984.7 / 163.9 |
| v3 technical | 100.0% | 15.9 | 32.0% / 32.0% | 0.2923 / 0.3250 | 2.0% | 165.9 | 1376.8 / 163.9 |
| v4 operational | 100.0% | 15.9 | 45.0% / 45.0% | 0.2758 / 0.1928 | 3.0% | 165.2 | 1478.9 / 163.9 |
| v5 graph | 100.0% | 15.9 | 46.0% / 46.0% | 0.2824 / 0.1831 | 4.0% | 175.7 | 1806.8 / 163.9 |

Operational context supplies the main step-change; graph context adds one
point at a modest input-token and latency cost.  These are engineering-split
findings only.  The next checkpoint remains an explicit validation decision;
this work does not advance to validation. (Stage C has since run on validation:
see `JEV_STAGE_C_VALIDATION.md`.)

Two early v2 narrative/domain ablation artifacts are retained in the
append-only registry but excluded from this table: they accidentally let the
candidate set vary with the model-context state.  Their corrected reruns use
the stable candidate-state builder above; no Stage B v1 or Stage B v2 record
was overwritten.

## Stage B v3 — causal-change candidate generation v3 (JEV-013)

Development-only, same ordered 100-case cohort as Stage B v1/v2. No
validation or locked-test case was read, previewed or evaluated. Every
number below is from a new experiment; no earlier artifact was modified.

### Why deployments were missing

`causal_change_candidates` built its options from `q_recent_changes`, whose
Cypher filters `NOT ch:Deployment`. Deployments are a separate label with a
separate tool, `q_deployment_history`. The causal-change *state* never carried
either list (changes appear only as candidates), so a true cause that was a
deployment was simply never offered. All six Stage B v2 misses (CS00001,
CS00006, CS00075, CS00122, CS00145, CS00165) are `change_type = deployment`
events that started before T0 and are visible through `q_deployment_history`.

### The fix: `candidate_generation_v3`

Every visible change **and** every visible deployment, normalized into one
structure (canonical id, event type, start time, component, deployment version
change and rollout strategy), deduplicated by canonical id, ordered newest
first then by id, plus the explicit `none` option. It uses only the two
time-gated Phase 5 tool functions; no hidden field is read
(`JEV_DATA_BOUNDARIES.md`). v2 stays callable and reproduces the stored Stage
B v2 candidate sets for 100/100 cases.

### Candidate recall before Jev (no API call)

`python3 -m agent.jev_v2.analyze_causal_candidates` (output in
`data/eval/jev/analysis/causal_change_candidates_v2_vs_v3_dev100.{md,json}`):

| Metric | v2 | v3 |
|---|---:|---:|
| Candidate recall | 94.0% | 100.0% |
| Cases with no true candidate | 6 | 0 |
| Avg candidates (incl. `none`) | 1.73 | 1.80 |
| Median / P90 candidates | 2 / 3 | 2 / 3 |
| Cases with zero real candidates | 44 | 39 |
| Cases with a deployment-type candidate | 0 | 7 (7%) |
| Cases with duplicate suppression | n/a | 0 |
| Future events dropped by the defensive gate | n/a | 0 |

No remaining observable ceiling on this cohort: every true causal change is
observably represented at T0. That is a dev-cohort result, not a claim about
validation or test recall (JEV-019).

### Controlled Jev rerun

`exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8`. Same 100 cases, same
Jev model (`jev-1.13.0`), same question version, same state, same evaluator;
only the candidate generation changed. Both sides re-aggregated with evaluator
v2.1 (`comparison_vs_exp_stage_b_dev_100_v2_...md` beside the v3 experiment).

| Metric | v2 | v3 |
|---|---:|---:|
| Candidate recall | 94.0% | 100.0% |
| End-to-end accuracy | 87.0% | 92.0% |
| Conditional accuracy (true change offered) | 92.6% | 92.0% |
| Macro F1 | 0.646 | 0.782 |
| False-confident (wrong at conf >= 0.90) | 5 (5.0%) | 0 |
| No-causal-change accuracy | 94.1% | 94.1% |
| Distractor selected, when a distractor was offered | 10.3% (n=39) | 10.0% (n=40) |
| Latency P50 / P95 (ms) | 157 / 273 | 181 / 438 |
| Cost per 1,000 decisions (USD) | 0.0503 | 0.0505 |

Five decisions flipped to correct (CS00001, CS00006, CS00122, CS00145,
CS00165), none to wrong; paired difference +5.0 points, bootstrap 95% CI
[+1.0, +10.0], exact McNemar p = 0.062. CS00075 is still wrong (Jev chose
`none` at 0.77 confidence). On the 93 cases whose inputs were identical, Jev
gave the same answer 93 times.

**Answer to the key question:** fixing recall improved end-to-end accuracy.
The larger option set did not reduce conditional accuracy here (92.6% vs
92.0%), but the set barely grew (1.73 to 1.80 options; 7 cases changed), so
this says little about what a much larger causal-change set would do. Of the
five recovered decisions, four were made at low or moderate confidence (0.25 to
0.78) and one (CS00006) at 0.92.

### Recency and distractor groups (v2.1 definitions)

| Group | v2 n / accuracy | v3 n / accuracy |
|---|---:|---:|
| A true change is the newest candidate | 26 / 88.5% | 32 / 87.5% |
| B true change older than at least one distractor | 0 / n/a | 0 / n/a |
| C no causal change | 68 / 94.1% | 68 / 94.1% |
| D two or more real change candidates | 15 / 86.7% | 17 / 88.2% |
| E true change not offered (candidate miss) | 6 / 0.0% | 0 / n/a |

**Group B is empty in both.** No case in this cohort has a visible true cause
older than a visible distractor, so the recency-versus-causality question the
spec calls one of the most important capability tests is still untestable on
this data (JEV-014). For context, always answering `none` scores 68% and
"newest change, else none" scores 71%; Jev's 92% is above both, but that alone
does not separate causal reasoning from a recency rule.

## JEV-018 — Jev versus the LLM primitive baseline

Experiments: Jev `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24`, LLM
`exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff`; paired report
`comparison_jev_vs_llm.{md,json}` in the Jev folder. 100 dev cases, all six
decisions (517 decisions each), run with the Stage B frozen settings
(`--frozen-config stage_b_frozen_v1 --pre-freeze`, the manifest being written
afterwards). Jev: `jev-1.13.0` pinned. LLM: `meta-llama/Llama-3.3-70B-Instruct-Turbo`
via Together AI, temperature 0.1, JSON mode, one repair re-prompt allowed.

**Identical inputs.** For every pair, the stored state, option set and
decision time hash identically (100/100 for each decision type; incident
17/17). Neither system received extra context.

**Contract reliability.** The LLM produced a valid first attempt on all 517
decisions: no invalid option, no malformed JSON, no repair needed, no
unrecoverable failure. Jev returned native typed results with zero API errors.
Contract failure was not a differentiator in this run.

### Results (dev-100; accuracy with 95% bootstrap CI; paired test on the same decisions)

| Decision | Trivial baseline | Jev | LLM | Jev minus LLM (paired 95% CI) | McNemar p |
|---|---:|---:|---:|---:|---:|
| issue_category | 18.0% | 73.0% [64, 82] | 76.0% [68, 84] | -3.0 [-11, +4] | 0.607 |
| root_cause (v4 context) | 10.0% | 48.0% [38, 58] | 24.0% [16, 32] | +24.0 [+15, +33] | <0.001 |
| causal_change (v3) | 68.0% | 92.0% [87, 97] | 80.0% [72, 87] | +12.0 [+5, +20] | 0.004 |
| owning_team, primary | 16.0% | 36.0% [27, 45] | 11.0% [5, 17] | +25.0 [+14, +36] | <0.001 |
| owning_team, acceptable | n/a | 49.0% | 22.0% | n/a | n/a |
| evidence_sufficiency | 94.0% | 14.0% [8, 21] | 43.0% [33, 53] | -29.0 [-39, -20] | <0.001 |
| incident_relationship (n=17) | 70.6% | 70.6% [47, 88] | 82.4% [65, 100] | -11.8 [-29, 0] | 0.500 |

Macro F1 (Jev / LLM): issue category 0.587 / 0.645; root cause 0.445 / 0.194;
causal change 0.782 / 0.597; owning team 0.262 / 0.059; evidence sufficiency
0.093 / 0.369. Incident relationship AUC of the raw probability: 0.692 / 0.675.
Candidate recall was 100% for every Choice decision and identical for both
systems, so end-to-end and conditional accuracy differ only for owning team
(primary 36% / 11%; acceptable conditional 49% / 22%).

### High-confidence errors, calibration, cost and latency

| Decision | Wrong at conf >= 0.90 / such predictions (Jev) | (LLM) | Latency P50 / P95 ms (Jev) | (LLM) |
|---|---:|---:|---:|---:|
| issue_category | 6 / 42 | 4 / 29 | 166 / 413 | 808 / 1347 |
| root_cause | 3 / 13 | 0 / 0 | 173 / 468 | 816 / 1374 |
| causal_change | 0 / 44 | 0 / 39 | 169 / 302 | 783 / 1722 |
| owning_team | 5 / 8 | 0 / 0 | 174 / 288 | 801 / 1579 |
| evidence_sufficiency | 2 / 2 | 0 / 5 | 171 / 315 | 789 / 1699 |
| incident_relationship | 1 / 8 | 2 / 9 | 156 / 296 | 649 / 2942 |

Cost, from provider-returned token counts at the versioned prices in
`config.py` (`PRICING_VERSION` 2026-09-23): Jev about $0.03 to $0.06 per 1,000
decisions; the LLM about $0.43 to $0.99 per 1,000, roughly 16 times more. The
Jev price is from the TypeSafe pricing documentation ($0.042 per million input
tokens, output free). The LLM price is Together's listed $1.04 per million for
"Llama 3.3 70B"; the page lists no separate Turbo row, so applying it to the
Turbo model id is an assumption. Token counts come from different tokenizers
and are not comparable between the two systems.

**Confidence is not comparable and is not ranked.** Jev's confidence is the
native probability of the typed primitive. The LLM's is a number it was asked
to write, and it barely varies: owning-team confidence was 0.8 on every
decision, root-cause mean 0.78 with a maximum of 0.8. Its low ECE on some
decisions reflects that near-constant value, not calibration skill, and the
"0 high-confidence predictions" entries above mean it never said 0.9, not that
it was never wrong confidently. Jev's confidence has real spread, and it is
still overconfident in places: 6 of 42 high-confidence issue-category
predictions and 5 of 8 owning-team ones were wrong.

### The six comparison questions

1. **Causal change, distractor-rich temporal selection.** Jev was ahead in every
   paired comparison (below), by 4 to 12 points. On no-change cases Jev picked a
   change 6 to 7% of the time and the LLM 24 to 25% (12% with opaque keys); on the multi-candidate group
   (D, n=17) Jev scored 82 to 88% and the LLM 59 to 71%. Because group B is
   empty, this is evidence about false positives and distractors, not about
   recency-versus-causality.
2. **Issue category, fully covered set.** Neither materially outperforms the other
   (73% vs 76%, p=0.61). Both are well above the 18% baseline and both are
   confidently wrong on roughly one in seven high-confidence predictions.
3. **Root cause, same operational context.** Jev's flat-choice performance is
   not weaker than the LLM's: 48% vs 24%. It is still a modest absolute
   result (52% wrong), and Jev's own answer changed on 6 of 100 decisions
   between two runs on identical inputs (45% then 48%).
4. **Owning team, 100%-recall set.** The LLM does not use the set better: 22%
   acceptable vs Jev's 49%. Both are weak in absolute terms.
5. **Evidence sufficiency.** Jev is weaker than the LLM (14% vs 43%), but both are
   far below the 94% majority baseline and both systematically under-call
   sufficiency (of 94 "sufficient" cases, Jev answered "partially sufficient" 82
   times and the LLM 57 times). The difficulty sits mainly in the state and
   target, not in Jev specifically; Jev is also the worse of the two.
6. **Incident relationship, Noul.** Too small to conclude (n=17, 5 positives).
   Discrimination is similar (AUC 0.69 vs 0.68); at a 0.5 threshold Jev caught
   1 of 5 related incidents and the LLM 2 of 5.

### Controls run alongside JEV-018

**Repeatability (Jev).** Where inputs were identical across runs, Jev gave the
same answer on: issue category 99/100, owning team 93/100, evidence
sufficiency 99/100, root cause 94/100 (accuracy 45% then 48%), incident
relationship 17/17 (each against its Stage B v2 or ablation run). For causal
change: 93/93 on the cases whose candidates v3 left unchanged, 100/100 between
the first two v3 runs, and 99/100 for each of the repeat and opaque-key runs.
It is not bit-deterministic, and root-cause and owning-team answers move by a few
points between runs. That is the same size as the v4 versus v5 root-cause gap
(45% vs 46% in the ablation), so that gap is not resolvable on this cohort.

**Repeatability (LLM), causal change.** Two canonical-id runs of the LLM scored
80% and 83% (97 of 100 answers identical). The single LLM run per decision in
the table above therefore carries a few points of noise that is not otherwise
measured.

**Opaque-key control (change-id number range).** The change-id number alone
separates true from non-true candidates in this cohort (see
`JEV_DATA_BOUNDARIES.md`). Rerunning causal change with id-free option aliases:

| Causal change, dev-100 | Canonical ids | Opaque keys |
|---|---:|---:|
| Jev | 92%, 92%, 91% (three runs) | 91% |
| LLM | 80%, 83% (two runs) | 87% |
| Jev minus LLM (paired) | +12 (p=0.004); +8 (p=0.057) | +4 [-2, +10] (p=0.344) |

Neither system's accuracy depends on the id number: Jev was unchanged within
run-to-run noise, and the LLM did better, not worse, without ids (its
false-positive rate on no-change cases fell from about 24% to 12%). The Jev
lead on causal change is consistent in direction (3 of 3) and in its lower
false-positive rate, but its size (4 to 12 points) depends on the run and the
key format and is statistically firm in only one of the three comparisons.

### Limitations

- One 100-case dev cohort; validation and test untouched at the time of writing
  (Stage C has since run on validation: `JEV_STAGE_C_VALIDATION.md`). Candidate
  strategies for root cause, owning team and (now) causal change were developed
  against this same cohort, so recall figures were in-sample here; validation
  recall confirmed them (JEV-019, closed).
- One LLM run per decision at temperature 0.1 with no seed for the main
  table; LLM noise measured only for causal change.
- Incident relationship has n=17; evidence sufficiency has 94/6/0 labels in
  this cohort, so its `insufficient` class was never evaluated.
- The LLM prompt was not tuned. A stronger prompt or model could change the
  gaps; this is the baseline the spec asked for, not a ceiling.
- Cost uses a versioned price assumption for the LLM.

## Stage C — validation (750 cases)

One run of the frozen Stage B configuration on the whole validation split, Jev
and the LLM on identical inputs, analysed against a protocol written before the
first call (`JEV_STAGE_C_PROTOCOL.md`). The full report, the twelve success
questions and the locked-benchmark recommendation are in
`JEV_STAGE_C_VALIDATION.md`; the machine-generated tables are
`stage_c_report.md` and the labelled post-hoc `stage_c_posthoc.md` in
`data/experiments/exp_stage_c_validation_jev_20260923T184036Z_fa984004/`.

| Decision | Jev | LLM | Class under the pre-registered rubric |
|---|---:|---:|---|
| Issue category | 78.4% | 79.3% | Supporting-only |
| Root cause | 37.2% | 20.7% | Supporting-only (degraded from dev) |
| Causal change | 89.3% | 84.8% | Candidate for locked benchmark |
| Owning team (primary) | 37.6% | 14.5% | Supporting-only |
| Evidence sufficiency | 12.4% | 41.9% | Weak / deprioritize |
| Incident relationship | 82.6% | 78.8% | Weak / deprioritize |

To re-run the analysis on stored experiments (no API, graph or hidden-truth
call):

```bash
python3 -m agent.jev_v2.stage_c_report --jev-val <id> --llm-val <id> --jev-dev <id> --llm-dev <id>
python3 -m agent.jev_v2.stage_c_posthoc --jev-val <id> --llm-val <id> --jev-dev <id> --llm-dev <id>
```

## Stage D — locked benchmark (frozen, superseded before use, not run)

**Status update.** The validation opaque-key control (`JEV_OPAQUE_KEY_CONTROL.md`,
protocol `JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md`) found that Jev's causal-change
answers move one way when canonical change ids are replaced by opaque keys (16 of 443
non-trivial answers, all to `none`; 2 in a canonical replicate; p=0.0013), although
accuracy did not fall. By the pre-registered rule the v1 freeze is recorded as
superseded (`data/eval/jev/locked_benchmark_frozen_v1_superseded.json`; a record only,
not enforced by the sealed runner, `JEV-038`). The commands below are kept as history
and must not be run. A replacement (`locked_benchmark_frozen_v2`) is proposed in the control report, not created.

The sealed configuration is `data/eval/jev/locked_benchmark_frozen_v1.json`
(manifest alongside), derived from the Stage B freeze and the Stage C selection
decisions; the pre-registered protocol is `JEV_LOCKED_BENCHMARK_PROTOCOL.md` and the
review that led to it is `JEV_STAGE_C_REVIEW.md`. Included: causal change, issue
category, root cause and owning team. Excluded: evidence sufficiency and incident
relationship.

```bash
# verify every guard and print the plan; loads no case ids, calls no API, writes no marker
python3 -m agent.jev_v2.run_experiment --name locked_benchmark_run --kind locked_benchmark \
    --split test --compare-llm --frozen-config locked_benchmark_frozen_v1 --check-only

# the one-shot run itself (needs explicit approval; nothing else may be varied)
python3 -m agent.jev_v2.run_experiment --name locked_benchmark_run --kind locked_benchmark \
    --split test --compare-llm --frozen-config locked_benchmark_frozen_v1

# the pre-registered analysis of that run
python3 -m agent.jev_v2.locked_report --jev <locked jev id> --llm <locked llm id>
```

The analysis code was rehearsed on stored validation data with
`locked_report --rehearsal --out-dir <dir outside data/experiments>`.

