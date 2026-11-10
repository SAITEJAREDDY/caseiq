# Phase 7 — Jev Primitive Evaluation Architecture

## Why this exists

Phases 5-6 established that the baseline autonomous agent rarely commits to
structured ID predictions. Phase 7 asks a narrower, prior question,
independent of any agent: how good is **Jev** — a typed, calibrated-
probability decision primitive from TypeSafe AI, not a chatbot — at the
individual classification/judgment decisions CaseIQ needs? This is offline,
decision-level evaluation only. No runtime integration (that's a later
phase), no agent-trace judging (Phase 8), no verifier/guardrail role.

## Jev API — verified against primary sources, not assumed

Before writing any code, I independently verified the current API across
13 primary-source fetches (PyPI, GitHub, the full `docs.typesafe.ai` page
tree via its own `llms.txt` index, and a raw call to PyPI's own JSON API) —
an initial web-research pass came back suspiciously well-matched to my own
prompt wording, so I re-verified everything myself before trusting it.

- **Endpoint**: `POST https://api.typesafe.ai/v1/systemone`,
  `Authorization: Bearer <TYPESAFE_API_KEY>`, body
  `{"state": <str|object|array>, "model": "jev-latest", "questions": {key: Question, ...}}`.
  `state` may be a structured JSON object with named fields — confirmed via
  `docs.typesafe.ai/concepts/state.md` — which is exactly what
  `state_builder.py`'s decision-specific projections need.
- **Three primitives**:
  - `Choice` — `{"type":"choice","instructions":str,"criteria":{option_key: description_or_null, ...}}`
    (up to 255 options) → `{"choice":str,"confidence":float,"probabilities":{option:float,...}}` (sums to 1).
  - `Score` — `{"type":"score","instructions":str,"criteria":[level0_desc,...]}` (2-10 ordered levels)
    → `{"score":float,"confidence":float,"legend":{"0":...},"probabilities":{"0":p0,...}}`. Not used by Phase 7's
    first tranche (none of the six decisions needed an ordinal scale over Choice/Noul), but available for a later
    severity primitive.
  - `Noul` — `{"type":"noul","instructions":str,"criteria":{"true":desc,"false":desc}?}` →
    `{"noul": 0.0-1.0}` — no separate confidence field; the value itself is the full probability.
- **Batching**: multiple named, mixed-type questions in one call, one `answers` dict keyed the same way —
  "adding questions barely changes response time." Exercised by `decisions.py::run_decisions_batched` for the
  parallel-question experiment (spec section 47).
- **Model versioning**: `jev-latest`/`jev-preview` both currently resolve to `jev-1.13.0`; every persisted decision
  record stores the response's own `model` field (the exact resolved id), not just the alias requested.
- **Pricing**: $0.042/million input tokens; output tokens are free.

## A near-miss dependency incident (already resolved)

The official `typesafe-sdk` package was installed to inspect it directly.
Its pin `tenacity>=9.0.0` silently upgraded the environment's `tenacity`
from `8.5.0` to `9.1.4`, which broke `langchain==0.2.16`/
`langchain-core==0.2.43`/`langchain-community==0.2.16`/`streamlit==1.35.0`'s
shared pin of `tenacity<9` — confirmed by `pip`'s own conflict output. Fully
reverted (uninstalled `typesafe-sdk`/`httpx2`/`httpcore2`/`truststore`/the
upgraded `tenacity`, reinstalled `tenacity==8.5.0`, verified `pip check`
clean and the live app + `agent_v2`/`eval_v2` import cleanly) before writing
any Phase 7 code. **Consequence**: `agent/jev_v2/client.py` is a small,
dependency-free `requests`-based client against the REST API directly —
exactly the same pattern Phase 5 used for Together AI
(`agent/agent_v2/together_chat.py`) after `langchain-openai` caused an
equivalent, larger incident. `requests` is already a project dependency;
nothing new was added to `requirements.txt`.

## Data flow and the boundary

```
OBSERVABLE BUILDER (never imports hidden truth)
  agent/agent_v2/tools.py's raw query functions (reused directly, not
  re-derived) + agent/agent_v2/time_gate.py::SimClock-style `as_of` gating
        │
        ▼
  state_builder.py → candidates.py → questions.py
        │
        ▼
  client.py::JevClient.system_one()  ── or ──  llm_baseline.py (Together AI)
        │
        ▼
  raw decision record (no ground truth anywhere in it)
        │
        ▼  (offline, separately)
  scoring.py  ←── agent.eval_v2.ground_truth (hidden truth)
        │
        ▼
  scored decision record → aggregate.py → registry.py → data/experiments/
```

`scoring.py` is the **only** module in `agent/jev_v2/` allowed to import
`agent.eval_v2.ground_truth` or `data.eval.eval_store`. Every other module
listed above is checked by `validate_boundaries.py`'s AST import scan. On
top of the static check, `client.py::assert_no_leakage()` is a **live
runtime guard**: every payload about to be sent to Jev or the LLM baseline
is scanned for `agent/graph_v2/validate_graph.py`'s existing
`BANNED_SUBSTRINGS` list (reused verbatim, not reinvented) and the call is
refused — not warned, refused — if anything matches.

## Why Choice/Noul scoring is exact-ID matching, not fuzzy text

Phase 6 had to build `text_match.py`'s two-tier fuzzy matching because
Phase 5's agent free-texts `predicted_root_cause_family`. Jev and the LLM
baseline are never asked to generate a string — they choose from a
predefined candidate set of real domain IDs (spec section 3's "do not ask
Jev to generate strings"). This means `scoring.py` can score root
cause/category/team/causal-change as a clean exact-ID match against
`gt_root_cause_id`/`gt_issue_category_id`/etc. — a real structural
advantage of the primitive-decision design over free-text generation, and
one reason this comparison is worth making at all.

## Reuse of Phase 5 and Phase 6, not a parallel framework

- **Observable data access**: `state_builder.py` calls `agent/agent_v2/tools.py`'s
  raw query functions directly (`q_case_context`, `q_technical_signals`,
  `q_recent_changes`, `q_telemetry`, `q_component_topology`,
  `q_active_incidents`, `q_customer_deployment`, `q_configuration_history`,
  `q_deployment_history`, `q_similar_cases`, `q_team_capability`) — not the
  LangChain `StructuredTool` wrappers, just the plain functions, which are
  already time-gated and bounded. Zero new Cypher was written for Phase 7.
- **Splits**: `agent.eval_v2.splits.case_ids_for_split()` — the same locked
  dev/validation/test partition Phase 6 generated, unmodified.
- **Statistics**: `agent.eval_v2.aggregate`'s `calibration_table`,
  `brier_and_ece`, `false_confident_rate`, `_bootstrap_ci`, `_mean` are
  called directly against Jev/LLM decision records via `(confidence_fn,
  correct_fn)` closures — they were already generic over record shape, so
  no reimplementation was needed.
- **Experiment ecosystem**: `agent.eval_v2.registry.new_experiment_id` and
  `dataset_checksum_digest` are reused directly; Phase 7 experiments write
  into the exact same `data/experiments/` directory and append to the same
  `registry.jsonl` Phase 6 uses, tagged with a new `experiment_type` field
  (`"jev_primitive"` / `"llm_primitive_baseline"`) rather than forking a
  second registry.
- **Regression suite**: `agent/jev_v2/regression_decisions.py` re-exports
  Phase 6's own fixed 9-case list (`agent.eval_v2.regression_cases`) rather
  than defining a second one.

No file under `agent/agent_v2/`, `agent/eval_v2/`, `agent/graph_v2/`, or any
`data/raw_v2|phase2|phase3` CSV was modified for Phase 7.

## Module map (`agent/jev_v2/`)

| Module | Responsibility |
|---|---|
| `config.py` | Jev/TypeSafe API settings, question/context/candidate-generation versions (per decision), LLM-baseline model config, pricing assumptions |
| `client.py` | `JevClient` (raw `requests`, retry/backoff on 429), `choice_question`/`score_question`/`noul_question` builders, the leakage guard |
| `reference_data.py` | Observable-only reference-table reads (issue categories, root causes, product→component→subcategory→root-cause chain) |
| `state_builder.py` | Decision-specific state projections; the 5 root-cause context-ablation levels |
| `candidates.py` | Per-decision candidate-set builders, each observable-rule-based and versioned (causal change: v2 and v3) |
| `questions.py` | The versioned question catalog |
| `decisions.py` | Orchestrates state+candidates+question → one Jev call → raw record; also the batched-question path |
| `llm_baseline.py` | The same orchestration against Together AI's Llama-3.3-70B-Instruct-Turbo; attempt-by-attempt contract tracking with one bounded repair |
| `scoring.py` | The only module allowed to import hidden truth |
| `aggregate.py` | Scored records → per-decision-type report, reusing Phase 6's generic statistics |
| `registry.py` | Persists into `data/experiments/`, reusing Phase 6's id/digest helpers |
| `reports.py` | Markdown rendering, including the Jev-vs-LLM comparison table |
| `run_experiment.py` | CLI (see `JEV_EVALUATION.md`), including `--frozen-config` and the validation/test split guards |
| `compare_jev_llm.py` | Paired Jev-vs-LLM comparison: input-parity check, per-decision metrics, McNemar test, paired bootstrap CI (JEV-018) |
| `compare_causal_change.py` | Read-only comparison of two stored causal-change experiments (v2 vs v3, canonical vs opaque keys) |
| `analyze_causal_candidates.py` | Offline candidate-recall measurement, v2 vs v3, with the structural-artifact diagnostics (no Jev call) |
| `paired_stats.py` | Exact McNemar p-value and paired bootstrap for the comparison reports |
| `frozen_config.py` | Loads and verifies the Stage B frozen configuration and its manifest |
| `parallel_runner.py` | Concurrent, checkpointed orchestration used for Stage C: builds each decision's input once, sends it to Jev and the LLM, scores in the calling thread |
| `stage_c_report.py` | Pre-registered Stage C analysis over stored experiments (read-only; no API, graph or hidden-truth call) |
| `stage_c_posthoc.py` | Labelled post-hoc descriptive analysis of the stored Stage C decisions; never feeds the capability classification |
| `stage_c_audit.py` | Read-only audit of the Stage C artifacts against the frozen configuration and the authoritative dev-versus-validation tables built from stored registry values |
| `threshold_policy.py` | `threshold_policy_v1`: selects confidence thresholds on validation only, never relaxing itself; its output is frozen in the locked configuration |
| `locked_benchmark.py` | Verification of the sealed locked-benchmark freeze, the pinned import closure, the environment check, the explicit-id guard and the one-shot run-state marker |
| `freeze_locked_benchmark.py` | Builds and seals `locked_benchmark_frozen_v1` (two separate steps; refuses to overwrite or to run after a locked run started) |
| `opaque_control.py` | Validation-only opaque-key control for causal change (JEV-025): hashed option keys, byte-level input-equivalence checks, runner for the opaque arm and the conditional canonical replicate; outside the sealed source list |
| `opaque_control_report.py` | The pre-registered analysis of that control (rules R1 to R3, paired outcomes, groups, integrity checks); read-only |
| `supersede_locked_benchmark.py` | Writes the supersession record for the v1 freeze (refuses unless the control's Jev verdict is material); changes no sealed file |
| `locked_report.py` | The pre-registered analysis of the locked run (validation as reference, frozen thresholds, co-primary metrics), with a rehearsal mode on stored validation data |
| `freeze_stage_b.py` | Writes the immutable freeze manifest |
| `compare_experiments.py` | Stage B v1 vs v2 comparison (Codex) |
| `regression_decisions.py` | Re-exports Phase 6's fixed 9-case regression suite |
| `validate_boundaries.py` | The checks described above |

## Versioning added for Stage B v3 (JEV-013 / JEV-018)

- **Per-decision candidate-generation versions** live in
  `config.CANDIDATE_GENERATION_VERSIONS` (issue category v1, root cause v2,
  causal change **v3**, owning team v2, evidence sufficiency v1, incident
  relationship v1). Older versions stay callable — causal change v2 is kept
  verbatim so Stage B v1/v2 remain reproducible — and every decision record
  stores its `candidate_generation_version`. `CANDIDATE_STRATEGY_VERSION` is
  now only a bundle label (`v3` = the v2 bundle plus causal change v3); the
  per-decision map is authoritative.
- **Evaluator v2.1** is additive reporting: `scoring.py`'s per-decision
  semantics are unchanged. Stored v2 `experiment.json` files keep their
  original values; comparisons re-aggregate stored records in memory.
- **LLM contract handling** records every attempt (`attempts`), whether the
  first attempt was valid, the failure kind (`malformed_json`,
  `missing_answer`, `invalid_option`, `invalid_confidence`,
  `invalid_probability`, `request_failed`), whether a repair was needed and
  whether it worked, and whether the decision was unrecoverable. One repair
  re-prompt is allowed (`LLM_REPAIR_MAX_ATTEMPTS`); the strict first-attempt
  accuracy counts a repaired decision as a failure, so repair cannot hide one.
  Jev returns native typed results, so it has no parse or option failures by
  construction (only transport errors, which are counted).
- **Cost** is computed from provider-returned token counts summed across
  attempts; per-token prices are versioned assumptions in `config.py`
  (`PRICING_VERSION`). Token counts come from different tokenizers, so
  they are not comparable across Jev and the LLM.
- **Freezing**: `data/eval/jev/stage_b_frozen_v1.json` (settings) plus
  `stage_b_frozen_v1_manifest.json` (hashes of the config, split file, every
  model-input-defining source file, the Phase 1–3 digest and the cohort ids).
  `run_experiment --frozen-config` takes every version from the file, refuses
  overrides, and refuses to run if anything drifted. See
  `docs/JEV_STAGE_B_FREEZE.md`.
- **Split guards**: `--split test` needs `--kind locked_benchmark`;
  `--split validation` needs `--kind validation`. The Phase 7 boundary
  validator runs both refusals without reaching the network.

