# CaseIQ

### The story of one support ticket, and what happens when your support team finally gets a memory.

*Microsoft AI Graphs TPM Demo · June 2026*

*(Characters are fictional. Every number labeled "measured" comes from this repo's own runs. Every number labeled "pretend" is a pretend, and we will tell you which is which.)*

---

## Chapter 1: Monday, 9:02 a.m.

Priya is a support engineer. She has not finished her coffee.

A ticket lands from a Gold-tier customer: *"Refunds are failing at checkout and finance is panicking."*

Here is what happens next in most support teams, and possibly in yours:

Priya opens four tabs. She asks in Slack, "Anyone seen this before?" Someone says "I think Marcus fixed something like this?" Marcus is on vacation. She searches the knowledge base and finds three articles, one of which has been wrong since 2022. Eventually she finds a similar case, reads it, realizes it was a different product, and starts over.

Nobody did anything *wrong*. The knowledge exists. It is just scattered across people, tickets, and articles, and every new case starts with an archaeology dig.

That dig is the leak. It is the part of the job that is not support. It is support *logistics*, and it happens ten thousand times a month.

CaseIQ is what happens when you give that logistics problem a memory.

---

## Chapter 2: The same ticket, but with a graph

Same Monday. Same coffee. Same ticket. This time the ticket goes into CaseIQ.

**First, it works out what the ticket is about.** Not with a dropdown, with plain English. A dual-confidence extractor reads the text and decides how sure it is:

- If it is **80% sure or better**, it assigns the product on its own and gets out of the way (🟢).
- If it is **60 to 79% sure**, it asks Priya to confirm with a single click (🟡).
- If it is less sure than that, it tries a semantic search against product descriptions. If *that* fails, it hands Priya a manual picker (🔴) instead of pretending to know.

That last part is a feature. The most dangerous thing a triage tool can do is be confidently wrong. CaseIQ is built to say "I don't know, you pick" before it says something wrong with a straight face.

**Then it walks the graph.** Neo4j holds the relationships a spreadsheet cannot: who raised what, about which product, who resolved it, which skills they used, which articles helped. In one four-hop traversal, CaseIQ pulls:

1. **The customer's story.** Tier, history, prior cases on this product. (Gold. Third refund issue this year. Handle with care.)
2. **Similar resolved cases**, same product, fastest fixes first.
3. **The best human for the job**, ranked by `skill match × 3 + cases resolved + KB articles used × 0.5`. Not "whoever is next in the queue." Whoever has actually fixed this.
4. **Knowledge articles that actually work.** Only ones with a resolution rate above 70%. The 2022 article that has never helped anyone is not invited.

Priya gets a recommendation in seconds, grounded in her own team's history.

**And right next to it, the control group.** Every answer is shown beside a "Without Graph" answer from the same model, with no access to the team's data. That answer sounds perfectly reasonable and says things like "check your payment gateway configuration." You know, advice. It is the difference between a colleague who has read your tickets and a colleague who has read the internet.

You can try this without typing a word. The app ships with three one-click scenarios: a payment gateway refund failure, an SSO onboarding blocker, and analytics export corruption.

---

## Chapter 3: The skeptic in the back row

Every story needs a skeptic. Ours is Dana, a director, who has seen many AI demos and one very bad AI incident.

Dana asks the only question that matters: **"What happens when it's wrong?"**

Good question. Language models are wonderful and also, occasionally, make up an agent who does not exist and quote that agent's imaginary resolution time to three decimal places. So CaseIQ does not trust itself. It has a third column.

**Meet Jev**, a typed, probabilistic decision model that acts as a second opinion. Before anyone trusts a recommendation, it is checked against the very data it was written from:

- Four plain, deterministic checks. Are the named agents and articles real? Do the quoted resolution times and rates match the graph? Was the evidence actually used? Was enough retrieved?
- Jev's own signals: unsupported claims, missed evidence, anchoring on weak options, and whether a human should look.

Then comes the part Dana likes: **plain code, not a model, makes the call.** Accept it. Ask the model to revise once, with the verifier's complaint in hand. Or send it to a human. And if Jev can't be reached, the answer is **never** auto-accepted. The safety net does not quietly turn itself off.

There is also a rule that a revision can never replace a grounded answer with an ungrounded one. The system is allowed to try harder. It is not allowed to get worse and call it progress.

Dana nods slowly. That is the highest praise Dana gives.

---

## Chapter 4: The math, told straight

Then Dana asks the second question: **"What does it cost, and what do I get?"**

Here is what we *measured*: running the full diagnostic pipeline costs about **$0.03 per case**. A cheaper LLM-only pass is about $0.001, and the graph agent without verification is about $0.02.

Here is what we are *pretending*, so you can plug in your own numbers. Suppose a team handles **10,000 cases a month**, CaseIQ saves **2 minutes of triage per case**, and an agent's time costs **$60 an hour**.

That is 20,000 minutes, or about 333 hours, or roughly **$20,000 a month** of reclaimed time, against about **$300** of model costs. Call it a 66x return on assumptions you are welcome to attack.

But the number to remember is not the 66. It is the **break-even: 1.8 seconds.** At three cents a case and a dollar an agent-minute, CaseIQ pays for itself if it saves Priya less time than it takes to sneeze. If it cannot do that, we should talk about something else.

(What this does not count: hosting, engineering time, and the human-review queue. Put those in your own business case. Dana will.)

There is a second, quieter saving. Auditing AI investigations at scale is expensive if a frontier LLM does the judging. In our Phase 8 runs, Jev judged for about **$0.18 per 1,000 judgments, against $3.52 for the LLM judge.** About twenty times cheaper. At a million judgments, that is roughly $3,340 you did not spend. And it was genuinely useful where it counted: it flagged **missed evidence (AUC 0.84)** and **anchoring on distractors (AUC 0.85)**.

---

## Chapter 5: The plot twist (where we admit things)

A story with no setbacks is a brochure. Here is the part where the hero trips.

**The agent we first built was, to put it kindly, creative.** In 300 baseline investigations, **every single one** called at least one tool that does not exist. 244 of them tried to read something called `get_system_logs`, a tool we never built and that the model was simply certain should be there. Every final answer needed a silent repair just to be valid. The agent never once filled in an ID field correctly.

So we hardened it: schema-constrained decoding, an alias registry so the model never sees raw IDs, and deterministic validators that reject nonsense before it runs. Same model, tighter leash. Result: **every tool name valid, zero invented IDs, 95.8% valid final answers on the first try.**

That was the happy ending of the chapter. Here is the unhappy one:

- **Plumbing is good. The brain is not yet.** Root-cause accuracy was **6% (1 of 17 cases)** across all three architectures. The agent abstains a lot, which is better than guessing, but it is not a finished detective.
- **The cheap option won something.** On issue-category accuracy, plain LLM-only scored **71%**, against 41% for LLM + Graph and 35% with Jev. (The 17 cases were chosen for coverage and deliberately include ones where the graph agent had failed, so this is not a verdict on graphs. It is still humbling.)
- **The verifier is a nervous hall monitor.** It sent **88%** of cases to human review. It is careful, not clairvoyant.
- **Early triage is a good idea with a flaw.** Jev can read just the ticket and guess the issue category correctly **77% of the time (27 of 35)**. Handing that hint to the agent lifted its first-answer category from **14 of 35 to 21 of 35** and critical-evidence recall from **59% to 81%**, at the same number of tool calls. But the improvement was not statistically significant (p = 0.12), and the agent **adopted all 8 of the wrong hints without a fight.** It is not reasoning past the hint. It is anchoring on it. Fixing that is on the list.
- **Everything here is synthetic data, dev cases only.** Real tickets will be messier, angrier, and more misspelled.

We wrote this chapter ourselves on purpose. If you are going to put a system between a customer and an answer, you deserve to know where it is weak before it tells you.

---

## Chapter 6: How the sausage got made

The demo you click on is only half the repo. The other half is a long research road, and it is worth knowing about because it is why the numbers above can be trusted.

**Phase 0** is the live app: Streamlit, a 12,741-node demo graph, Groq for the model.

**Phases 1 to 3** built a synthetic support universe: 25,000 cases and about two million rows, with **hidden ground truth** so we could grade the agent honestly.

**Phase 4** loaded it into a second Neo4j graph: **116,868 nodes and 325,539 relationships**, read-only for the agent.

**Phase 5** built the first diagnostic agent with 14 read-only, time-gated tools. This is the one that invented `get_system_logs`. **Phase 6** built the grader: a deterministic evaluator with locked dev, validation, and test splits. The test split has never been opened.

**Phase 7** tested Jev on six single decisions, and found along the way that its answers can depend on how the option keys are *named*, so we scrapped the locked benchmark before ever running it. **Phase 8** used Jev to judge agent traces (that is where the $0.18 vs. $3.52 comes from).

**Phase 9A** hardened the agent. **Phase 9** added the runtime verifier with its one retry round, plus a Diagnostic Agent page that runs LLM Only, LLM + Graph, and LLM + Graph + Jev side by side on the same case. **Phase 9+** added the early-triage hint from Chapter 5.

The rules we held ourselves to:

- Hidden ground truth is read only by evaluators, after a run exists. Import-closure checks and tripwire tests enforce it.
- The agent's graph access is `MATCH` and `RETURN` only, time-gated by a harness-owned clock.
- The model sees aliases, never real IDs, because ID structure turned out to sway it.
- Jev advises. `policy.py` decides.
- Frozen phases stay frozen, pinned by SHA-256 hashes.

Every phase has its own write-up in [`docs/`](docs/) and the data layers are explained in [`data/README.md`](data/README.md).

---

## Epilogue: what happens next

Priya does not get replaced. Priya gets her mornings back, and the interesting tickets, and a team memory that does not go on vacation.

For the project itself, the road ahead is short and clear:

1. **Make the agent a better detective.** This is the one that moves the 6%.
2. **Teach it to argue with a hint** instead of adopting it.
3. **Calibrate the verifier** on more than 16 smoke-test cases and retune its hand-set thresholds.
4. **Run an integrated CaseIQ comparison** once the agent has earned one.
5. **Pilot it on real, de-identified tickets**, and replace our pretend numbers with yours.

---

## Try it yourself

The whole thing runs on a laptop with a few free-tier accounts.

```bash
# Install (first run pulls PyTorch, about 2 minutes: go refill the coffee)
pip install -r requirements.txt

# Add your keys
cp .env.example .env

# Generate the synthetic data, then load the demo graph (both one-time)
python3 data/generate_data.py
python3 agent/neo4j_loader.py

# Start everything (add --dashboard for the KPI dashboard on port 8502)
./start.sh
```

The live app needs `GROQ_API_KEY`, `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT`, and the three `NEO4J_*` variables. The research half adds `NEO4J_V2_*`, `TOGETHER_API_KEY`, and `TYPESAFE_API_KEY`. Everything is listed in `.env.example`.

Open **Diagnostic Agent** in the sidebar to compare the three architectures on a stored case. Stored results open instantly for free. A live run costs about $0.001 (LLM Only), $0.02 (LLM + Graph), or $0.03 (LLM + Graph + Jev) per case.

A few things worth knowing before you start:

- **Aura Free naps.** Neo4j's free instances pause after about 3 days of silence and are deleted after about 30 paused days. Using the app counts as activity, and `python3 -m agent.neo4j_health` tells you which one is asleep.
- **Do not touch the dependency pins.** `langchain==0.2.16`, `langchain-core==0.2.43`, `langchain-community==0.2.16`, `streamlit==1.35.0`, and `tenacity==8.5.0` are a working set. Never `pip install typesafe-sdk` or `langchain-openai`. They quietly break the stack. Jev is reached through a small direct-HTTP client on purpose. Run `pip check` after any install.
- **Free-text tickets only work on the main page.** The Diagnostic Agent page works on cases already in its graph.
- **Free tiers have limits.** Groq's free tier is 8,000 tokens per minute, so the CLI demo waits 62 seconds between scenarios. Together returned HTTP 402s when credits ran low, and a sleeping laptop once hung a batch (use `caffeinate -i`; batches resume by tag).

### Checking its work

The live-app eval suite runs 20 test cases across six categories (skill match, confidence calibration, semantic search, graceful degradation, latency under 10 seconds, and resolution time) and logs them to LangSmith:

```bash
python3 run_evals.py             # live
python3 run_evals.py --dry-run   # stubbed, still logs
```

Unit tests cover the agent, verifier, early triage, comparison layer, and the main page's third column, none of which calls a paid API:

```bash
python3 -m unittest agent.agent_v3.test_agent_v3
python3 -m unittest agent.runtime_verifier.test_runtime_verifier
python3 -m unittest agent.early_triage.test_early_triage
python3 -m unittest agent.compare.test_compare
python3 -m unittest agent.test_triage_verifier
python3 -m agent.agent_v3.validate_boundaries
pip check
```

### Where things live

```
├── app.py                         # The live demo
├── pages/1_Diagnostic_Agent.py    # LLM Only / LLM + Graph / LLM + Graph + Jev / Compare All
├── measurement_dashboard.py       # The 7-section KPI dashboard
├── run_evals.py                   # Live-app eval suite
├── start.sh                       # Checks both databases, then starts the app
├── agent/
│   ├── graph_client.py · llm_client.py · semantic_search.py   # Live app core
│   ├── triage_verifier.py         # The third column
│   ├── graph_v2/ agent_v2/ eval_v2/ jev_v2/ trace_eval_v2/    # Phases 4 to 8
│   ├── agent_v3/                  # Phase 9A: the hardened agent
│   ├── early_triage/              # Early Jev hint
│   ├── runtime_verifier/          # Late Jev: checks, policy, retry
│   └── compare/                   # Three-architecture comparison
├── config/settings.py             # Env vars and confidence thresholds
├── docs/                          # One family of docs per phase
└── data/                          # Synthetic data, ground truth, run records
```

**Built with:** Neo4j AuraDB, Streamlit 1.35, LangChain 0.2.16, LangSmith, `sentence-transformers` (all-MiniLM-L6-v2), `openai/gpt-oss-120b` on Groq for the live app, `meta-llama/Llama-3.3-70B-Instruct-Turbo` on Together AI for the diagnostic agent, and Jev (`jev-1.13.0`) for verification. Python 3.11 or newer, tested on 3.13.

---

*CaseIQ is a demo and a research code base, not a production system. The ROI math is a template, not a promise. If someone quotes it to you as a guarantee, please send them Chapter 5.*
