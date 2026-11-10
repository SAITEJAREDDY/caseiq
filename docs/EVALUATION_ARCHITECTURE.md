# Phase 6 — Deterministic Evaluation Harness Architecture

## Why this exists

Phase 5 built an agent that investigates cases and produces a structured
`FinalDiagnosis`, but nothing checked that diagnosis against reality. Phase 6
is that missing half: a **deterministic** scorer (no LLM judge, no Jev) that
compares stored agent runs (`data/agent_runs/*.json`) against Phase 1-3's
hidden ground truth, and reports the result as many separate, inspectable
numbers rather than one blended score. This is the control condition Jev
(Phase 7+) will later have to beat.

## The two paths stay mechanically separate

```
RUNTIME (Phase 5, unchanged)                OFFLINE EVALUATION (Phase 6, new)

Agent (agent/agent_v2/)                     Stored run (data/agent_runs/*.json)
  |                                                |
  v                                                v
Tools -> Neo4j observable graph             agent/eval_v2/metrics.py
  |                                          (+ data/eval/eval_store.py --
  v                                           the ONLY sanctioned hidden-
data/agent_runs/<run_id>.json                truth accessor)
                                                    |
  NO import of agent.eval_v2                       v
  NO import of data.eval.eval_store           CaseEvalRecord
  (mechanically enforced --                        |
   agent/eval_v2/validate_boundaries.py)            v
                                              agent/eval_v2/aggregate.py
                                                    |
                                                    v
                                              data/experiments/<experiment_id>/
```

The direction that must never be crossed: `agent/agent_v2/*.py` (the
runtime loop, tools, schemas) must never import `agent.eval_v2` or
`data.eval.eval_store`, and never read anything under `data/experiments/`.
The reverse is expected and required: `agent/eval_v2/run_experiment.py`'s
`run_and_evaluate` mode *does* call `agent.agent_v2.loop.run_case()` to
produce fresh runs on demand (spec section 42's "run and evaluate" mode) --
that is the evaluator driving the agent from the outside, not the agent
reaching into the evaluator. `agent/eval_v2/validate_boundaries.py` checks
the one-directional constraint mechanically (import-graph scan + a
string-literal scan of `agent_v2/*.py` for `eval_v2`/`eval_store`/
`data/experiments`), and re-runs Phase 5's own `checksums.verify_or_die()`
first so a scoring run can never proceed against drifted Phase 1-3 data.

## Case-level records may hold resolved ground truth; only the runtime may not

`data/experiments/<id>/case_metrics.jsonl` embeds resolved hidden values
(e.g. the true root-cause name) next to the agent's prediction, by design --
spec section 38 explicitly wants a debuggable per-case drilldown artifact.
This is safe specifically because `data/experiments/` is never read by
`agent/agent_v2/`; the boundary is about *what the runtime can reach*, not
about hiding truth from every file on disk.

## Necessary, additive touches to frozen Phase 5 code

Two real defects were found while building this that would have silently
invalidated Phase 6 metrics if left alone. Both are purely additive --
neither changes what the agent decides or how it behaves:

1. **`model_provider` was hardcoded to `"groq"`** in
   `agent/agent_v2/trace.py`, regardless of which provider actually ran.
   Fixed to read `AGENT_MODEL_PROVIDER` from `config.py`. The evaluator
   (`agent/eval_v2/metrics.py::effective_model_provider`) also independently
   derives the true provider from `model_name` as a defensive fallback, so
   the handful of pre-fix runs already on disk still score correctly
   without editing files that exist.
2. **Repair events were invisible in the persisted trace.**
   `agent/agent_v2/loop.py` already silently normalizes malformed
   hypothesis arrays and repairs a non-compliant `submit_diagnosis` call,
   but recorded none of that. Spec sections 24/49/50 (contract-compliance
   metrics, repair-layer evaluation, the `clean_run` concept) are
   impossible without it. Fixed by adding a `repair_events: list[dict]`
   collected at the four existing call sites (hypothesis normalization,
   `submit_diagnosis` repair/fallback, forced-submit repair/fallback) and
   persisting it, plus two new version constants (`AGENT_LOOP_VERSION`,
   `REPAIR_LAYER_VERSION`) so a future loop/repair-layer change is
   distinguishable from a prompt or schema change.

Runs generated **before** this fix landed have no `repair_events` key.
`agent/eval_v2/contract.py::repair_summary` treats a missing key as
"repair status unknown" and `is_clean_run` never treats an unknown status as
clean -- it is excluded from `clean_run_rate`'s denominator entirely
(`process_and_contract.n_repair_status_unknown` reports how many).

Also additive: two new read-only functions in `data/eval/eval_store.py`
(`get_case_team_ownership`, `get_incident_relationship`), following the
exact pattern of the file's existing functions -- needed for routing and
incident-correlation metrics. No existing function there changed.

## Module map (`agent/eval_v2/`)

| Module | Responsibility |
|---|---|
| `config.py` | Versioning, confidence buckets, thresholds, split proportions/seed, paths |
| `ground_truth.py` | Wraps `data.eval.eval_store` + observable reference-table (product/component/category/root-cause/team name) lookups |
| `stratify.py` | `case_id -> {difficulty_archetype, evidence_sufficiency, incident_relationship, ...}` |
| `text_match.py` | Deterministic root-cause text matching (exact/containment tiers, taxonomy mapping for confusion matrices) |
| `evidence.py` | Critical/distractor retrieved-vs-cited, incident citation, unsupported-evidence pass-through |
| `contract.py` | Deterministic tool-error classification, repair-event summarization, `clean_run` definition |
| `metrics.py` | `evaluate_run(run) -> CaseEvalRecord` -- the per-case scorer |
| `confusion.py` | Confusion matrices (issue category, root cause, team, severity) |
| `aggregate.py` | Case records -> full experiment aggregate (slices, calibration, automation coverage, failure taxonomy, bootstrap CIs) |
| `registry.py` | Experiment creation/persistence, append-only `registry.jsonl` |
| `reports.py` | Aggregate dict -> Markdown report |
| `run_experiment.py` | CLI entry point (see `EVALUATION_EXPERIMENTS.md`) |
| `regression_cases.py` | The fixed 9-case permanent regression suite |
| `validate_boundaries.py` | The checks described above |

## Determinism

`metrics.py` and `aggregate.py` are pure functions: same stored run + same
frozen ground-truth CSVs + same code -> byte-identical output, verified by
`validate_boundaries.py`'s check 3 (calls `evaluate_run` twice on the same
run and diffs the JSON). The only randomized step anywhere in the harness is
`aggregate.py`'s percentile bootstrap, which uses a fixed seed
(`config.BOOTSTRAP_SEED`) specifically so it is reproducible too.

## What Phase 6 deliberately does not do

- No LLM-as-judge anywhere (spec section 56) -- root-cause text matching is
  two precisely-documented deterministic string rules, not a fuzzy score.
- No Jev (spec section 55).
- No tuning of the agent based on what this reveals (spec section 57) -- see
  `EVALUATION_EXPERIMENTS.md` for the smoke/regression-suite results and
  the honest limitations they surfaced.
- No single blended "CaseIQ score" (spec section 63) -- every dimension in
  `docs/EVALUATION_METRICS.md` stays independently reportable.
