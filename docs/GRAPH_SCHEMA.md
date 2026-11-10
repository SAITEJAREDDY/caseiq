# Phase 4 — Graph Schema

The Phase 4 runtime graph lives in a **separate Neo4j instance** from the
live app's demo graph (`NEO4J_V2_*` in `.env`, read only by
`agent/graph_v2/config.py`). It is built from the observable slice of
`data/raw_v2/` + `data/phase2/` + `data/phase3/` by `agent/graph_v2/build_graph.py`.
See [`GRAPH_DATA_BOUNDARIES.md`](GRAPH_DATA_BOUNDARIES.md) for what is
deliberately excluded and why.

## Conceptual diagram

```
(Customer)-[:RAISED]->(Case)
(Customer)-[:DEPLOYED]->(ProductVersion)<-[:HAS_VERSION]-(Product)
(Product)-[:HAS_COMPONENT]->(Component)
(Component)-[:DEPENDS_ON]->(Component)
(Component)-[:DEPENDS_ON_EXTERNAL]->(ExternalService)
(Component)-[:SUPPORTED_BY]->(Team)

(Case)-[:REPORTED_PRODUCT]->(Product)
(Case)-[:REPORTS_SYMPTOM]->(Symptom)
(Case)-[:REQUIRES_SKILL]->(Skill)
(Case)-[:NEARBY_CHANGE]->(ChangeEvent)
(Case)-[:OVERLAPS_INCIDENT]->(Incident)
(Case)-[:HAS_SIGNAL]->(CaseSignalObservation)-[:OF_TYPE]->(SignalType)
(Case)-[:HAS_TELEMETRY_FINDING]->(TelemetryFinding)-[:ON_COMPONENT]->(Component)
(Case)-[:HAS_CONFIG_SNAPSHOT]->(ConfigurationSnapshot)-[:ON_COMPONENT]->(Component)
(Case)-[:CONSULTED]->(KnowledgeArticle)
(Case)-[:SIMILAR_TO]-(Case)                          {similarity_score}
(Case)-[:HAS_EVENT]->(InvestigationEvent)
(Case)-[:CONFIRMED_DIAGNOSIS]->(RootCauseFamily)      {disposition_at}   -- resolved-hypothesis only
(Case)-[:CONFIRMED_DIAGNOSIS_COMPONENT]->(Component)  {disposition_at}   -- resolved-hypothesis only

(InvestigationEvent) -- multi-labeled by ref_table, e.g.:
  :TriageDecision, :RoutingTransition, :AssignmentDecision, :EvidenceQuery,
  :ResolutionAttempt, :Mitigation, :VerificationCheck, :Reopen,
  :KBInteraction, :SimilarCaseInteraction, :Escalation,
  :EngineeringEngagement, :CustomerInteraction, :CollaborationEvent

(TriageDecision)-[:PREDICTS_PRODUCT|PREDICTS_COMPONENT|PREDICTS_CATEGORY|PREDICTS_SUBCATEGORY|PREDICTS_TEAM]->(...)
(RoutingTransition)-[:FROM_TEAM]->(Team), -[:TO_TEAM]->(Team)
(AssignmentDecision)-[:ASSIGNED_AGENT]->(Agent), -[:FOR_TEAM]->(Team)
(InvestigationEvent)-[:INTRODUCES]->(Hypothesis)
(InvestigationEvent)-[:RESOLVES]->(Hypothesis)            -- disposition event, if reached
(Hypothesis)-[:CONSIDERS_COMPONENT]->(Component), -[:CONSIDERS_CATEGORY]->(IssueCategory)
(InvestigationEvent:EvidenceLink)-[:UPDATES]->(Hypothesis)
(Hypothesis)-[:SUPPORTED_BY|CONTRADICTED_BY]->(CaseSignalObservation|ConfigurationSnapshot|ChangeEvent|Incident|TelemetryFinding)
(Hypothesis)-[:CONSIDERS_DEPENDENCY_PATH]->(Component)
(ResolutionAttempt)-[:PERFORMED_BY]->(Agent), -[:FOR_TEAM]->(Team), -[:USES_RESOLUTION_TYPE]->(ResolutionType), -[:TARGETS_HYPOTHESIS]->(Hypothesis)
(Mitigation)-[:FOR_ATTEMPT]->(ResolutionAttempt)
(Reopen)-[:REOPENED_AFTER]->(InvestigationEvent)
(KBInteraction)-[:ABOUT_ARTICLE]->(KnowledgeArticle)
(SimilarCaseInteraction)-[:ABOUT_SIMILAR_CASE]->(Case)
(Escalation)-[:FROM_TEAM]->(Team), -[:TO_TEAM]->(Team)
(CollaborationEvent)-[:WITH_TEAM]->(Team)

(KnowledgeArticle)-[:COVERS_PRODUCT|COVERS_COMPONENT|COVERS_CATEGORY|COVERS_SUBCATEGORY|COVERS_SYMPTOM|COVERS_ROOT_CAUSE|COVERS_RESOLUTION_TYPE]->(...)
(IssueSubcategory)-[:BELONGS_TO]->(IssueCategory)
(IssueSubcategory)-[:TYPICALLY_INVOLVES_COMPONENT|TYPICALLY_CAUSED_BY|TYPICALLY_REQUIRES_SKILL|TYPICALLY_PRESENTS_AS|TYPICALLY_OWNED_BY]->(...)  {weight}
(RootCauseFamily)-[:TYPICALLY_RESOLVED_BY]->(ResolutionType)                                                                                     {weight}
(Agent)-[:MEMBER_OF]->(Team), -[:HAS_SKILL]->(Skill), -[:SUPPORTS_PRODUCT]->(Product), -[:SUPPORTS_COMPONENT]->(Component), -[:HAS_EXPERIENCE]->(IssueCategory), -[:HAS_SHIFT]->(AgentShift)
```

## Node labels

| Label | Source | Canonical id | Notes |
|---|---|---|---|
| `Customer` | `raw_v2/customers.csv` | `id` | always loaded in full |
| `Case` | `raw_v2/case_observable.csv` **only** | `id` | never reads `cases.csv`/`case_ground_truth.csv` |
| `Product` | `raw_v2/products.csv` | `id` | |
| `ProductVersion` | `phase2/product_versions.csv` | `id` | also carries `product_id` property for lookup |
| `Component` | `raw_v2/components.csv` | `id` | |
| `IssueCategory` | `raw_v2/issue_categories.csv` | `id` | |
| `IssueSubcategory` | `raw_v2/issue_subcategories.csv` | `id` | |
| `Symptom` | `raw_v2/symptoms.csv` | `id` | |
| `Team` | `raw_v2/teams.csv` | `id` | |
| `Skill` | `raw_v2/skills.csv` | `id` | |
| `Agent` | `raw_v2/agents.csv` | `id` | |
| `AgentShift` | `phase2/agent_schedule.csv` | `id` | |
| `KnowledgeArticle` | `raw_v2/knowledge_articles.csv` | `id` | |
| `RootCauseFamily` | `raw_v2/root_causes.csv` | `id` | name catalog; see boundaries doc for why linking to a `Case` is restricted |
| `ResolutionType` | `raw_v2/resolution_types.csv` | `id` | |
| `SupportPlan` / `SLAPolicy` | `phase2/support_plans.csv` / `sla_policies.csv` | `id` | |
| `ExternalService` | `phase2/external_dependencies.csv` | `id` | |
| `ChangeEvent` (+`Deployment` extra label) | `phase2/change_events.csv` + `deployments.csv` | `id` | deployments share the same node/id, extra label + properties merged on |
| `Incident` | `phase2/incidents.csv` | `id` | |
| `ServiceHealthEvent` | `phase2/service_health_events.csv` | `id` | ambient, case-independent |
| `ConfigurationSnapshot` | `phase2/configuration_snapshots.csv` | `id` | |
| `SignalType` | distinct `case_signals.csv` `signal_code` values | the code itself | deduped catalog |
| `CaseSignalObservation` | `phase2/case_signals.csv` | `id` | |
| `TelemetryFinding` | summarized from `phase2/case_telemetry.csv` | `case_id:component_id:metric_code` | deterministic composite key, see `telemetry_summarize.py` |
| `InvestigationEvent` | `phase3/case_lifecycle_events.csv` | `id` = `event_id` | base label; gets one extra type-specific label per matching Phase 3 detail table (see below) |
| `Hypothesis` | `phase3/diagnostic_hypotheses.csv` | `native_id` = the table's own `id` | distinct node (not multi-labeled) because a hypothesis has both a creation and a disposition event |
| `ResolutionAttempt` | (multi-label on `InvestigationEvent`) | `native_id` property = `resolution_attempts.csv`'s own `id` | cross-referenced by `mitigations.csv` |

## Type-specific labels merged onto `InvestigationEvent`

`TriageDecision`, `RoutingTransition`, `AssignmentDecision`, `EvidenceQuery`,
`EvidenceLink`, `ResolutionAttempt`, `Mitigation`, `VerificationCheck`,
`Reopen`, `KBInteraction`, `SimilarCaseInteraction`, `Escalation`,
`EngineeringEngagement`, `CustomerInteraction`, `CollaborationEvent` — one
node per `case_lifecycle_events.csv` row, `id = event_id`, with the matching
Phase 3 detail table's columns merged on as properties via a second `MATCH
... SET`. This avoids a duplicate node per event while still supporting
label-filtered queries (`MATCH (h:Hypothesis)`) and generic timeline queries
(`MATCH (ie:InvestigationEvent)`) equally.

## Constraints

One `IS UNIQUE` constraint per canonical id, for every label above, plus two
extra constraints for the cross-referenced native ids: `Hypothesis.native_id`
and `ResolutionAttempt.native_id`. Full list: `agent/graph_v2/schema.py`.

## Indexes

`InvestigationEvent(case_id)`, `InvestigationEvent(timestamp)`,
`ChangeEvent(started_at)`, `ChangeEvent(component_id)`,
`Incident(started_at)`, `Incident(component_id)`,
`CaseSignalObservation(case_id)`, `CaseSignalObservation(timestamp)`,
`TelemetryFinding(case_id)`, `ConfigurationSnapshot(case_id)`,
`Case(created_date)` — chosen for the access patterns in
[`GRAPH_QUERY_CATALOG.md`](GRAPH_QUERY_CATALOG.md) (case timeline retrieval,
recent-change lookup, incident lookup). Not over-indexed: reference/taxonomy
tables are small enough that a label scan is already fast.

## Ordering, not a `:NEXT` chain

`InvestigationEvent.seq` (per case) plus `.timestamp` give a total order.
Decision-snapshot and "what happened first" queries filter/sort on these
properties directly (`WHERE ie.timestamp <= $asof ORDER BY ie.seq`).
Deliberately no `(:InvestigationEvent)-[:NEXT]->(:InvestigationEvent)` chain
— ~390K extra edges for no query benefit over property-based ordering, and a
real cost at Neo4j's per-tier relationship ceiling (see the scale note in
the root `README.md`/`data/README.md`). Easy to add later if a graph-walk
access pattern specifically needs it.

## Scale note: why the standing graph is a bounded case subset

AuraDB Free hard-caps a database at 400,000 relationships (discovered by
hitting it directly: an attempted full 25,000-case load failed mid-way with
`Neo.ClientError.Transaction.TransactionHookFailed`). Measured scaling from
two real loads (500 and 2,000 cases): ~72.7 relationships and ~26.2 nodes
per case, on top of a ~144K-relationship / ~52K-node fixed "world" graph
(taxonomy, topology, KB, and the ambient `ChangeEvent`/`ServiceHealthEvent`/
`Incident` pool, all loaded in full regardless of case count). A true
25,000-case load would need an estimated ~3.9M relationships — about 10x the
platform ceiling.

`build_graph.py --mode small --n-cases N` picks a deterministic, connected
subset (the first N case ids, sorted; every shared taxonomy/topology/KB/
ambient-evidence table still loaded in full) rather than sampling
disconnected rows. **The standing Phase 4 graph uses `N = 2,500`** — chosen
for headroom (measured **116,868 nodes / 325,539 relationships**, about 29%
/ 81% of the Free-tier node/relationship ceilings respectively), rebuilt
with `python3 -m agent.graph_v2.build_graph --mode small --n-cases 2500
--wipe`. `--mode full` (all 25,000 cases) remains available for a paid Aura
tier or a locally-run, uncapped Neo4j instance.
