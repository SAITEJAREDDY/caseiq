# Phase 5 — Running Agent Experiments

## Prerequisites

The same `NEO4J_V2_*` credentials Phase 4 uses (`.env`), pointing at the
standing 2,500-case graph. No new environment variables are required; the
agent reuses `config.settings.GROQ_API_KEY`/`GROQ_MODEL` read-only.

## Running one case

```bash
python3 -m agent.agent_v2.run_single --case-id CS00191
```

Prints the full step-by-step trace (tool, args, hypotheses, rationale,
compact result, latency, status) followed by the final structured
diagnosis, then persists the run and prints its path. This is the primary
debugging mode — use it to inspect exactly what the agent saw and decided
at each step.

## Running a batch

```bash
# explicit case list (recommended -- lets you target specific scenario types)
python3 -m agent.agent_v2.run_batch --case-ids CS00191 CS00002 CS00003

# first N cases by case id
python3 -m agent.agent_v2.run_batch --n 10
```

Each case's run persists independently (a failure on one case does not stop
the batch). Prints a per-case one-line summary (stop reason, tool/LLM call
counts, token usage, evidence sufficiency, confidence, human-review flag,
any citation violations) plus a JSON summary at the end.

Do not run all 2,500 cases — spec §40 explicitly scopes Phase 5 to small,
controlled batches (10s of cases, not the full graph). A representative
spread across `gt_difficulty_archetype` values and evidence-sufficiency
levels is more useful than raw volume; see the case-selection approach
below.

### Picking representative cases

Archetype/evidence-richness are hidden fields — using them to *select*
which case IDs to run through the agent (a dev-time choice about what to
test) is fine and does not touch the runtime path; the agent itself never
sees these fields. Example (reads `case_ground_truth.csv`/
`phase2_ground_truth.csv`/`incident_cases.csv` directly, outside any
`agent/agent_v2/` module):

```python
import csv
gt = {r["id"]: r for r in csv.DictReader(open("data/raw_v2/case_ground_truth.csv"))}
clear_cases = [cid for cid, row in gt.items() if row["gt_difficulty_archetype"] == "clear"]
```

## Selecting the model

`agent/agent_v2/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `AGENT_MODEL_PROVIDER` | `together` | `together` or `groq` |
| `AGENT_MODEL_NAME` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` (or `config.settings.GROQ_MODEL` if provider is `groq`) | override to compare models later |
| `AGENT_TEMPERATURE` | `0.1` | low, for a reproducible baseline |
| `AGENT_MAX_TOKENS` | `1300` | completion budget per LLM call |
| `AGENT_MAX_TOOL_CALLS` | `10` | investigation budget |
| `AGENT_MAX_REPEATED_SAME_TOOL` | `2` | redundancy threshold |
| `AGENT_SIM_CLOCK_STEP_MINUTES` | `15` | simulated time advance per tool call |

All overridable via environment variables without code changes, per spec
§38's "make the model configurable" — Phase 5 does not build multi-model
routing, just a single configurable baseline. Uses the project's existing
`TOGETHER_API_KEY` (already in `.env` for Phase 1-3 narrative generation) or
`GROQ_API_KEY`/`GROQ_MODEL` from `config.settings`, read-only — see
`BASELINE_AGENT_ARCHITECTURE.md`'s "Model provider" section for why
Together AI is the default and how `agent/agent_v2/together_chat.py` talks
to it without touching this project's pinned `langchain` versions.

## Where traces are stored

`data/agent_runs/<run_id>.json` — one file per run (run metadata, full
step-by-step trace, token usage, final diagnosis, citation violations).
`data/agent_runs/runs_index.jsonl` — one append-only line per run
(`run_id`, `case_id`, `stop_reason`, `overall_confidence`,
`evidence_sufficiency`, `human_review_required`, `num_tool_calls`,
`citation_violations`) for fast listing without opening every run file:

```bash
python3 -c "
import json
for line in open('data/agent_runs/runs_index.jsonl'):
    r = json.loads(line)
    print(r['case_id'], r['stop_reason'], r['overall_confidence'], r['human_review_required'])
"
```

## How costs/latency are measured

Every LLM call's `token_usage` (prompt/completion/total) is summed into
`token_usage` on the persisted run, alongside `num_llm_calls` and
`num_tool_calls`. `approx_cost_usd` is computed from a configurable
placeholder rate (`APPROX_USD_PER_1K_INPUT_TOKENS`/`_OUTPUT_TOKENS` in
`config.py`) and is explicitly labeled an estimate, not exact provider
billing — update the rate constants from your Groq console for accurate
accounting. Per-step `latency_ms` is recorded in the trace for both the LLM
call and (implicitly, via the gap between steps) tool execution.

## If you switch to `AGENT_MODEL_PROVIDER=groq`

`openai/gpt-oss-120b` on Groq's free/on-demand tier is capped at **8000
tokens/minute** — tight enough for this 15-tool agentic loop that a real
batch run hit an 18-minute forced backoff on a single request during
development (see `BASELINE_AGENT_ARCHITECTURE.md`). This is why Together AI
is the default provider, not Groq. If you switch back to compare models,
expect a single case to take several minutes wall-clock when retries are
needed (`agent/agent_v2/llm.py::invoke_with_retry` backs off automatically —
expected, not a bug), and budget batch wall-clock time accordingly, the same
way the live app's own CLI (`agent/main.py --all`) adds a cooldown between
scenarios for the same underlying reason. Together AI's paid tier used here
has no equivalent throttle — a full case typically completes in 10-15
seconds.

## Reproducibility

Every persisted run records `prompt_version`, `toolset_version`,
`output_schema_version`, and `graph_version` (Phase 4's standing-graph tag)
so a later run can be told apart from an earlier one after either the
prompt or the tool schemas change. The LLM call itself is not deterministic
(temperature 0.1, and neither provider's serving stack is guaranteed
bit-reproducible even at temperature 0) — the graph, tools, and harness
logic are fully deterministic; only the model's own token sampling is not.
