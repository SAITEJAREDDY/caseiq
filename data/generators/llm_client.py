"""
Together AI chat-completions wrapper for narrative generation.

Model: Qwen/Qwen3.8-Flash (confirmed live on Together's serverless catalog,
$0.15 / $0.47 per 1M input/output tokens, 1M context, Sept 2026).

Every prompt+response is cached to disk keyed by a hash of the exact request.
This is what makes the narrative stage reproducible and resumable: re-running
the pipeline with the same seed replays cached text instead of re-calling the
API, and an interrupted run picks up where it left off without re-spending
tokens.
"""
import hashlib
import json
import os
import time

import requests
from dotenv import load_dotenv

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY", "")
TOGETHER_MODEL = "Qwen/Qwen3.8-Flash"
TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"
PRICE_PER_1M_INPUT = 0.15
PRICE_PER_1M_OUTPUT = 0.47

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".narrative_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


def estimated_cost_usd():
    cost = (usage_totals["prompt_tokens"] / 1e6 * PRICE_PER_1M_INPUT
            + usage_totals["completion_tokens"] / 1e6 * PRICE_PER_1M_OUTPUT)
    return cost


def print_usage_summary():
    print(f"  Together AI usage this run: {usage_totals['calls']:,} calls, "
          f"{usage_totals['prompt_tokens']:,} input tok, {usage_totals['completion_tokens']:,} output tok "
          f"-> ${estimated_cost_usd():.4f}")


class TogetherAuthError(RuntimeError):
    pass


def _cache_path(key):
    return os.path.join(CACHE_DIR, f"{key}.json")


def _cache_key(model, temperature, messages, seed, reasoning_effort):
    payload = json.dumps({"model": model, "temperature": temperature, "messages": messages,
                           "seed": seed, "reasoning_effort": reasoning_effort}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_get(key):
    path = _cache_path(key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)["response"]
    return None


def cache_put(key, prompt_messages, response_text):
    with open(_cache_path(key), "w", encoding="utf-8") as f:
        json.dump({"prompt": prompt_messages, "response": response_text}, f, ensure_ascii=False)


def chat_completion(messages, temperature=0.9, max_tokens=2500, json_mode=True,
                     seed=None, use_cache=True, max_retries=4, timeout=90, reasoning_effort="low"):
    """Returns the assistant's text content, using the disk cache when possible.
    Raises TogetherAuthError if TOGETHER_API_KEY is missing/rejected."""
    if not TOGETHER_API_KEY:
        raise TogetherAuthError(
            "TOGETHER_API_KEY is not set. Add it to .env before running the narrative stage."
        )

    key = _cache_key(TOGETHER_MODEL, temperature, messages, seed, reasoning_effort)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            return cached

    body = {
        "model": TOGETHER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
        "reasoning_effort": reasoning_effort,
        "stream_options": {"include_usage": True},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if seed is not None:
        body["seed"] = seed

    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}

    delay = 2.0
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(TOGETHER_URL, headers=headers, json=body, timeout=timeout, stream=True)
        except requests.RequestException as e:
            last_error = e
            time.sleep(delay)
            delay *= 2
            continue

        if resp.status_code == 401:
            raise TogetherAuthError(f"Together API rejected the key (401): {resp.text[:300]}")
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            retry_after = float(resp.headers.get("Retry-After", delay))
            resp.close()
            print(f"    [rate-limit/{resp.status_code}] retry {attempt + 1}/{max_retries} "
                  f"in {retry_after:.1f}s", flush=True)
            time.sleep(retry_after)
            delay *= 2
            continue
        if resp.status_code != 200:
            err_text = resp.text[:500]
            resp.close()
            raise RuntimeError(f"Together API error {resp.status_code}: {err_text}")

        try:
            text, usage = _read_sse_stream(resp)
        except Exception as e:
            last_error = e
            time.sleep(delay)
            delay *= 2
            continue

        if usage:
            usage_totals["prompt_tokens"] += usage.get("prompt_tokens", 0)
            usage_totals["completion_tokens"] += usage.get("completion_tokens", 0)
            usage_totals["calls"] += 1

        if use_cache:
            cache_put(key, messages, text)
        return text

    raise RuntimeError(f"Together API call failed after {max_retries} retries: {last_error}")


def _read_sse_stream(resp):
    chunks = []
    usage = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            break
        obj = json.loads(payload)
        if obj.get("usage"):
            usage = obj["usage"]
        choices = obj.get("choices") or []
        if not choices:
            continue
        content = choices[0].get("delta", {}).get("content")
        if content:
            chunks.append(content)
    return "".join(chunks), usage


def parse_json_object(text):
    """Lenient JSON parsing: strips markdown code fences if the model wrapped its output."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    return json.loads(t.strip())
