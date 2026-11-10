# Phase 5 — Agent Data Boundaries

This document is Phase 5's leakage-review reference, in the same spirit as
Phase 4's [`GRAPH_DATA_BOUNDARIES.md`](GRAPH_DATA_BOUNDARIES.md). It states
exactly what the baseline agent can and cannot reach, and how that is
enforced mechanically rather than by convention alone.

## What the runtime agent can access

- The Phase 4 Neo4j runtime graph (`NEO4J_V2_*`), read-only, through the 14
  tools in `agent/agent_v2/tools.py` — never raw Cypher chosen by the model.
- Nothing else. No file system access, no other database, no web access.

## What remains evaluation-only

Everything Phase 4 already fenced off stays fenced off: `case_ground_truth.csv`,
`phase2_ground_truth.csv`, `phase3_ground_truth.csv`,
`phase3_event_quality_labels.csv`, `ideal_investigation_requirements.csv`,
and the four Phase 1 tables that re-materialize a `gt_*` fact under a
different name (`case_components.csv`, `case_products.csv`'s confirmed
rows, `case_team_ownership.csv`, `agent_cases.csv`) — see
`GRAPH_DATA_BOUNDARIES.md` for why those four specifically. Phase 5 adds
nothing new to this list; it only adds a consumer (the agent) that must
never reach it.

`data/eval/eval_store.py` remains the sole reader of the five genuinely
hidden files. It is never imported by, and never imports from, anything
under `agent/agent_v2/`.

## Tests protecting this boundary (`agent/agent_v2/validate_boundaries.py`)

1. **Import scan** — walks the AST of every `agent/agent_v2/*.py` file and
   fails if any `import`/`from ... import` statement names `eval_store` or
   `data.eval`.
2. **Filename-literal scan** — the same AST-based, docstring-excluding scan
   Phase 4 uses (a string literal inside a module/function/class docstring
   is exempt, since these files' own docstrings legitimately *name* what
   they must never open, as documentation) — fails if any evaluation-only
   or `excluded_redundant` filename appears as an exact-match code
   reference anywhere in `agent/agent_v2/`.
3. **Read-only Cypher scan** — every Cypher-shaped string literal in
   `tools.py` (contains `MATCH`/`RETURN`) is checked against
   `CREATE|MERGE|SET|DELETE|REMOVE|DETACH` (case-insensitive). The tool
   layer must be provably incapable of writing to the graph.
4. **Tool-result field-name scan** — every Cypher `AS alias` and every
   Python dict-literal key used to build a tool's *return value* is checked
   against Phase 4's banned-substring list (`gt_`, `causal`, `distractor`,
   `optimal`, `_correct`, `warranted`, `mistake`, `efficiency`,
   `misleading`, `_relevant`, `_missed`, ...). **Deliberately scoped to tool
   results, not the agent's own `FinalDiagnosis` output schema** — see the
   note below, this distinction matters.
5. **Through-the-tool-layer time-travel re-test** — re-runs Phase 4's
   decision-snapshot check, but this time by calling
   `get_recent_changes`/`get_technical_signals`/`get_active_incidents`
   directly (the actual functions the agent calls), not raw Cypher, against
   a real case (CS00191) at an `as_of` before and after a known event's own
   timestamp.

## A finding worth documenting: why `FinalDiagnosis` is exempt from the banned-substring scan

The first version of check 4 scanned `schemas.py`'s `FinalDiagnosis` fields
directly and failed on `predicted_causal_change_id` and
`causal_change_confidence` for containing "causal." This was a false
positive that exposed a real category distinction worth stating explicitly:

- A **tool result** field named `is_causal` or `is_correct` would be a
  leak — it would mean the *graph* is handing the agent an answer key.
- A **`FinalDiagnosis` field** named `predicted_causal_change_id` is the
  *agent's own inferred conclusion* — exactly what spec §21/§29 require the
  agent to produce ("predicted causal/relevant change where applicable").
  The word "causal" here describes the agent's belief, not a fact read off
  the graph.

The check was corrected to scan only what tools *return* (observable
evidence handed to the model) rather than what the agent *concludes*
(`agent/agent_v2/validate_boundaries.py::check_tool_result_field_names`).
Applying a leakage scan to the wrong side of that boundary would have
forced either fabricating euphemisms for exactly the fields the spec asks
for, or silently weakening the check — neither acceptable. Getting this
distinction right matters more than making the scan pass.

## Structural, not just conventional

As with Phase 4: the separation between "runtime agent" and "evaluation
store" is enforced by what code exists and what it imports, not by prompt
instructions telling the model not to look. There is no code path from
`agent/agent_v2/` to `data/eval/eval_store.py` for a future integrator to
accidentally wire up — the import scan would fail the build if one were
added.
