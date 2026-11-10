# Phase 7 — Stage B Frozen Configuration

`stage_b_frozen_v1`, frozen 2026-09-23. This is the exact configuration a later
Stage C (validation) run must use, unmodified. Nothing here is "auto" or
"latest": every version is explicit, and a mismatch stops the run.

Stage C was run once on the validation split on 2026-09-23 with this
configuration, unmodified; the report is `JEV_STAGE_C_VALIDATION.md`. The locked
test split has not been read by any Phase 7 experiment.

## Files

| File | Role |
|---|---|
| `data/eval/jev/stage_b_frozen_v1.json` | The per-decision settings (this document renders them) |
| `data/eval/jev/stage_b_frozen_v1_manifest.json` | sha256 of the config, the split file, and the model-input-defining source files; the Phase 1-3 dataset digest; the dev cohort ids; the reference experiments |
| `agent/jev_v2/frozen_config.py` | Loader and verifier |
| `agent/jev_v2/freeze_stage_b.py` | Writes the manifest; refuses to overwrite one |

## Frozen versions

| Decision | Primitive | Question | Candidates | Context |
|---|---|---|---|---|
| issue_category | choice | `issue_category_v1` | `candidate_generation_v1` | n/a |
| root_cause | choice | `root_cause_v1` | `candidate_generation_v2` | v4_operational |
| causal_change | choice | `causal_change_v1` | `candidate_generation_v3` | n/a |
| owning_team | choice | `owning_team_v1` | `candidate_generation_v2` | n/a |
| evidence_sufficiency | choice | `evidence_sufficiency_v2` | `candidate_generation_v1` | n/a (state projection v2) |
| incident_relationship | noul | `incident_relationship_v1` | `candidate_generation_v1` | n/a |

Context version applies to root cause only.

| Setting | Frozen value |
|---|---|
| Jev model requested (pinned) | `jev-1.13.0` (resolved at freeze: `jev-1.13.0`) |
| Jev API | `/v1/systemone` (v1) |
| LLM baseline | `meta-llama/Llama-3.3-70B-Instruct-Turbo`, temperature 0.1, max tokens 400, 1 repair attempt |
| Evaluator | `v2.1` |
| Question set / candidate bundle | `v2` / `v3` |
| Pricing assumptions | `2026-09-23` |
| Split | `case_splits_v1` (file sha256 in the manifest) |
| Dev reference cohort | first 100 dev case ids, decision time = case `created_date` |
| Causal-change option keys | canonical ids |

## Why each setting

- **Root cause context v4.** On dev-100, v5 (graph) reached 46% and v4
  (operational) 45%, one case apart, with v4 sending about 18% fewer input tokens
  (1,479 vs 1,807 mean) at lower latency; v3 reached 32%. A second v4 run on
  identical inputs scored 48% (94 of 100 answers unchanged), so the v4/v5 gap is
  inside run-to-run noise.
  v4 is the preferred default on cost, and Stage C validates that choice rather
  than tuning it.
- **Root cause and owning team candidates v2.** They raised recall to 100% on
  dev-100 (68% and 61% before) at some cost in conditional accuracy. The cutoffs
  (top 15 plus `RC40`; top 12 teams) were chosen on that same cohort, so the
  recall is in-sample until validated.
- **Causal change candidates v3.** Fixes JEV-013: deployment-type causes were
  never offered under v2 (6 of 100 dev cases). Recall 94% to 100%.
- **Evidence sufficiency v2 kept.** Accuracy is low (Jev 14%, LLM 43%, against a
  94% majority baseline), but the v1 result was a state-projection mismatch that
  v2 corrects. The remaining weakness is a measured result Stage C should test,
  not something to keep tuning on dev.
- **Issue category and incident relationship.** Unchanged since Stage B; not
  retuned.
- **Jev model pinned.** The explicit version id is accepted by the API and
  resolved identically to the `jev-latest` alias at freeze, so alias drift cannot
  change results between Stage B and Stage C.
- **Canonical change ids.** Stage B v1/v2 and the v3 rerun all used them, so the
  freeze keeps them for comparability. The id-number range separates true from
  non-true candidates in dev-100, and the opaque-key control found no reliance on
  it (Jev 92% vs 91%; LLM 80% and 83% vs 87%). See `JEV_EVALUATION.md`.

## Reference experiments (all dev-100)

| Role | Experiment | Type |
|---|---|---|
| causal_change_v3_jev | `exp_causal_change_v3_dev100_20260923T171806Z_f96a8bb8` | jev_primitive |
| frozen_settings_jev | `exp_stage_b_final_dev100_jev_20260923T173652Z_c5a41b24` | jev_primitive |
| frozen_settings_llm | `exp_stage_b_final_dev100_llm_20260923T173653Z_766e73ff` | llm_primitive_baseline |
| control_opaque_keys_jev | `exp_causal_change_v3_opaque_keys_dev100_jev_20260923T172653Z_cc0c9491` | jev_primitive |
| control_opaque_keys_llm | `exp_causal_change_v3_opaque_keys_dev100_llm_20260923T172653Z_9076cf7d` | llm_primitive_baseline |
| control_repeat_jev | `exp_causal_change_v3_repeat_dev100_jev_20260923T174042Z_aee6568c` | jev_primitive |
| control_repeat_llm | `exp_causal_change_v3_repeat_dev100_llm_20260923T174042Z_42cf10d8` | llm_primitive_baseline |

The two `frozen_settings` runs were made with `--pre-freeze` (versions checked
before the manifest existed). No frozen source file was modified after they were
run; the manifest hashes those exact files.

## How Stage C was run

```bash
python3 -m agent.jev_v2.run_experiment --name stage_c_validation --kind validation \
    --split validation --compare-llm --frozen-config stage_b_frozen_v1 \
    --workers 8 --protocol docs/JEV_STAGE_C_PROTOCOL.md
```

`--workers` (concurrent orchestration, `parallel_runner.py`) and `--protocol`
(records the pre-registered protocol's hash) change scheduling and provenance,
not what is sent to either model.

No `--pre-freeze`, and no override flags (`--context-version`,
`--candidate-version`, `--causal-key-mode`, `--jev-model` are refused with
`--frozen-config`). The run first verifies the working tree against the
manifest; any of the following stops it with a specific message: a changed
question or candidate version, a changed source file, a changed split file, a
changed Phase 1-3 dataset digest, or a changed cohort id list. `--split
validation` is also refused unless `--kind validation` is given, and `--split
test` unless `--kind locked_benchmark` is given.

Hashed source files:

- `agent/jev_v2/candidates.py`
- `agent/jev_v2/questions.py`
- `agent/jev_v2/state_builder.py`
- `agent/jev_v2/reference_data.py`
- `agent/jev_v2/scoring.py`
- `agent/jev_v2/decisions.py`
- `agent/jev_v2/llm_baseline.py`
- `agent/jev_v2/client.py`
- `agent/agent_v2/tools.py`

A change to any of them requires a new `freeze_version`, not an edit.

## What is not frozen

Jev and the LLM are not bit-deterministic. Measured on dev-100, Jev returned the
same answer on 93% to 100% of decisions across repeated runs on identical inputs
(owning team and root cause least stable). LLM sampling is temperature 0.1 with
no seed. Stage C should be read with that spread in mind; it ran once per system,
so validation carries no repeat measurement.

## Development-only capability map

Every line is measured on the 100-case dev cohort, one Jev run and one LLM run
per decision unless noted. It is a map of where each primitive stands, not a
recommendation to use Jev everywhere and not a validated result. Stage C
measured these decisions on validation: see `JEV_STAGE_C_VALIDATION.md`, which
supersedes this map for any generalization claim. The locked-benchmark
configuration that follows Stage C is derived from this freeze:
`locked_benchmark_frozen_v1` (see `JEV_STAGE_C_REVIEW.md`); that freeze was later recorded as
superseded before use (`JEV_OPAQUE_KEY_CONTROL.md`).

| Decision | Jev | LLM baseline | Reading |
|---|---:|---:|---|
| Issue category | 73% | 76% | **Comparable.** No significant difference (p=0.61). Both moderate. |
| Root cause (v4) | 48% | 24% | **Jev stronger**, still modest in absolute terms. |
| Causal change (v3) | 91-92% | 80-87% | **Jev stronger** in 3 of 3 paired comparisons (+4 to +12; firm in one). Recency-vs-causality untested. |
| Owning team (primary / acceptable) | 36% / 49% | 11% / 22% | **Jev stronger, both weak.** |
| Evidence sufficiency | 14% | 43% | **Both weak; Jev weaker.** Both far below the 94% majority baseline. |
| Incident relationship | 70.6% (AUC 0.69) | 82.4% (AUC 0.68) | **Insufficient sample** (n=17). |

Jev returned valid typed output on every call and cost about one sixteenth of
the LLM per decision at roughly one fifth of the median latency; the LLM also
produced a valid first attempt every time, so contract reliability did not
separate them.
