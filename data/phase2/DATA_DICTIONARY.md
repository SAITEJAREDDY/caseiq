# CaseIQ Phase 2 — Diagnostic & Operational Intelligence

Phase 2 adds a technical-evidence layer on top of the frozen Phase 1 dataset
(`data/raw_v2/`): telemetry, discrete signals, change/deployment history, a
component dependency graph, platform incidents, and basic operational/SLA
context. Phase 1 answered "what kind of case is this?" (product, component,
issue category, root cause, resolution, severity). Phase 2 answers "what did
the technical environment around this case actually look like?" — without
ever restating or leaking the Phase 1 answer directly into an observable field.

Phase 1 itself was **not modified**. `data/raw_v2/*.csv` is read-only input to
Phase 2; a checksum manifest (`data/generators_phase2/.phase1_checksums.json`)
captured every Phase 1 file's hash before Phase 2 code first ran, and
`validate_phase2.py` re-checks it on every run.

## Scale (actual, this build)

| Table | Rows |
|---|---|
| `product_versions` | 241 |
| `customer_deployments` | 34,525 |
| `component_dependencies` | 1,307 |
| `external_dependencies` | 10 |
| `external_dependency_links` | 168 |
| `change_events` | 38,005 |
| `deployments` | 4,806 |
| `case_change_links` | 34,324 |
| `case_telemetry` | 206,274 |
| `case_signals` | 122,950 |
| `configuration_snapshots` | 20,881 |
| `service_health_events` | 5,048 |
| `incidents` | 650 |
| `incident_cases` | 4,635 |
| `support_plans` | 4 |
| `sla_policies` | 16 |
| `customer_entitlements` | 5,000 |
| `agent_capacity` | 180 |
| `agent_schedule` | 905 |
| `team_capacity_snapshots` | 600 |
| `phase2_observable` | 25,000 |
| `phase2_ground_truth` | 25,000 |
| **Total new rows** | **~505,500** |

`phase2_ground_truth.evidence_sufficiency` breaks down as 23,178 `sufficient` /
1,409 `partially_sufficient` / 413 `insufficient` — most cases have decent
traceable evidence (as in real support data), with a deliberate minority left
genuinely ambiguous or evidence-poor for testing confidence calibration.

Some counts land a little under the original planning estimate (notably
`case_signals` and `component_dependencies`) — that's a deliberate choice, not
a shortfall: the generators were tuned to what the underlying category/root-
cause structure actually supports, not padded to hit a round number, per the
explicit "don't inflate volume for its own sake" instruction driving this
build.

## Section 1 — How Phase 2 joins to Phase 1 (read this first)

Every Phase 2 table keys back to Phase 1 via one or more of: `case_id`
(-> `raw_v2/cases.csv`), `customer_id`, `product_id`, `component_id`,
`agent_id`, `team_id`. There is no new case, customer, product, component,
agent, or team entity in Phase 2 — only new facts *about* the existing ones.

`phase2_ground_truth.causal_component_id` / `origin_component_id` always
reference a Phase 1 `components.csv` id, and `phase2_ground_truth` rows are in
1:1 correspondence with `raw_v2/cases.csv` rows (same 25,000 case ids).

## Section 2 — Observable vs. ground truth (same discipline as Phase 1)

Every evidence table — `case_telemetry`, `case_signals`, `change_events`,
`deployments`, `case_change_links`, `configuration_snapshots`,
`service_health_events`, `incidents`, `incident_cases` — is **fully
observable**: it carries no causal label, no "this is the real cause" flag.
That's the point: it's what a runtime system or an investigating engineer
would actually see.

All causal judgments live *only* in `phase2_ground_truth.csv`:

| Column | Meaning |
|---|---|
| `causal_component_id` / `origin_component_id` | Where the fault actually originated (identical value in this build; kept as two columns because a future multi-hop model may want to distinguish "implicated" from "true origin") |
| `causal_change_id` | The one `change_events.id` that actually caused the case, if any |
| `contributing_change_ids` | Semicolon-joined ids of changes that partially contributed (rare) |
| `irrelevant_change_ids` | Semicolon-joined ids of nearby changes that are pure distractors |
| `causal_signal_ids` | Semicolon-joined ids into `case_signals.csv` that are genuinely diagnostic |
| `distractor_signal_ids` | Semicolon-joined ids into `case_signals.csv` that are noise |
| `incident_id` / `incident_relationship` | Which incident (if any) this case's time/region overlapped, and how it actually relates — see Section 5 |
| `external_dependency_causal` | True if the root cause is genuinely an external vendor/dependency fault |
| `evidence_sufficiency` | `sufficient` / `partially_sufficient` / `insufficient`, derived mechanically from what evidence actually exists (see below) — never from `difficulty_archetype` directly |
| `expected_confidence_band` | `high` / `medium` / `low`, derived from `evidence_sufficiency` (and nudged down one band for `dependency_root_cause` cases, which are inherently harder to attribute correctly even with clean evidence) |

`phase2_observable.csv` is the companion descriptive-only index: it says *how
much* evidence exists for a case (telemetry present? how many signals? how
many nearby changes? any incident-window overlap?) without saying whether any
of it is actually relevant. A classifier trained only on `phase2_observable`
plus Phase 1's `case_observable.csv` has no way to shortcut to the answer.

`evidence_sufficiency` logic (`generate_evidence.py`): `insufficient` if there
is no telemetry anomaly AND at most 1 total signal AND no causal change;
`sufficient` if a causal signal, a causal change, or a clear telemetry anomaly
exists; `partially_sufficient` otherwise.

## Section 3 — Topology tables

- **`product_versions`**: ~5 historical versions per Phase 1 product, ending
  at the version already recorded in `raw_v2/products.csv`. `is_current` flags
  the one matching that recorded version.
- **`customer_deployments`**: one row per (customer, product, environment).
  Product selection is weighted toward products the customer's own Phase 1
  case history actually touched (via `cases.product_reported_id`/
  `gt_product_id`), topped up to the customer's `num_products_deployed` count.
  Version selection is weighted toward recent versions with a long tail of
  laggards — this is what makes `version incompatibility`/`bad deployment`
  root causes plausible later (a customer running an old version is exactly
  who a breaking deployment change would hit).
- **`component_dependencies`**: a rule-based (not random) directed graph.
  Each component's "flavor" (1-2 issue-category tags) is inferred from Phase
  1's `issue_subcategory_components.csv` weights (`evidence_taxonomy.
  component_flavors()`), then `evidence_taxonomy.DEPENDENCY_RULES` says which
  flavors depend on which (e.g. an `INTEGRATION_API`-flavored component
  depends on `IDENTITY_AUTH`/`NETWORKING`-flavored ones; a `DATA_CORRUPTION`-
  flavored one depends on `STORAGE_DB`-flavored ones). Foundational/leaf
  categories (`STORAGE_DB`, `NETWORKING`, `IDENTITY_AUTH`, `THIRD_PARTY`,
  `DEPLOYMENT`, `CONFIGURATION`, `UNKNOWN`) have no outgoing edges — they are
  what other things depend on, not the other way around. This graph is what
  lets "dependency-flavored" root causes (see Section 7) plant evidence one
  hop away from the component Phase 1 actually confirmed.
- **`external_dependencies`** / **`external_dependency_links`**: a small
  registry of 10 external vendors (IdP, payment processor, tax/FX vendors,
  SMS/email/push providers, DNS/CDN, cloud IaaS, fraud vendor) linked to the
  components that plausibly call them (`THIRD_PARTY`/`BILLING`/
  `IDENTITY_AUTH`/`SECURITY`/`NETWORKING`-flavored components, plus anything
  with `origin_product_category == "Messaging"`).

## Section 4 — Change & evidence tables

- **`change_events`**: a background pool of ambient platform change activity
  (deployments, config/policy/permission changes, migrations, credential
  rotations, etc. — see `evidence_taxonomy.CHANGE_TYPES`) generated per
  component across the same ~730-day window Phase 1's cases span, **plus** a
  per-case causal change for cases whose root cause's evidence pattern rolled
  one (see Section 7). Every row is observable; nothing here says which one
  (if any) actually caused a given case.
- **`deployments`**: the subset of `change_events` with `change_type ==
  "deployment"`, with deploy-specific detail (`version_from`/`version_to`
  from `product_versions`, rollout strategy, duration). `description` is
  LLM-written (see Section 9).
- **`case_change_links`**: which changes are *near* a case in time and scope
  — `time_proximity_hours` and `scope_match` (`same_customer` /
  `same_component` / `same_product` / `platform_wide`) are both purely
  observable/mechanical. This is the candidate pool a human or model would
  actually search; whether any candidate is the real cause is a
  `phase2_ground_truth` question, not a `case_change_links` column.
- **`case_telemetry`**: 1-2 metrics' worth of readings over a 4-hour window
  ending at the case's `created_date`. When the case's root cause has a
  plausible anomalous-metric pattern, one metric ramps/steps into anomaly
  starting partway through the window; readings before that point (and any
  second, "healthy" metric included alongside it) stay within
  `evidence_taxonomy.METRIC_CATALOG`'s normal range. `is_anomalous` flags
  which specific readings are the injected anomaly. A deliberate minority of
  cases get sparse or zero telemetry (weighted by the root cause's
  `evidence_richness` and by `gt_difficulty_archetype == "vague"`), modeling
  real "we don't actually have great observability here" cases.
- **`case_signals`**: discrete timestamped events. Each case draws 0-4 causal
  signals from its root cause's `signal_pool` (`evidence_taxonomy.
  ROOT_CAUSE_EVIDENCE_PATTERNS`) plus 0-6 distractor signals sampled from
  *other* issue categories' signal pools on unrelated components — the
  ambiguity-by-construction pattern carried over from Phase 1's symptom
  pools.
- **`configuration_snapshots`**: a point-in-time config key/value pulled
  during investigation (~70% of cases get one), from a small catalog of
  plausible keys (feature flags, rate limits, TLS version, pool sizes, etc.).
  `note` is a deterministic template, not LLM text.

## Section 5 — Incident tables

- **`service_health_events`**: ambient, case-independent health blips per
  component (~20/component over the full window) — background noise, never
  linked to a specific case.
- **`incidents`**: platform-wide events. Each is **seeded from a real Phase 1
  case** whose root cause already belongs to an incident-eligible category
  (`RELIABILITY`, `THIRD_PARTY`, `CAPACITY`, `NETWORKING`, `STORAGE_DB`,
  `IDENTITY_AUTH` — `evidence_taxonomy.INCIDENT_CATEGORY_WEIGHTS`) and whose
  severity is Sev1/Sev2. This guarantees every incident has at least one
  genuinely-caused case by construction, rather than hoping random time
  windows happen to overlap real cases.
- **`incident_cases`**: every case whose `created_date`/region falls inside an
  incident's window (+/-30min buffer) gets classified — and this is
  deliberately **not** "inside the window = caused by it" (the spec's
  Scenario E requirement). The seed case is always `directly_caused`. Other
  cases on the *same* component are usually `directly_caused`, sometimes
  `partially_influenced`. Cases on a component that *depends on* the
  incident's component (via `component_dependencies`) are usually
  `partially_influenced`, sometimes `coincidental_unrelated`. Everything else
  that merely overlaps in time/region splits between
  `coincidental_unrelated` and `customer_assumed_incorrectly` — a case that
  happened to occur during a well-known incident but was actually unrelated.
  Actual distribution in this build: directly_caused 683, partially_influenced
  111, coincidental_unrelated ~2,520, customer_assumed_incorrectly ~1,350.

## Section 6 — Operational / capacity tables

`support_plans` (4) x `sla_policies` (4 severities each, 16 total) model
response/resolution-time SLA targets by plan tier. `customer_entitlements`
assigns each customer a plan weighted by their Phase 1 `tier`. **This is
strictly a commercial/SLA-target fact — it has no bearing on `gt_severity`**,
which Phase 1 already fixed purely from business impact
(`generate_cases._severity_from_impact`). `agent_capacity`/`agent_schedule`
and `team_capacity_snapshots` give basic, static capacity context (not a
staffing simulation) — deliberately minimal per the Phase 3 boundary (no
routing/reassignment/queueing history here, see Section 8).

## Section 7 — The root-cause -> evidence-pattern design

The core mechanism, in `data/generators_phase2/evidence_taxonomy.py`'s
`ROOT_CAUSE_EVIDENCE_PATTERNS` (one entry per Phase 1 root cause): for a given
`gt_root_cause_id`, it fixes which metrics plausibly go anomalous, which
signal codes are plausible causal evidence, the probability a dedicated
causal change exists (and its type), and whether evidence should be planted
one hop away via `component_dependencies` ("dependency-flavored").

This is why, in the generated data, a `policy misconfiguration` case has a
~70% chance of a causal `policy_change` change event and a ~74%-observed rate
of a causal `POLICY_EVAL_DENY`/`HTTP_403` signal, while a `database
contention` case has only an ~8%-observed rate of any causal change at all
(matching the spec's Scenario A/B pair directly) — every evidence field is
*derived from* the existing Phase 1 ground truth, never invented
independently and reconciled afterward.

`evidence_richness: "low"` (on root causes like `insufficient
monitoring/alerting`, `known product limitation`, and `insufficient
information to determine root cause`) deliberately suppresses telemetry and
signal generation — these are the cases meant to end up
`evidence_sufficiency == "insufficient"`.

## Section 8 — LLM usage (the only two narrative surfaces)

Per the agreed "Lean" scope, Together AI (`Qwen/Qwen3.8-Flash`, reusing
`data/generators/llm_client.py` as-is) wrote exactly two fields:
`incidents.summary` and `deployments.description`. Every other text field in
Phase 2 (`change_events` has no free-text field at all;
`service_health_events.description`, `case_signals.message`,
`configuration_snapshots.note` are all deterministic templates/interpolation)
is mechanical, per the spec's "structured generation first, language
generation second" instruction — a log message or a routine config diff isn't
higher quality for having been generated by an LLM, and doing so for
~200,000+ rows would have cost far more time/money for no benefit.

## Section 9 — Reproducibility

Phase 2 uses its own seed (`PHASE2_SEED = 2026`) and its own
`random.Random` instances, threaded explicitly through every `generate_*`
function — it never reads or writes Python's global `random` state, so it
cannot perturb Phase 1 (which seeds the global `random` module directly) even
if both were imported in the same process. Every `generate_*` module takes
Phase 1 data as read-only input via `load_phase1.py`, which only ever opens
`data/raw_v2/*.csv` in read mode.

**All "recent activity" timestamps (background changes, deployments, health
events, capacity snapshots, entitlement start dates) are anchored to
`load_phase1.phase2_now` — `max(case.created_date) + 14 days`, computed from
Phase 1's own frozen data — never to `datetime.now()` at Phase 2 build time.**
An earlier version of this pipeline captured `datetime.now()` once per module
at import time; because that value differs by however many minutes elapsed
between separate process launches, and because a handful of near-boundary
"is this change within 72h of the case" window checks would occasionally flip
as a result, the shared `random.Random` stream would end up consuming a
slightly different number of draws run to run — cascading into thousands of
reordered/differently-sampled rows despite the identical seed. This was
caught by running the changes stage twice back-to-back and diffing the
output (`change_events.csv` row count differed by 1-2 rows and thousands of
lines were reordered between the two runs), and fixed by switching every
`datetime.now()` call to the shared, data-derived anchor. Verified fix: two
consecutive `--full --changes-only` runs now produce byte-identical
`change_events.csv` / `deployments.csv` / `case_change_links.csv`.

Re-running `build_phase2.py --full` with the same seed reproduces
byte-identical structural output. The LLM narrative stage is additionally
cached to disk (`data/generators/.narrative_cache/`, shared with Phase 1)
keyed by exact request hash, so a re-run replays cached text instead of
re-spending tokens — confirmed on this build's second full run, which cost
only $0.0929 (vs $0.2368 for the first) since most incident/deployment
payloads were unchanged and hit the cache.
