# Phase 6 — Metric Catalog

Every metric below is deterministic: a plain function of a stored agent run
(`data/agent_runs/*.json`) and Phase 1-3's hidden ground truth. None uses an
LLM judge or Jev (spec sections 55-56). Implementations live in
`agent/eval_v2/metrics.py` (per-case) and `agent/eval_v2/aggregate.py`
(cross-case).

## Universal rule: a null prediction is not scored as wrong

Every predicted field (`predicted_product_id`, `predicted_component_id`,
etc.) is independently nullable by design (`agent/agent_v2/schemas.py`'s
`FinalDiagnosis` -- the agent is told to leave a field unset rather than
guess). Accuracy for a field is computed only over cases where the agent
actually made a prediction (`n_scored`); a separate `prediction_rate =
n_scored / n_total` reports how often it committed to an answer at all.
**A low prediction rate and a low accuracy are different problems and are
never conflated into one number.**

## Outcome correctness

| Metric | Definition | Denominator |
|---|---|---|
| `product` / `component` / `issue_category` / `issue_subcategory` | Exact ID match against `case_ground_truth.gt_*_id` | Cases with a non-null prediction for that field |
| `root_cause_exact` | Normalized exact string match (`text_match.exact_match`) of `predicted_root_cause_family` against `root_causes.csv`'s name (via `gt_root_cause_id`) **or** `phase3_ground_truth.actual_root_cause_name` | Cases with a non-null `predicted_root_cause_family` |
| `root_cause_containment` | Normalized substring containment either direction (`text_match.containment_match`), same two truth sources | same |
| `causal_change` | Exact ID match of `predicted_causal_change_id` against `phase2_ground_truth.causal_change_id` | Cases where a causal change truly exists (excludes true-negative "no causal change" cases, scored separately below) |
| `severity_exact` / `severity_within_one` | `predicted_severity` normalized via a fixed alias table (`sev1`/`p1`/`critical`/`urgent`→1, ... ; unmapped text is excluded, not scored wrong) vs. `gt_severity` (Sev1=most severe..Sev4=least), ordinal distance 0 / ≤1 | Cases with a normalizable prediction |
| `team_primary` / `team_acceptable` | `recommended_team_id` against `case_team_ownership.csv`'s `role=="primary"` row, or against the full acceptable set (primary+secondary) | Cases with a non-null prediction |
| `evidence_sufficiency` | `sufficient`/`partial`/`insufficient` vs. `phase2_ground_truth.evidence_sufficiency` mapped `sufficient→sufficient`, `partially_sufficient→partial`, `insufficient→insufficient` | All cases (required field) |

**Known limitation, disclosed rather than hidden:** root-cause matching is
free-text-vs-free-text. Spec section 56 bans an LLM judge here, so this
under-counts true positives whenever the agent phrases a correct root cause
differently from the ground-truth string (e.g. "auth policy misconfigured"
vs. "policy misconfiguration") -- it never over-counts, since containment
still requires a real substring relationship. `root_cause_exact` and
`root_cause_containment` are always reported as two separate numbers, never
blended.

### Causal change: four-way outcome, not a single accuracy number

- **correct**: predicted the real `causal_change_id`.
- **false_positive**: predicted a causal change ID when the case truly has
  none (`phase2_ground_truth.causal_change_id == ""`).
- **missed**: predicted nothing when a real causal change exists.
- **distractor_selected_as_causal_change** (`evidence.py`): predicted a
  change ID that is in `irrelevant_change_ids`/`distractor_signal_ids`
  rather than the true causal one -- the sharpest signal of the agent being
  actively misled rather than merely uncertain.

## Evidence metrics (`agent/eval_v2/evidence.py`)

"Retrieved" = the ID appears in the run's own `evidence_ids_seen` (i.e. it
was in a real tool result this run — never re-derived some other way).
"Cited" = the ID appears in a hypothesis's `supporting_evidence`/
`contradicting_evidence` or as `predicted_causal_change_id`.

- **Critical evidence** = `phase3_ground_truth.critical_evidence_ids` ∪
  `phase2_ground_truth.causal_signal_ids` ∪ `{causal_change_id}`.
  `all_critical_retrieved` / `all_critical_cited` are booleans; cases with
  zero critical evidence (`no_critical_evidence_exists`) are excluded from
  both rates rather than counted as automatic passes.
- **Distractor evidence** = `distractor_signal_ids` ∪ `irrelevant_change_ids`.
  Tracked the same way, plus `distractor_selected_as_causal_change` above.
- **Incident correlation**: `incident_retrieved` / `incident_cited`
  (substring search across `evidence_summary`/`rationale`/
  `unresolved_uncertainties` in addition to structured citations, since the
  schema has no dedicated `predicted_incident_id` field), reported per
  `incident_relationship` value (`directly_caused`, `partially_influenced`,
  `coincidental_unrelated`, `customer_assumed_incorrectly`).
- **Unsupported evidence rate**: reuses `citation_violations`, computed once
  by `loop.py` at execution time and never re-derived differently by the
  evaluator (spec section 45's "credit only for evidence actually
  retrieved this run").

## Confidence and calibration (`aggregate.py::confidence_and_calibration`)

Seven fixed buckets: `0.0-0.5, 0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8-0.9, 0.9-0.95,
0.95-1.0`. Computed independently for `product`, `component`, `root_cause`
(paired with `root_cause_containment` as the correctness signal),
`causal_change`, `team` (paired with `team_acceptable`), `severity` (paired
with `within_one`), and `overall_confidence` (paired with
`root_cause_containment` as a proxy, since there is no single "overall
correctness").

**Brier score / ECE are binary (chosen-answer), not full multiclass
calibration** (spec section 17's own caution): the schema gives one
confidence for the field the agent chose, not a probability distribution
over every possible product/component/root-cause. `brier_and_ece`'s
returned `note` field states this every time it is computed, so it can
never be mistaken for a full categorical calibration metric downstream.

**False-confident rate** = `wrong AND confidence >= 0.90`
(`config.FALSE_CONFIDENT_THRESHOLD`), reported per field and additionally
sliced by `insufficient_evidence` / `ambiguous` (archetype `vague` or
`wrong_product_mentioned`) / `customer_misdiagnosis`
(`false_confident_by_scenario`).

## Human review

`human_review_agreement` compares the agent's own `human_review_required`
against a **derived reference label**, not a direct ground-truth field:
`evidence_sufficiency == "insufficient" OR escalation_warranted == true OR
expected_confidence_band == "low"`. This is explicitly labeled a proxy
(`outcome.human_review.note`) per spec section 15's instruction to keep
objective and fuzzy-judgment labels separate -- it is the best deterministic
approximation available in Phase 1-3's schema, not a hidden
"should-have-escalated" field that doesn't exist.

## Process / contract compliance (`agent/eval_v2/contract.py`)

- **Tool-use**: `total_steps`, `diagnostic_tool_calls` (excludes the
  terminal `submit_diagnosis` step), `unique_tool_types`, `redundant_calls`
  (reuses the trace's own `redundant: true` flag from Phase 5's own
  redundancy detector -- never re-implemented differently here, per spec
  section 23).
- **Tool errors**, classified by deterministic string rules
  (`classify_tool_error`): `unknown_tool` (hallucinated tool name),
  `validation_error` (bad/missing argument), `neo4j_error`, `other`.
- **Repair events** (`repair_summary`): counts of
  `hypothesis_normalization` / `final_diagnosis_repair` /
  `final_diagnosis_fallback` events, read from the run's own
  `repair_events` (present on runs generated after the Phase 6
  instrumentation fix -- see `EVALUATION_ARCHITECTURE.md`). A run without
  this key reports `repair_status_known: false`, never assumed clean.
- **`clean_run`**: true only if repair status is known, `repair_event_count
  == 0`, zero tool errors, zero citation violations, and
  `stop_reason == "model_submitted"` (not a forced or failed ending).
  `process_and_contract` reports `root_cause_accuracy_among_clean_runs` vs.
  `..._among_repaired_runs` side by side -- the whole point of spec section
  50's "does the repair layer mask real unreliability."

## Hypothesis recovery (`metrics.py::_hypothesis_recovery`)

Uses **only** the structured `hypotheses: list[str]` field every regular
tool call already carries (never private reasoning, per spec section 25).
A step's hypothesis set "matches truth" via `text_match.containment_match`
against the true root-cause name. Reports `initial_hypothesis_correct`,
`final_hypothesis_correct`, `hypothesis_revisions` (count of steps where the
hypothesis-label set changed), `recovered_from_wrong_initial` (wrong→right),
`abandoned_correct_hypothesis` (right→wrong) -- `None` (excluded from rate
denominators) when there is no root-cause truth to compare against or no
diagnostic steps carried a hypothesis.

## Efficiency

Token usage and `approx_cost_usd` are read directly from the run (already
computed by Phase 5, at a documented placeholder rate -- see
`agent/agent_v2/config.py`). `total_llm_latency_ms` sums each step's own
`latency_ms`, which measures **LLM call latency only** -- Neo4j tool
execution time is not separately instrumented in the trace and is not
included; this is stated explicitly wherever the number is reported.

## Failure taxonomy (multi-label, `metrics.py::_failure_tags`)

Each case gets a list (possibly empty, possibly several) of: `wrong_product`,
`wrong_component`, `wrong_issue_category`, `wrong_root_cause` (both text-match
tiers fail), `wrong_causal_change` (false-positive or missed),
`wrong_team` (fails the acceptable-set match), `severity_error` (fails
within-one), `missed_incident`, `false_incident_attribution`,
`insufficient_evidence_overconfident` (`low_evidence` stratum AND
`overall_confidence >= 0.90`), `critical_evidence_missed`,
`distractor_selected`, `tool_loop_redundancy`, `contract_schema_problem`
(any repair event or unsupported citation), `budget_exhaustion`,
`tool_failure` (a tool error beyond the self-correctable unknown-tool kind),
`agent_stopped_too_early` (submitted after ≤2 diagnostic tool calls with
`evidence_sufficiency != "sufficient"`). A case with zero applicable tags is
not forced into one (spec section 33 explicitly allows multiple or none).

## Automation-coverage simulation (evaluation-only, spec section 19)

For thresholds `[0.70, 0.80, 0.85, 0.90, 0.95]` against `overall_confidence`:
`pct_eligible`, `accuracy_among_eligible` (using `root_cause_containment` as
the correctness proxy), `wrong_auto_action_rate`, and
`human_review_pct_below_threshold` for the cases that would remain manual.
This never changes agent behavior -- it is purely a report computed after
the fact, establishing what a future automation gate would look like against
today's baseline.

## Statistical uncertainty

Percentile bootstrap (2,000 resamples, fixed seed
`config.BOOTSTRAP_SEED`) on `root_cause_containment`, `component`,
`team_acceptable`, `issue_category` accuracy. Reported as
`point_estimate`/`ci_low`/`ci_high`; below 5 scored cases, the CI is
explicitly reported as unreliable (`ci_low`/`ci_high` are `null`) rather than
computed on too little data.

## Confusion matrices (`agent/eval_v2/confusion.py`)

Issue category, team, and severity are built directly from categorical IDs.
Root cause is bucketed via `text_match.map_text_to_id`, which maps free text
onto the ~40-row `root_causes.csv` taxonomy through the same two
deterministic tiers (exact, then containment) -- reporting `ambiguous_text`
when 2+ root causes' names all containment-match (e.g. generic text like
"misconfiguration" alone) and `unmapped_text` when none do, rather than
guessing a winner.
