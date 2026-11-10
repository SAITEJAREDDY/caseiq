"""Jev as a trace evaluator: one typed question about one completed trace, one `system_one` call, one typed answer.

Reuses the dependency-free direct-HTTP client from Phase 7 (`agent.jev_v2.client`); the official SDK is never installed. The only change is the leakage guard: the
Phase 7 client applies its own value scan inside `system_one`, which refuses ordinary English words that the agent's free text can contain, so this evaluator builds the
payload itself, applies the Phase 8 guard (`guard.py`), and posts it with the client's own retrying transport.

Jev is asked for typed decisions only: a probability for the five Noul judgments and a choice with probabilities for the review decision. It is never asked for an explanation.
"""
import time

from agent.jev_v2.client import JevClient
from agent.trace_eval_v2 import questions
from agent.trace_eval_v2.config import jev_model
from agent.trace_eval_v2.guard import assert_request_clean


class TraceJevClient(JevClient):
    def judge(self, state: dict, question: dict, key: str) -> dict:
        assert_request_clean(state, question)  # raises LeakageError; a tripped guard stops the call
        payload = {"state": state, "model": self.model, "questions": {key: question}}
        return self._post_with_retry(payload)


_client = None


def get_client() -> TraceJevClient:
    global _client
    if _client is None:
        _client = TraceJevClient(model=jev_model())
    return _client


def ask(judgment: str, state: dict, client: TraceJevClient = None) -> dict:
    """Returns the raw judgment record for one (judgment, packet): typed answer, model id, usage, latency, status."""
    client = client or get_client()
    question = questions.jev_question(judgment)
    t0 = time.time()
    try:
        resp = client.judge(state, question, judgment)
        latency_ms = (time.time() - t0) * 1000
        return {"judge": "jev", "judgment": judgment, "question_version": questions.question_version(judgment), "status": "ok",
                "jev_model": resp.get("model"), "answer": resp["answers"][judgment], "usage": resp.get("usage"), "latency_ms": round(latency_ms, 1)}
    except Exception as e:  # noqa: BLE001 - recorded, never hidden; a guard failure is re-raised by the caller's own check
        if e.__class__.__name__ == "LeakageError":
            raise
        return {"judge": "jev", "judgment": judgment, "question_version": questions.question_version(judgment), "status": "error", "error": str(e)[:300],
                "latency_ms": round((time.time() - t0) * 1000, 1)}
