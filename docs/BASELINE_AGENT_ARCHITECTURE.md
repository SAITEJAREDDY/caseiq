# Phase 5 — Baseline Agent Architecture

## Lifecycle

```
Case ID
  │
  ▼
get_case_context (implicit, harness reads it to seed the SimClock)
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ LOOP (up to MAX_TOOL_CALLS steps):                        │
│   1. LLM call: model sees system prompt + full message    │
│      history (older tool results collapsed, see below)    │
│      + 15 bound tools (14 diagnostic + submit_diagnosis)  │
│   2. Model calls exactly one tool, carrying its current    │
│      hypothesis state on every call                        │
│   3. If submit_diagnosis: loop ends, stop_reason=          │
│      "model_submitted"                                     │
│   4. Else: harness executes the tool (read-only Cypher,     │
│      as_of = current sim_clock value), advances sim_clock,  │
│      appends the result, records a trace step               │
└─────────────────────────────────────────────────────────┘
  │
  ▼ (if budget exhausted without submit_diagnosis)
Forced final call: submit_diagnosis is the ONLY bound tool,
harness tells the model to wrap up now -> stop_reason=
"tool_budget_exhausted"
  │
  ▼
Citation check (every evidence ID the model cited must have
appeared in a real tool result this run)
  │
  ▼
Persist run -> data/agent_runs/<run_id>.json
```

Implementation: `agent/agent_v2/loop.py::run_case()`.

## Why one LLM call per step, hypothesis state on every tool call

An earlier design considered a separate `update_hypotheses` tool call
interleaved with diagnostic tool calls. Rejected: it doubles LLM calls for
no real benefit. Instead, **every diagnostic tool's argument schema shares a
`StepContext` mixin** (`hypotheses: list[str]`, `rationale: str`) that the
model must fill in on every call — restating its complete current belief
state as compact `"label:confidence"` strings. This gives a fully structured,
auditable trace of how confidence evolved, without needing hidden
chain-of-thought (spec §23), at the cost of one field the model fills in
alongside its normal tool choice — not an extra round-trip.

`submit_diagnosis` (the terminal tool) overrides this with the richer
`list[HypothesisUpdate]` form (label, confidence, supporting/contradicting
evidence IDs, status) — safe to make richer there because that schema is
bound only once, not multiplied across 14 other tool definitions.

## Model provider: Together AI, not the live app's Groq

The live app uses `ChatGroq(model_name="openai/gpt-oss-120b")`
(`agent/llm_client.py`). The baseline agent's first working version reused
that exact model, per the initial reasoning that gpt-oss-120b is
purpose-built for agentic tool use and the spec's own "use a model already
practical within the project's current stack." That reasoning under-weighted
one fact: **Groq's free/on-demand tier caps `openai/gpt-oss-120b` at 8000
tokens/minute**, which a 15-tool agentic loop with growing conversation
history burns through in a handful of steps. Two real failures during
development, fixed in order, before the provider itself was reconsidered:

1. **Schema duplication.** The first version gave every tool's argument
   schema a `list[HypothesisUpdate]` (nested object) field. Since the full
   JSON schema for all 15 bound tools is sent on every call, and each tool's
   schema independently duplicates whatever `StepContext` contains, the
   *tool schemas alone* measured ~10,088 tokens — before any system prompt
   or conversation history, already over Groq's entire per-minute budget.
   Switching to the flat `list[str]` form for the 14 non-terminal tools
   dropped this to ~4,161 tokens (still true today, and still worth keeping
   regardless of provider — it also cuts real per-call cost).
2. **Unbounded conversation growth.** Even with lean schemas, a real 10-step
   investigation's accumulated tool-result history grew large enough that by
   the final (forced-submit) call, the model's response was cut off
   mid-JSON by `max_tokens`, producing an unparseable tool call. Fixed with
   `KEEP_LAST_N_FULL_TOOL_RESULTS` (`agent/agent_v2/config.py`): only the
   most recent 4 tool results are sent to the model in full; older ones are
   collapsed to a one-line placeholder in the *model-facing* message list
   (`loop.py::_trimmed_for_llm`) while the full, untrimmed history is still
   what gets persisted to the trace file. Also kept regardless of provider —
   bounded context is good practice, not a Groq-specific workaround.

Even after both fixes, a real batch run hit an **18-minute forced backoff**
on a single request under Groq's free tier — the throughput, not just the
per-request size, is the binding constraint for this workload. Together AI
is already integrated in this project (`data/generators/llm_client.py`,
real paid usage for Phase 1-3 narrative generation) with no equivalent
throttle, so it is the default provider
(`AGENT_MODEL_PROVIDER=together`, `meta-llama/Llama-3.3-70B-Instruct-Turbo`
by default — `AGENT_MODEL_PROVIDER=groq` still works for comparison).
Since `langchain-openai` (the natural way to point LangChain at any
OpenAI-compatible endpoint) currently requires `langchain-core>=1.x` and
this project pins `langchain==0.2.16`/`langchain-core==0.2.43` for the live
app, installing it force-upgrades shared dependencies and breaks
`langchain-groq`/`langchain`/`langchain-community` project-wide — confirmed
by doing it once and having to revert. Instead,
[`agent/agent_v2/together_chat.py`](../agent/agent_v2/together_chat.py)
implements the narrow `.bind_tools(tools).invoke(messages)` surface the loop
actually needs, directly over `requests` (the same raw-HTTP pattern already
proven in `data/generators/llm_client.py`) plus `langchain_core`'s own
`AIMessage`/`convert_to_openai_tool` — no new pinned-version-incompatible
dependency.

## Tolerating a less strictly tool-call-compliant model

Llama-3.3-70B-Instruct-Turbo is noticeably less consistent than gpt-oss-120b
was at strictly honoring a bound tool's JSON schema. Observed in testing:
occasionally hallucinating a plausible-sounding but non-existent tool name
(e.g. `get_system_logs`), occasionally double-encoding an array-typed
argument as a JSON string instead of a true array, and on the terminal call,
using a hypothesis `status` value outside the declared enum (`"open"`
instead of `"active"/"rejected"/"confirmed"`) or omitting a required field.
None of these are graph/tool-layer bugs — they're model output-formatting
slips — and none require a different model to make the baseline usable, just
a harness that doesn't crash on them:

- **Unknown tool name:** the tool-not-found error message now lists every
  valid tool name, so the model can self-correct on its next call (it
  reliably does, in testing).
- **Malformed `hypotheses` on regular tool calls:** `_normalize_hypotheses()`
  (`loop.py`) accepts a true list, a JSON-string-encoded list, or a bare
  string, and always returns a clean `list[str]` — both for the trace record
  and for what actually gets sent into the tool's own schema validation.
- **Malformed `submit_diagnosis` args:** `_repair_final_diagnosis_args()`
  (`loop.py`) is tried once, after a direct `FinalDiagnosis(**args)`
  validation failure — it coerces out-of-enum hypothesis statuses to
  `"active"`, fills a missing `overall_confidence` from the max hypothesis
  confidence, and fills a missing `evidence_summary` from the model's own
  `rationale`. Only if repair *also* fails does the run fall back to
  `_fallback_diagnosis()` (`human_review_required=True`, `evidence_
  sufficiency="insufficient"`) — a legitimate, honestly-labeled outcome
  rather than a crash.

A 429/rate-limit error can still occur transiently under load from either
provider; `agent/agent_v2/llm.py::invoke_with_retry` retries with the
server's suggested delay (or exponential backoff), mirroring the existing
retry pattern in `data/generators/llm_client.py`.

## Time-gating (`time_gate.py`)

`SimClock` starts at the case's own `created_date` and advances by a fixed
15-simulated-minutes step after every tool call — never derived from any
hidden field (in particular never from `gt_resolution_duration_hours`).
`as_of` is read from the clock at call time and is **not** an argument the
model can set — each tool closure reads it directly from the harness-owned
`SimClock` instance passed into `make_tools()`. This is what makes "a query
made before a hypothesis confirmation must not see later evidence" (spec
§43) true by construction rather than by convention.

## Stopping conditions and budgets

| Condition | Trigger | `stop_reason` |
|---|---|---|
| Confident diagnosis / insufficient evidence / human review | model calls `submit_diagnosis` | `model_submitted` |
| Tool budget exhausted | `MAX_TOOL_CALLS` (default 10) reached without a submit | `tool_budget_exhausted` (forced final call made) |
| Model won't call a tool | two consecutive non-tool-call responses | `agent_failed_to_call_tool` (fallback diagnosis, `human_review_required=True`) |

"Confident diagnosis," "insufficient evidence," and "human review required"
are **not separate tools or code paths** — they are just different field
values the model chooses on the same `submit_diagnosis` call
(`evidence_sufficiency`, `human_review_required`). This was a deliberate
simplification: it keeps the terminal-tool schema single and lets the model
express partial states (e.g. fairly confident about a root cause but
`evidence_sufficiency: "partial"` because the directly relevant telemetry
was unavailable — spec §31's example).

Redundancy: identical `(tool_name, args)` pairs are tracked per run
(`_args_key`, ignoring the hypotheses/rationale fields); a 3rd identical
call (`MAX_REPEATED_SAME_TOOL = 2`) is intercepted with a synthetic
"redundant, no new information" result instead of re-querying Neo4j — logged
with `redundant: true` in the trace rather than silently hidden, so
inefficiency remains measurable (spec §27).

## Final output schema (`FinalDiagnosis`, `schemas.py`)

Every prediction field is paired with its own `Optional[float]` confidence
and is independently nullable — the model is told (system prompt) to leave
a field unset rather than guess. `evidence_sufficiency` and
`human_review_required`/`human_review_reason` are separate from
`overall_confidence` (spec §31: a fairly-confident hypothesis can still
coexist with insufficient evidence). `recommended_next_action` is free text
but system-prompt-constrained to non-destructive support actions (inspect,
route, validate, request, escalate — never a production change).

## Citation validation

`_collect_evidence_ids()` walks every tool result this run and collects
every value returned under an `evidence_id` key. After the model submits,
every ID in any hypothesis's `supporting_evidence`/`contradicting_evidence`
and `predicted_causal_change_id` (if set) is checked against that set.
Anything not found is recorded in `citation_violations` in the persisted
run — flagged, not silently dropped, so a future eval pass can penalize
fabricated citations specifically (spec §29).

## Trace persistence

See [`AGENT_EXPERIMENTS.md`](AGENT_EXPERIMENTS.md) for the run/CLI
mechanics. Every run is versioned (`prompt_version`, `toolset_version`,
`output_schema_version`, `graph_version`) so later experiments can tell
"agent v1" apart from "agent v2" without overwriting history (spec §36).
