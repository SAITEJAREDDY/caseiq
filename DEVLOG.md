# Build Log — Customer Support Intelligence Graph POC

**Project:** Microsoft AI Graphs TPM Demo  
**Stack:** Neo4j AuraDB · Groq (Llama 3.3 70B) · LangChain · LangSmith · Python 3.11  
**Date:** May 2026

---

## Build Order & Status

| Step | File | Status |
|------|------|--------|
| 1 | Folder structure | ✅ Done |
| 2 | `data/generate_data.py` | ✅ Done |
| 3 | `config/settings.py`, `.env.example` | ✅ Done |
| 4 | `agent/neo4j_loader.py`, `agent/graph_client.py` | ✅ Done |
| 5 | `agent/prompts.py` | ✅ Done |
| 6 | `agent/memory.py` | ✅ Done |
| 7 | `agent/llm_client.py` | ✅ Done |
| 8 | `agent/main.py` | ✅ Done |
| 9 | `requirements.txt` | ✅ Done (iterated) |
| 10 | `README.md` | ✅ Done |
| 11 | End-to-end test | ✅ Done — all 3 scenarios verified |

---

## Step-by-Step Log

### Step 1 — Folder Structure
Created:
```
/data/raw/
/agent/
/config/
```

---

### Step 2 — Synthetic Data Generator (`data/generate_data.py`)

**First version:** Basic scale per original spec (50 customers, 100 cases, etc.)

**Redesigned to enterprise scale with full business rules:**

| Entity | Count |
|--------|-------|
| Customers | 2,000 |
| Cases | 10,000 |
| Products | 50 |
| KB Articles | 501 |
| Agents | 150 |
| Skills | 40 |
| Total edges | 47,435 |

**Business rules implemented:**
- Products follow 80/20 rule: Payment Gateway v2 (25%), SSO Integration Module (20%), Analytics Dashboard (15%), remaining 47 products share 40%
- Priority distribution: High 15% · Medium 55% · Low 30%
- Status distribution: Resolved 65% · Open 25% · Escalated 10%
- Resolution time by priority: High 2–8h · Medium 8–48h · Low 24–120h
- Customer tier weighting: Gold 10% · Silver 30% · Bronze 60% — Gold customers assigned cases 12× more often than Bronze
- Gold tier: 40% faster resolution · Silver: 15% faster · Bronze: baseline
- Agent seniority: Senior 20% · Mid 50% · Junior 30% — High-priority cases only assigned to Senior/Mid
- Agent workload power law: top 20% of agents resolve 50% of cases (weight 6×) · bottom 30% resolve 10% (weight 0.5×)
- KB articles: top 10 articles → weight 10× · next 40 → 2.5× · rest → 0.5×
- Article resolution rate by age: <30 days → 0.30–0.60 · >180 days with high views → 0.75–0.95
- 12 realistic case description templates with product name and error code injection
- Similar cases clustered by product (same product = higher similarity score)

**All 14 CSVs verified and written to `/data/raw/`.**

---

### Step 3 — Config & Environment

**`config/settings.py`:** Central config loaded via `python-dotenv`. Exports typed constants for Groq, LangSmith, Neo4j, memory window size, and the 3 hardcoded demo scenarios.

**`.env.example`:** Template with comments pointing to exact credential sources.

**Recurring bug discovered (3 times):** `os.environ["actual_key_value"]` — the API key value was being used as the dictionary lookup key instead of the variable name. This silently fails at runtime because no env var named `gsk_...` exists.

**Rule:** `os.environ["GROQ_API_KEY"]` takes the **variable name** as a string. The actual secret value belongs in `.env`, never in source code.

---

### Step 4 — Graph Layer

#### Architecture Change: Fabric Graph → Neo4j AuraDB

**Original spec:** Microsoft Fabric Graph with GQL queries via REST API.  
**Changed to:** Neo4j AuraDB Free with Cypher queries via the official `neo4j` Python driver.

**Reason:** Fabric Graph requires manual browser-based setup (no programmatic provisioning), whereas Neo4j AuraDB is instantly available, free, and has a mature Python driver — better for a timed demo build.

**`agent/neo4j_loader.py`:**
- Connects to AuraDB using `neo4j+s://` URI
- Creates uniqueness constraints for all 6 node types before loading
- Uses `MERGE` (not `CREATE`) throughout — safe to re-run without duplicates
- Batched writes of 500 rows per transaction to avoid memory pressure on 10k+ rows
- Uses `UNWIND $rows` pattern for efficient bulk operations
- Loads all 6 node types then all 8 relationship types in dependency order
- Prints node + relationship counts on completion

**`agent/graph_client.py`:**
- 4 Cypher query functions matching the original GQL spec signatures
- `find_similar_cases(case_description, product_id)` — top 5 resolved cases ordered by resolution time
- `find_best_agents(product_id, required_skills)` — weighted match score: skill match × 3 + cases resolved × 1 + articles used × 0.5
- `find_kb_articles(product_id)` — articles with resolution_rate > 0.7, ordered by rate then usage count
- `get_full_recommendation(customer_id, product_id)` — true 4-hop traversal across Customer → Case → Product → Articles + Agents
- `USE_MOCK = False` flag at top of file — flip to `True` to bypass Neo4j during development

**Neo4j load confirmed:**
```
Nodes:         12,741
Relationships: 47,435
Load time:     13.8s
```

---

### Step 5 — Prompts (`agent/prompts.py`)

Single `SYSTEM_PROMPT` constant. Key constraints built into the prompt:
- Must reason from graph data provided — no hallucination
- Must cite which graph relationships led to each recommendation
- Must recommend 2 best agents and 3 KB articles with explicit reasoning
- Must estimate resolution time from similar cases
- Must flag escalation risk when applicable
- Tone: executive-readable, concise

---

### Step 6 — Memory (`agent/memory.py`)

**Original approach:** `ConversationBufferWindowMemory` from `langchain.memory`

**Problem:** `ConversationBufferWindowMemory` is tied to `ConversationChain` which was deprecated in LangChain 0.2.7. The modern LCEL pattern uses `RunnableWithMessageHistory` which requires a `BaseChatMessageHistory`-compatible class.

**Solution:** Custom `WindowChatHistory` class extending `BaseChatMessageHistory` + Pydantic v1 `BaseModel`.

**Pydantic v1 issue:** First attempt used `self._max_messages = k * 2` in `__init__`, which fails because LangChain's Pydantic v1 models raise `ValueError` for undeclared fields set via `__setattr__`.

**Fix:** Declare `max_messages: int = 10` as a class-level Pydantic field, not a runtime attribute.

```python
class WindowChatHistory(BaseChatMessageHistory, BaseModel):
    messages: list[BaseMessage] = Field(default_factory=list)
    max_messages: int = 10
```

Window behaviour: stores last `k * 2` messages (k human + k AI). Trims from the front on every `add_messages` call.

---

### Step 8 — main.py — Comparison Mode

**Comparison format:** Each scenario runs twice — once WITHOUT GRAPH (single-shot, no context) and once WITH GRAPH (4-hop graph traversal → LLM reasoning). A programmatically-computed Graph Intelligence Summary is appended showing similar cases, top agent, KB articles, hops traversed, and confidence level.

**Issue — empty WITHOUT GRAPH responses for Scenarios A and B:**
`_raw_llm` (the no-graph baseline chain) used `reasoning_effort="high"` with `max_tokens=3500`. On complex scenarios (payment gateway, SSO), the reasoning model exhausted its 3500-token budget on internal thinking, leaving 0 tokens for visible output. Scenario C (data export) happened to use fewer reasoning tokens and produced output normally.

**Fix:** Set `reasoning_effort="low"` for `_raw_llm`. The baseline chain is intentionally a simple advisor response — it doesn't benefit from extended reasoning. This also naturally reduces TPM usage, leaving more budget for the WITH GRAPH call which needs `reasoning_effort="high"` for deep multi-hop reasoning.

**Issue — TPM rate limit when running `--all`:**
Running 3 scenarios back-to-back with two LLM calls each (~7,000 tokens/scenario) exceeds the Groq free-tier 8,000 TPM cap immediately after the first scenario completes.

**Fix:** Added a 62-second cooldown between scenarios in `--all` mode. The TPM window is a rolling 60-second counter; 62s ensures it has fully reset.

**End-to-end test result (all 3 scenarios):**
- Scenario A: no-graph 3316ms | graph traversal 1163ms | graph LLM 5330ms ✅
- Scenario B: no-graph 7453ms | graph traversal 571ms | graph LLM 4021ms ✅
- Scenario C: no-graph 4747ms | graph traversal 682ms | graph LLM 5593ms ✅
- LangSmith traces confirmed visible in `support-intelligence-poc` project

---

### Step 7 — LLM Client (`agent/llm_client.py`)

**Issue 1 — groq proxies error:**
```
pydantic.v1.error_wrappers.ValidationError: Client.__init__() got an unexpected 
keyword argument 'proxies'
```
`groq==0.9.0` passes a deprecated `proxies` argument to `httpx`. Broke when `httpx>=0.28.0` removed support for it.

**Fix:** Upgraded `groq` to `0.37.1` (last version in the 0.x series before the 1.0 rewrite, compatible with `httpx>=0.28` and `langchain-groq==0.1.9`).

**Issue 2 — model decommissioned:**
```
groq.BadRequestError: The model `llama-3.1-70b-versatile` has been decommissioned
```
Groq retired `llama-3.1-70b-versatile` from their API.

**Fix:** Updated model to `llama-3.3-70b-versatile` in `config/settings.py`.

**Issue 3 — ConversationChain deprecated:**
`ConversationChain` was deprecated in LangChain 0.2.7 and will be removed in 1.0.

**Fix:** Replaced with LCEL pattern:
```python
chain = ChatPromptTemplate | ChatGroq
chain_with_history = RunnableWithMessageHistory(chain, get_session_history, ...)
```

**Test result:** Two-turn conversation confirmed working. Turn 2 recalled Turn 1 context correctly, proving memory is live. LangSmith trace visible at `smith.langchain.com → support-intelligence-poc`.

---

## Dependency Issues Summary

| Package | Original Version | Final Version | Reason Changed |
|---------|-----------------|---------------|----------------|
| `langsmith` | `0.1.0` | `0.1.147` | `langchain 0.2.x` requires `>=0.1.17` |
| `langchain-groq` | `0.1.0` | `0.1.9` | `0.1.0` requires `langchain-core<0.2.0`, conflicts with `langchain==0.2.x` |
| `groq` | `0.9.0` | `0.37.1` | `0.9.0` uses deprecated `httpx proxies` arg, broken on `httpx>=0.28` |
| `GROQ_MODEL` | `llama-3.1-70b-versatile` | `openai/gpt-oss-120b` | `llama-3.1` decommissioned; upgraded to `llama-3.3` then switched to `gpt-oss-120b` per demo spec |

---

## Architecture Decisions

### Why Neo4j over Fabric Graph
Fabric Graph requires a live Fabric workspace, manual node/edge schema creation in the browser, and a service-principal OAuth flow for API access — none of which can be scripted in a time-boxed demo build. Neo4j AuraDB Free spins up in 2 minutes, accepts Python driver connections immediately, and the Cypher queries are more expressive for the multi-hop traversal being demonstrated.

### Why LCEL over ConversationChain
`ConversationChain` is on the deprecation path. `RunnableWithMessageHistory` is the LangChain-recommended pattern, integrates cleanly with LangSmith tracing, and is composable — the same `_chain = prompt | llm` base can be reused without the chain wrapper overhead.

### Why custom WindowChatHistory over InMemoryChatMessageHistory
`InMemoryChatMessageHistory` (LangChain's built-in) has no message limit. For a demo agent that will run 3 scenarios with multiple turns, unbounded history would inflate prompt tokens. The custom `WindowChatHistory` keeps exactly the last `k` exchange pairs and drops the oldest on overflow.

---

## Current File Tree

```
/
├── .env                         ← real credentials (gitignored)
├── .env.example                 ← template for onboarding
├── requirements.txt
├── DEVLOG.md                    ← this file
├── config/
│   ├── __init__.py
│   └── settings.py
├── agent/
│   ├── __init__.py
│   ├── prompts.py
│   ├── memory.py
│   ├── llm_client.py
│   ├── graph_client.py
│   └── neo4j_loader.py
└── data/
    ├── generate_data.py
    └── raw/
        ├── customers.csv        ← 2,000 rows
        ├── cases.csv            ← 10,000 rows
        ├── products.csv         ← 50 rows
        ├── knowledge_articles.csv ← 501 rows
        ├── agents.csv           ← 150 rows
        ├── skills.csv           ← 40 rows
        ├── customer_cases.csv   ← 10,000 rows
        ├── case_products.csv    ← 10,000 rows
        ├── case_skills.csv      ← 16,028 rows
        ├── agent_cases.csv      ← 6,532 rows
        ├── agent_skills.csv     ← 676 rows
        ├── agent_articles.csv   ← 1,451 rows
        ├── article_products.csv ← 501 rows
        └── similar_cases.csv    ← 2,247 rows
```

---

## What's Left

- [x] `agent/main.py` — comparison mode, all 3 scenarios
- [x] `README.md` — setup instructions
- [x] End-to-end test — all 3 scenarios verified live against Neo4j AuraDB
- [x] LangSmith traces confirmed in `support-intelligence-poc` project
