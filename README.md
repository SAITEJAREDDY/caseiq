# CaseIQ

*Graph-powered support intelligence · Microsoft AI Graphs TPM Demo · June 2026*

> **9:02 a.m.** A Gold customer writes: *"Refunds are failing at checkout and finance is panicking."*
>
> The fix already exists. Marcus solved this exact problem in March. But Marcus is on vacation, his ticket is buried under 10,000 others, and the first KB article anyone finds has been wrong since 2022.
>
> **CaseIQ finds Marcus's fix in seconds, then checks its own answer before anyone trusts it.**

---

## What it does

**1. Reads the ticket.** Plain English in, product out. At 80%+ confidence it auto-assigns. At 60 to 79% it asks for one click to confirm. Below that it tries semantic search, and if that fails it hands you a picker. It would rather say "you pick" than be confidently wrong.

**2. Walks the graph.** One four-hop Neo4j traversal pulls the customer's history, similar resolved cases (fastest fixes first), the best agent for the job (`skill match × 3 + cases resolved + KB articles used × 0.5`), and only KB articles with a 70%+ resolution rate.

**3. Shows its work.** Every answer appears three ways, side by side: **Without Graph** (the model guessing from the internet), **With Graph** (grounded in your team's history), and **With Graph + Jev** (grounded *and* audited).

**4. Checks itself.** Four deterministic checks (are the named agents and articles real, do the quoted numbers match, was the evidence used, was enough retrieved) plus Jev's signals for unsupported claims, missed evidence and anchoring. Then plain code, not a model, decides: accept, revise once, or send to a human. If Jev is unreachable, nothing is auto-accepted.

---

## Why it pays

| | Measured cost per case |
|---|---|
| LLM only | ~$0.001 |
| LLM + Graph | ~$0.02 |
| LLM + Graph + Jev | ~$0.03 |

**Break-even is 1.8 seconds.** At $0.03 a case and $60 an hour of agent time, CaseIQ pays for itself if it saves less time than a sneeze. *Pretend* a team runs 10,000 cases a month and saves 2 minutes each: that's about $20,000 of reclaimed time for about $300 of model spend. Swap in your own numbers (and add hosting and review time).

**Auditing gets cheap too.** Judging agent investigations cost **$0.18 per 1,000 with Jev vs. $3.52 with an LLM judge**, about 20x less, and Jev flagged missed evidence (AUC 0.84) and anchoring (AUC 0.85) well.

---

## The honest scoreboard

*Synthetic data, dev cases only.*

**What works**

- **Zero phantom tools.** The first agent called a tool that doesn't exist in all 300 baseline runs (244 times it was an imaginary `get_system_logs`). After contract hardening: every tool valid, zero invented IDs, **95.8%** valid answers on the first try.
- **Early triage helps.** Jev guesses the issue category from the ticket alone **77%** of the time. With that hint, the agent's first answer was right on **21 of 35** cases vs. 14 of 35 without, and evidence recall rose from **59% to 81%** (not yet statistically significant, p = 0.12).

**What doesn't (yet)**

- **Root cause is hard.** **6%** accuracy (1 of 17) across all three architectures. The plumbing is solid; the detective needs work.
- **The cheap model won one round.** LLM-only scored 71% on issue category vs. 41% with the graph, on a 17-case set that deliberately includes the graph agent's failures.
- **The agent anchors.** It adopted all 8 wrong early hints without pushback.
- **The verifier is nervous.** It sends 88% of cases to human review.

**Next:** a better agent, one that argues with hints, a calibrated verifier, then a pilot on real tickets.

---


---

## Under the hood

**Stack:** Neo4j AuraDB · Streamlit · LangChain · LangSmith · `sentence-transformers` · `gpt-oss-120b` on Groq (live app) · Llama 3.3 70B on Together AI (diagnostic agent) · Jev (`jev-1.13.0`) for verification · Python 3.11+.

**The research behind it:** nine phases, from a synthetic support universe (25,000 cases with hidden ground truth) to a 116,868-node graph, a diagnostic agent, a deterministic grader with a never-opened test split, and the runtime verifier. Ground truth is only ever read by evaluators, the agent's graph access is read-only, and frozen phases are pinned by SHA-256 hashes. Full write-ups are in [`docs/`](docs/) and [`data/README.md`](data/README.md).

---

*A demo and research code base, not a production system. The ROI math is a template, not a promise.*
