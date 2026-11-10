# Phase 4 — Graph Query Catalog

The canonical retrieval operations Phase 5 will later wrap as agent tools.
Implemented as plain parameterized Cypher in
[`agent/graph_v2/queries/catalog.py`](../agent/graph_v2/queries/catalog.py) —
not an LLM-facing tool API (that's explicitly out of scope for Phase 4).
Every function only traverses the runtime graph; none can reach
`data/eval/eval_store.py`.

For each operation: purpose, inputs, the graph path it walks, and whether a
caller would also need to fall back to raw CSV evidence.

## A. Case context — `case_context(session, case_id)`

**Purpose:** the starting point for any investigation — who raised this,
what they said, what they run.
**Inputs:** `case_id`.
**Graph path:** `Case` → `RAISED` ← `Customer` → `DEPLOYED` → `ProductVersion`
← `HAS_VERSION` ← `Product` ← `REPORTED_PRODUCT` ← `Case`; `Case` →
`REPORTS_SYMPTOM` → `Symptom`.
**Raw evidence needed:** no — everything here is graph-native.

## B. Component topology — `component_topology(session, component_id)`

**Purpose:** "what does this depend on, and what depends on it" — the base
for any dependency-flavored hypothesis.
**Inputs:** `component_id`.
**Graph path:** `Component` → `DEPENDS_ON` → `Component` (upstream);
`Component` ← `DEPENDS_ON` ← `Component` (downstream); `Component` →
`DEPENDS_ON_EXTERNAL` → `ExternalService`.
**Raw evidence needed:** no.

## C. Recent changes/deployments — `recent_changes_for_case(session, case_id)`

**Purpose:** "what changed near this case" — the real observable candidate
pool for a causal-change hypothesis, no causal label attached.
**Inputs:** `case_id`.
**Graph path:** `Case` → `NEARBY_CHANGE` → `ChangeEvent` (optionally also
labeled `Deployment`), returning `time_proximity_hours`/`scope_match`.
**Raw evidence needed:** no — `NEARBY_CHANGE` already carries the
proximity/scope facts a human would compute.

## D. Signals + telemetry findings — `signals_and_telemetry_for_case(session, case_id)`

**Purpose:** discrete observed events plus summarized metric behavior
(normal findings included — they eliminate hypotheses too).
**Inputs:** `case_id`.
**Graph path:** `Case` → `HAS_SIGNAL` → `CaseSignalObservation` → `OF_TYPE` →
`SignalType`, and `CaseSignalObservation` → `ON_COMPONENT` → `Component`;
`Case` → `HAS_TELEMETRY_FINDING` → `TelemetryFinding` → `ON_COMPONENT` →
`Component`.
**Raw evidence needed:** only if a caller wants every individual raw
`case_telemetry.csv` reading behind a specific finding — the finding's
`id` (`case_id:component_id:metric_code`) is the lookup key back into the
CSV.

## E. Incident overlap — `overlapping_incidents(session, case_id)`

**Purpose:** "is there a known incident this case's time/region overlapped"
— the fact only, never the relevance judgment.
**Inputs:** `case_id`.
**Graph path:** `Case` → `OVERLAPS_INCIDENT` → `Incident` → `AFFECTS_COMPONENT`
→ `Component`.
**Raw evidence needed:** no. **Deliberately does not** return
`phase2/incident_cases.csv`'s `relationship` column (see
`GRAPH_DATA_BOUNDARIES.md` Section 3) — the caller must judge relevance from
the incident's own component/timing versus the case's own investigation
trail (query G).

## F. Similar historical cases — `similar_historical_cases(session, case_id)`

**Purpose:** "find resolved cases that looked like this and how they were
resolved" (spec's own example query) without leaking the active case's
answer.
**Inputs:** `case_id`.
**Graph path:** `Case` → `SIMILAR_TO` → `Case`, then for each similar case:
→ `CONFIRMED_DIAGNOSIS` → `RootCauseFamily`, → `HAS_EVENT` →
`ResolutionAttempt {is_permanent: true}`, → `CONSULTED` → `KnowledgeArticle`.
**Raw evidence needed:** no. Only ever returns facts about the *similar*
case, never the case passed in as `case_id`.

## G. Decision snapshot — `decision_snapshot(session, case_id, asof)`

**Purpose:** "what did the investigation know as of time T" — the
time-aware retrieval capability spec sections 31/51 require for agentic
evals.
**Inputs:** `case_id`, `asof` (a timestamp string in the same format as the
data, e.g. `"2025-08-06 05:00:00"`).
**Graph path:** `Case` → `HAS_EVENT` → `InvestigationEvent` filtered
`WHERE timestamp <= $asof`; hypotheses via `InvestigationEvent` →
`INTRODUCES` → `Hypothesis`, cross-checked against `RESOLVES` to report
`disposition_as_of` as `'pending'` unless the disposition event itself is
also `<= asof`.
**Raw evidence needed:** no. **Validated directly against the source CSV**
in `validate_graph.py` check 5 — not just internally self-consistent.

## H. Teams/skills for an issue — `teams_and_skills_for_issue(session, subcategory_id=None, component_id=None)`

**Purpose:** "who typically owns this kind of problem" — population-level
roster/runbook knowledge, not a case-specific routing answer.
**Inputs:** `subcategory_id` and/or `component_id`.
**Graph path:** `IssueSubcategory` → `TYPICALLY_OWNED_BY` → `Team`,
`IssueSubcategory` → `TYPICALLY_REQUIRES_SKILL` → `Skill`, `Component` →
`SUPPORTED_BY` → `Team`.
**Raw evidence needed:** no.

## Not yet built (Phase 5's job)

An LLM-facing tool wrapper around these functions (natural-language tool
descriptions, argument validation/coercion, error handling for a
conversational agent loop) — deliberately out of scope for Phase 4 per spec
sections 24/48.
