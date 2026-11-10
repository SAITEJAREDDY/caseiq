# CaseIQ Phase 3 — Investigation, Decisions, and Resolution Lifecycle

Phase 1 (`data/raw_v2/`) answers *what actually happened* to each of the
25,000 cases. Phase 2 (`data/phase2/`) answers *what technical evidence
existed* around it. Phase 3 (`data/phase3/`) answers the third question: *what
did support engineers actually do* while investigating and resolving each
case — triage, routing, hypotheses, evidence queries, resolution attempts,
escalation, KB/similar-case usage, collaboration, verification, closure, and
reopens.

Neither `data/raw_v2/` nor `data/phase2/` was modified. Both checksum
manifests (`data/generators_phase3/.phase1_checksums.json`,
`.phase2_checksums.json`) were captured before any Phase 3 code ran, and
`validate_phase3.py` re-checks both on every run.

## Scale (actual, this build)

| Table | Rows |
|---|---|
| `triage_history` | 25,000 |
| `routing_history` | 27,348 |
| `assignment_history` | 27,348 |
| `diagnostic_hypotheses` | 34,778 |
| `hypothesis_evidence` | 53,306 |
| `evidence_queries` | 53,306 |
| `resolution_attempts` | 26,694 |
| `mitigations` | 2,483 |
| `resolution_verification` | 19,732 |
| `case_reopens` | 1,008 |
| `kb_interactions` | 50,078 |
| `similar_case_interactions` | 16,184 |
| `escalations` | 3,469 |
| `engineering_engagements` | 2,420 |
| `customer_interactions` | 21,500 |
| `collaboration_events` | 2,937 |
| `case_lifecycle_events` | 415,772 |
| `case_outcomes_phase3` | 25,000 |
| `phase3_ground_truth` | 25,000 |
| `phase3_event_quality_labels` | 202,437 |
| `ideal_investigation_requirements` | 25,000 |
| **Total new rows** | **~1,060,800** |

No table was padded to hit a round number — every count is what the per-case
simulation actually produced. `resolution_verification`'s count (19,732)
equals (16,205 resolved-status cases + 2,519 escalated-status cases, both of
which carry a real resolution) + 1,008 reopens (each reopened case is
verified twice: once for the interim fix, once for the permanent one) =
19,732 exactly; the 6,276 open-status cases correctly get none.

## Section 1 — How Phase 3 joins to Phase 1 and Phase 2

Every Phase 3 table keys back to Phase 1 via `case_id` (-> `raw_v2/cases.csv`)
plus `agent_id`/`team_id`/`component_id`/`article_id` where relevant. No new
case, agent, team, component, or KB-article entity is introduced. Two Phase 3
tables additionally reference Phase 2 ids: `evidence_queries.result_ref_ids`
resolves into `phase2/change_events.csv`, `phase2/case_signals.csv`, or
`phase2/incidents.csv` depending on `query_type`, and `hypothesis_evidence`
carries the same references at the point they were incorporated into a
hypothesis.

`case_lifecycle_events` is the canonical per-case timeline: every other
Phase 3 table's rows correspond to exactly one `case_lifecycle_events` row via
`event_id`, so the full ordered event stream for any case can be reconstructed
by sorting that case's `case_lifecycle_events` rows by `seq` and following
`ref_table`/`ref_id` back into the specific table for full detail.

## Section 2 — Observable vs. hidden (same discipline as Phase 1 and Phase 2)

Seventeen tables are **fully observable** — everything a runtime agent could
legitimately see about a case's own history, with zero comparison-to-truth
judgment: `triage_history`, `routing_history`, `assignment_history`,
`diagnostic_hypotheses`, `hypothesis_evidence`, `evidence_queries`,
`resolution_attempts`, `mitigations`, `resolution_verification`,
`case_reopens`, `kb_interactions`, `similar_case_interactions`, `escalations`,
`engineering_engagements`, `customer_interactions`, `collaboration_events`,
`case_lifecycle_events`, and the derived per-case index `case_outcomes_phase3`
(counts and elapsed-time metrics computed purely from the case's own
generated timeline — e.g. `num_hypotheses`, `time_to_resolution_hours`,
`sla_outcome`).

Three tables are **hidden** — they require Phase 1/2 ground truth to compute
and must never be exposed to a runtime agent under evaluation:

- **`phase3_ground_truth.csv`** (1 row/case): `initial_routing_correct`,
  `eventual_routing_correct`, `diagnosis_matches_truth`,
  `causal_change_identified`, `causal_signal_identified`,
  `critical_evidence_ids`, `critical_evidence_missed`,
  `escalation_warranted`, `escalation_occurred`,
  `investigation_efficiency_label` (`efficient`/`moderate`/`inefficient`),
  `sla_outcome`, `expected_confidence_band`, `actual_root_cause_name`, and
  `time_to_correct_team_hours` (this one specifically requires knowing which
  team was "correct," i.e. Phase 1's `gt_primary_team_id` — it looked like an
  observable timing metric at first but isn't, since no runtime system can
  independently know the ideal team; it lives here, not in
  `case_outcomes_phase3`).
- **`phase3_event_quality_labels.csv`** (long/tidy, 1 row/label,
  `event_id, case_id, label_name, label_value`): per-routing-transition
  `routing_mistake_type` (`correct` / `understandable_but_incorrect` /
  `avoidable_error` / `misleading_customer_information` /
  `insufficient_evidence` / `capacity_availability`); per-hypothesis
  `hypothesis_correct` / `targets_true_root_cause`; per-resolution-attempt
  `action_appropriateness` (`appropriate` / `useful_but_unnecessary` /
  `ineffective` / `risky`); per-escalation `escalation_warranted` /
  `escalation_timing`; per-KB-interaction `kb_relevant`; per-similar-case
  `similar_case_relevant` / `similar_case_misleading`.
- **`ideal_investigation_requirements.csv`** (1 row/case): the investigation
  *envelope*, not a rigid script — `required_evidence_types`,
  `correct_routing_team_id`, `correct_hypothesis_root_cause`,
  `key_decision_points`, `appropriate_remediation_class`.

`validate_phase3.py` enforces this split mechanically: every observable
file's column names are checked against a banned-substring list (`gt_`,
`_correct`, `_warranted`, `_appropriate`, `mistake`, `_missed`, `efficiency`,
`misleading`, `_relevant`) and the build fails if any leak through.

## Section 3 — The core mechanism: derive the trajectory, don't invent it

Exactly like Phase 2 derived evidence from `gt_root_cause_id` instead of
inventing it independently, Phase 3 derives every investigation step from
fields Phase 1/2 already fixed:

- **Initial triage** (`triage_history`, `generate_investigation.py::_run_triage`):
  the predicted product is always `product_reported_id` (correct except for
  `wrong_product_mentioned` cases, where it's wrong *by definition* — verified
  1,786/1,810 of that archetype have `product_reported_id != gt_product_id`).
  The predicted subcategory is a weighted sample over subcategories associated
  (via `issue_subcategory_symptoms.csv`) with the case's own observed
  symptoms — but see the important caveat in Section 8 about why this alone
  isn't archetype-discriminating and what was done about it. The predicted
  component, when the category/product guess is already right, is sampled
  from the case's own `case_components.csv` rows (naturally correct for
  single-component cases, naturally sometimes wrong for the 1,920
  `multi_component_symptoms` cases); when the category/product guess is
  wrong, it's sampled from the (wrong) predicted product's real component
  list, weighted toward the predicted category via
  `issue_subcategory_components.csv`-derived weights — so a wrong guess is
  still a *plausible* wrong guess, never arbitrary.
- **Initial routing** (`routing_history`/`assignment_history`): the team for
  a given component/product/subcategory is looked up primarily via
  `issue_subcategory_teams.csv` (verified to reproduce `gt_primary_team_id`
  exactly, 3,000/3,000 sampled), falling back to `component_teams.csv` /
  `product_teams.csv` only when no subcategory signal is available. Agent
  assignment scores real candidates on skill overlap
  (`agent_skills.csv`/`case_required_skills.csv`), category/component/product
  expertise (`agent_issue_category_experience.csv`,
  `agent_components.csv`/`agent_products.csv`), and availability
  (`phase2/agent_capacity.csv` utilization) — never a random pick.
- **Hypothesis evolution** (`diagnostic_hypotheses`/`hypothesis_evidence`/
  `evidence_queries`): hypothesis #1 targets the initial (possibly wrong)
  triage guess. Each evidence query reveals only Phase 2 rows that actually
  exist **and have already happened as of that query's own timestamp** (see
  Section 4) for the component under suspicion. If nothing matches, confidence
  drops and the next hypothesis stop is forced toward
  `gt_component_id`/`gt_issue_category_id`; for `dependency_flavored` root
  causes specifically (a Phase 2 evidence-pattern property, *not* the same
  axis as Phase 1's `dependency_root_cause` archetype label — they're
  correlated but distinct), a further stop targets
  `phase2_ground_truth.causal_component_id`, one hop away via
  `component_dependencies`. The final hypothesis is always forced to converge
  on the true root cause for every non-open case (see Section 7's forced-
  convergence note).
- **Resolution attempts** (`resolution_attempts`/`mitigations`): 0-2 earlier
  attempts are sampled from `root_cause_resolutions.csv`'s weighted pool for
  the case's actual root cause, **excluding** `gt_resolution_type_id` (so
  they're plausible-but-wrong, never arbitrary), with `result` in
  `no_effect`/`partial_improvement`/`inconclusive`. The final attempt always
  uses `gt_resolution_type_id` with `result="success"`. Attempts whose
  resolution type reads as interim/workaround-flavored
  (`MITIGATION_FLAVORED_RESOLUTION_TYPES` in `phase3_taxonomy.py`) get a
  matching `mitigations.csv` cross-reference row.
- **Similar-case interactions** reuse Phase 1's own `similar_cases.csv`
  directly as the candidate pool — never an independently invented similarity
  metric.
- **Collaboration** reuses `gt_secondary_team_id` directly as the natural
  "consulted, not owning" partner team.
- **Escalation / reopen presence** are hard-anchored to Phase 1's own
  `gt_escalated`/`gt_reopened` booleans (verified exact 1:1 match on the full
  build, see Section 7).

## Section 4 — Temporal knowledge boundary (no future-information leakage)

Every new Phase 3 timestamp is an offset from the case's own already-fixed
`created_date` (a synthesized time-of-day is added once per case) and, for
non-open cases, the window is capped at exactly `created_date +
gt_resolution_duration_hours` — Phase 3 never contradicts Phase 1's own
duration. `evidence_queries` only ever reveals a Phase 2 row whose own
timestamp (`change_events.started_at`, `case_signals.timestamp`,
`configuration_snapshots.snapshot_at`, `incidents.started_at`) is **on or
before** the query's own timestamp — enforced in
`generate_investigation.py::_run_query` and independently re-checked by
`validate_phase3.py`. A hypothesis's stated confidence is computed only from
evidence discovered by queries that have already run; nothing before that
point in the simulated timeline can reference `gt_root_cause_id` or any other
fact not yet "discovered."

One deliberate subtlety worth calling out: `generate_changes.py` (Phase 2)
always attaches a case's causal `change_event` to the *visible*
`gt_component_id`, even when the root cause is `dependency_flavored` (whose
symptom evidence — telemetry/signals — lives one hop away on
`causal_component_id`). Early versions of the hypothesis-confirmation logic
let "found the causal change on the visible component" alone count as
confirmation, which let 2 cases falsely confirm the wrong hypothesis before
ever reaching the true dependency. Fixed by requiring dependency-flavored
confirmation to come from the *origin*-side telemetry/signal evidence
specifically, not the surface-level change alone (see git history / code
comments in `_evidence_matches_truth`).

## Section 5 — Investigation-action / query / resolution taxonomies

`phase3_taxonomy.py` defines every closed vocabulary used across the tables:
9 `QUERY_TYPES` (get_customer_deployment, query_telemetry, query_signals,
query_configuration, query_recent_changes, query_dependency_graph,
search_similar_cases, search_kb, check_active_incidents) mapped per issue-
category to a typical investigation order (`CATEGORY_QUERY_PROFILE`); 42
`RESOLUTION_TYPE_TO_ACTION` codes (one per Phase 1 `resolution_types.csv`
row); routing-mistake / escalation / collaboration / customer-interaction /
KB-interaction / verification / reopen-reason vocabularies. Reused rather
than reinvented: Phase 2's 18 issue-category keys
(`generators_phase2/evidence_taxonomy.py`), so query behavior is keyed off
the same ontology Phase 2's evidence was generated from.

## Section 6 — KB, similar-case, escalation, and engineering-engagement logic

- **`kb_interactions`**: candidate articles are pulled from
  `article_issue_categories.csv`/`article_components.csv` for the case's
  *currently suspected* category/component (the final confirmed one, not
  necessarily the initial guess), scored by `resolution_rate` +
  specificity/outdated adjustments + a relevance bonus if the article is
  actually linked (`article_root_causes.csv`) to the true root cause, then
  ranked with a deterministic tie-break on article id (see Section 9). Not
  every case's top-ranked article is relevant — irrelevant/outdated articles
  can still be "viewed" or "ignored."
- **`similar_case_interactions`**: only the 11,379/25,000 cases with at least
  one `similar_cases.csv` row get any; the top 1-3 by similarity score, with
  0-2 actually "opened." Whether an opened similar case is truly relevant
  (same `gt_root_cause_id`) or misleading is a hidden label, never inflating
  the observable `opened` flag.
- **`escalations`**: only for `gt_escalated == true` cases (3,469).
  `escalation_type`/`trigger_code` are derived from severity, evidence
  sufficiency, and incident overlap; `to_team_id` is `gt_secondary_team_id`
  when set, else the catch-all `TM15` (Support Escalation).
- **`engineering_engagements`**: only for a small allowlist of structurally
  code-level root causes (`product defect`, `race condition`, `incomplete
  migration`, `data migration defect`, `breaking API contract change`,
  `schema mismatch`, `incomplete rollback`,
  `idempotency/duplicate-processing failure`), and even then, not always
  (2,420 rows total — a deliberately uncommon activity relative to normal
  support resolution, per spec).

## Section 7 — Consistency anchors verified on the full 25,000-case build

- `escalations.csv` case coverage: 3,469/3,469, exactly matching
  `cases.gt_escalated == true`.
- `case_reopens.csv` case coverage: 1,008/1,008, exactly matching
  `cases.gt_reopened == true`.
- Every non-open case's final `resolution_attempts` row's
  `resolution_type_id` matches `cases.gt_resolution_type_id`.
- Every non-open case has exactly one `disposition == "confirmed"`
  `diagnostic_hypotheses` row whose `suspected_root_cause_name` matches the
  case's true root-cause name — hypotheses are forced to converge by
  construction (this is a deliberate design choice: Phase 1 already fixed
  that every non-open case *was* correctly resolved, so an investigation that
  never reaches the right answer would contradict frozen Phase 1 truth; what
  varies by difficulty is the *path*, not the destination).
- The 6,276 `status == "open"` cases (verified to still carry every `gt_*`
  diagnostic field except the resolution-outcome ones) get a full triage +
  routing + hypothesis trajectory but **zero** `resolution_attempts` /
  `mitigations` / `resolution_verification` / `case_reopens` rows — modeling
  "still being investigated," a natural ~25% minority.
- Initial-routing accuracy by `gt_difficulty_archetype` (see Section 8's
  caveat on why this needed an explicit accuracy target rather than emerging
  from symptom-pool noise alone): `clear` 93.7%, `dependency_root_cause`
  78.3%, `multi_component_symptoms` 71.7%, `wrong_product_mentioned` 71.3%,
  `vague` 60.8%, `customer_misdiagnosis` 56.7%.
- Hypothesis-count distribution: 1 hypothesis (correct first guess) 63.6%,
  2 hypotheses 33.8%, 3 hypotheses 2.7%. Routing-transition distribution: no
  reassignment 90.6%, one reassignment 9.4% — a realistic majority-efficient,
  meaningful-minority-harder shape (spec §54), measured rather than
  hand-tuned to an exact target.

## Section 8 — A finding worth documenting: symptom-pool ambiguity does not vary by archetype

The original design intended initial-triage accuracy to fall out purely from
how ambiguous the case's `case_symptoms.csv` rows are across
`issue_subcategory_symptoms.csv`'s weighted subcategory pools — mirroring how
Phase 2 let root-cause evidence patterns alone (without special-casing
archetype) produce difficulty-correlated behavior. Measured directly on all
25,000 cases, this turned out **not** to hold: the true subcategory's average
share of total candidate weight is ~22% and argmax accuracy is ~62%,
essentially *identical* across every `gt_difficulty_archetype` value. Phase
1's archetype label evidently drives other things (case-component count,
`product_reported_id` vs `gt_product_id`, narrative vagueness) rather than
symptom-to-subcategory statistics specifically.

Since spec §3 explicitly requires triage error rates to vary by archetype,
`phase3_taxonomy.TRIAGE_ACCURACY_BY_ARCHETYPE` sets an explicit accuracy
target per archetype (0.90 for `clear` down to 0.30 for
`customer_misdiagnosis`). The coin flip (correct vs. wrong) is
archetype-set; *which* wrong subcategory gets guessed, when it is wrong,
still comes from the real weighted candidate pool — so the guess itself is
never arbitrary, only the accuracy rate is an explicit, spec-mandated
parameter rather than something that fell out of Phase 1's own data.

## Section 9 — LLM usage (Lean scope, two narrative surfaces)

Per spec §47, Together AI (`Qwen/Qwen3.8-Flash`, reusing
`data/generators/llm_client.py` and its disk cache as-is) wrote exactly two
fields: `escalations.summary` (3,469 rows) and
`engineering_engagements.finding_summary` (2,420 rows) — ~5,900 items total.
Every other Phase 3 text-shaped field (`case_lifecycle_events.note`,
resolution/mitigation descriptions, customer-interaction requested-info text)
is either empty or a short deterministic interpolation — no LLM call, per the
same "structured generation first" principle Phase 2 followed. Prompts are
built only from fields already legitimately known as of that event's position
in the timeline (escalation type/trigger/severity/the hypothesis already
confirmed by that point, engineering activity type/root cause/component) —
never a bypass straight to `gt_root_cause_id` independent of what the
simulated investigation actually discovered.

Deterministic tie-breaking note: `kb_interactions`' article ranking sorts a
Python `set` of candidate ids into a scored list; without a secondary
tie-break key, `PYTHONHASHSEED`'s per-process randomization of string hashing
made set-iteration order (and therefore which article wins a score tie)
differ between separate runs with the identical seed — caught by the
twice-run diff described in Section 10, fixed by sorting on `(-score,
article_id)` instead of `-score` alone.

Actual run: 564 Together AI calls, ~416.8K input + ~430.0K output tokens,
**$0.2646**, ~21.6 minutes total build time (most of it the LLM stage). A
handful of batch-level JSON-parse hiccups occurred (as in Phase 2) and were
absorbed by the existing single-item retry tier; only 8 of 2,420 engineering
findings (0.3%) and 0 of 3,469 escalation summaries ultimately fell back to
the plain template — 99.7%+ of both fields are real generated prose, and
every row has non-empty text.

## Section 10 — Reproducibility

`PHASE3_SEED = 2027`, a single `random.Random` instance threaded explicitly
through every function — Phase 3 never touches Python's global `random`
module. Unlike Phase 2, Phase 3 has no ambient/background generation step at
all (it only re-references existing Phase 1/2 rows plus case-relative
offsets), so there is no `phase3_now`-style anchor needed and no wall-clock
call anywhere in the pipeline — the bug class Phase 2 hit structurally cannot
recur here.

Verified by running `build_phase3.py --full --skip-narratives` twice
back-to-back and diffing every output file: after fixing the KB tie-break
issue (Section 9), all 21 CSVs are byte-identical across the two runs. The
LLM narrative stage is additionally disk-cached
(`data/generators/.narrative_cache/`, shared across all three phases) keyed
by exact request hash.

## Section 11 — Known simplifications (documented, not hidden)

- Escalations and engineering engagements are placed *after* the hypothesis
  loop confirms (i.e., after the true root cause is already known in the
  simulated timeline), modeling "escalating to get a fix authorized/built"
  rather than "escalating because we're stuck." This is a common, realistic
  real-world escalation pattern (Sev1 visibility/incident-response
  escalation, or getting engineering resourced to build a patch) but is not
  the *only* realistic escalation trigger; a future iteration could add a
  pre-confirmation "escalating because evidence is insufficient" branch.
- Customer-interaction delays only explicitly gate the timeline for
  `evidence_sufficiency == "insufficient"` cases (a `request_logs`
  interaction with a multi-hour response delay before the hypothesis loop
  runs); other cases get a single end-of-case status/closure interaction.
- "Decision snapshots" (spec §39) and "counterfactual alternatives" (spec
  §40) are not materialized as separate tables. A decision snapshot is
  reconstructable by joining `case_lifecycle_events` on timestamp (everything
  known up to that point); counterfactual alternatives are stored inline as
  `routing_history.alternative_teams_considered` and
  `resolution_attempts.alternatives_considered` — both drawn from the same
  real weighted candidate pools used to pick the actual choice, not invented.
- "Troubleshooting actions" (spec §13) and "resolution attempts" (spec §14)
  are the same table (`resolution_attempts`): a troubleshooting action *is* a
  resolution attempt whose `result` is `no_effect`/`partial_improvement`
  rather than `success`.

## Section 12 — Mapping from the spec's suggested file names

| Spec-suggested name | Actual file(s) | Note |
|---|---|---|
| `case_lifecycle_events.csv` | same | canonical timeline spine |
| `triage_history.csv` | same | |
| `routing_history.csv` | same | |
| `assignment_history.csv` | same | |
| `investigation_actions.csv` | `evidence_queries.csv` | investigation (info-gathering) actions are all queries in this schema |
| `evidence_queries.csv` | same | |
| `diagnostic_hypotheses.csv` | same | |
| `hypothesis_evidence.csv` | same | |
| `troubleshooting_actions.csv` | `resolution_attempts.csv` | merged — see Section 11 |
| `resolution_attempts.csv` | same | |
| `kb_interactions.csv` | same | |
| `similar_case_interactions.csv` | same | |
| `escalations.csv` | same | |
| `engineering_engagements.csv` | same | |
| `customer_interactions.csv` | same | |
| `collaboration_events.csv` | same | |
| `mitigations.csv` | same | plus a `resolution_attempts.is_permanent`/`is_temporary` flag on every row |
| `resolution_verification.csv` | same | |
| `case_reopens.csv` | same | |
| `case_outcomes_phase3.csv` | same | also serves the "phase3_observable.csv" role (compact per-case index) |
| `ideal_investigation_requirements.csv` | same | |
| `phase3_observable.csv` / `phase3_ground_truth.csv` | `case_outcomes_phase3.csv` (observable) / `phase3_ground_truth.csv` + `phase3_event_quality_labels.csv` (hidden) | split into a case-level table and a long-format event-level table rather than one wide hidden table, since the per-event judgments (routing mistakes, per-hypothesis correctness, per-action appropriateness) don't share one schema |
