# Phase 7 — Jev Data Boundaries

## The boundary

```
OBSERVABLE BUILDER                              OFFLINE SCORING
(never sees hidden truth)                       (the ONLY place hidden truth is read)

state_builder.py ─┐
candidates.py     ├─→ decisions.py ─→ Jev / LLM ─→ raw decision record ─→ scoring.py ←── agent.eval_v2.ground_truth
questions.py      │                                (no ground truth            │         (data.eval.eval_store)
client.py         │                                 anywhere in it)            ▼
llm_baseline.py   │                                                     scored decision record
reference_data.py ┘
```

Everything left of "raw decision record" is built exclusively from
`agent/agent_v2/tools.py`'s raw, `as_of`-gated query functions (Phase 5's
own proven observable/hidden boundary — Phase 7 does not re-derive or
re-prove it, it inherits it by construction) and from observable
reference/taxonomy CSVs (`reference_data.py`). Everything right of it is
offline, reads hidden truth freely, and is never called from the left side.

## Mechanical checks (`agent/jev_v2/validate_boundaries.py`)

1. **Import-direction scan**: `state_builder.py`, `candidates.py`,
   `questions.py`, `client.py`, `decisions.py`, `llm_baseline.py`,
   `reference_data.py` never import `agent.eval_v2.ground_truth` or
   `data.eval.eval_store` (AST-based, reusing Phase 4/5/6's method). Only
   `scoring.py` imports either.
2. **Runtime leakage guard** (`client.py::assert_no_leakage`): every
   payload about to be sent to Jev or the LLM baseline is scanned
   immediately before the network call — a live guard, not just a
   static one, since spec section 65 asks for both. Dict *keys* (in
   `state` and in each question's own body) are checked against the full
   `BANNED_SUBSTRINGS` list from `agent/graph_v2/validate_graph.py` (reused
   verbatim, not reinvented) — a key literally named e.g.
   `causal_component_id` would mean a hidden field name leaked into the
   payload's structure. String *values* are checked against a narrower
   `VALUE_BANNED_SUBSTRINGS` list (see the finding below for why).
3. **Time-boundary re-test**: reuses CS00191's known evidence timestamps
   (the real policy change `CH030460` at `2024-10-10 23:26`, the real
   signal `SG0000943`) through `agent.agent_v2.tools`' raw functions
   directly — an `as_of` before either timestamp must not surface it; the
   case's own `created_date` must. Not re-derived logic: this is Phase 5's
   own already-proven time-gating, exercised again through Phase 7's call
   path to prove Phase 7 didn't accidentally bypass it.
4. **Determinism**: `scoring.py::score_decision` called twice on the same
   stored decision record produces byte-identical JSON.

## A finding worth documenting: two leakage-guard false positives

Both were caught by running real experiments against the live API, not by
any offline test — they only manifest once real question text and real
internal identifiers hit the scan:

1. The `causal_change` question's own wording ("...most likely **causally**
   related to the observed incident?") tripped the guard, because
   `BANNED_SUBSTRINGS` contains the bare word `causal` — correct for
   catching a hidden field name like `causal_component_id`, wrong for
   flagging the ordinary English word a legitimate question about
   causation must use. **This is not a leak**: the question is *asking*
   whether something is causal, using only observable candidates; it is
   not exposing which one *actually is* causal. Fixed by narrowing the
   VALUE-scan list to exclude words that are legitimate domain vocabulary
   (`causal`, `distractor`, `optimal`, `mistake`, `misleading`,
   `efficiency`, `_relevant`) while keeping the full list for KEY-scanning,
   where an actual field-name leak would show up.
2. The internal Python identifier `"causal_change"` — Phase 7's own name
   for this decision type, used as the `questions` dict's key — also
   matched the KEY-scan for the same reason. **This is not a leak either**:
   it is a name we chose ourselves in `decisions.py::DECISION_TYPES`, never
   pulled from any data source. Fixed by scanning `state` and each
   question's own *body* (`instructions`/`criteria`) fully, but not the
   outer `questions` dict's own key names.

Both are the same class of self-referential false positive Phase 5 hit for
its `FinalDiagnosis` output-schema field names (`predicted_causal_change_id`
legitimately containing "causal") and Phase 6 hit for its own
`validate_boundaries.py` docstrings (legitimately naming `eval_store`) —
**our own hand-written names and questions are not leaks of a hidden
answer; they are the deliberate content of the system being built.** The
distinction that actually matters, confirmed in the same finding: a
genuine leak is a hidden *field name* accidentally appearing in a data
structure sent externally, not any occurrence of an English word the
domain naturally uses.

## Time boundaries

Every decision in this first tranche uses `as_of = the case's own
created_date` — a fixed, well-defined T0 ("ticket just arrived") rather
than an arbitrary or hidden-derived later point. This sidesteps the more
elaborate multi-timepoint question (spec sections 66-69) for now: since
every state-builder function already takes `as_of` as a parameter and every
underlying tool call is already `as_of`-gated (Phase 5's proven mechanism,
re-verified above), extending to later snapshots (e.g. using Phase 3's own
`diagnostic_hypotheses.csv`/`evidence_queries.csv` timestamps as natural T1/
T2/T3 boundaries) requires no new boundary work — just calling the same
functions with a later `as_of` — and is deferred to a documented second
tranche alongside component/subcategory/severity/human-review/evidence-
relevance/hypothesis-support (spec section 22's staging).

## What is NOT guarded (and doesn't need to be)

`scoring.py` freely imports and reads hidden truth — that is its entire
purpose, exactly mirroring Phase 6's evaluator. Decision records persisted
under `data/experiments/` may (and do) embed resolved ground-truth values
for debugging (spec section 55's drilldown artifact), the same designed
exception Phase 6 documented for `data/experiments/*/case_metrics.jsonl` —
the constraint is that the *runtime/observable-construction* side never
reaches it, not that no file on disk ever contains it.

## Stage B v3 additions (JEV-013 / JEV-018)

### Candidate generation v3 is observable-only

`candidate_generation_v3` for causal change reads exactly two inputs, both
Phase 5's own time-gated raw tool functions: `q_recent_changes` and
`q_deployment_history`. The rule is generic (every visible change and every
visible deployment, deduplicated by canonical id, plus `none`); it never asks
whether an event "should" appear and reads nothing from `eval_store` or Phase 1
`gt_*` columns.

- **Time gate**: both tools already filter `started_at <= as_of` in Cypher.
  v3 re-checks the same comparison defensively and counts anything it drops
  (`future_events_dropped`; 0 on the dev-100 cohort).
- **Not exposed**: a deployment's `status` (a completed or rolled-back state can
  post-date the decision) and `time_proximity_hours`. `environment` and `region`
  are not returned by either projection.
- **Deduplication**: both tools read the same `ChangeEvent` id space and label
  deployments `:ChangeEvent:Deployment`, so the two result sets do not overlap
  by construction (0 duplicates suppressed on dev-100). The rule remains: the
  same canonical id from both projections is one real-world event.

`validate_boundaries.py` check [5] builds v3 candidates for CS00001 (a
deployment is the true cause) and CS00191 in both key modes **with every
hidden-truth reader replaced by a tripwire that raises**, then runs the
leakage guard on the resulting payload and scans the candidate metadata keys.
Check [6] re-scans every stored Jev/LLM input across all Phase 7 experiments.
Check [7] verifies the Stage B frozen configuration against the working tree.
Check [8] runs the CLI with `--split validation` and `--split test` under a
non-matching `--kind` and requires refusal without touching the network or
creating an experiment.

### Two structural artifacts in the synthetic candidates (not leaks)

Measured on the dev-100 cohort (`analyze_causal_candidates.py`, output in
`data/eval/jev/analysis/`):

1. **Change-id number range.** Every true causal change has an id number in
   30400-30469; every other visible candidate is in 1302-27899. The id alone
   separates them perfectly. This is how the generator numbered injected versus
   background events; it is visible in an id, not a hidden field.
2. **Deployment presence.** Seven dev-100 cases show a deployment; in six it is
   the true cause.

Neither is hidden ground truth entering the input, and the leakage guard is
right not to flag them. They do mean a system could in principle use them, so
the opaque-key control (`--causal-key-mode opaque`) replaces change ids with
id-free aliases and remaps answers to canonical ids before scoring. Result on
dev-100: Jev 92% with real ids versus 91% with aliases; see `JEV_EVALUATION.md`
for the LLM figures. The frozen configuration keeps canonical ids so Stage B
and Stage C stay comparable; the control result is recorded beside it.

### What Jev and the LLM are shown, and what they are not

Both receive the same `state`, the same option set (keys and one-line
descriptions), the same question wording and the same decision time; the
comparison verifies this per pair by hashing the stored state, candidates and
`as_of` (100/100 identical for every decision type; incident 17/17). Neither
receives the true answer, the difficulty archetype, a stratification label, or
any Phase 3 hypothesis outcome.

