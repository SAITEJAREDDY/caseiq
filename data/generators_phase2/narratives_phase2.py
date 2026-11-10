"""
Phase 2's only LLM-touching module: fills incidents.summary and
deployments.description via Together AI (Qwen/Qwen3.8-Flash), reusing
data/generators/llm_client.py as-is (same disk cache, same retry/backoff,
same token accounting — llm_client.usage_totals accumulates across both
Phase 1 and Phase 2 runs in the same process if both are called, but each
build script prints its own delta via print_usage_summary() at the point it
calls it).

Per the Phase 2 plan's "Lean" LLM-scope decision, every other Phase 2 text
field (change_events.description, service_health_events.description,
case_signals.message, configuration_snapshots.note) is a deterministic
template — this module intentionally does NOT touch those.
"""
import concurrent.futures as cf
import time

from llm_client import chat_completion, parse_json_object, TogetherAuthError

BATCH_SIZE = 15
MAX_WORKERS = 10

_INCIDENT_SYSTEM_PROMPT = """You are writing brief internal incident summaries for a synthetic \
enterprise-support dataset used to train and evaluate incident-correlation systems. For each \
incident in the input JSON array, write a 1-2 sentence SUMMARY an SRE would post in an incident \
channel: what broke, roughly how, and its user-facing effect. Do not invent additional root causes \
beyond what's implied by the fields given. Vary tone/length across incidents.

Respond with ONLY a JSON object: {"incidents": [{"i": <int>, "summary": "..."}, ...]} covering \
every index in the input, in any order."""

_DEPLOY_SYSTEM_PROMPT = """You are writing brief internal deployment-change descriptions for a \
synthetic enterprise-support dataset used to train and evaluate change-correlation systems. For \
each deployment in the input JSON array, write a 1-2 sentence DESCRIPTION an engineer would log \
in a change ticket: what was deployed and to what, in plain engineering language. Do not invent \
outcomes (success/failure) beyond what's implied by the fields given. Vary tone/length.

Respond with ONLY a JSON object: {"deployments": [{"i": <int>, "description": "..."}, ...]} \
covering every index in the input, in any order."""


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


def template_fallback_incidents(incidents):
    for inc in incidents:
        dur_min = _minutes_between(inc["started_at"], inc["ended_at"])
        inc["summary"] = (f"{inc['severity'].capitalize()} incident affecting component "
                           f"{inc['component_id']} in {inc['region']}, lasting about {dur_min} minutes.")


def template_fallback_deployments(deployments):
    for dep in deployments:
        vf, vt = dep.get("version_from") or "an earlier version", dep.get("version_to") or "a newer version"
        dep["description"] = (f"Deployed {dep['product_id']} {vt} (from {vf}) via a "
                               f"{dep['rollout_strategy']} rollout.")


def _minutes_between(start_str, end_str):
    from datetime import datetime
    fmt = "%Y-%m-%d %H:%M:%S"
    return int((datetime.strptime(end_str, fmt) - datetime.strptime(start_str, fmt)).total_seconds() // 60)


def fill_incident_summaries(incidents, seed=42, component_names=None):
    component_names = component_names or {}

    def payload(idx, inc):
        return {"i": idx, "component": component_names.get(inc["component_id"], inc["component_id"]),
                "region": inc["region"], "severity": inc["severity"],
                "duration_minutes": _minutes_between(inc["started_at"], inc["ended_at"])}

    def worker(batch):
        p = [payload(i, inc) for i, inc in batch]
        messages = [{"role": "system", "content": _INCIDENT_SYSTEM_PROMPT},
                    {"role": "user", "content": str(p)}]
        text = chat_completion(messages, temperature=0.85, max_tokens=1800, seed=seed)
        data = parse_json_object(text)
        by_idx = {r["i"]: r for r in data["incidents"]}
        for idx, inc in batch:
            if idx in by_idx:
                inc["summary"] = by_idx[idx]["summary"]
            else:
                raise ValueError(f"missing index {idx} in response")

    def fallback_single(item):
        idx, inc = item
        messages = [{"role": "system", "content": _INCIDENT_SYSTEM_PROMPT},
                    {"role": "user", "content": str([payload(0, inc)])}]
        text = chat_completion(messages, temperature=0.85, max_tokens=300, seed=seed)
        inc["summary"] = parse_json_object(text)["incidents"][0]["summary"]

    def fallback_template(item):
        _idx, inc = item
        template_fallback_incidents([inc])

    indexed = list(enumerate(incidents))
    batches = [indexed[i:i + BATCH_SIZE] for i in range(0, len(indexed), BATCH_SIZE)]
    _run_batches(batches, worker, fallback_single, fallback_template, "incident summaries")


def fill_deployment_descriptions(deployments, seed=42, product_names=None):
    product_names = product_names or {}

    def payload(idx, dep):
        return {"i": idx, "product": product_names.get(dep["product_id"], dep["product_id"]),
                "version_from": dep["version_from"], "version_to": dep["version_to"],
                "rollout_strategy": dep["rollout_strategy"], "deploy_duration_minutes": dep["deploy_duration_minutes"]}

    def worker(batch):
        p = [payload(i, dep) for i, dep in batch]
        messages = [{"role": "system", "content": _DEPLOY_SYSTEM_PROMPT},
                    {"role": "user", "content": str(p)}]
        text = chat_completion(messages, temperature=0.85, max_tokens=1800, seed=seed)
        data = parse_json_object(text)
        by_idx = {r["i"]: r for r in data["deployments"]}
        for idx, dep in batch:
            if idx in by_idx:
                dep["description"] = by_idx[idx]["description"]
            else:
                raise ValueError(f"missing index {idx} in response")

    def fallback_single(item):
        idx, dep = item
        messages = [{"role": "system", "content": _DEPLOY_SYSTEM_PROMPT},
                    {"role": "user", "content": str([payload(0, dep)])}]
        text = chat_completion(messages, temperature=0.85, max_tokens=300, seed=seed)
        dep["description"] = parse_json_object(text)["deployments"][0]["description"]

    def fallback_template(item):
        _idx, dep = item
        template_fallback_deployments([dep])

    indexed = list(enumerate(deployments))
    batches = [indexed[i:i + BATCH_SIZE] for i in range(0, len(indexed), BATCH_SIZE)]
    _run_batches(batches, worker, fallback_single, fallback_template, "deployment descriptions")
