"""A minimal tool-calling chat client for Together AI's OpenAI-compatible
endpoint, built directly on langchain_core primitives (AIMessage, tool-schema
conversion) rather than the `langchain-openai` package.

Why this exists instead of `ChatOpenAI(base_url=...)`: this project pins
langchain==0.2.16 / langchain-core==0.2.43 / langsmith==0.1.147 (the live
app's working, tested stack). The current `langchain-openai` release
requires langchain-core>=1.x, and installing it force-upgrades langchain-core
project-wide, which breaks langchain-groq/langchain/langchain-community and
therefore the live app. Rather than touch versions the live app depends on,
this module implements just the sliver of the chat-model interface the
Phase 5 loop actually uses (`.bind_tools(tools).invoke(messages)`), via raw
HTTP -- the same pattern already proven in data/generators/llm_client.py for
Together AI narrative generation.
"""
import json
import uuid

import requests
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"


def _message_to_openai_dict(m):
    if isinstance(m, SystemMessage):
        return {"role": "system", "content": m.content}
    if isinstance(m, HumanMessage):
        return {"role": "user", "content": m.content}
    if isinstance(m, ToolMessage):
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    if isinstance(m, AIMessage):
        d = {"role": "assistant", "content": m.content or ""}
        if m.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
                }
                for tc in m.tool_calls
            ]
        return d
    raise TypeError(f"Unsupported message type: {type(m)}")


class TogetherRateLimitError(RuntimeError):
    def __init__(self, response):
        self.response = response
        super().__init__(f"Together AI rate limit: {response.status_code} {response.text[:300]}")


class _BoundTogetherChat:
    def __init__(self, parent, tools):
        self._parent = parent
        self._tools = [convert_to_openai_tool(t) for t in tools]

    def invoke(self, messages):
        payload = {
            "model": self._parent.model,
            "temperature": self._parent.temperature,
            "max_tokens": self._parent.max_tokens,
            "messages": [_message_to_openai_dict(m) for m in messages],
            "tools": self._tools,
        }
        resp = requests.post(
            TOGETHER_URL,
            headers={"Authorization": f"Bearer {self._parent.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if resp.status_code == 429:
            raise TogetherRateLimitError(resp)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        content = choice.get("content") or ""
        raw_tool_calls = choice.get("tool_calls") or []
        tool_calls = [
            {
                "name": tc["function"]["name"],
                "args": json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {},
                "id": tc.get("id") or uuid.uuid4().hex,
                "type": "tool_call",
            }
            for tc in raw_tool_calls
        ]
        usage = data.get("usage", {})
        return AIMessage(
            content=content,
            tool_calls=tool_calls,
            response_metadata={
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "model_name": self._parent.model,
            },
        )


class ChatTogether:
    """Drop-in-enough replacement for ChatGroq for this project's narrow
    usage: `.bind_tools(tools).invoke(messages)`."""

    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def bind_tools(self, tools) -> _BoundTogetherChat:
        return _BoundTogetherChat(self, tools)
