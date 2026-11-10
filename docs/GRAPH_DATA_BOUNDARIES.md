# Phase 4 — Graph Data Boundaries

This document is the leakage-review reference for the Phase 4 Neo4j runtime
graph (`agent/graph_v2/`). It states exactly what enters the runtime graph,
what stays as raw observable evidence outside it, what belongs exclusively to
the evaluation store, and why — so a reviewer can check "did anything hidden
leak in?" without re-deriving the reasoning from scratch.

## 1. Two different questions, two different splits

Phase 1/2/3 already draw an observable-vs-hidden line (unprefixed columns vs
`gt_*`, and a handful of explicitly-named hidden files) to answer: **"is this
safe for a classifier to train on?"** Phase 4 has to answer a stricter,
different question: **"could a runtime agent legitimately know this before
or without investigating?"**

Most Phase 1/2/3 "observable" tables pass both tests. Four Phase 1 tables do
not — they re-materialize a `gt_*` fact under a different column name, which
is invisible to a "does the column start with `gt_`" scan but is exactly the
answer key from the runtime graph's point of view:

| File | Column | What it actually is |
|---|---|---|
| `case_components.csv` | `relation = confirmed` | `gt_component_id`, restated |
| `case_components.csv` | `relation = candidate` | a Phase 1 distractor component |
| `case_products.csv` | `relation = confirmed` | `gt_product_id`, restated |
| `case_team_ownership.csv` | (all rows) | `gt_primary_team_id` / `gt_secondary_team_id`, restated |
| `agent_cases.csv` | (all rows) | `gt_assigned_agent_id`, restated |

Confirmation this isn't hypothetical: Phase 1's own `raw_v2/DATA_DICTIONARY.md`
(Section 7, "Graph mapping for a future Neo4j loader") sketches
`(Case)-[:CAUSED_BY]->(RootCause)`, `(Case)-[:CONFIRMED_PRODUCT]->(Product)`,
and an undifferentiated `(Case)-[:HAS_COMPONENT]->(Component)` straight from
`case_components.csv`. Implemented literally, every one of these would hand
a runtime agent the answer before it investigated anything. Phase 4
deliberately does not implement that sketch.

## 2. The governing principle

**Any edge connecting a `Case` to a diagnosis-shaped entity (component,
category, root-cause family, owning team, assigned agent) is created only
from Phase 3's own observable investigation tables — never from Phase 1/2.**

Concretely, in `agent/graph_v2/loaders/investigation.py`:
- `triage_history.csv` → the *initial, possibly wrong* guess (`PREDICTS_*`
  edges from a `TriageDecision`-labeled `InvestigationEvent`) — legitimately
  known at case creation, since it's the guess itself, not the answer.
- `diagnostic_hypotheses.csv` → the evolving suspects (`CONSIDERS_COMPONENT`,
  `CONSIDERS_CATEGORY` from a `Hypothesis` node).
- `routing_history.csv` / `assignment_history.csv` → the real, sometimes
  wrong, time-ordered team/agent sequence.
- Only a `disposition == "confirmed"` `Hypothesis` produces
  `(Case)-[:CONFIRMED_DIAGNOSIS]->(RootCauseFamily)` and
  `(Case)-[:CONFIRMED_DIAGNOSIS_COMPONENT]->(Component)` — and even then, the
  edge carries `disposition_at` as a property specifically so a
  decision-snapshot query at an earlier timestamp `T` can filter it out with
  `WHERE rel.disposition_at <= T` (see Section 5).

This still lets the graph answer "what was Case B's final diagnosis?" for a
resolved historical case (spec's own example is legitimate — this is
historical knowledge, not a leak). The values coincide with
`case_ground_truth.csv`'s `gt_root_cause_id`/`gt_component_id` only because
Phase 3 was built to force convergence for every non-open case — but the
*provenance* is Phase 3's observable record, never a direct read of Phase 1's
hidden truth. `case_ground_truth.csv` is never opened by any loader module
(mechanically checked, see Section 6).

One more subtlety, verified empirically during the build: Phase 3 gives
**every** case — including the ~25% still `status == "open"` — exactly one
confirmed hypothesis; only `resolution_attempts`/`mitigations`/
`resolution_verification`/`case_reopens` are absent for open cases. So
`CONFIRMED_DIAGNOSIS` exists for open cases too. This is still Phase 3's own
observable investigation conclusion, not a hidden field, and the
`disposition_at` property is exactly what keeps it from leaking into a
decision-snapshot query taken before that hypothesis was actually confirmed.

## 3. Incident relevance is not copied onto the overlap edge

`phase2/incident_cases.csv` has a `relationship` column
(`directly_caused` / `partially_influenced` / `coincidental_unrelated` /
`customer_assumed_incorrectly`). Phase 2's own dictionary calls this table
"fully observable," but the classification itself is exactly the causal
determination a future agent must infer (a case that merely overlapped a
well-known incident but was unrelated is the spec's own worked example of
what must not be handed over for free).

Phase 4 loads the observable overlap fact — `(Case)-[:OVERLAPS_INCIDENT]->
(Incident)` — from every `incident_cases.csv` row, but **drops the
`relationship` column entirely**. The agent has to reason about relevance
using the topology graph (does the case's suspected component match or
depend on the incident's component?) and the incident's own timestamps —
exactly the observable facts a real investigator would have.

## 4. Population-level taxonomy facts are not case-specific truth

Tables like `issue_subcategory_root_causes.csv`, `issue_subcategory_teams.csv`,
`root_cause_resolutions.csv`, and `article_root_causes.csv` say things like
"this subcategory is historically caused by X in 30% of cases" or "this KB
article covers root-cause family Y." These are loaded as `TYPICALLY_*` /
`COVERS_*` edges with a `weight` — genuine textbook/runbook-shaped domain
knowledge a real support engineer would have access to, and structurally
incapable of naming *this specific case's* answer (they connect taxonomy
nodes to other taxonomy nodes, never to a `Case` node).

## 5. Time-awareness is a first-class requirement, not an afterthought

Every `InvestigationEvent` (and its type-specific label: `Hypothesis`,
`ResolutionAttempt`, `Escalation`, etc.) carries its own `timestamp`
property, and `(case_id, seq)` gives a total order. A decision-snapshot query
filters `WHERE ie.timestamp <= $asof` and gets exactly the events that had
already happened — verified against the source CSV directly in
`validate_graph.py`'s check 5, not just checked for internal
self-consistency.

The two `Case`-level shortcut edges (`CONFIRMED_DIAGNOSIS`,
`CONFIRMED_DIAGNOSIS_COMPONENT`) are the one place a fact doesn't originate
from a timestamped node itself, so they explicitly carry `disposition_at` as
an edge property for the same filtering to apply. Every other Case-to-
diagnosis fact is reached by first traversing to a timestamped
`InvestigationEvent`/`Hypothesis`, so it's automatically time-gated by
construction.

## 6. What enters the graph — full classification

The authoritative, file-by-file classification for all 88 Phase 1/2/3 CSVs
lives in [`agent/graph_v2/manifests/dataset_classification.json`](../agent/graph_v2/manifests/dataset_classification.json),
in four buckets:

- **`runtime_graph`** (and `runtime_graph_filtered` for a row-level subset) —
  loaded into Neo4j.
- **`runtime_raw_evidence`** — `case_telemetry.csv` only: 206K raw metric
  samples, summarized deterministically into `TelemetryFinding` nodes
  (`agent/graph_v2/telemetry_summarize.py`); the raw CSV remains the source
  of truth for any tool that needs a specific reading, addressable by the
  same `case_id:component_id:metric_code` key the finding node uses.
- **`evaluation_only`** — the five genuinely hidden files
  (`case_ground_truth.csv`, `phase2_ground_truth.csv`,
  `phase3_ground_truth.csv`, `phase3_event_quality_labels.csv`,
  `ideal_investigation_requirements.csv`) plus the four re-materialization
  tables from Section 1. Read only by `data/eval/eval_store.py`.
- **`deferred`** — technically loadable but superseded by a richer table
  (`case_articles.csv` by Phase 3's `kb_interactions.csv`) or low enough
  value to skip in v1 (`team_capacity_snapshots.csv`).
- **`excluded_redundant`** — `cases.csv`, the wide merge of
  `case_observable.csv` + `case_ground_truth.csv`; no loader ever opens it,
  `case_observable.csv` is used directly instead.
- **`metadata`** — the `DATA_DICTIONARY.md` files and generator code; not
  data.

## 7. Mechanical enforcement, not just documentation

`agent/graph_v2/validate_graph.py` runs two independent checks so this
boundary isn't just a promise:

1. **Live graph scan** — enumerates every label, relationship type, and
   property key actually present in the loaded Neo4j graph (`CALL
   db.labels()` / `db.relationshipTypes()` / `db.propertyKeys()`) and fails
   if any matches a banned-substring list (`gt_`, `causal`, `distractor`,
   `optimal`, `_correct`, `warranted`, `mistake`, `efficiency`, `misleading`,
   `_relevant`, `_missed`, …) — the same discipline `validate_phase3.py`
   already used on the CSVs themselves.
2. **Source scan** — an AST-based walk of every file under
   `agent/graph_v2/loaders/` (plus `build_graph.py`, `schema.py`,
   `telemetry_summarize.py`) that collects every string literal *except
   module/function/class docstrings* (which legitimately name evaluation_only
   files in prose, explaining what must never be read) and fails if any of
   the nine `evaluation_only`/`excluded_redundant` filenames appears as an
   exact file-path literal. This is what actually caught and confirmed the
   boundary is real: the check initially had to be taught to ignore
   docstrings and to require exact filename matches (not substring
   containment, which false-positived on `similar_cases.csv` containing the
   substring `cases.csv`) before it could tell true references from
   deliberate documentation apart.

`data/eval/eval_store.py` is the sole reader of the five evaluation_only
files. It is never imported by anything under `agent/graph_v2/`, and it never
imports anything from `agent/graph_v2/` — a future CaseIQ agent given access
to the runtime graph and raw observable evidence has no code path to this
module at all.
