# Phase 7 — Question Catalog

Six decisions (spec sections 8, 12, 13, 15, 17, 16 — the "first tranche,"
spec section 22). Every wording lives in `agent/jev_v2/questions.py`'s
`QUESTIONS` dict, versioned via `agent/jev_v2/config.py::QUESTION_VERSIONS`.
A wording change requires a new version key, never an in-place edit to a
version an experiment has already run against (spec section 6).

## issue_category (`issue_category_v1`, Choice)

- **Purpose**: the highest-level, best-populated classification decision —
  a natural first primitive to validate the whole pipeline against.
- **State** (`state_builder.py::issue_category_state`): ticket
  (title/description/symptoms/environment/region/impact/priority),
  customer (tier/industry/company size), reported product, a light signal
  count/type summary. Deliberately excludes deployment history, KB, SLA,
  and agent-availability data (spec section 23's "does not need every
  available agent, full KB history, unrelated SLA information").
- **Candidates** (`candidates.py::issue_category_candidates`): all 18
  canonical `issue_categories.csv` rows — a small, fixed, observable set;
  no filtering strategy needed.
- **Ground truth**: `case_ground_truth.gt_issue_category_id`, exact match.

## root_cause (`root_cause_v1`, Choice)

- **Purpose**: the single most important CaseIQ diagnostic primitive (spec
  section 73).
- **State**: five context-ablation levels
  (`state_builder.py::root_cause_state`, spec section 24), each a strict
  superset of the previous:
  - `v1_narrative`: ticket title/description only.
  - `v2_domain`: + full ticket fields, reported product, deployed
    components (from `q_customer_deployment`).
  - `v3_technical`: + technical signals and available telemetry
    categories (`q_technical_signals`/`q_telemetry`).
  - `v4_operational`: + recent changes, recent deployments, active
    incidents (`q_recent_changes`/`q_deployment_history`/`q_active_incidents`).
  - `v5_graph`: + component dependency topology and similar-case summaries
    (`q_component_topology`/`q_similar_cases`).
- **Candidates** (`candidates.py::root_cause_candidates`): v2 aggregates
  public product-component topology support (weight 1), observed
  signal-component support (4), and reported-symptom -> subcategory ->
  root-cause support (4 times the public relation weights).  It selects the
  deterministic top 15 plus **always-included `RC40`** ("insufficient
  information to determine root cause"), the taxonomy's explicit abstention
  entry.  The stable candidate context is independent of the model-context
  ablation level.  It never uses the true category or root cause to narrow
  the list.
- **Ground truth**: `case_ground_truth.gt_root_cause_id`, exact match.
  `scoring.py` also reports `candidate_answer_present` (recall) separately
  from `correct_given_present` (conditional accuracy) so a candidate-miss
  is never blamed on Jev.

## causal_change (`causal_change_v1`, Choice; `candidate_generation_v3`)

- **Purpose**: the strongest distractor-resistance test — Phase 2
  deliberately plants nearby non-causal changes near real ones.
- **State** (`state_builder.py::causal_change_state`): ticket, product,
  deployed components, technical evidence (signals + telemetry
  categories). Deliberately excludes the changes themselves from `state`
  (they live in `candidates`, described, not narrated) so the question is
  "pick from this list," not "read this list and describe it back."
- **Candidates** (`candidates.py::causal_change_candidates`, versioned):
  - **v3 (current, JEV-013)**: every observable change (`q_recent_changes`)
    **and every observable deployment** (`q_deployment_history`) at this
    case's `as_of`, normalized into one structure (canonical source id, event
    type, start time, component, deployment version transition and rollout
    strategy), deduplicated by canonical id, ordered newest first then by id,
    plus the explicit `"none"` key ("No recent change is causally related to
    this incident"). Each option is described by type/component/start time
    (deployments also by version change and rollout). A defensive re-check
    drops anything that started after `as_of`. `status` (a completed or
    rolled-back state can post-date the decision) and `time_proximity_hours`
    are deliberately not exposed; `environment` and `region` are not returned
    by either Phase 5 projection.
  - **v2 (Stage B v1/v2, kept verbatim for reproducibility)**: `q_recent_changes`
    only. That query excludes deployment-type events, so a deployment that was
    the true cause was never offered (6 of 100 dev cases).
  - An opaque-key mode (`key_mode="opaque"`, v3 only) replaces change ids with
    id-free aliases (`option_1`, ...) in the options sent to the model. It is a
    diagnostic control, not a production setting; answers are mapped back to
    canonical ids before scoring.
- **Ground truth**: `phase2_ground_truth.causal_change_id`, or `"none"` if
  empty. `scoring.py` additionally tracks `false_positive` (picked a change
  when none is causal), `missed` (picked none when one is causal),
  `distractor_selected`, and — spec section 14's explicit anti-recency
  check — whether the picked change was simply the newest one
  (`selected_is_newest_change`) and whether the TRUE causal change itself
  was the newest (`true_causal_change_is_newest`), so recency-driven
  correct answers can be told apart from genuine causal reasoning
  (`aggregate.py::causal_change_recency_categories`, evaluator v2.1): group A
  true change is the newest candidate, B it is older than at least one
  distractor, C no causal change exists, D two or more real changes were
  offered (overlaps A/B/C), E the true change was not offered at all (a
  candidate miss, never scored as a model error). Equal timestamps count as A.

## owning_team (`owning_team_v1`, Choice; `candidate_generation_v2`)

- **State** (`state_builder.py::owning_team_state`): ticket, product,
  deployed components, evidence summary.
- **Candidates** (`candidates.py::owning_team_candidates`): v2 aggregates
  observable component ownership across all deployed components plus
  product-team, observed signal-component, and symptom/subcategory/team
  support, then selects a deterministic top 12.  This replaces v1's
  order-dependent first-eight deployed-component slice.
- **Ground truth**: `case_team_ownership.csv`'s full role set —
  `correct` = exact primary-team match, `acceptable_match` = any role
  (primary or secondary) match, both reported separately (spec section 15).

## evidence_sufficiency (`evidence_sufficiency_v2`, Choice)

- **Why Choice, not Noul**: Phase 2's real label set is three-way
  (`sufficient`/`partially_sufficient`/`insufficient`); collapsing it to a
  yes/no Noul would destroy information spec section 17 explicitly says not
  to lose. The three candidate keys are worded to match Phase 2's own
  labels exactly, so no relabeling step is needed at scoring time.
- **State** (`state_builder.py::evidence_sufficiency_state`): the broadest
  state of the six by design — ticket, product, technical evidence,
  operational events, configuration-snapshot count, and (v2) a time-gated
  telemetry summary with abnormal finding count/details.  v1 exposed only
  metric categories, which was semantically incomplete for a label partly
  derived from clear telemetry anomalies.
- **Ground truth**: `phase2_ground_truth.evidence_sufficiency`, exact match.

## incident_relationship (`incident_relationship_v1`, Noul)

- **Purpose**: the strongest false-correlation test — Phase 2 deliberately
  includes cases where an active incident overlaps in time/region but is
  coincidental or a customer misassumption.
- **Cardinality**: not one decision per case — one Noul decision **per
  candidate incident** `q_active_incidents` returns at this case's `as_of`
  (`candidates.py::incident_candidates`; `decisions.py::build_incident_inputs`).
  Most cases have zero candidate incidents (only ~4,635 of 25,000 cases have
  any incident association at all) and simply produce no decision row.
- **State** (`state_builder.py::incident_relationship_state`): ticket,
  product, case signal count, and the one candidate incident's own fields
  (region, time window, severity, status, summary, affected components).
- **Ground truth**: true only if this candidate incident's id matches
  `phase2_ground_truth.incident_id` **and** the relationship is
  `directly_caused` or `partially_influenced`; false for
  `coincidental_unrelated`/`customer_assumed_incorrectly`, and false by
  default for any incident that overlaps but isn't the recorded one.

## Deferred to a second tranche (spec section 22)

Component (visible-vs-origin split), issue-subcategory (needs a more
careful candidate-generation strategy over ~126 options), severity (Score
primitive, not yet exercised), human-review need, evidence relevance, and
hypothesis support are explicitly **not** built in this first tranche —
building all eleven decisions at once before any of the first six are
validated is exactly the anti-pattern spec section 22 warns against.
