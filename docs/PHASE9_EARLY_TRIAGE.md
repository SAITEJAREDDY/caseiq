# Phase 9+: Jev-assisted early triage

Jev now has **two separate roles** in the diagnostic workflow:

| Role | When | What it does | Where |
|---|---|---|---|
| **Early Jev = triage guidance** | after the case context is loaded, before any graph tool | suggests an issue category from the ticket text; a provisional hint the agent may reject | `agent/early_triage/`, `agent/agent_v3/triage_hint.py` |
| **Late Jev = answer verification** | after the agent's final answer | three typed signals (missed evidence, distractor anchoring, review) feeding the plain-code policy: accept / continue / human review | `agent/runtime_verifier/` (unchanged) |

Jev supplies probabilities; plain code decides. The early suggestion is never evidence, never a diagnosis and never shown as verified.

## Call sequence and the one insertion point

```
harness: get_case_context (step 1, unchanged)
   │
   ▼  agent_v3/loop.py::run_case, immediately after step 1 and before the first model-chosen tool
early_triage(ctx)                     ── Jev Choice over 18 categories + ABSTAIN, ticket fields only
   │   plain code: validate → drop ABSTAIN / p < 0.30 / invalid / error / timeout / not in taxonomy → fallback
   ▼
provisional hint block in every agent prompt (or nothing, on a fallback)
   │
   ▼
agent loop as before (tools, hypotheses, final answer)  → triage_outcome recorded (confirmed / changed / dropped)
   │
   ▼
late verifier as before (its packet is built from the trace and graph only; it never receives the hint)
```

`run_case(..., triage=None)` takes the callback as an argument, so `loop.py` never imports Jev. `run_verified_case(..., early_triage=False)` keeps the Phase 9 behavior by default; the comparison page's LLM + Graph + Jev mode passes `early_triage=True`.

## Mode decision

| Mode | Early Jev | Graph | Late Jev |
|---|---|---|---|
| LLM Only | no (never calls Jev or the graph) | no | no |
| **LLM + Graph** | **no: the unchanged baseline** | yes | no |
| **LLM + Graph + Jev** | **yes** | yes | yes |

Stored LLM + Graph + Jev runs made before this feature have late verification only; the page labels them "Early Jev: not used".

## What early Jev sees and returns

- **Input (allow-list, `early_triage_state_v1`):** title, description, reported symptoms, environment, region, business impact, affected users, priority; customer tier, industry, size; product name. Not sent: case or customer ids, status, dates, signals, telemetry, any tool result. Anything else in the case context is dropped by construction.
- **Question (`early_triage_category_v1`):** a typed Choice over the 18 taxonomy categories plus `ABSTAIN` ("the ticket alone does not support choosing any category"). Jev returns the choice and a probability for every option; nothing else. The existing Phase 7 client and leakage guard are reused (`agent.jev_v2.client`); the official SDK is not installed.
- **Plain-code policy (`TriageConfig`, hand-set, untuned):** ABSTAIN → fallback; top probability below 0.30 → fallback; invalid answer (unknown choice, not a distribution, choice not the maximum) → fallback; API error, 20 s timeout or a missing key → fallback; a category that is not in the graph taxonomy, or whose name differs from the graph's, → fallback. Otherwise a hint, labelled low (p ≥ 0.70), moderate (≥ 0.40) or high uncertainty. A leakage-guard trip is not a fallback: it stops the run.

## What the agent is told

```
EARLY TRIAGE HINT (provisional and unverified)
Source: Jev early triage. It read only the ticket text and basic customer/product details; no tool, log, telemetry or graph evidence had been examined.
Suggested issue category: CATEGORY_XXX = <name> (probability 0.62, moderate uncertainty).
Other categories Jev considered: CATEGORY_YYY = <name> (0.20).            (only competitors at or above 0.05)
This is a prior, not a finding, and it may be wrong. Test it against the evidence you retrieve, weigh the competing categories, and reject or replace it if the evidence
points elsewhere. It is not evidence and cannot be cited. Choose your final issue_category from the evidence.
Suggested starting points for this category (advisory only: every tool stays available and no category or evidence is ruled out): get_technical_signals; get_telemetry (metric_category Networking); ...
```

The block is appended to the user message only. The tool catalog, action schema and final schema are not touched (a test compares every schema handed to the model with and without a hint), so nothing is hard-filtered. The advisory tool map (`priorities.py`) is hand-written from what each category means and is unvalidated. When there is no hint, prompts are byte-identical to the unchanged baseline (a test pins a hash taken before the code was edited).

## What is recorded and shown

`run["early_triage"]`: status, fallback flag and reason, suggested category, probability, margin, uncertainty, competing categories, the top of Jev's distribution, abstain probability, advisory tools, latency, Jev input tokens, model, question and state versions. `run["triage_hint_text"]` is the exact text the agent saw. `triage_outcome` (for the agent's first answer and its final one): `confirmed`, `changed` (and whether the new category was one of Jev's listed alternatives), `dropped`, `no_suggestion`. Verified records also carry `early_triage_used` and add Jev's early tokens to `jev_input_tokens`.

Diagnostic Agent page: a one-line "Early Jev (triage guidance)" on the card (marked "provisional suggestion, not a diagnosis"), an *Early Jev* part in **What Jev Added** next to *Late Jev*, a comparison-table row, an impact bullet, and an expander with the distribution, advisory tools and the exact hint text.

## Boundaries (tested)

Import closure of the early-triage modules holds no hidden-truth reader, evaluation store or scoring module; hidden-truth readers replaced by tripwires are never called during a run; a context poisoned with `gt_*`-style fields sends none of them; a leakage-guard trip is not suppressed and the request never leaves the process; no runtime module can import `evaluation.py` or `run_dev.py`; the late verifier's packet contains none of the hint. Phase 1-8 files are unchanged (`validate_boundaries`: 199 pinned files, none changed).

## Dev comparison (35 dev cases, descriptive only)

Setup: the first 36 case ids (sorted) of the 72 dev `verify100` cases that have a stored LLM + Graph baseline; the set was fixed for run time before any correctness result was read. CS00182 hit a Together `422 grammar failed to compile` error and was not re-run, so **N = 35**. One run per case per arm, temperature 0.1, so run-to-run noise is not separated from any effect. Full tables: `data/early_triage_eval/report_v1.md`.

| | LLM + Graph (stored baseline) | Early triage + agent, first answer | LLM + Graph + Jev, final |
|---|---|---|---|
| Issue category correct | 14/35 (40%) | 21/35 (60%) | 19/35 (54%) |
| No category selected | 14 | 6 | 8 |
| Critical evidence recalled (25 cases that have any) | 59% | 81% | 85% |
| Model tool calls (mean) | 8.1 | 8.2 | 11.4 |
| Est. cost per case | $0.019 | | $0.036 |

- **Early Jev alone:** it gave a hint on all 35 cases (0 abstentions) and was right on 27 (77%, 95% CI 61-88%); 30 of the 35 were at p ≥ 0.70. It took 0.13 s per call.
- **The category gain is Jev's, not the agent's.** Paired against the baseline the first answer won 11 cases, lost 4 (exact McNemar p = 0.12: not significant). But the agent never disagreed with Jev: it kept the hint in 29 of 35 cases (21 right, **8 wrong**) and selected no category in the other 6; it changed the category in 0. All 8 wrong hints were adopted, and the baseline had been correct on 3 of those 8. The design lets the agent reject the hint; in this sample it did not.
- **Evidence retrieval was higher after the hint** (mean evidence items 9.6 vs 7.2) with the same number of tool calls. This is descriptive: it may reflect the advisory tool suggestions or ordinary run noise; it was not isolated.
- **Late verification changed nothing useful.** 28 of 35 first answers were sent back for an extra round; the finals were ACCEPT 2, HUMAN_REVIEW 21, PRIORITY_REVIEW 12 (the 2 accepted: 1 correct category, 1 wrong; of the 33 sent to review, 18 had the correct category). The extra round roughly doubled cost and cut category accuracy from 21 to 19.
- **A side effect to fix:** 3 of the 35 runs ended in CONTRACT_FAILURE, all in the extra round: the agent kept the hinted category but had no evidence to cite for it (`selection_without_citation`), and failed validation after the one repair. Round-1 answers were all valid. The baseline sample had none.
- **Not claimed:** improvement (the interval is wide and there is one run per arm), or that the agent tests the hint. Untuned and unvalidated: the hint wording, the 0.30 floor, the uncertainty bands and the advisory tool map. The obvious next lever, not tried: make the "select a category only if you can cite evidence for it" rule explicit in the hint.

## Run it

```bash
python3 -m agent.runtime_verifier.run --early-triage CS00014     # one dev case, live (Together + Jev, about $0.03)
python3 -m agent.early_triage.run_dev                            # the evaluation set (36 cases), resumable, use caffeinate -i
python3 -m agent.early_triage.evaluation                         # offline report: data/early_triage_eval/report_v1.{md,json}
python3 -m unittest agent.early_triage.test_early_triage         # 36 tests, offline
```
