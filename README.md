# CaseIQ — Graph-Powered Support Intelligence

**Microsoft AI Graphs TPM Demo · June 2026**

CaseIQ is a Streamlit demo and a research code base for graph-grounded support-case triage. Two halves share this repository:

1. **The live demo app** (Phase 0, `app.py`). Submit a support case in plain English; dual-confidence extraction picks the product, a Neo4j graph supplies customers, similar cases, agents and KB articles, and the grounded recommendation is shown next to a no-graph LLM baseline.
2. **The diagnostic-agent research program** (Phases 1-9). A synthetic support-domain dataset with hidden ground truth, a second Neo4j runtime graph (116,868 nodes / 325,539 relationships), an autonomous diagnostic agent with read-only time-gated tools, a deterministic evaluator, Jev (a typed, probabilistic decision model) evaluated offline, and a **runtime verifier** that checks the agent's answer before it is trusted. The newest piece is the **Diagnostic Agent** page of the Streamlit app, which runs it.

## Where things stand

| Phase | What it is | Code | Docs | Status |
|---|---|---|---|---|
| 0 | Live demo app (Groq, original demo graph) | `app.py`, `agent/*.py` | this file | working |
| 1-3 | Synthetic data: support domain → diagnostic and operational intelligence → investigations and resolutions, with hidden ground truth | `data/generators*`, `data/raw_v2`, `phase2`, `phase3` | `data/README.md` | frozen |
| 4 | Neo4j runtime graph, observable data only | `agent/graph_v2` | `docs/GRAPH_*.md` | frozen |
| 5 | Baseline diagnostic agent, 14 read-only time-gated tools | `agent/agent_v2` | `docs/AGENT_*.md`, `BASELINE_AGENT_ARCHITECTURE.md` | frozen; the historical baseline |
| 6 | Deterministic evaluator; locked dev / validation / test splits | `agent/eval_v2` | `docs/EVALUATION_*.md` | frozen |
| 7 | Jev primitive evaluation (six single decisions) | `agent/jev_v2` | `docs/JEV_*.md` | closed; the locked benchmark was never run |
| 8 | Jev as an agent-trace evaluator (six typed judgments) | `agent/trace_eval_v2` | `docs/PHASE8_TRACE_EVALUATION.md`, `TRACE_EVAL_*.md` | closed |
| 9A | Contract-hardened agent `agent_v3` (same model) | `agent/agent_v3`, `agent/contracts` | [below](#diagnostic-agent-and-runtime-verifier-phases-9a-and-9) | working; 100-case verification stopped at 72 of 100 |
| 9 | Runtime verifier, one retry round, Streamlit page that compares LLM Only / LLM + Graph / LLM + Graph + Jev | `agent/runtime_verifier`, `agent/compare`, `pages/1_Diagnostic_Agent.py` | `docs/PHASE9_RUNTIME_VERIFIER.md` | MVP; smoke-tested on 16 dev cases |
| 9+ | Jev early triage: a provisional issue-category hint from the ticket text, before any graph investigation (guidance only; the late verifier is unchanged) | `agent/early_triage`, `agent/agent_v3/triage_hint.py` | `docs/PHASE9_EARLY_TRIAGE.md` | working; dev comparison on 72 cases, descriptive only |

### What the program has measured (all on dev cases)

- **Phase 5 baseline, 300 dev traces.** Every trace called at least one tool that does not exist (244 called `get_system_logs`); 174 traces had a call rejected for a missing component id; every final submission needed a silent repair to validate; no trace ever filled an ID-valued prediction field.
- **Phase 8, Jev judging traces.** Simple deterministic rules match or beat Jev for support, premature close and final consistency. Jev is a useful supporting signal for missed evidence (AUC 0.84), distractor anchoring (0.85) and priority-review triage, at about $0.18 per 1,000 judgments against $3.52 for the LLM judge. It never chose "auto-close" (0 of 150 traces).
- **Phase 9A, same model, hardened protocol.** Schema-constrained decoding, an alias registry and deterministic validators removed phantom tools and invented ids: every tool name valid, 0 invented ids and 0 invalid citations in every run set. First-pass final-answer validity was 98% (first version, 50 cases), 92% (after the one correction, same 50) and 95.8% (72 verification cases), with no unrecoverable failure. The first version had quietly stopped stating hypotheses (365 of 409 steps empty); the correction forbids an empty hypothesis state.
- **Phase 9, runtime verifier, 16-case smoke.** All 16 finished end-to-end: 2 ACCEPT and 14 HUMAN_REVIEW after at most one extra investigation round.
- **Three architectures side by side (17 stored dev cases, chosen for coverage, not sampled).** Root-cause accuracy was 6% for LLM Only, LLM + Graph and LLM + Graph + Jev alike (1 of 17); issue-category accuracy was 71% / 41% / 35%; the graph agent abstained on the root cause in 41% of cases (LLM Only 59%, whose prompt prefers null to a guess), and the verifier sent 88% of cases to human review. The set deliberately includes cases where the graph agent's stored run was wrong, so this is not evidence about the architectures in general.
- **The agent itself is still weak.** It abstains often, and Phase 6 judges only 3 of the 72 verification cases correct (Phase 6's text matching under-counts paraphrases). Improving the agent or model is the named next step.

---

## Live demo app — what it does

### 1. Dual-Confidence Case Extraction
Every free-text submission passes through a two-stage pipeline before graph traversal even starts:

```
User Input
   │
   ▼
Keyword Extraction (LLM)
   │
   ├─ ≥ 0.80 confidence → Auto-assign product  [🟢]
   ├─ 0.60–0.79          → Confirm with user    [🟡]
   └─ < 0.60             → Semantic Search
                               │
                               ├─ ≥ 0.80 similarity → Auto-assign  [🟢]
                               ├─ 0.50–0.79          → Confirm       [🟡]
                               └─ < 0.50             → Manual Picker [🔴]
```

| Badge | Path | What the user sees |
|-------|------|--------------------|
| 🟢 Auto-assign | High confidence | Case goes straight to graph analysis |
| 🟡 Needs confirmation | Medium confidence | Yes / Let me select buttons appear |
| 🔴 Manual selection | Insufficient evidence | Product dropdown + rephrase option |

### 2. Graph Intelligence (4-hop traversal)
Once a product is confirmed, the agent traverses Neo4j:
1. **Customer profile** — tier, history, prior cases on this product
2. **Similar resolved cases** — filtered by product, ordered by resolution time
3. **Best-match agents** — ranked by skill match × 3 + cases resolved + KB articles used × 0.5
4. **KB articles** — resolution rate > 70%, ordered by effectiveness

Every WITH GRAPH response is paired with a WITHOUT GRAPH baseline to make the graph lift visible.

### 3. A third answer: With Graph + Jev
The main page now shows three answers to the same ticket: **Without Graph** (general knowledge), **With Graph Intelligence** (recommendation written from the retrieved graph data) and **With Graph + Jev**
(that recommendation checked against the very data it was written from, `agent/triage_verifier.py`). The check has four deterministic grounding checks (named agents and articles come from the retrieved data, quoted
resolution times / rates / usage counts match it, the retrieved evidence is actually used, enough was retrieved), four typed Jev signals (unsupported claims, missed evidence, anchoring on weak options, review
NORMAL / REVIEW / PRIORITY_REVIEW) and a plain-code policy: accept, ask the model to **revise once** with the verifier's message, then accept or send to human review / priority review. If Jev cannot be reached the
answer is never auto-accepted. Each column shows LLM / Graph / Jev chips and its latency; the third adds the verdict, the checks, the Jev numbers, the message sent for the revision and the original answer. Turn it off with
**Third column: verify with Jev** in the sidebar. It needs `TYPESAFE_API_KEY`; a revision costs one more Groq call (watch the free-tier token limit below).
The **⚖️ COMPARISON** panel under the answers (Assignment Quality, Response Quality, Observability, Quality Score) gets the same third column. In it the fixed demo values of the first two columns (skill match 23% / 94%, escalation risk, confidence, typed-in token estimates) are left as they were and labelled; the Jev column uses only real values: the agent named in the verified answer with its stored seniority and resolution time, the escalation level that answer states, the verdict, the grounding checks, Jev's numbers, the latency and the Jev and revision call counts. Where verification ran, With Graph's fixed "Hallucination Risk: None" is replaced by the measured grounding result of that answer. A revision is never allowed to replace a grounded answer with an ungrounded one (the original is kept and still flagged). The quality score uses the app's original formula, which does not measure grounding, so verification can only lower it (through latency); grounding is shown next to it.
This verifies a *recommendation*, not a diagnosis, and Jev was evaluated in this project on diagnostic traces, not on recommendations, so treat it as a demonstration with hand-set thresholds. The diagnostic agent (Phases 5-9)
cannot take free text: it works on cases already in its graph, on the **Diagnostic Agent** page. The quality-score numbers are the app's original heuristics, not measurements.

### 4. Measurement Dashboard
A separate Streamlit page (`/dashboard`) tracks 7 KPI sections:
- Technical quality (precision, recall, F1)
- Business value (CSAT, FCR, escalation rate)
- Financial impact (cost per resolution, monthly savings)
- Before vs. after comparison
- Key insights
- Formula reference
- **Extraction confidence distribution** — % auto-assigned / confirmed / manual picked

---

## Stack

| Component | Technology |
|-----------|-----------|
| Graph database | Neo4j AuraDB Free |
| LLM (reasoning) | `openai/gpt-oss-120b` via Groq API |
| LLM (extraction) | Same model, `temperature=0`, max 300 tokens |
| Semantic search | `sentence-transformers` · `all-MiniLM-L6-v2` |
| Similarity | Cosine similarity via NumPy (pre-embedded at startup) |
| LLM framework | LangChain 0.2.16 — LCEL + RunnableWithMessageHistory |
| Observability | LangSmith — project `support-intelligence-poc` |
| UI | Streamlit 1.35 — light theme |
| Language | Python 3.11+ (developed and tested on 3.13) |

The offline research program (Phases 1-9) adds:

| Component | Technology |
|-----------|-----------|
| Runtime graph | A **second** Neo4j AuraDB instance (`NEO4J_V2_*`), 116,868 nodes / 325,539 relationships, read-only for the agent |
| Diagnostic agent model | `meta-llama/Llama-3.3-70B-Instruct-Turbo` on Together AI, temperature 0.1, direct HTTP (no `langchain-openai`) |
| Jev | Direct-HTTP client `agent/jev_v2/client.py`, model `jev-1.13.0` (never the `typesafe-sdk` package) |
| Agent protocol | One schema-constrained JSON action per turn (`response_format` JSON schema), validated again in code |
| Verification | Deterministic checks + three Jev signals + a plain-code policy |

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

`sentence-transformers` will pull PyTorch — first install takes ~2 minutes.

### 2. Create `.env`

```bash
cp .env.example .env
```

Required variables:

```
GROQ_API_KEY=          # console.groq.com → API Keys
LANGCHAIN_API_KEY=     # smith.langchain.com → Settings → API Keys
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=support-intelligence-poc
NEO4J_URI=             # neo4j+s://<id>.databases.neo4j.io
NEO4J_USERNAME=        # AuraDB instance username
NEO4J_PASSWORD=        # AuraDB instance password
```

The offline research phases use additional variables that the live app ignores
(all listed in `.env.example`):
`NEO4J_V2_URI` / `NEO4J_V2_USERNAME` / `NEO4J_V2_PASSWORD` (the Phase 4 graph),
`TOGETHER_API_KEY` (Phase 1-3 narratives, the Phase 5 and Phase 9A agents, the Phase 7/8 LLM baseline) and
`TYPESAFE_API_KEY` (Jev: Phase 7/8 evaluations and the Phase 9 runtime verifier).

### 3. Generate synthetic data (one-time)

```bash
python3 data/generate_data.py
```

Produces 14 CSV files in `data/raw/`:
- 2,000 customers · 10,000 cases · 50 products · 501 KB articles · 150 agents · 40 skills
- ~47,435 relationship edges

> **Note:** `data/` also contains a much larger, three-phase synthetic-data
> research program (`raw_v2/`, `phase2/`, `phase3/` — 25,000 cases,
> ~2M rows total) built for offline evaluation and future agentic-eval
> work. It is separate from, and not read by, the live app described here —
> see [`data/README.md`](data/README.md) for what it is and how it's built.
>
> That research dataset now also has a Neo4j runtime graph
> (`agent/graph_v2/`) loaded into a **second, separate** AuraDB instance —
> see [`docs/GRAPH_SCHEMA.md`](docs/GRAPH_SCHEMA.md). It requires its own
> `NEO4J_V2_URI`/`NEO4J_V2_USERNAME`/`NEO4J_V2_PASSWORD` in `.env` and never
> touches the `NEO4J_*` instance/credentials the live app above uses.
>
> A baseline autonomous diagnostic agent (`agent/agent_v2/`) now investigates
> cases in that graph through a 14-tool read-only layer, with zero access to
> hidden ground truth — see
> [`docs/BASELINE_AGENT_ARCHITECTURE.md`](docs/BASELINE_AGENT_ARCHITECTURE.md).
> It defaults to Together AI (`TOGETHER_API_KEY`, already used for Phase 1-3
> narrative generation) rather than this app's Groq setup — Groq's free-tier
> rate limit proved too tight for a multi-step tool-calling agent — but it
> is otherwise fully separate code. See `docs/AGENT_EXPERIMENTS.md` to run
> it.
>
> A deterministic evaluation harness (`agent/eval_v2/`, no LLM judge, no
> Jev) now scores those agent runs against Phase 1-3's hidden ground truth
> and reports many independent metrics (outcome correctness, evidence
> retrieval, calibration, contract compliance, efficiency) rather than one
> blended score — see
> [`docs/EVALUATION_ARCHITECTURE.md`](docs/EVALUATION_ARCHITECTURE.md) and
> [`docs/EVALUATION_EXPERIMENTS.md`](docs/EVALUATION_EXPERIMENTS.md) (the
> latter documents an important early finding: the current baseline agent
> almost never populates its ID-valued prediction fields).
>
> Phase 7 (`agent/jev_v2/`) evaluates **Jev** — TypeSafe AI's typed,
> probabilistic decision model — offline, as an individual-decision primitive.
> It is not wired into the agent and is not used as a judge or guardrail.
> Each decision is one observable case snapshot, one narrow question, and a
> fixed answer space (issue category, root cause, causal change, owning team,
> evidence sufficiency, incident relationship). Answers are scored
> deterministically against the same hidden truth and the same
> dev/validation/test splits Phase 6 uses, and compared with a plain LLM
> baseline (Llama-3.3-70B via Together AI) on identical inputs. Detailed
> results live in the experiment reports and docs, not here — see
> [`docs/JEV_PRIMITIVE_ARCHITECTURE.md`](docs/JEV_PRIMITIVE_ARCHITECTURE.md),
> [`docs/JEV_EVALUATION.md`](docs/JEV_EVALUATION.md),
> [`docs/JEV_STAGE_B_FREEZE.md`](docs/JEV_STAGE_B_FREEZE.md),
> [`docs/JEV_STAGE_C_PROTOCOL.md`](docs/JEV_STAGE_C_PROTOCOL.md),
> [`docs/JEV_STAGE_C_VALIDATION.md`](docs/JEV_STAGE_C_VALIDATION.md),
> [`docs/JEV_STAGE_C_REVIEW.md`](docs/JEV_STAGE_C_REVIEW.md),
> [`docs/JEV_LOCKED_BENCHMARK_PROTOCOL.md`](docs/JEV_LOCKED_BENCHMARK_PROTOCOL.md) and
> [`docs/JEV_ISSUE_LOG.md`](docs/JEV_ISSUE_LOG.md).
>
> **Jev integration and a dependency constraint.** Jev is called through a
> small dependency-free `requests` client (`agent/jev_v2/client.py`, POST
> `https://api.typesafe.ai/v1/systemone`). Do **not** `pip install
> typesafe-sdk`: it requires `tenacity>=9`, which silently upgrades `tenacity`
> and breaks the `tenacity<9` pin shared by `langchain==0.2.16`,
> `langchain-core==0.2.43`, `langchain-community==0.2.16` and
> `streamlit==1.35.0` (`pip check` will show the conflict). Set
> `TYPESAFE_API_KEY` in `.env`; only `agent/jev_v2/` reads it.
>
> **Staged workflow.** Stage A (smoke/regression) and Stage B (dev split) are
> done; the Stage B configuration is frozen in
> `data/eval/jev/stage_b_frozen_v1.json` with a hash manifest that pins every
> question, candidate-generation and context version, the Jev model
> (`jev-1.13.0`) and the model-input source files. Stage C runs that frozen
> configuration once, unmodified, against the validation split (the runner
> refuses any override or drift):
>
> ```bash
> python3 -m agent.jev_v2.run_experiment --name stage_c_validation \
>     --kind validation --split validation --compare-llm \
>     --frozen-config stage_b_frozen_v1 --workers 8
> ```
>
> The locked test split is a one-shot holdout. Its configuration is sealed in
> `data/eval/jev/locked_benchmark_frozen_v1.json` (with a hash manifest that
> pins the code, the pre-registered protocol and the Stage C artifacts); the
> runner refuses `--split test` without `--kind locked_benchmark` and that
> configuration, refuses every override and subset, and after the run starts
> accepts only a `--resume` of the same run. `--check-only` verifies every guard
> without loading any case. The locked split is not opened without explicit
> approval. Current phase: Phase 7, offline Jev primitive evaluation — Stage C
> validation has been run and reviewed. The v1 locked configuration is recorded
> as **superseded before use**: a pre-registered validation control
> (`docs/JEV_OPAQUE_KEY_CONTROL.md`) found that Jev's causal-change answers
> depend on the option-key identity. The locked benchmark has not been run and
> is not ready to run; a replacement configuration is proposed, not created.

> **Phase 8** (`agent/trace_eval_v2/`) evaluates **Jev as a trace evaluator**: whether it can
> judge the support, missed evidence, anchoring, premature closure, final-answer consistency and
> human-review need of a *completed* Phase 5 agent run. Six independent typed questions per trace
> (Jev and, on the identical packet, an LLM judge), scored against deterministic reference labels
> and 165 controlled trace perturbations, on 150 dev traces only. Jev is a passive observer and never
> the ground truth; nothing is gated at runtime (that is Phase 9). Measured result: Jev is a useful
> supporting signal for missed evidence, distractor anchoring and PRIORITY triage, and simple
> deterministic rules do as well for lexical support, premature close and consistency. Phase 8 is
> complete. See [`docs/PHASE8_TRACE_EVALUATION.md`](docs/PHASE8_TRACE_EVALUATION.md),
> [`docs/TRACE_EVAL_QUESTION_CATALOG.md`](docs/TRACE_EVAL_QUESTION_CATALOG.md),
> [`docs/TRACE_EVAL_REFERENCE_LABELS.md`](docs/TRACE_EVAL_REFERENCE_LABELS.md) and
> [`docs/TRACE_EVAL_DATA_BOUNDARIES.md`](docs/TRACE_EVAL_DATA_BOUNDARIES.md).

### 4. Load into Neo4j AuraDB (one-time)

```bash
python3 agent/neo4j_loader.py
```

Idempotent — safe to re-run. Expected output:
```
Nodes:         12,741
Relationships: 47,435
Load time:     ~14s
```

### Dependency pins (do not change)

`langchain==0.2.16`, `langchain-core==0.2.43`, `langchain-community==0.2.16`, `streamlit==1.35.0` and `tenacity==8.5.0` are a working set: langchain and streamlit both require `tenacity<9`.
**Never `pip install typesafe-sdk`** (it needs `tenacity>=9` and breaks the stack) and never install `langchain-openai` (it force-upgrades `langchain-core`). Jev and Together are reached through small
direct-HTTP clients on purpose. After any install, `pip check` must report no broken requirements (it does today). The unit tests use `jsonschema`, which arrives with Streamlit.


---

## Starting the databases (Neo4j Aura)

Both graphs are **hosted Neo4j Aura instances**, so there is nothing to start locally: `NEO4J_*` is the live app's demo graph (12,741 nodes / 47,435 relationships) and `NEO4J_V2_*` is the Phase 4 agent graph
(116,868 nodes / 325,539 relationships). Aura Free **pauses an instance after about 3 days without a query**, and a paused instance's hostname stops resolving (its data is kept); it is deleted only if it stays paused for about 30 days.

- `./start.sh` checks both databases, prints what is wrong if one is not reachable, then starts the app (`./start.sh --dashboard` also starts the measurement dashboard on port 8502). Running `streamlit run app.py` directly works too.
- Both sidebars (the main app and **Diagnostic Agent**) show a **Databases** block with a per-database status and the fix. The check is one trivial `RETURN 1` per database, cached for five minutes; it counts as activity, so using the app keeps the instances from pausing. If the machine is off for days they can still pause.
- `python3 -m agent.neo4j_health` prints the same status (`--counts` adds node and relationship counts, `--wait 120` retries after you resume an instance). It only reads.
- **Resuming a paused instance needs the Aura console** (console.neo4j.io → the instance → Resume, about a minute). It cannot be done from here without Aura API credentials, which are not configured. If an instance was deleted, create a new free one, update `.env`, and reload
  (`python3 agent/neo4j_loader.py` for the live app; `python3 -m agent.graph_v2.build_graph --mode small --wipe` for the Phase 4 graph).

---

## Running the apps

```bash
# Main chat interface (port 8501)
streamlit run app.py

# Measurement dashboard (port 8502)
streamlit run measurement_dashboard.py --server.port 8502
```

Both apps start together; the main app shows a "📊 Dashboard" button in the top-right that links to port 8502.

### Diagnostic Agent page (Phases 9A and 9)

Open **Diagnostic Agent** in the sidebar of the main app (it is `pages/1_Diagnostic_Agent.py`; restart `streamlit run app.py` if it does not show). Pick a **dev case** and an **execution mode**:

| Mode | What runs | Graph | Jev |
|---|---|---|---|
| **LLM Only** | The ticket and the issue-category / root-cause vocabulary go to the model once. No Neo4j, no tools. | ✕ | ✕ |
| **LLM + Graph** | The autonomous agent with the Neo4j tool layer and evidence retrieval. The unchanged baseline: no early triage, no verification. | ✓ | ✕ |
| **LLM + Graph + Jev** (default) | **Early Jev** (triage guidance: a provisional category hint from the ticket text, before any graph tool), then the agent, then **late Jev** (verification: deterministic checks, three Jev signals, the policy, and one extra investigation round if asked). | ✓ | ✓ |
| **Compare All** | The three above on the same case, side by side. | | |

- **Stored or live.** Each architecture shows whether a stored result exists; stored results open instantly with no API call. **Load available stored results** reloads them, **Run missing modes** runs only what is missing (in parallel, with a live progress panel and a cost estimate first), **Re-run all three live** starts over. Live runs are saved, so an interrupted page loses nothing.
- **Compare All** shows an architecture card per mode (label, LLM / Graph / Jev badges, root cause, component, confidence, tools, evidence, latency, cost, and the verifier's decision and risks for the Jev card), highlights where architectures disagree, a comparison table, **What the Graph Added** (evidence, changes, incidents, similar cases, whether the diagnosis changed), **What Jev Added**, in two labelled parts: *Early Jev — triage guidance* (the suggested category, its probability and uncertainty, whether the agent kept, changed or dropped it; always marked provisional, never shown as a diagnosis) and *Late Jev — answer verification* (initial diagnosis, missed-evidence and distractor risk, review signal, extra tool calls, final disposition, whether verification changed the answer) and **Architecture Impact**. All of this is computed deterministically from the results (no extra model call) and is descriptive: it never says one answer is better.
- **Traces.** Expandable tool trace for the graph modes and a per-pass runtime-verification trace for the Jev mode. Only structured state and tool results are shown; no reasoning text.
- **Show evaluation / ground truth** (off by default, dev cases only) adds a separate panel scoring each architecture against the dev ground truth (✓ / ✕ / ABSTAIN). It runs only after the results exist and never feeds back into a run.
- **Architecture Results** tab: a small aggregate over stored dev cases that have a result for all three architectures, with N always shown. It is a look at stored runs, not a benchmark.

Live runs need `TOGETHER_API_KEY`, the Phase 4 graph and, for the Jev mode, `TYPESAFE_API_KEY`; about $0.001 (LLM Only), $0.02 (LLM + Graph) and $0.03 (LLM + Graph + Jev, early and late Jev together) per case. Stored LLM + Graph + Jev runs made before early triage existed show "Early Jev: not used". The page works on cases already in the graph, not on free-text tickets (use the main page for those).

### Quick-prompt chips
The empty state shows 3 one-click scenarios to demo without typing:

| Chip | Product | Customer tier |
|------|---------|---------------|
| Payment Gateway Refund Failure | Payment Gateway v2.1 | Gold |
| SSO Onboarding Blocked | SSO Integration Module | Gold |
| Analytics Export Corruption | Analytics Dashboard | Gold |

---

## CLI demo (original)

The original terminal-mode demo is still available:

```bash
python3 agent/main.py                 # interactive picker
python3 agent/main.py --scenario A    # Payment Gateway
python3 agent/main.py --scenario B    # SSO
python3 agent/main.py --scenario C    # Analytics
python3 agent/main.py --all           # all 3 (62s cooldown between runs)
```

---

## Graph schema (live app)

```
(Customer)-[:RAISED]->(Case)-[:ABOUT]->(Product)
(Agent)-[:RESOLVED]->(Case)
(Agent)-[:HAS_SKILL]->(Skill)
(Case)-[:REQUIRES_SKILL]->(Skill)
(Agent)-[:USED]->(KnowledgeArticle)
(KnowledgeArticle)-[:COVERS]->(Product)
(Case)-[:SIMILAR_TO]->(Case)
```

---

## Automated Evaluation Suite (live app)

Run the full eval suite to validate system quality and log results to LangSmith:

```bash
python3 run_evals.py            # live run — hits Neo4j + Groq + LangSmith
python3 run_evals.py --dry-run  # stub results only — still logs to LangSmith
```

### 6 eval categories (20 test cases total)

| # | Category | What it checks | Test cases |
|---|----------|---------------|------------|
| 1 | **Skill Match** | `find_best_agents()` returns agents covering required skills | 3 |
| 2 | **Confidence Calibration** | HIGH-confidence extractions map to the correct product | 3 |
| 3 | **Semantic Search** | `SemanticMatcher` routes product-adjacent descriptions correctly | 5 |
| 4 | **Graceful Degradation** | Vague / nonsense inputs reach the manual product picker | 3 |
| 5 | **Latency** | Full graph recommendation completes in < 10 s | 3 |
| 6 | **Resolution Time** | Top-ranked agents outperform random by ≥ 1 hour | 3 |

### Viewing results in LangSmith

Each run creates a uniquely-named experiment (`evals-support-intelligence-YYYY-MM-DD-HH-MM-SS`):

1. Open `smith.langchain.com`
2. **Projects** → `support-intelligence-poc`
3. **Datasets & Testing** → `support-intelligence-evals`
4. Filter traces by the experiment tag to see all 20 test results

Compare two experiments side-by-side to track improvements across versions:
```
Run 1: evals-support-intelligence-2026-06-20-09-00-00  →  19/20  (95%)
Run 2: evals-support-intelligence-2026-06-21-10-30-00  →  20/20  (100%)
```

Each test case is logged as a structured Run with:
- `inputs` — the structured test input (agent name, user text, scenario)
- `outputs` — actual result (score, latency, similarity, etc.)
- `pass` feedback — 1.0 / 0.0 per test case
- `score` feedback — numeric metric where applicable
- Tags — `[experiment_name, eval_category]` for filtering

---

## Confidence thresholds

Configurable in `config/settings.py`:

| Constant | Default | Meaning |
|----------|---------|---------|
| `CONF_HIGH` | `0.80` | Auto-assign, no user interaction |
| `CONF_MEDIUM` | `0.60` | Show confirmation dialog |
| `CONF_LOW` | `0.50` | Semantic floor — below this → manual picker |

---

## Observability

LangSmith traces every LLM call (both extraction and reasoning) at:
`smith.langchain.com → Projects → support-intelligence-poc`

The WITH GRAPH calls include the full structured graph context as the human message, making it straightforward to audit what the model received vs. what it produced.

---

## Token budget (Groq free tier)

Groq free tier: **8,000 TPM** on `openai/gpt-oss-120b`.

| Call | `reasoning_effort` | `max_tokens` | Typical usage |
|------|--------------------|-------------|---------------|
| Extraction | n/a (`temp=0`) | 300 | ~200 tokens |
| Without graph | `low` | 4,000 | ~1,500 tokens |
| With graph | `low` | 4,000 | ~2,500 tokens |

Running `--all` in CLI mode adds a 62-second cooldown between scenarios so the TPM window fully resets.

---

## Diagnostic agent and runtime verifier (Phases 9A and 9)

```
case (a dev case in the Phase 4 graph)
  │
  ▼   LLM + Graph + Jev only:  EARLY JEV = triage guidance (ticket text only, before any graph tool)
  │        typed Choice over the 18 categories + ABSTAIN → plain code → a provisional hint, or a fallback (nothing changes)
  ▼
agent_v3  ── Phase 5 tools, same model, validated, alias-bound ──►  proposed diagnosis          (LLM + Graph = this, alone)
                                                                        │
                    ┌───────────────────────────────────────────────────┴───────────────────────┐
                    ▼                                                                           ▼
        deterministic checks D1-D4                            Jev: missed evidence · distractor anchoring · review signal
                    └───────────────────────────────────┬───────────────────────────────────────┘
                                                        ▼
                          LATE JEV = answer verification; policy.py (plain code decides)
                          ACCEPT · CONTINUE_INVESTIGATION · HUMAN_REVIEW · PRIORITY_REVIEW
                                                        │ CONTINUE (first pass only)
                                                        ▼
                     the same session resumes with the verifier's message and 4 more tool calls → final answer → verified once more
```

### The agent (`agent/agent_v3/`, Phase 9A)

Phase 5's model and read-only tools, made to obey a contract. Nothing in Phases 1-8 was modified.

- **Protocol.** The harness runs `get_case_context` as step 1. Each later turn the model returns one JSON object under a provider-enforced schema: its current hypotheses (1-4, each with a status of active / rejected / confirmed and evidence citations), a tool, and that tool's arguments. Finalization is a second constrained call.
- **Registry and aliases.** Everything the model may name (products, components, teams, evidence, changes, incidents, the issue-category and root-cause taxonomy) is registered when observed and shown as a hash-keyed alias such as `COMPONENT_KZT`. Aliases are sparse three-consonant codes keyed on the case; they encode no order, recency or role, and canonical ids are never shown. The alias-to-id map stays outside the model and maps answers back deterministically.
- **Tool validation.** A tool name or argument that does not exist is rejected before anything runs with a structured error listing the allowed tools (`tool_contract_repair`, budget 2 per run, never silently rewritten). Component-scoped tools are only offered once a component has been observed. Tool descriptions say what data exists (technical signals are the closest thing to a log feed; there is no raw log search).
- **Final answer.** `status` is DIAGNOSIS_PROPOSED, INSUFFICIENT_EVIDENCE or HUMAN_REVIEW_REQUIRED (CONTRACT_FAILURE is assigned only by the harness). Optional selections (issue category, root cause, component, causal change, owning team) may be `null`: abstaining is valid, inventing an id is not. Every citation must be evidence actually retrieved. One repair is allowed (`final_contract_repair`); a second failure is CONTRACT_FAILURE with human review.
- **What the provider enforces.** Probed directly: enums, `minItems`, `maxItems`, `maxLength` and numeric bounds are enforced at decode time; `uniqueItems` is not, and one garbled property name got through. The deterministic validators are therefore authoritative, not decoration.
- **Records.** `data/agent_runs_v3/`, in the Phase 5 run shape (the unchanged Phase 6 evaluator scores them) plus `tool_contract_errors`, `tool_contract_repairs`, `final_contract_errors`, `final_contract_repair`, `registry_snapshots`, `alias_mappings` and `validation_result`. The machine-readable contract is `agent/contracts/agent_contract_v1.json`, generated from the code and checked against it.
- **Cohorts.** `agent/agent_v3/cohorts.py` fixes two disjoint dev cohorts (50 for iteration, 100 for verification), stratified by contract-relevant situation, before any run.

### The runtime verifier (`agent/runtime_verifier/`, Phase 9)

| Check | Type | Question |
|---|---|---|
| D1 valid final contract | deterministic | Schema, bounds and every cited item or selected entity retrieved before the answer (computed from the alias map, independently of the agent loop). |
| D2 evidence support | deterministic | Does a proposal cite retrieved evidence and rest on a supported hypothesis? |
| D3 final consistency | deterministic | Confidence vs. top hypothesis; confidence of 0.8 or more despite stated uncertainty; a final top hypothesis never stated and matching no retrieved evidence. |
| D4 premature finalization | deterministic | No evidence at all, or no supported hypothesis while at least 2 tool calls were still available. |
| Missed evidence | Jev, P(yes) | Does it appear that important evidence was missed? |
| Distractor anchoring | Jev, P(yes) | Is the investigation anchored on weak evidence while stronger evidence exists? |
| Review signal | Jev, choice | NORMAL / REVIEW / PRIORITY_REVIEW. |

Jev reuses the Phase 8 review packet, question versions and leakage-guarded client; it is never asked which root cause is right. **Policy** (`policy.py`, thresholds in `models.VerifierConfig`, hand-set and untuned): invalid answer or references → HUMAN_REVIEW; premature, unsupported, missed-evidence ≥ 0.75 or distractor ≥ 0.75 → CONTINUE_INVESTIGATION on the first pass and HUMAN_REVIEW on the second; Jev unreachable → HUMAN_REVIEW (never auto-accept); Jev review = PRIORITY → PRIORITY_REVIEW; inconsistent answer → HUMAN_REVIEW; the agent proposed nothing or asked for review → HUMAN_REVIEW; confidence below 0.55 → HUMAN_REVIEW; otherwise ACCEPT. There are never more than two verification passes.
Each verified run stores the initial and final result, every pass's checks and Jev numbers, the policy decisions, whether the extra round ran, latency, estimated cost and, when a person is needed, a review packet (`data/runtime_verifier_runs/`).

### Jev early triage (`agent/early_triage/`, `agent/agent_v3/triage_hint.py`)

Jev has two separate roles. **Early Jev = triage guidance**: right after the case report is loaded and before the first graph tool, it reads the ticket and suggests an issue category. **Late Jev = answer verification** (the section above, unchanged).
Full write-up: `docs/PHASE9_EARLY_TRIAGE.md`.

- **Call sequence.** case context → `EarlyTriage(ctx)` (one typed Jev Choice over the 18 taxonomy categories plus an explicit `ABSTAIN`) → validation → plain-code policy → hint text → the agent loop as before → final answer → `triage_outcome` recorded → late verification. The single insertion point is `agent_v3/loop.py::run_case`, right after step 1; the loop takes an injected `triage` callback and never imports Jev.
- **What Jev sees.** An allow-list of the case context only: ticket text, environment, region, impact, priority, customer tier / industry / size, product name. No ids, dates, status, signals, telemetry or graph result. The existing Phase 7 client and leakage guard are reused; a guard trip is never suppressed.
- **What the agent is told.** A block that says, in effect: *provisional, unverified; source Jev, ticket text only; category X with probability p and low/moderate/high uncertainty; other plausible categories; a prior, not a finding; test it, reject or replace it; not evidence, cannot be cited; advisory starting tools for this category.* The tool catalog, action schema and final schema are untouched, so no tool, category or evidence item is filtered away.
- **Plain code decides what to do with the answer.** ABSTAIN, a top probability below 0.30, an invalid answer (unknown choice, bad table, choice not the maximum), an API error, a 20 s timeout, a missing key, or a category that is not in the graph's taxonomy is a **fallback**: no hint, and every prompt is byte-identical to the unchanged workflow (a test pins this, including a hash of the baseline prompts taken before the code was edited). Uncertainty bands (low ≥ 0.70, moderate ≥ 0.40, else high), the 0.30 minimum and the advisory tool map are hand-set and unvalidated.
- **What is recorded.** The early prediction and distribution, probability, uncertainty, latency, Jev input tokens, model, fallback status and reason, the exact hint text shown, and `triage_outcome` = confirmed / changed / dropped / no_suggestion for both the agent's first answer and its final answer.
- **What the page shows.** A one-line "Early Jev (triage guidance)" on the card ("provisional suggestion, not a diagnosis — the agent kept / changed it"), an *Early Jev* part in **What Jev Added**, a comparison-table row, and an expander with the distribution, the advisory tools and the exact text the agent saw.
- **What it does not do.** It does not feed the late verifier (the verifier's packet is built from the trace and the graph only; a test checks the packet has none of the hint), and the policy does not use the suggestion. The agent's answer, which the late verifier does see, can of course echo the hint.
- **Mode decision.** LLM Only never calls Jev or the graph. **LLM + Graph is the unchanged baseline** (no triage, no verification). **LLM + Graph + Jev has both**: early triage and late verification.

**Dev comparison (35 dev cases, one run per arm, descriptive only; details in `docs/PHASE9_EARLY_TRIAGE.md`).** Early Jev gave a hint on every case and was right on 27 of 35 (77%). The agent's first answer had the right category on 21 of 35 against 14 of 35 for the stored LLM + Graph baseline (11 cases won, 4 lost, p = 0.12, not significant). But the agent never disagreed with Jev: it kept the hint in 29 cases (all 8 wrong hints included), so the gain is Jev's ticket-only accuracy, not evidence-driven correction. Critical-evidence recall was 81% vs 59% at the same number of tool calls. Late verification sent 33 of 35 to review and the extra round cost about twice as much; 3 runs ended in CONTRACT_FAILURE in that round because the agent kept the hinted category without evidence to cite. No improvement is claimed.

### The comparison layer (`agent/compare/`)

One `ComparisonResult` schema and one set of adapters turn every architecture's stored or live record into the same shape, so the page has a single rendering path. The mode boundaries are structural:
`llm_only.py` imports nothing but the model transport and config (a test checks its import closure and that no graph or Jev object is reachable), the graph mode calls the agent loop with `verifier=None`, and the Jev mode is
`run_verified_case`. `evaluation.py` is the only module that reads ground truth; runtime modules cannot import it (also tested). `insights.py` builds every comparison sentence from the results alone. LLM Only's records are in `data/comparison_runs/`.
LLM Only's free-text component is not comparable with the graph agent's selected component, so "diagnosis changed" between them is judged on issue category and root cause only.

### Commands

```bash
# Phase 9: one dev case through agent -> verifier -> policy -> optional second round (live: Together + Jev, ~$0.03)
python3 -m agent.runtime_verifier.run CS00729
python3 -m agent.runtime_verifier.show CS00729 CS01031     # print stored end-to-end traces (an ACCEPT, and a CONTINUE that ends in HUMAN_REVIEW)
python3 -m agent.runtime_verifier.smoke                    # the 16-case dev smoke set

# Three-architecture comparison (results appear in the Diagnostic Agent page)
python3 -m agent.compare.cli CS00729 --modes llm_only                 # cheap: one direct model call
python3 -m agent.compare.cli --smoke --modes llm_only                 # the 16 dev smoke cases
python3 -m agent.compare.cli CS00019 --modes llm_only llm_graph llm_graph_jev   # all three in parallel (about $0.05, a few minutes)

# Jev early triage (live: Together + Jev, about $0.03 per case)
python3 -m agent.runtime_verifier.run --early-triage CS00014          # early triage + agent + late verifier on one dev case
python3 -m agent.early_triage.run_dev --limit 3                       # the fixed dev case list (72 cases); resumable; use `caffeinate -i`
python3 -m agent.early_triage.evaluation                              # offline: compare with the stored LLM + Graph baseline (reads dev ground truth)

# Phase 9A: agent only
python3 -m agent.agent_v3.dry_run --n 3                    # real graph, stub model, no API cost: plumbing and leakage check
python3 -m agent.agent_v3.cohorts --show                   # the two fixed dev cohorts
python3 -m agent.agent_v3.run_batch --cohort iter50 --tag my_run       # spends Together credits; resumable by tag; use `caffeinate -i` on a laptop
python3 -m agent.agent_v3.evaluate --tag my_run --cohort iter50        # protocol metrics + before/after vs Phase 5 + observational outcomes (offline)
python3 -m agent.agent_v3.contract_export                  # does agent/contracts/agent_contract_v1.json match the code?
```

---

## Research pipeline reference (Phases 1-8)

Each phase has its own docs (see the table above and `docs/`). Frozen or closed phases should be re-run only to reproduce, never to tune.

```bash
python3 -m agent.graph_v2.build_graph --mode small --wipe   # Phase 4: build the 2,500-case runtime graph (second Neo4j instance)
python3 -m agent.agent_v2.run_single --case-id CS00191      # Phase 5: one baseline-agent investigation with its trace
python3 -m agent.agent_v2.run_batch --n 10                  # Phase 5: a controlled batch (one JSON per run in data/agent_runs/)
# Phase 6: the dev / validation / test partition is locked; see docs/EVALUATION_SPLITS.md (never regenerate it, never evaluate on test)
python3 -m agent.eval_v2.run_experiment --help              # Phase 6: run-and-evaluate or evaluate-existing (docs/EVALUATION_EXPERIMENTS.md)
python3 -m agent.trace_eval_v2.cli check --stage smoke      # Phase 8: build every packet and run the leakage guard; no API call
```

Phase 7 (`agent/jev_v2/`) is closed: its Stage B configuration is frozen and its locked benchmark was superseded before use and must not be run (`docs/JEV_ISSUE_LOG.md`, `docs/JEV_LOCKED_BENCHMARK_PROTOCOL.md`).

---

## Safety rules and data boundaries

- **Hidden truth stays in evaluation code.** Ground truth (`*_ground_truth.csv`, `data/eval/eval_store.py`) is read only by evaluators, after a run exists. The agent, the verifier and every judge see runtime-observable state only: no `gt_*` fields, no hidden causal labels, no Phase 6 scores. Enforced by import-closure checks, tests that build real packets with the hidden-truth readers replaced by tripwires, and a leakage guard (`agent/trace_eval_v2/guard.py`) applied to every Jev request.
- **Dev cases only.** Every phase after 6 uses the dev split. The locked test split has not been used by any evaluation; Phase 7's locked benchmark was never run.
- **Jev is a signal, not a decision maker,** and is never asked for a root cause. Plain code (`policy.py`) decides.
- **Opaque ids.** Model-facing identifiers are aliases, because Phase 7 found that identifier structure can influence a model.
- **No chain-of-thought** is requested, stored or evaluated; only structured hypothesis state.
- **Read-only graph.** The agent's Cypher is MATCH/RETURN only, time-gated by a harness-owned clock. Graph counts are re-checked by the validators.
- **Frozen phases stay frozen.** `data/eval/agent_contract_9a/frozen_inputs_9a.json` holds sha256 pins of the Phase 1-8 files taken before the first Phase 9A live run; `validate_boundaries` compares against them.
- **Dependencies:** see [Dependency pins](#dependency-pins-do-not-change).

---

## Testing and verification

| Command | Covers | Expected |
|---|---|---|
| `python3 -m unittest agent.agent_v3.test_agent_v3` | Phase 9A agent: validators, registry, aliases, repair budgets, loop, evaluator mechanics, provider client | 42 tests OK, offline |
| `python3 -m unittest agent.runtime_verifier.test_runtime_verifier` | Verifier: deterministic checks, policy, the one-retry loop, boundary tests | 19 tests OK (one reads the live graph) |
| `python3 -m unittest agent.early_triage.test_early_triage` | Early triage: call order (before any graph tool), the hint reaches every prompt as provisional guidance, no tool / category / schema is narrowed, baseline prompts byte-identical, every fallback (abstain, low probability, invalid answer, Jev error, timeout, missing key, out-of-taxonomy) leaves prompts identical, a wrong initial category is changed / confirmed / dropped and recorded, the late verifier's packet never contains the hint, the mode boundaries, hidden-truth isolation (import closure, allow-list, guard trip not suppressed, no truth reader called), the page | 36 tests OK (one reads the live graph and is skipped if unreachable) |
| `python3 -m unittest agent.compare.test_compare` | Comparison: LLM Only never touches the graph or Jev, graph mode never touches Jev, the Jev mode runs the verifier, ground truth is read only after the runs, the page renders stored and missing results without API calls | 19 tests OK (page tests read stored dev runs) |
| `python3 -m unittest agent.trace_eval_v2.test_trace_eval` | Phase 8 | 45 tests OK, offline |
| `python3 -m unittest agent.jev_v2.test_v2` | Phase 7 | 60 tests OK, offline |
| `python3 -m agent.agent_v2.validate_boundaries` / `agent.eval_v2.validate_boundaries` / `agent.trace_eval_v2.validate_boundaries` | Phase 5 / 6 / 8 hidden-truth and direction-of-import boundaries | all checks green |
| `python3 -m agent.agent_v3.validate_boundaries` | Phase 9A: import closure, alias properties, real-graph leak replay, dev-only, frozen files, pins, graph counts | 11/11 (needs the Phase 4 graph) |
| `python3 -m unittest agent.test_triage_verifier` | The main page's third column and its COMPARISON panel: grounding checks on a realistic recommendation, every policy path, the one-revision flow and the never-worsen rule, the leakage guard on a real packet, no evaluation code reachable, the real panel rendered for every state | 25 tests OK, offline (includes rendering the real comparison panel) |
| `python3 -m unittest agent.test_neo4j_health` | Neo4j health check: paused / wrong password / not configured / healthy are told apart; it never writes | 5 tests OK, offline |
| `pip check` | Dependency consistency | no broken requirements |

None of these calls a paid API. Only the commands that say so do (`run_batch`, `runtime_verifier.run` / `smoke`, the page's live button).

---

## Known limitations and status

- **The agent is weak.** Phase 6 judges only 3 of 72 verification cases correct, and it abstains often (about half of the finals select nothing). Diagnostic quality was deliberately not optimized in Phase 9A.
- **The verifier is an MVP.** Thresholds are hand-set and untuned; Jev's signals are not calibrated for production (it over-alarms on missed evidence and distractors, and its NORMAL probability never exceeded 0.01 in the smoke passes, so its review signal cannot by itself justify ACCEPT). Only 16 dev cases were smoke-tested; that cannot show whether the verifier discriminates good from bad answers.
- **The extra investigation round did not rescue any case** in the smoke set. In most continued cases the agent, told to look further, retreated from a diagnosis to INSUFFICIENT_EVIDENCE.
- **Phase 9A is unfinished.** The 100-case verification stopped at 72 of 100 (95.8% first-pass final validity on those 72); there is no separate Phase 9A write-up, so this README and `agent/contracts/agent_contract_v1.json` are its documentation.
- **Scope of the page.** It runs cases already in the graph; it does not take free-text tickets. Its live-run button was not exercised in a browser (the stored and agent-only views were tested headlessly; the live function is the one the command-line smoke run used).
- **Environment.** The directory is not a git repository, so the sha256 pins and Phase 7 manifests are the only integrity record of frozen work. Provider balances matter: Together returned flapping HTTP 402s when credits ran low (the client retries for about three minutes before stopping), and a laptop sleeping mid-batch hung workers (use `caffeinate -i`; batches resume by tag).
- **The comparison view is a lens, not a verdict.** Its 17-case aggregate uses cases chosen for coverage (including ones where the graph agent's stored run was wrong), the three results per case come from separate, non-deterministic runs, and LLM Only is allowed to answer null (it does so for the root cause in most cases). Its component and team are free text, so they are only compared with the graph modes by containment in the optional evaluation panel.
- **The main page's Jev column is a demonstration.** On the one real ticket tried end to end (the refund-error example) every grounding check passed while Jev put unsupported claims at 0.85, so the answer was revised once and then accepted at 0.67: Jev may be reacting to interpretive statements the graph data does not contain, and its numbers are not calibrated for this artifact.
- **Early triage is anchoring, so far.** In the 35-case dev comparison the agent adopted every wrong early hint (8 of 8) and changed none; 3 runs failed the final contract after keeping a hinted category without evidence; one case (CS00182) hit a Together grammar-compile error and was not re-run. The hint wording, the 0.30 floor and the advisory tool map are unvalidated.
- **Next step** named for the program: improve the agent or model, then run an integrated CaseIQ comparison.

---

## Project structure

```
├── app.py                        # Main Streamlit chat interface (live demo app)
├── pages/
│   └── 1_Diagnostic_Agent.py     # Diagnostic Agent page: LLM Only / LLM + Graph / LLM + Graph + Jev / Compare All (dev cases)
├── measurement_dashboard.py      # KPI dashboard (7 sections)
├── run_evals.py · eval_judge.py · langsmith_eval_logger.py   # live-app eval suite (console + LangSmith)
├── evals_dashboard.py · test_extraction.py
├── start.sh                      # checks both Neo4j databases, then starts the app (--dashboard adds the dashboard)
├── requirements.txt · .env.example · .streamlit/config.toml
├── agent/
│   ├── triage_verifier.py · triage_ui.py                            # the main page's third column: grounding checks + Jev + policy, and its rendering
│   ├── neo4j_health.py · db_status_ui.py                            # database health check, CLI and sidebar status block
│   ├── graph_client.py · llm_client.py · semantic_search.py · prompts.py · memory.py
│   ├── cost_callback.py · main.py · neo4j_loader.py · utils.py      # live app + CLI demo (original demo graph)
│   ├── graph_v2/                 # Phase 4: loads raw_v2 + phase2 + phase3 into a SEPARATE Neo4j instance (docs/GRAPH_SCHEMA.md)
│   ├── agent_v2/                 # Phase 5: baseline diagnostic agent + 14-tool read-only layer (historical baseline, frozen)
│   ├── eval_v2/                  # Phase 6: deterministic evaluator, locked splits, experiment registry (hidden truth read here only)
│   ├── jev_v2/                   # Phase 7: offline Jev primitive evaluation; direct-HTTP Jev client; frozen Stage B config
│   ├── trace_eval_v2/            # Phase 8: Jev / LLM judges on agent traces (packet projection, questions, guard; evaluator-side labels and analysis)
│   ├── agent_v3/                 # Phase 9A: contract-hardened agent
│   │   ├── registry.py           #   observed-entity registry, hash-keyed aliases, tool-result exposure
│   │   ├── catalog.py            #   tool catalog, action schema, action validator
│   │   ├── final_contract.py     #   final schema, validator, canonical mapping, CONTRACT_FAILURE result
│   │   ├── loop.py               #   investigation loop; optional verifier callback and one resumed round
│   │   ├── prompts.py · llm.py · backend.py · trace.py · config.py
│   │   ├── cohorts.py · run_batch.py · evaluate.py · dry_run.py      # evaluator-side or harness tooling
│   │   ├── contract_export.py · validate_boundaries.py · test_agent_v3.py
│   ├── early_triage/             # Jev early triage: triage · priorities · config · run_dev · evaluation (offline) · tests
│   ├── runtime_verifier/         # Phase 9: deterministic_checks · jev_checks · policy · verifier · run · show · smoke · models · tests
│   ├── compare/                  # three-architecture comparison: models · llm_only · ticket · adapters · orchestrator · insights · evaluation · aggregate · cli · tests
│   └── contracts/
│       └── agent_contract_v1.json  # machine-readable Phase 9A contract (generated from agent_v3, checked against it)
├── config/
│   └── settings.py               # All env vars + confidence thresholds (live app)
├── docs/                         # Phase 4-9 reference documents (one family per phase)
│   ├── GRAPH_*.md                # Phase 4: schema, data boundaries, query catalog
│   ├── AGENT_*.md · BASELINE_AGENT_ARCHITECTURE.md      # Phase 5
│   ├── EVALUATION_*.md           # Phase 6: architecture, metrics, splits, experiments
│   ├── JEV_*.md                  # Phase 7: architecture, questions, boundaries, Stage B/C, locked-benchmark protocol, issue log
│   ├── PHASE8_TRACE_EVALUATION.md · TRACE_EVAL_*.md     # Phase 8
│   └── PHASE9_RUNTIME_VERIFIER.md                      # Phase 9 (there is no separate Phase 9A doc)
│   └── PHASE9_EARLY_TRIAGE.md                          # Jev early triage: design, boundaries, dev comparison
└── data/                         # see data/README.md for every layer and artifact
    ├── raw/                      # live-app CSVs (gitignored)
    ├── raw_v2/ · phase2/ · phase3/                      # Phases 1-3 synthetic data (+ generators*)
    ├── eval/                     # hidden-truth accessor + splits/, jev/, trace_eval/, agent_contract_9a/
    ├── agent_runs/               # Phase 5 runs
    ├── agent_runs_v3/            # Phase 9A runs
    ├── runtime_verifier_runs/    # Phase 9 verified runs
    ├── early_triage_eval/        # early-triage dev comparison: fixed case lists, one record per case, report_v1.{md,json}
    ├── comparison_runs/          # LLM Only runs (the other two architectures reuse agent_runs_v3 and runtime_verifier_runs)
    └── experiments/              # Phase 6-8 experiment folders + registry.jsonl
```
