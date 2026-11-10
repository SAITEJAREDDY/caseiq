"""Chat client for the Phase 9A agent: the same Together model as Phase 5, called with a JSON-schema `response_format` so the provider
enforces the action/final schema at decode time (probed: an out-of-enum tool name or alias demanded in the prompt still comes back inside the enum).

Infrastructure faults are kept apart from contract results: a 402 (credits exhausted) or a persistent network failure raises and stops the
batch; it is never recorded as the agent violating its contract.
"""
import re
import time
from dataclasses import dataclass

import requests

from agent.agent_v3.config import MODEL_NAME, MODEL_PROVIDER, TEMPERATURE

TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"


class ProviderCreditError(RuntimeError):
    """HTTP 402 persisting through the bounded retry window: the account is out of credit. No run can proceed; not a contract failure."""


class ProviderUnavailable(RuntimeError):
    """Retries exhausted on a 5xx, timeout or connection error. The case is retried later; it is not a contract failure."""


class ProviderSchemaError(RuntimeError):
    """HTTP 400/422: the provider rejected our request or schema. A harness bug, never charged to the model."""


@dataclass
class LLMResult:
    content: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    http_retries: int = 0


def _retry_after(resp, default: float) -> float:
    h = resp.headers.get("retry-after")
    if h:
        try:
            return float(h)
        except ValueError:
            pass
    m = re.search(r"try again in ([\d.]+)(ms|s)", resp.text or "")
    if m:
        return float(m.group(1)) / (1000 if m.group(2) == "ms" else 1)
    return default


class TogetherJSONClient:
    def __init__(self, api_key: str, model: str = MODEL_NAME, temperature: float = TEMPERATURE):
        if MODEL_PROVIDER != "together":
            raise RuntimeError(f"agent_v3 is defined for the Together-hosted baseline model; provider is {MODEL_PROVIDER!r}")
        self.api_key, self.model, self.temperature = api_key, model, temperature

    CREDIT_RETRIES = 8          # a 402 is never billed and the provider says balances take up to 5 minutes to update, and it was observed to flap
    CREDIT_BACKOFF = (5, 10, 20, 30, 30, 30, 30, 30)  # seconds; ~3 minutes in total before the batch is stopped

    def complete(self, messages: list, schema: dict, name: str, max_tokens: int, max_retries: int = 6) -> LLMResult:
        payload = {"model": self.model, "temperature": self.temperature, "max_tokens": max_tokens, "messages": messages,
                   "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        t0, retries, last, credit_waits = time.time(), 0, "", 0
        attempt = -1
        while attempt + 1 < max_retries:
            attempt += 1
            try:
                resp = requests.post(TOGETHER_URL, headers=headers, json=payload, timeout=120)
            except (requests.Timeout, requests.ConnectionError) as e:
                last = f"{type(e).__name__}: {e}"
                retries += 1
                time.sleep(min(2 ** attempt, 20))
                continue
            if resp.status_code == 200:
                data = resp.json()
                ch = data["choices"][0]
                u = data.get("usage") or {}
                return LLMResult((ch.get("message") or {}).get("content") or "", ch.get("finish_reason") or "",
                                 u.get("prompt_tokens", 0), u.get("completion_tokens", 0), (time.time() - t0) * 1000, retries)
            if resp.status_code == 402:
                if credit_waits >= self.CREDIT_RETRIES:
                    raise ProviderCreditError(resp.text[:300])
                time.sleep(self.CREDIT_BACKOFF[credit_waits])
                credit_waits += 1
                retries += 1
                attempt -= 1  # a 402 does not consume the ordinary retry budget
                last = "402"
                continue
            if resp.status_code == 429:
                retries += 1
                time.sleep(_retry_after(resp, min(2 ** attempt * 2, 40)) + 0.1)
                last = "429"
                continue
            if resp.status_code >= 500:
                retries += 1
                last = f"{resp.status_code} {resp.text[:120]}"
                time.sleep(min(2 ** attempt, 20))
                continue
            raise ProviderSchemaError(f"{resp.status_code}: {resp.text[:400]}")
        raise ProviderUnavailable(f"gave up after {max_retries} attempts: {last}")
