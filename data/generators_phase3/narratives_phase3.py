"""
Phase 3's only LLM-touching module: fills `escalations.summary` and
`engineering_engagements.finding_summary` via Together AI (Qwen/Qwen3.8-Flash),
reusing data/generators/llm_client.py as-is — same disk cache, same 3-tier
batch -> single -> template fallback pattern as
generators_phase2/narratives_phase2.py.

Per the Phase 3 plan's Lean LLM scope, every other Phase 3 text field is a
deterministic template; only these two rarest, highest-value surfaces get the
LLM. Prompts are built only from fields already established as of that
event's own position in the timeline (escalation_type/trigger_code/severity/
the hypothesis already confirmed by that point) — never from `gt_root_cause_id`
directly bypassing the simulated investigation, so an escalation summary can
never state more than what the timeline had already legitimately discovered.
"""
import concurrent.futures as cf
import time

from llm_client import chat_completion, parse_json_object, TogetherAuthError

BATCH_SIZE = 15
MAX_WORKERS = 10

_ESCALATION_SYSTEM_PROMPT = """You are writing brief internal escalation summaries for a synthetic \
enterprise-support dataset used to train and evaluate support-investigation systems. For each escalation \
in the input JSON array, write a 1-2 sentence SUMMARY an agent would post when escalating: why it's being \
escalated and to whom, based only on the fields given. Do not invent facts beyond what's given. Vary tone/length.

Respond with ONLY a JSON object: {"escalations": [{"i": <int>, "summary": "..."}, ...]} covering every \
index in the input, in any order."""

_ENGINEERING_SYSTEM_PROMPT = """You are writing brief internal engineering-investigation notes for a \
synthetic enterprise-support dataset. For each engagement in the input JSON array, write a 1-2 sentence \
FINDING_SUMMARY an engineer would log for that activity type and suspected root cause, in plain engineering \
language. Do not invent facts beyond what's given. Vary tone/length.

Respond with ONLY a JSON object: {"engagements": [{"i": <int>, "finding_summary": "..."}, ...]} covering \
every index in the input, in any order."""


def _progress_line(label, done, total, start, width=30):
    elapsed = time.time() - start
    rate = done / elapsed if elapsed > 0 else 0
    eta_min = (total - done) / rate / 60 if rate > 0 else 0
    pct = done / total * 100 if total else 100
    filled = int(pct / 100 * width)
    bar = "#" * filled + "-" * (width - filled)
    return (f"  {label}: [{bar}] {pct:5.1f}%  {done:>5}/{total}  "
            f"elapsed {elapsed / 60:5.1f}m  ETA {eta_min:5.1f}m")


def _run_batches(batches, worker_fn, fallback_single_fn, fallback_template_fn, label):
    total = len(batches)
    if total == 0:
        return
    done = 0
    start = time.time()
    step = 20
    print(_progress_line(label, 0, total, start), flush=True)
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(worker_fn, batch): batch for batch in batches}
        for fut in cf.as_completed(futures):
            batch = futures[fut]
            done += 1
            try:
                fut.result()
            except TogetherAuthError:
                raise
            except Exception as e:
                print(f"  {label}: batch failed ({type(e).__name__}: {e}); falling back per-item", flush=True)
                for item in batch:
                    try:
                        fallback_single_fn(item)
                    except Exception as e2:
                        print(f"  {label}: single fallback also failed ({type(e2).__name__}: {e2}); using template",
                              flush=True)
                        fallback_template_fn(item)
            if done % step == 0 or done == total:
                print(_progress_line(label, done, total, start), flush=True)


def template_fallback_escalations(escalations):
    for e in escalations:
        e["summary"] = (f"Escalating as a {e['escalation_type'].replace('_', ' ')} "
                         f"({e['trigger_code'].replace('_', ' ')}) from {e['from_team_id']} to {e['to_team_id']}.")


def template_fallback_engineering(engagements):
    for eng in engagements:
        eng["finding_summary"] = f"Engineering performed {eng['activity_type'].replace('_', ' ')} on this case."


def fill_escalation_summaries(escalations, context_by_id, seed=42):
    """context_by_id: escalation id -> {severity, component, product, suspected_root_cause}."""
    def payload(idx, e):
        ctx = context_by_id.get(e["id"], {})
        return {"i": idx, "escalation_type": e["escalation_type"], "trigger_code": e["trigger_code"],
                "from_team": e["from_team_id"], "to_team": e["to_team_id"],
                "severity": ctx.get("severity", ""), "suspected_root_cause": ctx.get("suspected_root_cause", "")}

    def worker(batch):
        p = [payload(i, e) for i, e in batch]
        messages = [{"role": "system", "content": _ESCALATION_SYSTEM_PROMPT},
                    {"role": "user", "content": str(p)}]
        text = chat_completion(messages, temperature=0.85, max_tokens=1800, seed=seed)
        data = parse_json_object(text)
        by_idx = {r["i"]: r for r in data["escalations"]}
        for idx, e in batch:
            if idx in by_idx:
                e["summary"] = by_idx[idx]["summary"]
            else:
                raise ValueError(f"missing index {idx} in response")

    def fallback_single(item):
        idx, e = item
        messages = [{"role": "system", "content": _ESCALATION_SYSTEM_PROMPT},
                    {"role": "user", "content": str([payload(0, e)])}]
        text = chat_completion(messages, temperature=0.85, max_tokens=300, seed=seed)
        e["summary"] = parse_json_object(text)["escalations"][0]["summary"]

    def fallback_template(item):
        _idx, e = item
        template_fallback_escalations([e])

    indexed = list(enumerate(escalations))
    batches = [indexed[i:i + BATCH_SIZE] for i in range(0, len(indexed), BATCH_SIZE)]
    _run_batches(batches, worker, fallback_single, fallback_template, "escalation summaries")


def fill_engineering_findings(engagements, context_by_id, seed=42):
    """context_by_id: engagement id -> {root_cause, component, product}."""
    def payload(idx, eng):
        ctx = context_by_id.get(eng["id"], {})
        return {"i": idx, "activity_type": eng["activity_type"], "root_cause": ctx.get("root_cause", ""),
                "component": ctx.get("component", ""), "product": ctx.get("product", "")}

    def worker(batch):
        p = [payload(i, eng) for i, eng in batch]
        messages = [{"role": "system", "content": _ENGINEERING_SYSTEM_PROMPT},
                    {"role": "user", "content": str(p)}]
        text = chat_completion(messages, temperature=0.85, max_tokens=1800, seed=seed)
        data = parse_json_object(text)
        by_idx = {r["i"]: r for r in data["engagements"]}
        for idx, eng in batch:
            if idx in by_idx:
                eng["finding_summary"] = by_idx[idx]["finding_summary"]
            else:
                raise ValueError(f"missing index {idx} in response")

    def fallback_single(item):
        idx, eng = item
        messages = [{"role": "system", "content": _ENGINEERING_SYSTEM_PROMPT},
                    {"role": "user", "content": str([payload(0, eng)])}]
        text = chat_completion(messages, temperature=0.85, max_tokens=300, seed=seed)
        eng["finding_summary"] = parse_json_object(text)["engagements"][0]["finding_summary"]

    def fallback_template(item):
        _idx, eng = item
        template_fallback_engineering([eng])

    indexed = list(enumerate(engagements))
    batches = [indexed[i:i + BATCH_SIZE] for i in range(0, len(indexed), BATCH_SIZE)]
    _run_batches(batches, worker, fallback_single, fallback_template, "engineering findings")
