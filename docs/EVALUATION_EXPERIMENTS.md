# Phase 6 — Running Experiments

## Prerequisites

Same `NEO4J_V2_*` credentials as Phase 4/5, plus `data/eval/splits/case_splits_v1.json`
(`python3 -m agent.eval_v2.splits --generate`, already done -- see
`EVALUATION_SPLITS.md`). `run_and_evaluate` mode additionally needs whatever
Phase 5 needs to run the agent (Together AI/Groq API key).

## CLI

```bash
# run fresh + evaluate N dev-split cases
python3 -m agent.eval_v2.run_experiment --name smoke_v1 --kind smoke \
    --split dev --n 15 --run-mode run_and_evaluate

# the permanent regression suite (9 fixed cases, always from `dev`)
python3 -m agent.eval_v2.run_experiment --name regression_v1 --kind smoke \
    --regression-suite --run-mode run_and_evaluate

# re-score already-persisted runs without calling the agent again --
# this is how you re-evaluate old runs after an evaluator bug fix (see below)
python3 -m agent.eval_v2.run_experiment --name rescope --kind adhoc \
    --case-ids CS00191 CS00002 --run-mode evaluate_existing

# explicit run ids (skips the "most recent run per case id" lookup)
python3 -m agent.eval_v2.run_experiment --name rescope2 --kind adhoc \
    --case-ids CS00191 --run-mode evaluate_existing --run-ids run_CS00191_...

# the locked test split -- requires an explicit --kind locked_benchmark
python3 -m agent.eval_v2.run_experiment --name locked_v1 \
    --kind locked_benchmark --split test --run-mode run_and_evaluate
```

`--kind` is one of `smoke` / `engineering` / `baseline` / `locked_benchmark`
/ `adhoc` (spec section 51's staged sizing -- this repo does not enforce
case-count ceilings per kind, but names the intent so `registry.jsonl`
stays legible over time).

## Output

`data/experiments/<experiment_id>/`:
- `experiment.json` -- full config (agent version fields, dataset checksum
  digest, split version, evaluator version, case ID list, run ID list) plus
  the complete aggregate.
- `case_metrics.jsonl` / `case_metrics.csv` -- one row per case (spec
  section 5's run-level evaluation record).
- `confusion_matrices.json`.
- `report.md` -- human-readable summary (spec section 41).

`data/experiments/registry.jsonl` is append-only; nothing in this package
ever opens it in write mode except to append.

## What has actually been run so far

Two pipeline-validation passes, both against the `dev` split, both on the
Together AI default (`meta-llama/Llama-3.3-70B-Instruct-Turbo`,
`prompt_version v1`, `toolset_version v1`, `agent_loop_version v1`,
`repair_layer_version v1`):

- **`regression_v2_rescored`** (9 cases: the permanent regression suite --
  see `regression_cases.py` for what each one covers)
- **`smoke_v2_rescored`** (12 fresh `dev`-split cases, `CS00001`-`CS00028`)

(The `_v1`/original runs of both are still on disk, superseded by the
`_v2_rescored` re-scoring below -- kept, not deleted, per spec section 4's
"never overwrite a previous experiment.")

### A real evaluator bug found and fixed during this validation

The first pass scored `causal_change` accuracy as `0.0%` with a nonzero
`prediction_rate`, which didn't square with manually inspecting the raw
runs (`predicted_causal_change_id` was `null` in every single one of the 21
runs scored). The bug: `causal_change`'s denominator was accidentally built
around "does a true causal change exist," not "did the agent make a
prediction" -- unlike every other field in this catalog, so a genuine
"agent said nothing" was being counted identically to "agent guessed
wrong." Fixed in `metrics.py` (see the comment at the causal-change block)
and both experiments were **re-scored from the exact same persisted runs**
via `--run-mode evaluate_existing` -- no new LLM calls, no re-running the
agent -- producing the `_v2_rescored` experiments above. This is the
concrete demonstration of spec section 43's reason for keeping execution
and scoring separate: an evaluator bug was fixed without touching the
(expensive) agent runs it was scoring.

### Headline results (21 total fresh runs across both experiments)

**Every ID-valued prediction field the agent can populate — `predicted_product_id`,
`predicted_component_id`, `predicted_category_id`, `predicted_subcategory_id`,
`predicted_root_cause_family`, `predicted_causal_change_id`,
`predicted_severity`, `recommended_team_id` — was `null` in every one of the
21 runs**, including cases like CS00191 where the correct component (`CM032`)
appeared repeatedly in retrieved evidence throughout the trace. Only
`evidence_sufficiency`, `overall_confidence`, `human_review_required`,
`recommended_next_action`, `evidence_summary`, and the free-text hypothesis
labels/descriptions are ever populated. Concretely, from `smoke_v2_rescored`
(12 cases):

| Field | prediction_rate |
|---|---|
| product / component / category / subcategory / root_cause / causal_change / severity / team | 0% (0/12) |
| evidence_sufficiency | 100% (12/12) |

This is not a scoring artifact -- it is the literal content of
`final_diagnosis.predicted_*` across every run, confirmed by direct
inspection, not just the aggregate. **This is the most important finding
of this validation pass**, and per spec section 57 it is reported here,
not acted on: no prompt, schema, or agent-logic change has been made in
response. It does mean that right now, product/component/category/
root-cause/causal-change/severity/team accuracy are all `n/a` (undefined,
not "0%" -- there is no wrong answer to measure, only an absent one)
whenever this baseline agent is evaluated -- a real, honest characteristic
of the current baseline, not a gap in the evaluator.

**Other confirmed findings, consistent across both experiments:**
- **Tool-error rate 100%**: every one of the 21 runs hit at least one
  hallucinated (nonexistent) tool-name call. Overwhelmingly the same
  hallucinated name: `get_system_logs` (26 of 35 total unknown-tool errors
  across all persisted runs), followed by `get_customer_info` (6),
  `get_system_status` (2), `get_customer_issues` (1) -- the model
  consistently wants a raw-log-style tool this toolset deliberately doesn't
  expose (spec's 14-tool catalog has `get_technical_signals`/
  `get_telemetry`/`get_service_health` instead). The harness's self-
  correction path handles this (the model recovers on its next call, per
  `BASELINE_AGENT_ARCHITECTURE.md`), so it does not stall investigations,
  but it means `clean_run_rate` is `0%` across every run scored so far.
- `evidence_sufficiency` accuracy: 22.2% (regression, n=9) / 16.7% (smoke,
  n=12) against the mapped Phase 2 ground truth -- low, though both samples
  are small.
- `human_review_agreement` (agent's own flag vs. the derived reference
  label): 55.6% (regression) / 25.0% (smoke).
- Mean tool calls per case: ~7.1-7.25 (budget is 10); zero
  `redundant_call` or `budget_exhaustion` events in either experiment.
- Mean cost: ~$0.0014/case; mean LLM latency ~10-12s/case (Together AI).

## Why no larger baseline experiment has been run yet

Spec section 51 stages experiment size (smoke -> engineering (50-100) ->
baseline (several hundred) -> locked benchmark) deliberately, and section 57
says document poor performance rather than immediately tuning around it.
Given the finding above, running a several-hundred-case `baseline`-kind
experiment right now would mostly re-confirm the same near-zero ID
prediction rate at a higher sample size, at real Together AI cost, without
adding much beyond tighter confidence intervals on the two fields that *are*
populated (`evidence_sufficiency`, `human_review_required`). Running one is
one command away (`--split dev --n 300 --kind baseline`) whenever it's
wanted; it has been deliberately deferred rather than run automatically.

## Reproducibility

Every experiment records `dataset_checksum_digest` (a fresh hash over Phase
1-3's frozen-baseline manifests, via `agent.graph_v2.checksums`), the full
agent version block (with a `homogeneous: false` fallback if the scored runs
turn out to have been generated under different code/model versions -- see
`run_experiment.py::_agent_version_fields_from_runs`), `evaluator_version`,
and `split_version`. As with Phase 5, the agent's own token sampling is not
bit-reproducible; the splits, ground truth, tool layer, and every metric
computed here are.
