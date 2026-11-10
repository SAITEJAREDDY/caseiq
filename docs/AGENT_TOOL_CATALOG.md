# Phase 5 — Agent Tool Catalog

The 14 read-only, time-gated tools the baseline agent uses to investigate a
case, implemented in
[`agent/agent_v2/tools.py`](../agent/agent_v2/tools.py). Every tool wraps a
`MATCH`/`RETURN`-only Cypher query against the Phase 4 runtime graph
(`NEO4J_V2_*`) — none can write to it (mechanically checked by
`validate_boundaries.py`). None can reach `data/eval/eval_store.py`.

For the shared mechanics (hypothesis-state mixin, `as_of` time-gating,
result bounding), see
[`BASELINE_AGENT_ARCHITECTURE.md`](BASELINE_AGENT_ARCHITECTURE.md). This
document covers each tool individually.

## 1. `get_case_context`

**Purpose:** the case's own t=0 observable report — always call first.
**Inputs:** none (case-scoped by the harness).
**Outputs:** title, description, environment, region, reported impact/
affected users, priority, created_date, status, customer tier/industry/size,
reported product, reported symptoms.
**Temporal behavior:** not `as_of`-gated — everything here was known at case
creation by definition.
**Observable-data boundary:** deliberately does **not** return a confirmed
product/component/root-cause — those only enter the graph via the agent's
own investigation (`get_component_topology`, hypotheses), never as a
shortcut from this tool.
**Limitations:** `reported_symptoms` are what the customer said, which can
be wrong (customer-misdiagnosis cases exist by design).

## 2. `get_customer_deployment`

**Purpose:** what does this customer actually run.
**Inputs:** none.
**Outputs:** deployed products/versions/environments/regions/status, and
each product's component list.
**Temporal behavior:** **not** `as_of`-gated. `deployed_at` timestamps in
this dataset are generated independently across the full ~730-day window,
not causally tied to any one case's date (verified empirically — a case's
own customer can have every recorded deployment timestamped after the
case's own creation). Treated like topology/taxonomy: standing, always-
knowable "what does this customer run" context.
**Limitations:** no per-customer "enabled components" concept exists in the
source data; a product's full component list is returned as the closest
available proxy.

## 3. `get_component_topology`

**Purpose:** dependency graph exploration for a specific component.
**Inputs:** `component_id` (required — learned from an earlier tool result).
**Outputs:** upstream dependencies, downstream dependents, external
dependencies, owning teams.
**Temporal behavior:** not gated — the dependency graph is static topology.
**Observable-data boundary:** never indicates which dependency is causal.

## 4. `get_technical_signals`

**Purpose:** discrete observed events (HTTP errors, auth/authz failures,
TLS failures, DB errors, etc.).
**Inputs:** optional `component_id` filter.
**Outputs:** evidence_id, signal_type, message, timestamp, component_id.
**Temporal behavior:** `timestamp <= as_of`.
**Observable-data boundary:** no causal/distractor/relevance label. Some
signals are noise from unrelated components by design (verified on CS00191:
a real `HTTP_403` sits alongside two unrelated distractor signals with no
distinguishing field).

## 5. `get_telemetry`

**Purpose:** summarized metric behavior, grouped by category (Compute,
Application, Networking, Database, Identity, Storage, Integration,
Capacity, Security, Data — reusing `evidence_taxonomy.METRIC_CATALOG`'s
`family` field rather than inventing a new taxonomy).
**Inputs:** optional `metric_category`, optional `component_id`. Calling
with no category returns only the list of categories that have data for
this case — not raw values — forcing a deliberate second call (spec §6:
"tool usage should require intentional evidence gathering").
**Outputs:** per-metric baseline/observed range/status/direction/anomaly
window. Normal (non-anomalous) findings are included, not filtered out —
they can eliminate a hypothesis just as usefully as an anomaly confirms one.
**Temporal behavior:** `window_start <= as_of`.

## 6. `get_recent_changes`

**Purpose:** non-deployment changes (policy, config, firewall, DNS,
certificate, feature-flag, capacity) near the case.
**Inputs:** optional `component_id`.
**Outputs:** evidence_id, change_type, component_id, started_at/
completed_at, status, initiated_by, time_proximity_hours, scope_match.
**Temporal behavior:** `started_at <= as_of`.
**Observable-data boundary:** never labels a change as causal — verified on
CS00191, where the real causal `policy_change` and an unrelated
`manual_config_change` distractor are returned identically.

## 7. `get_deployment_history`

**Purpose:** version/deployment changes, kept separate from tool 6 per
spec §8.
**Inputs:** optional `component_id`.
**Outputs:** evidence_id, component_id, version_from/to, rollout_strategy,
deploy_duration_minutes, description, started_at, status.
**Temporal behavior:** `started_at <= as_of`.

## 8. `get_configuration_history`

**Purpose:** observable configuration snapshots captured during a case's
investigation (feature flags, rate limits, TLS versions, pool sizes, etc.).
**Inputs:** optional `component_id`.
**Outputs:** evidence_id, component_id, config_key, config_value,
snapshot_at, note.
**Temporal behavior:** `snapshot_at <= as_of`.

## 9. `get_service_health`

**Purpose:** platform service-health events for one component.
**Inputs:** `component_id` (required — not case-linked in the graph, so a
component must be named).
**Outputs:** evidence_id, started_at/ended_at, severity, description.
**Temporal behavior:** `started_at <= as_of`.

## 10. `get_active_incidents`

**Purpose:** incidents whose time/region window overlaps this case.
**Inputs:** none.
**Outputs:** evidence_id, region, started_at/ended_at, severity, status,
summary, affected_components.
**Temporal behavior:** `started_at <= as_of` ("had been published").
**Observable-data boundary:** deliberately omits Phase 2's
`incident_cases.relationship` classification (`directly_caused` /
`coincidental_unrelated` / ...) — exactly the causal-relevance judgment the
agent must determine itself. See `AGENT_DATA_BOUNDARIES.md`.

## 11. `get_similar_cases`

**Purpose:** similar historical (already-resolved) cases and how they were
diagnosed/resolved.
**Inputs:** none.
**Outputs:** evidence_id (the similar case's id), similarity_score, title,
historical_diagnosis, historical_actions.
**Temporal behavior:** the similar case's own `created_date <= as_of` (it
must have genuinely existed already to serve as "prior art"), and only
`status = 'resolved'` cases are returned.
**Observable-data boundary:** never reveals anything about the *current*
case's own answer — only the similar case's own outcome. A similar case's
outcome is not proof of the current case's cause (told to the model in the
system prompt).

## 12. `search_knowledge_base`

**Purpose:** keyword/component/category search over the KB corpus.
**Inputs:** optional `keyword`, `component_id`, `category_id`.
**Outputs:** evidence_id, title, summary, resolution_rate, outdated.
**Temporal behavior:** not gated, for the same ambient-pool reason as
customer deployments (KB `created_date` spans the full dataset window
independent of any one case's date).
**Limitations (documented, not hidden):** no embeddings/semantic search —
this is a keyword-substring + graph-traversal search, a deliberate baseline
simplification. Some returned articles are outdated or only partially
relevant by design (spec §13) — the agent must judge, not a filter.

## 13. `get_team_capability`

**Purpose:** which teams typically own a component/subcategory, and what
skills are typically required — supports routing.
**Inputs:** optional `component_id`, `subcategory_id` (at least one).
**Outputs:** teams (id, name, role, weight), skills (id, name, weight).
**Observable-data boundary:** population-level roster facts only; never
`gt_secondary_team_id` or any case-specific "correct" team.

## 14. `get_agent_availability`

**Purpose:** agent capacity/skills within a team, to support (not make) a
routing/assignment recommendation.
**Inputs:** `team_id` (required — usually from `get_team_capability`).
**Outputs:** agent_id, seniority, max_concurrent_cases,
current_utilization_pct, skills. Sorted by utilization ascending (least
loaded first) but the agent decides what to do with that.

## Omitted: known-problem / known-issue tool

Spec §14 explicitly permits omitting a tool rather than fabricating new
truth to support it. No Phase 1/2/3 table cleanly represents an observable
"this is a known issue" flag — the closest candidate,
`resolution_types.RT38` (`confirm_as_designed`), is a resolution outcome
recorded only *after* a case is resolved, not a queryable "is this pattern
already known" signal available during investigation. Building this tool
would have required inventing a new hidden-truth-adjacent concept, which is
explicitly out of scope. Omitted.

## Terminal tool: `submit_diagnosis`

Not a diagnostic tool — calling it ends the investigation. See
`BASELINE_AGENT_ARCHITECTURE.md` for its full schema and the stopping-
condition logic around it.
