# Phase 9: runtime verification MVP

A working end-to-end path: **case → agent → tools → proposed diagnosis → deterministic checks + Jev signals → policy → (optional one more investigation round) → ACCEPT / HUMAN_REVIEW / PRIORITY_REVIEW**.
Implementation-first: no benchmark, no threshold tuning, dev cases only. Jev produces signals; plain code (`policy.py`) decides.

## What runs

| Part | Where | Notes |
|---|---|---|
| Agent | `agent/agent_v3/` | Phase 5 tools and model, unchanged model. Constrained JSON actions, tool-name/argument validation (one correction, budget 2), final answer validated (one repair), every entity and evidence id is an alias the agent actually observed. Invalid tool → structured `unknown_tool` error listing allowed tools. |
| Verifier | `agent/runtime_verifier/` | `deterministic_checks.py`, `jev_checks.py`, `policy.py`, `verifier.py`, `run.py` (orchestrator), `models.py` (thresholds). |
| Loop hook | `agent_v3/loop.py` | `run_case(..., verifier=cb)`: after a valid final answer the callback runs; on `CONTINUE_INVESTIGATION` the same session resumes with the verifier's message and 4 extra tool calls, then is verified once more. Never more than two passes. |
| UI | `pages/1_Diagnostic_Agent.py` | `streamlit run app.py` → "Diagnostic Agent". Modes: agent + verification / agent only. Shows status, evidence check, missed-evidence and distractor risk, review signal, per-pass details, review packet. Dev cases only; stored runs open instantly, "Run agent live" needs Together + Jev keys. |

## Checks (split from Phase 8's findings)

Deterministic: **D1** valid final contract (schema, bounds, every cited item/selected entity was retrieved before the answer; computed from the alias map, independent of the loop's validator) ·
**D2** evidence support (a proposal cites retrieved evidence and rests on a supported hypothesis) · **D3** final consistency (confidence vs top hypothesis, ≥0.8 despite uncertainty, a final top hypothesis never stated and matching no retrieved evidence) ·
**D4** premature finalization (no evidence at all, or no supported hypothesis while ≥2 tool calls were still available).
Jev (typed, Phase 8 packet and question versions, opaque aliases, leakage guard on every call): `missed_evidence_probability`, `distractor_anchor_probability`, review signal NORMAL / REVIEW / PRIORITY_REVIEW. Jev is never asked for a root cause.

## Policy (`policy.py`, thresholds in `models.VerifierConfig`)

D1 fails → HUMAN_REVIEW · D4/D2 fail, missed-evidence ≥ 0.75, or distractor ≥ 0.75 → CONTINUE_INVESTIGATION (first pass) / HUMAN_REVIEW (second pass) · Jev unreachable → HUMAN_REVIEW (never auto-accept) ·
Jev review = PRIORITY (or P ≥ 0.5) → PRIORITY_REVIEW · D3 fails → HUMAN_REVIEW · agent proposed no diagnosis or asked for review → HUMAN_REVIEW · confidence < 0.55 → HUMAN_REVIEW · otherwise ACCEPT.
The "agent did not clear its own result" rule is an addition to the spec'd order: an `INSUFFICIENT_EVIDENCE` answer is not something to ACCEPT.

## Runtime boundary

The verifier sees the ticket, the agent's trace, tool results, structured hypotheses, final result and the observable evidence its tools could return. Never `gt_*`, hidden labels, Phase 6 scores. Enforced by tests
(import closure allow-list; a real packet built from a real dev run with hidden-truth readers replaced by tripwires; the Phase 8 guard on every live Jev call). Phase 1–8 files are pinned and unchanged; graph 116,868 / 325,539; `tenacity==8.5.0`; no `typesafe-sdk`.

## Smoke results (16 dev cases, `data/eval/agent_contract_9a/phase9_smoke_cases.json`; records in `data/runtime_verifier_runs/`)

16/16 completed end-to-end, 0 contract failures, Jev available in every pass. First pass: 8 CONTINUE, 6 HUMAN_REVIEW, 2 ACCEPT. After the one extra round: **2 ACCEPT, 14 HUMAN_REVIEW**; the extra round ran in 8 cases and rescued none.
Mean 179 s and about $0.026 per case (about $0.42 total; estimate from list prices). Post hoc Phase 6 check (evaluation only, never fed back): the 2 ACCEPTs were 1 correct, 1 wrong; all 14 HUMAN_REVIEWs were wrong or unanswered.

## Three-architecture comparison (UI)

The Diagnostic Agent page can run or open a dev case as **LLM Only** (ticket and answer vocabulary to the model once; no Neo4j, no tools, no Jev), **LLM + Graph** (the agent with the Neo4j tools; the unchanged baseline: no early triage, verifier off) or **LLM + Graph + Jev**
(this document's late verifier, now preceded by Jev early triage: see `docs/PHASE9_EARLY_TRIAGE.md`), or compare all three side by side (`agent/compare/`; README has the details). Live Compare All was run through the page on a fresh dev case (all three in parallel, 196 s, about $0.05, all stored afterwards).
On the 17 stored dev cases that have all three results (chosen for coverage, not sampled): root-cause accuracy 6% / 6% / 6%, issue-category accuracy 71% / 41% / 35%, abstention 59% / 41% / 59%, human-review rate 88% for the Jev mode, average tool calls 0 / 8.1 / 10.1, average cost $0.001 / $0.019 / $0.027.
These are observations on a biased set (it includes cases where the graph agent's stored run was wrong), not a benchmark.
**Every number in this document (the 16-case smoke and the 17-case aggregate) was measured with the late verifier only**, before early triage existed; `run_verified_case` still defaults to that behavior (`early_triage=False`), and the page's LLM + Graph + Jev mode now adds early triage on top of it.

## Known limitations

- The agent is weak: only 1 of 16 final answers was correct by Phase 6 (which under-counts paraphrases), and it abstains a lot. "Everything goes to review" looks similar to "the verifier works" on this sample; 16 cases cannot separate them.
- In 6 of the 8 continued cases the agent answered with a diagnosis, was told to look further, and came back with INSUFFICIENT_EVIDENCE: the feedback pushes it to abstain rather than to repair the diagnosis.
- Thresholds are hand-set defaults, not tuned. Jev signals are not calibrated (Phase 8: over-alarming on missed evidence and distractors). Jev's NORMAL probability never exceeded 0.01 in the 24 smoke passes, so its review signal cannot by itself justify ACCEPT; one ACCEPT had missed-evidence 0.74, one point under the threshold.
- Only dev smoke testing. The UI's live-run button was not exercised in a browser; stored and agent-only views were tested headlessly, and the live function is the one the CLI smoke used.
- Phase 9A's 100-case contract verification was stopped at 72/100 and is unfinished; no separate Phase 9A write-up exists (see the root `README.md`). On the 72 completed cases: tool names 100% valid, tool arguments 99.7%, first-pass final answers 95.8%, 0 invented ids, 0 invalid citations, 0 unrecoverable failures; Phase 6 judged 3 of the 72 correct.

## Run it

```bash
python3 -m agent.runtime_verifier.run CS00729            # one dev case, live (Together + Jev), late verification only
python3 -m agent.runtime_verifier.run --early-triage CS00729   # the same, with Jev early triage before the investigation
python3 -m agent.runtime_verifier.show CS00729 CS01031   # print stored end-to-end traces
python3 -m agent.runtime_verifier.smoke                  # the 16-case smoke set
python3 -m unittest agent.runtime_verifier.test_runtime_verifier agent.agent_v3.test_agent_v3
```
