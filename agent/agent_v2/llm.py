"""Phase 5's own chat-model client -- separate from agent/llm_client.py (the
live app's chain), so changing the baseline agent's model/provider/
temperature never affects the live app. Reuses config.settings.GROQ_API_KEY/
TOGETHER_API_KEY read-only.

Provider is configurable (AGENT_MODEL_PROVIDER in config.py); Together AI is
the default (see config.py for why). Groq remains available for comparison.
"""
import re
import time

import config.settings as _live_settings
import groq
from langchain_groq import ChatGroq

from agent.agent_v2.config import AGENT_MAX_TOKENS, AGENT_MODEL_NAME, AGENT_MODEL_PROVIDER, AGENT_TEMPERATURE
from agent.agent_v2.together_chat import ChatTogether, TogetherRateLimitError


def get_llm():
    if AGENT_MODEL_PROVIDER == "together":
        return ChatTogether(
            api_key=_live_settings_together_key(),
            model=AGENT_MODEL_NAME,
            temperature=AGENT_TEMPERATURE,
            max_tokens=AGENT_MAX_TOKENS,
        )
    if AGENT_MODEL_PROVIDER == "groq":
        return ChatGroq(
            api_key=_live_settings.GROQ_API_KEY,
            model_name=AGENT_MODEL_NAME,
            temperature=AGENT_TEMPERATURE,
            max_tokens=AGENT_MAX_TOKENS,
        )
    raise ValueError(f"Unknown AGENT_MODEL_PROVIDER: {AGENT_MODEL_PROVIDER!r}")


def _live_settings_together_key() -> str:
    import os

    key = os.environ.get("TOGETHER_API_KEY", "")
    if not key:
        raise RuntimeError("TOGETHER_API_KEY not set in .env (used by data/generators/ and, optionally, agent_v2)")
    return key


def _retry_delay_seconds(exc: Exception, default: float) -> float:
    """Mirrors the retry pattern already used in data/generators/llm_client.py."""
    response = getattr(exc, "response", None)
    if response is not None:
        header = response.headers.get("retry-after")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
    match = re.search(r"try again in ([\d.]+)(ms|s)", str(exc))
    if match:
        value, unit = match.groups()
        return float(value) / 1000 if unit == "ms" else float(value)
    return default


def invoke_with_retry(bound_llm, messages, max_retries: int = 6, base_delay: float = 2.0):
    """`bound_llm.invoke(messages)` with retry-on-429, reading the server's
    suggested wait when available (else exponential backoff)."""
    for attempt in range(max_retries):
        try:
            return bound_llm.invoke(messages)
        except (groq.RateLimitError, TogetherRateLimitError) as e:
            if attempt == max_retries - 1:
                raise
            delay = _retry_delay_seconds(e, default=base_delay * (2**attempt))
            print(f"    [rate-limit/429] retry {attempt + 1}/{max_retries} in {delay:.1f}s", flush=True)
            time.sleep(delay + 0.1)
