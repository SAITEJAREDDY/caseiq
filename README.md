# CaseIQ: Graph-Powered Support Intelligence

*Microsoft AI Graphs TPM Demo · June 2026*

> **Ticket in. Context out. Fewer "have you tried turning it off and on again?" moments.**

---

## TL;DR (for people with 90 seconds and a meeting at 2)

| | |
|---|---|
| **Problem** | Support teams spend the first minutes of every case doing archaeology: Which product is this? Who has seen this before? Which agent knows this? Is there a KB article, or are we about to invent one? |
| **Product** | CaseIQ reads a plain-English ticket, finds the product, walks a Neo4j knowledge graph (customer, similar cases, best-fit agents, proven KB articles), and writes a recommendation grounded in that data. A second model-checker (Jev) audits the answer before anyone trusts it. |
| **Why a graph?** | Support data is a web of relationships, not a spreadsheet. "Who resolved a similar case on this product, using which article, how fast?" is one traversal in a graph and a small adventure in SQL. |
| **Status** | Working demo plus an honest research program. **Not production.** Read "The Honest Scoreboard" before you quote any number to your VP. |
| **Cost to run** | About **$0.001 to $0.03 per case** for the diagnostic agent, depending on how much machinery you switch on. |

---

## The Problem, in Numbers You Can Argue With

Every support org has the same three leaks. The figures below are **illustrative placeholders: swap in your own**.

| Leak | What it looks like | Metric it moves |
|---|---|---|
| **Misrouted cases** | Ticket sits in the wrong queue, gets bounced twice | First-contact resolution (FCR), reassignment rate |
| **Reinvented fixes** | Agent solves a problem the team solved last Tuesday, from scratch | Mean time to resolve (MTTR), cost per case |
| **Unchecked AI answers** | A confident recommendation that confidently cites an agent who does not exist | Escalation rate, trust, your weekend |

CaseIQ goes after all three, and it measures itself while doing it.

---

## Use Cases (a.k.a. Where the ROI Comes From)

### 1. Instant product triage: "Which product is this about?"

**Scenario:** A customer writes *"refunds are failing at checkout and finance is panicking."*

**What CaseIQ does:** A dual-confidence extractor reads the text and picks a path:

| Confidence | Badge | What happens |
|---|---|---|
| 0.80 or higher | 🟢 | Auto-assigns the product. Zero clicks. |
| 0.60 to 0.79 | 🟡 | Asks the user to confirm. One click. |
| Below 0.60 | falls back to semantic search | Auto-assign at 0.80+ similarity, confirm at 0.50 to 0.79, otherwise 🔴 manual picker |

**ROI lever:** Fewer misroutes and no "what product is this?" back-and-forth. A vague ticket degrades gracefully to a human picker instead of being confidently wrong.

---

### 2. Route to the right human, not the next human

**Scenario:** Gold-tier customer, SSO integration blocked, and the on-call agent has never seen SSO.

**What CaseIQ does:** Ranks agents by `skill match × 3 + cases resolved + KB articles used × 0.5`, so the person who has actually fixed this class of problem floats to the top.

**ROI lever:** Lower MTTR and fewer reassignments. Senior people stop being used as expensive routers.

---

### 3. Don't reinvent the fix

**Scenario:** The analytics export is corrupting data. Someone has solved this before.

**What CaseIQ does:** Pulls similar resolved cases (same product, ordered by resolution time) and only KB articles with a **resolution rate above 70%**, ranked by effectiveness. Articles that technically exist but never work do not get recommended.

**ROI lever:** KB deflection, faster first response, and institutional memory that survives people quitting.

---

### 4. "Show your work" AI: graph vs. no-graph, side by side

**Scenario:** Your skeptical director asks, *"Why not just ask the LLM?"*

**What CaseIQ does:** Every answer is shown three ways, to the same ticket:

| Column | What it is |
|---|---|
| **Without Graph** | A general-knowledge LLM answer (the control group) |
| **With Graph** | The same model, grounded in retrieved graph data |
| **With Graph + Jev** | The grounded answer, audited against the data it was written from |

**ROI lever:** The graph lift is visible instead of asserted. This is the demo that answers the budget question in the room.

---

### 5. An AI answer that is allowed to say "a human should look at this"

**Scenario:** The model recommends an agent, quotes a resolution time, and gets one number wrong.

**What CaseIQ does:** Four deterministic grounding checks (are named agents and articles real, do quoted numbers match, was the evidence used, was enough retrieved) plus Jev's typed signals (unsupported claims, missed evidence, anchoring). Then plain code, not a model, decides: **accept, revise once, or send to human review.** If Jev is unreachable, the answer is **never** auto-accepted.

**ROI lever:** Cheap insurance against the expensive failure. One hallucinated "fix" on a Gold customer costs more than a year of verifier calls.

---

### 6. Automated QA on AI investigations (the unglamorous money-saver)

**Scenario:** You want to audit thousands of agent investigations. Reviewing each with a frontier LLM judge adds up fast.

**What CaseIQ measured (Phase 8, 150 dev traces):**

| Judge | Cost per 1,000 judgments |
|---|---|
| LLM judge | **$3.52** |
| Jev | **$0.18** (about 20x cheaper) |

Jev was a useful supporting signal for **missed evidence (AUC 0.84)** and **distractor anchoring (AUC 0.85)**, plus priority-review triage. Simple deterministic rules matched or beat it on the rest, which we also report, because we like our credibility intact.

**ROI lever:** At 1M judgments, the difference is about **$3,340**. That pays for a lot of coffee.

---

### 7. A KPI dashboard that makes the finance conversation boring (good)

A separate dashboard tracks 7 sections: technical quality (precision, recall, F1), business value (CSAT, FCR, escalation rate), financial impact (cost per resolution, monthly savings), before vs. after, key insights, formula reference, and extraction confidence distribution.

---

## The ROI Model (bring your own numbers)

CaseIQ's measured costs are real. The savings side depends on **your** volumes and wages, so here is the formula instead of a made-up victory lap.

```
Monthly ROI = (cases × minutes_saved_per_case ÷ 60 × loaded_hourly_cost)
              − (cases × cost_per_case_of_CaseIQ)
```

**Worked example. Every input below is an assumption, not a measurement:**

| Input | Assumed value |
|---|---|
| Cases per month | 10,000 *(same size as the demo dataset)* |
| Triage minutes saved per case | 2 |
| Loaded agent cost | $60/hour ($1/minute) |
| CaseIQ cost per case (upper end, full Jev pipeline) | $0.03 *(measured)* |

- Value: 10,000 × 2 min = 20,000 min ≈ 333 hours ≈ **$20,000/month**
- Cost: 10,000 × $0.03 = **$300/month**
- Net: **about $19,700/month** (roughly 66x, on assumptions you should challenge)

**The number to remember is break-even:** at $0.03 per case and $1 per agent-minute, CaseIQ pays for itself if it saves **1.8 seconds per case.** If you can't beat 1.8 seconds, we have a different conversation.

*(Not counted: LLM and graph hosting, engineering time, and the human-review queue. A real business case should include all three.)*

---

## The Honest Scoreboard

We would rather lose a hype contest than a trust contest. Everything below is measured on **synthetic data, dev cases only.**

### Wins

| Metric | Result |
|---|---|
| Phantom tools / invented IDs after contract hardening (Phase 9A) | **0** (baseline: 244 of 300 traces called a tool that doesn't exist) |
| First-pass valid final answers, 72 verification cases | **95.8%** |
| Early triage: Jev's ticket-only category guess | **77% correct (27 of 35)** |
| Agent's first-answer category, with vs. without early triage | **21 of 35 vs. 14 of 35** (not statistically significant, p = 0.12) |
| Critical-evidence recall, same number of tool calls | **81% vs. 59%** |
| Verifier safety behavior | Never auto-accepts when Jev is unreachable. Never ships a worse revision over a grounded answer. |

### Things we are not going to hide

| Finding | Reality |
|---|---|
| Root-cause accuracy, 3 architectures, 17 cases | **6% (1 of 17), all three.** The agent is weak at root cause. Improving it is the named next step. |
| Issue-category accuracy, same 17 cases | LLM Only **71%**, LLM + Graph 41%, LLM + Graph + Jev 35%. Yes, the cheap one won. The set deliberately includes cases where the graph agent's stored run was wrong, so this is not a verdict on graphs. |
| Human review rate | The verifier sent **88%** of cases to review (33 of 35 in the early-triage run). It is cautious, not clairvoyant. |
| Early triage failure mode | The agent kept the hinted category **in all 8 wrong cases**. The gain comes from Jev's ticket-only accuracy, not from the agent correcting itself. Pure anchoring, so far. |
| The extra investigation round | Rescued 0 smoke-test cases and roughly doubled the cost. |
| The main page's "quality score" | Original demo heuristics, not measurements. Treat as scenery. |

**PM translation:** the *plumbing* (grounding, validation, safe failure, cheap auditing) is solid. The *brain* needs another iteration. Anyone selling you a 90% root-cause accuracy from this repo is selling you something.

---

## How It Works

### Live demo app (`app.py`, Phase 0)

```
Ticket text
   │
   ▼
Dual-confidence extraction ──► product (🟢 auto / 🟡 confirm / 🔴 manual)
   │
   ▼
Neo4j 4-hop traversal
   ├─ Customer profile (tier, history, prior cases)
   ├─ Similar resolved cases (by product, fastest first)
   ├─ Best-match agents (skill × 3 + resolved + KB × 0.5)
   └─ KB articles (>70% resolution rate)
   │
   ▼
Three answers: Without Graph │ With Graph │ With Graph + Jev
```

**Try it without typing:** three one-click scenarios (Payment Gateway refund failure, SSO onboarding blocked, Analytics export corruption), all Gold tier.

### Diagnostic Agent page (Phases 9A and 9)

Pick a stored dev case and compare:

| Mode | Graph | Jev | Approx. cost per case |
|---|:-:|:-:|---|
| LLM Only | no | no | ~$0.001 |
| LLM + Graph | yes | no | ~$0.02 |
| LLM + Graph + Jev (default) | yes | yes | ~$0.03 |
| Compare All | all three side by side | | ~$0.05 |

Jev plays two roles. **Early:** reads the ticket and suggests a provisional issue category before any graph tool runs (guidance only, never evidence). **Late:** verifies the final answer. Plain code (`policy.py`) makes every decision. Jev is a signal, never a judge.

Outcomes: `ACCEPT`, `CONTINUE_INVESTIGATION` (once), `HUMAN_REVIEW`, `PRIORITY_REVIEW`.

---

## The Research Program (Phases 1 to 9+)

| Phase | What shipped | Status |
|---|---|---|
| 0 | Live demo app (Groq, 12,741-node demo graph) | Working |
| 1-3 | Synthetic support data with hidden ground truth (25,000 cases, ~2M rows) | Frozen |
| 4 | Neo4j runtime graph, 116,868 nodes / 325,539 relationships | Frozen |
| 5 | Baseline diagnostic agent, 14 read-only time-gated tools | Frozen (historical baseline) |
| 6 | Deterministic evaluator, locked dev / validation / test splits | Frozen |
| 7 | Jev primitive evaluation (six single decisions) | Closed (locked benchmark never run) |
| 8 | Jev as agent-trace evaluator (six typed judgments) | Closed |
| 9A | Contract-hardened agent (same model) | Working; 100-case verification stopped at 72 |
| 9 | Runtime verifier, one retry round, three-way comparison page | MVP; 16-case smoke test |
| 9+ | Jev early triage | Working; 35-case dev comparison, descriptive only |

Full detail for every phase lives in [`docs/`](docs/) and [`data/README.md`](data/README.md).

---

## Stack

| Layer | Technology |
|---|---|
| Graph database | Neo4j AuraDB Free (two instances: demo graph + research graph) |
| Live-app LLM | `openai/gpt-oss-120b` via Groq |
| Diagnostic agent LLM | `meta-llama/Llama-3.3-70B-Instruct-Turbo` via Together AI |
| Verifier / early triage | Jev (`jev-1.13.0`, direct HTTP) |
| Semantic search | `sentence-transformers` all-MiniLM-L6-v2, cosine similarity |
| Orchestration | LangChain 0.2.16 (LCEL) |
| Observability | LangSmith |
| UI | Streamlit 1.35 |
| Language | Python 3.11+ (tested on 3.13) |

---

## Quick Start

```bash
# 1. Install (first run pulls PyTorch, ~2 min: go refill the coffee)
pip install -r requirements.txt

# 2. Configure
cp .env.example .env     # then fill in your keys

# 3. Generate synthetic data (one-time)
python3 data/generate_data.py          # 2,000 customers, 10,000 cases, 501 KB articles, 150 agents

# 4. Load the demo graph (one-time, idempotent, ~14s)
python3 agent/neo4j_loader.py

# 5. Run
./start.sh                             # checks both databases, then starts the app
./start.sh --dashboard                 # also starts the KPI dashboard on :8502
```

**Required `.env` keys (live app):** `GROQ_API_KEY`, `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`.
**Research phases add:** `NEO4J_V2_*`, `TOGETHER_API_KEY`, `TYPESAFE_API_KEY`. All are listed in `.env.example`.

> **Aura Free naps.** An instance pauses after about 3 days of silence and is deleted after about 30 paused days. Using the app counts as activity. `python3 -m agent.neo4j_health` tells you who is asleep.

> **Dependency pins: do not touch.** `langchain==0.2.16`, `langchain-core==0.2.43`, `langchain-community==0.2.16`, `streamlit==1.35.0`, `tenacity==8.5.0`. Never `pip install typesafe-sdk` or `langchain-openai`: both break the stack. Jev is reached through a small direct-HTTP client on purpose. Run `pip check` after any install.

### Useful commands

```bash
# One dev case through agent → verifier → policy (~$0.03)
python3 -m agent.runtime_verifier.run CS00729

# Compare all three architectures on one case (~$0.05)
python3 -m agent.compare.cli CS00019 --modes llm_only llm_graph llm_graph_jev

# Jev early triage on one case
python3 -m agent.runtime_verifier.run --early-triage CS00014

# CLI demo of the original app
python3 agent/main.py --scenario A     # A = Payment, B = SSO, C = Analytics, --all = all three
```

---

## Quality Gates

**Live-app eval suite:** 20 test cases across 6 categories, logged to LangSmith.

```bash
python3 run_evals.py             # live: Neo4j + Groq + LangSmith
python3 run_evals.py --dry-run   # stubbed results, still logs
```

| Category | What it protects |
|---|---|
| Skill match | Recommended agents actually cover the required skills |
| Confidence calibration | High-confidence extractions map to the right product |
| Semantic search | Product-adjacent descriptions route correctly |
| Graceful degradation | Nonsense input reaches the manual picker, not a confident guess |
| Latency | Graph recommendation in under 10 s |
| Resolution time | Top-ranked agents beat random by at least 1 hour |

**Unit tests** (none call a paid API unless noted in the full docs):

```bash
python3 -m unittest agent.agent_v3.test_agent_v3                   # 42 tests
python3 -m unittest agent.runtime_verifier.test_runtime_verifier   # 19 tests
python3 -m unittest agent.early_triage.test_early_triage           # 36 tests
python3 -m unittest agent.compare.test_compare                     # 19 tests
python3 -m unittest agent.test_triage_verifier                     # 25 tests
python3 -m agent.agent_v3.validate_boundaries                      # 11/11 boundary checks
pip check
```

---

## Guardrails (the boring part that keeps you out of an incident review)

- **Hidden truth stays hidden.** Ground truth is read only by evaluators, after a run exists. Enforced by import-closure checks, tripwire tests, and a leakage guard on every Jev request.
- **Read-only graph.** The agent's Cypher is `MATCH`/`RETURN` only, time-gated by a harness-owned clock.
- **Opaque IDs.** The model sees aliases, not real identifiers, because Phase 7 found that ID structure can sway a model.
- **Plain code decides.** Jev advises. `policy.py` rules.
- **Dev split only.** The locked test split has never been opened.
- **Frozen means frozen.** Phase 1 to 8 files are pinned by SHA-256 hashes.

---

## Known Limitations (the "no surprises" section)

1. **The agent is weak at root cause** (see the scoreboard). Diagnostic quality was deliberately not optimized in Phase 9A.
2. **The verifier is an MVP.** Thresholds are hand-set. Jev's NORMAL probability never exceeded 0.01 in smoke tests, so it cannot by itself justify an ACCEPT.
3. **Free-text tickets only work on the main page.** The Diagnostic Agent page works on cases already in its graph.
4. **Everything is synthetic.** Real tickets are messier, funnier, and more misspelled.
5. **Early triage is anchoring today.** The agent adopted every wrong hint. Hint wording and thresholds are unvalidated.
6. **The Jev column on the main page is a demonstration.** On the one real ticket tried end to end, every grounding check passed while Jev flagged unsupported claims at 0.85.
7. **Provider hiccups are real.** Together returned HTTP 402s when credits ran low, and a sleeping laptop hung a batch (use `caffeinate -i`; batches resume by tag).

---

## Roadmap

1. **Improve the agent or model.** The named next step, and the one that moves the 6%.
2. **Fix the anchoring.** Make the agent challenge an early hint instead of adopting it.
3. **Calibrate the verifier** on more than 16 cases, then re-tune thresholds.
4. **Integrated CaseIQ comparison** once the agent earns it.
5. **Pilot on real, de-identified tickets** and replace the illustrative ROI inputs with measured ones.

---

## Project Layout

```
├── app.py                         # Main Streamlit app (live demo)
├── pages/1_Diagnostic_Agent.py    # LLM Only / LLM + Graph / LLM + Graph + Jev / Compare All
├── measurement_dashboard.py       # 7-section KPI dashboard
├── run_evals.py                   # Live-app eval suite (LangSmith)
├── start.sh                       # Database health check + launcher
├── agent/
│   ├── graph_client.py · llm_client.py · semantic_search.py   # Live app core
│   ├── triage_verifier.py         # Main page's third column
│   ├── graph_v2/ agent_v2/ eval_v2/ jev_v2/ trace_eval_v2/    # Phases 4 to 8
│   ├── agent_v3/                  # Phase 9A: contract-hardened agent
│   ├── early_triage/              # Jev early triage
│   ├── runtime_verifier/          # Phase 9: checks + policy + retry
│   └── compare/                   # Three-architecture comparison layer
├── config/settings.py             # Env vars and confidence thresholds
├── docs/                          # Reference docs, one family per phase
└── data/                          # Synthetic datasets, ground truth, run records
```

---

*CaseIQ is a demo and research code base. The ROI model is a template, not a promise. If someone quotes it to you as a guarantee, please send them this README, preferably the Honest Scoreboard.*
