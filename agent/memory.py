from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage
from pydantic.v1 import BaseModel, Field


class WindowChatHistory(BaseChatMessageHistory, BaseModel):
    """Chat history capped at the last k exchange pairs (2k messages total)."""

    messages: list[BaseMessage] = Field(default_factory=list)
    max_messages: int = 10  # k=5 pairs → 10 messages

    def add_messages(self, messages: list[BaseMessage]) -> None:
        self.messages.extend(messages)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def clear(self) -> None:
        self.messages = []


# Session store — keyed by session_id string
_store: dict[str, WindowChatHistory] = {}


def get_session_history(session_id: str, k: int = 5) -> WindowChatHistory:
    if session_id not in _store:
        _store[session_id] = WindowChatHistory(max_messages=k * 2)
    return _store[session_id]


def clear_session(session_id: str) -> None:
    _store.pop(session_id, None)
