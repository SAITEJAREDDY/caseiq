"""Minimal, dependency-free Jev/TypeSafe API client. Deliberately does NOT
use the official `typesafe-sdk` package -- its `tenacity>=9.0.0` pin
conflicts with this project's pinned `langchain==0.2.16`/`streamlit==1.35.0`
stack (`tenacity<9`), confirmed by actually installing it and hitting a real
pip conflict, then reverting (see docs/JEV_PRIMITIVE_ARCHITECTURE.md) --
exactly the same class of near-miss Phase 5 hit with `langchain-openai`.
This client is plain `requests` (already a project dependency) against the
REST API directly, verified via docs.typesafe.ai's own HTTP API reference:

    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <TYPESAFE_API_KEY>
    {"state": <str|object|array>, "model": "jev-latest", "questions": {key: Question, ...}}
"""
import re
import time

import requests

from agent.graph_v2.validate_graph import BANNED_SUBSTRINGS
from agent.jev_v2.config import (
    BASE_RETRY_DELAY_SECONDS,
    JEV_MODEL,
    MAX_RETRIES,
    TYPESAFE_API_KEY,
    TYPESAFE_BASE_URL,
    TYPESAFE_SYSTEM_ONE_PATH,
)

_RETRY_AFTER_MS_RE = re.compile(r"(\d+)\s*ms", re.IGNORECASE)


class TypeSafeAPIError(RuntimeError):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"TypeSafe API error {status_code}: {body[:300]}")


class TypeSafeRateLimitError(TypeSafeAPIError):
    def __init__(self, status_code: int, body: str, retry_after_ms=None):
        self.retry_after_ms = retry_after_ms
        super().__init__(status_code, body)


class LeakageGuardError(RuntimeError):
    """Raised when a payload about to be sent to an external API contains a
    banned substring (spec section 65) -- a live guard, not just a static
    source-code scan. Never caught/suppressed; a tripped guard must stop the
    call, not degrade to a warning."""


# Value-scan uses a NARROWER list than the key-scan. Found by hitting a real
# false positive: the causal_change question legitimately asks whether a
# change is "causally related" to an incident -- ordinary English for the
# exact thing spec section 13 asks Phase 7 to test, not a leak of a hidden
# `causal_*` field. The full BANNED_SUBSTRINGS list is right for scanning
# KEYS (a dict key literally named `causal_component_id` or `is_distractor`
# would be a real field-name leak -- spec section 65's actual examples are
# all field-name-shaped); several of its entries ("causal", "distractor",
# "optimal", "mistake", "misleading", "efficiency", "_relevant") are also
# plausible ordinary words in a hand-written question about causation,
# relevance, or evidence quality, so they are excluded from the VALUE-scan
# to avoid flagging Phase 7's own legitimate question text as a leak.
_VALUE_SCAN_EXCLUSIONS = {"causal", "distractor", "optimal", "mistake", "misleading", "efficiency", "_relevant", "is_distractor"}
VALUE_BANNED_SUBSTRINGS = [b for b in BANNED_SUBSTRINGS if b not in _VALUE_SCAN_EXCLUSIONS]


def _flatten(obj, keys: list, values: list):
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(str(k))
            _flatten(v, keys, values)
    elif isinstance(obj, list):
        for item in obj:
            _flatten(item, keys, values)
    else:
        values.append(str(obj))


def assert_no_leakage(payload: dict):
    """Scans an about-to-be-sent request payload before it ever leaves the
    process. Deliberately scans `state` fully (keys+values) and each
    question's own BODY (`instructions`/`criteria`) fully, but does NOT
    scan the outer `questions` dict's own key names -- those are Phase 7's
    own hand-written decision-type identifiers (e.g. "causal_change",
    "root_cause"), fixed Python names we chose ourselves, not data pulled
    from any hidden source. Scanning them produced a real false positive
    ("causal_change" naturally contains "causal") -- the same class of
    self-referential false positive Phase 5/6 already hit and fixed for
    their own output-schema field names.

    Dict KEYS (within state/question bodies) are checked against the full
    BANNED_SUBSTRINGS list (a key literally named e.g. `causal_component_id`
    would mean a hidden field name leaked into the payload structure);
    string VALUES are checked against the narrower VALUE_BANNED_SUBSTRINGS
    (free text legitimately uses some of the same words for other reasons --
    see the comment above)."""
    keys, values = [], []
    _flatten(payload.get("state"), keys, values)
    for question_body in (payload.get("questions") or {}).values():
        _flatten(question_body, keys, values)

    key_haystack = " ".join(keys).lower()
    value_haystack = " ".join(values).lower()
    for banned in BANNED_SUBSTRINGS:
        if banned in key_haystack:
            raise LeakageGuardError(f"payload about to be sent to Jev/LLM has a KEY containing banned substring '{banned}'")
    for banned in VALUE_BANNED_SUBSTRINGS:
        if banned in value_haystack:
            raise LeakageGuardError(f"payload about to be sent to Jev/LLM has a VALUE containing banned substring '{banned}'")


def choice_question(instructions: str, criteria: dict) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def score_question(instructions: str, criteria: list) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": criteria}


def noul_question(instructions: str, criteria: dict = None) -> dict:
    q = {"type": "noul", "instructions": instructions}
    if criteria:
        q["criteria"] = criteria
    return q


class JevClient:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or TYPESAFE_API_KEY
        self.base_url = base_url or TYPESAFE_BASE_URL
        self.model = model or JEV_MODEL
        if not self.api_key:
            raise RuntimeError("TYPESAFE_API_KEY is not set -- add it to .env before calling Jev")

    def system_one(self, state, questions: dict, model: str = None) -> dict:
        """One batched call: `questions` may mix Choice/Score/Noul entries
        (spec section 47's parallel-question support). Returns the raw
        response dict: {"model": ..., "answers": {key: {...}}, "usage": {...}}."""
        payload = {"state": state, "model": model or self.model, "questions": questions}
        assert_no_leakage(payload)
        return self._post_with_retry(payload)

    def _post_with_retry(self, payload: dict) -> dict:
        url = f"{self.base_url}{TYPESAFE_SYSTEM_ONE_PATH}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
            except requests.RequestException as e:
                last_exc = e
                time.sleep(BASE_RETRY_DELAY_SECONDS * (2**attempt))
                continue

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429:
                retry_after_ms = self._parse_retry_after_ms(resp)
                delay = (retry_after_ms / 1000.0) if retry_after_ms else BASE_RETRY_DELAY_SECONDS * (2**attempt)
                if attempt == MAX_RETRIES - 1:
                    raise TypeSafeRateLimitError(resp.status_code, resp.text, retry_after_ms)
                print(f"    [jev 429] retry {attempt + 1}/{MAX_RETRIES} in {delay:.1f}s", flush=True)
                time.sleep(delay + 0.1)
                continue

            if resp.status_code >= 500:
                if attempt == MAX_RETRIES - 1:
                    raise TypeSafeAPIError(resp.status_code, resp.text)
                time.sleep(BASE_RETRY_DELAY_SECONDS * (2**attempt))
                continue

            # 4xx other than 429: not retryable
            raise TypeSafeAPIError(resp.status_code, resp.text)

        raise TypeSafeAPIError(-1, f"exhausted retries; last connection error: {last_exc}")

    @staticmethod
    def _parse_retry_after_ms(resp):
        header = resp.headers.get("Retry-After")
        if header:
            try:
                return float(header) * 1000
            except ValueError:
                pass
        m = _RETRY_AFTER_MS_RE.search(resp.text or "")
        return float(m.group(1)) if m else None
