# Phase 6 — Dataset Splits

## What is split

The 2,500 cases actually loaded into the Phase 4 standing graph --
`CS00001`-`CS02500`, reproduced exactly via
`agent/eval_v2/splits.py::_graph_case_ids()`, which mirrors
`agent/graph_v2/build_graph.py::_small_mode_case_ids`'s own selection
(`sorted(case_observable.csv ids)[:2500]`). Splits are **not** computed over
the full 25,000-row Phase 1-3 dataset -- an experiment can only ever run the
agent against cases that exist in the graph, so splitting a population the
agent can't reach would be meaningless.

## How the split is generated

`python3 -m agent.eval_v2.splits --generate`

1. Every case is stratified by `(difficulty_archetype, evidence_sufficiency)`
   -- 18 possible strata, several sparsely populated (e.g. `dependency_root_cause|insufficient`
   has only ~3-4 cases total).
2. Within each stratum, case IDs are sorted (removing any incidental
   ordering from file/dict iteration) and shuffled with
   `random.Random(SPLIT_SEED)` (`SPLIT_SEED = 20260923`, `agent/eval_v2/config.py`).
3. Each stratum is sliced 40% `dev` / 30% `validation` / 30% `test`
   (`SPLIT_PROPORTIONS`), rounding independently per stratum so every
   stratum -- not just the aggregate -- is represented proportionally in
   all three splits.

This guarantees no archetype or evidence-richness level is concentrated in
one split (spec section 2's explicit requirement), confirmed empirically:

| Split | clear | customer_misdiagnosis | dependency_root_cause | multi_component_symptoms | vague | wrong_product_mentioned | Total |
|---|---|---|---|---|---|---|---|
| dev | 552 | 131 | 46 | 68 | 118 | 84 | 999 |
| validation | 414 | 99 | 35 | 51 | 88 | 63 | 750 |
| test | 414 | 98 | 36 | 50 | 88 | 65 | 751 |

(`python3 -m agent.eval_v2.splits --stats` reproduces this at any time.)

## Output files

- `data/eval/splits/case_splits_v1.json` -- `{case_id: {"split": "dev" |
  "validation" | "test"}}`. No hidden value beyond the bucket label itself.
- `data/eval/splits/split_manifest_v1.json` -- seed, proportions,
  stratification key, per-stratum and overall counts, generation timestamp.

## Split usage policy

| Split | Intended use |
|---|---|
| `dev` (999 cases, 40%) | Debugging evaluation code, inspecting individual traces, smoke/engineering-scale experiments, the permanent regression suite (all 9 regression cases are drawn from `dev`) |
| `validation` (750 cases, 30%) | Later phases: threshold selection, Jev question design, architecture experimentation |
| `test` (751 cases, 30%) | **Locked.** Never for prompt tuning, tool redesign, confidence-threshold tuning, Jev-question tuning, or agent-policy optimization -- only for a final, one-shot benchmark read after everything else is frozen |

### The lock is enforced two ways

1. **By convention**: `generate_splits()` refuses to overwrite an existing
   `case_splits_v1.json` unless called with `force=True` -- there is no CLI
   flag to force it casually; it requires editing a call site directly and
   understanding this document first.
2. **By a CLI guardrail**: `run_experiment.py --split test` raises an
   argument-parser error unless `--kind locked_benchmark` is also passed.
   This does not make misuse impossible (nothing stops someone from passing
   `--kind locked_benchmark` on a whim), but it makes accidental
   tuning-on-test require a deliberate, visible, named decision rather than
   an easy default.

## Regenerating a split (should be rare)

Only with an explicit, documented reason -- e.g. the graph's case population
changes (a re-build with `--n-cases` different from 2500), or a real defect
in the stratification logic itself is found. Bump `SPLIT_VERSION` in
`config.py` (e.g. `v1` -> `v2`) rather than overwriting `case_splits_v1.json`
in place, so any experiment that already ran against `v1` remains
interpretable against the split it actually used --
`experiment.json`'s `split_version` field records this per experiment.
