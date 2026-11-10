# Phase 8 data boundaries

Jev and the LLM judge see runtime-observable trace state only. Hidden truth and Phase 6 scores are used offline, after the judge has answered.

## What a judge may see (`agent/trace_eval_v2/trace_projection.py`)

The agent's instructions and tool names; the case as reported (title, description, product, environment, region, impact, priority, customer tier, symptoms); the agent's diagnostic steps with their timestamps
(tool, arguments, outcome, compact tool result, evidence returned, the hypotheses restated at that step); invalid-tool and repair events; the final structured answer exactly as the harness validated it, with
missing fields left null; and the inventory of observable evidence the agent's own time-gated tools could return, flagged by whether this trace retrieved it. Every internal id is replaced by an opaque alias
(`trace_alias_v1`, a hash keyed on the case and the id; kind prefix only). Event type, timestamp, component, text and every other observable field are kept.

Never included: the agent's free-text `rationale` (so no judge is asked to read or evaluate a chain of thought); anything from the hidden Phase 1 to 3 files; the hidden causal, distractor and critical evidence
sets; escalation, routing or diagnosis correctness; the Phase 6 scores; the reference labels; the review policy's verdict; which inventory items matter.

## Evaluator only (`labels.py`, `perturbations.py`, `scorer.py`, `analysis.py`, `corpus.py`, `experiments.py`, `metrics.py`)

The hidden critical and distractor evidence, the Phase 6 outcome, the reference labels for J1 to J6, the review policy, the observable-only baselines' scoring, the alias reverse map, and the perturbation
selection logic (which reads hidden truth only to choose which observable item to remove, move or reuse). The reference labels are stored apart from the packets (`pool_labels_v1.jsonl`,
`reference_labels.jsonl`) and no judge-facing module reads them.

## Enforced, not just stated (`python3 -m agent.trace_eval_v2.validate_boundaries`)

1. The static import closure of the seven model-facing modules contains no hidden-truth reader, no Phase 6 scoring module and no evaluator-side Phase 8 module.
2. Nothing under `agent_v2`, `jev_v2`, `eval_v2` or `graph_v2` imports Phase 8 (one direction only).
3. Every stored packet re-passes the leakage guard for all six questions, holds no `rationale` field and matches its recorded digest (726 packets in the registered experiments).
4. Building a packet from a real trace with every `eval_store` reader and `get_hidden_truth` replaced by a tripwire never trips one.
5. Reference labels re-computed twice are byte-identical to each other and to the stored labels.
6. Stored packets re-project to the identical digest from the stored trace, context and alias scheme.
7. For every registered run the two judges were given the same packets, the same question versions and the same judged (trace, judgment) pairs.
8. Only dev cases are used (pool, corpus, all Phase 8 experiments); no validation or test case; no `locked_benchmark` experiment; no locked run-state marker.
9. `tenacity==8.5.0`; `typesafe-sdk` absent.

## The runtime guard (`guard.py`), applied to every request before it is sent

Keys must not be an evaluation column name or contain a hidden-field marker; values must not contain a marker or name an evaluation column as a whole word; no canonical internal id may remain anywhere.
It replaces Phase 7's value scan for this phase because that scan refuses ordinary English words (`warranted`) that an agent's own free text can contain. The guard raises and stops the call; it is never
downgraded to a warning. Offline tests cover it (a clean packet with ordinary words passes; hidden field names, ids and banned keys are refused; both judges refuse before any call).

## Identifier projection

Phase 7 found that model decisions can depend on identifier structure. Every id is aliased for both judges alike. The mapping is evaluator-side only. Perturbation P6 re-aliases a trace with a different mapping (25 traces): every Jev probability stayed within 0.10 on every judgment (mean absolute change 0.011 to 0.024; two
decision flips at the 0.5 boundary each on J1 and J5, of 25), and the LLM judge moved by more than 0.10 on 3 of 25 traces for J1 and 1 of 25 for J2. Identifier structure is therefore not driving either judge here.
This tests invariance between two alias mappings; it is not a canonical-versus-alias comparison, which would put canonical ids in front of a judge and was not run.
