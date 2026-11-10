"""The LLM judge baseline: the same packet, the same question and the same allowed answers as Jev, sent to meta-llama/Llama-3.3-70B-Instruct-Turbo (Together AI).

Reuses Phase 7's transport and parsing helpers (retrying HTTP call, structured-output classifier, repair prompt); the prompt is built here so it can carry each
judgment's yes/no meaning and option descriptions exactly as Jev's question object does. Contract failures are recorded attempt by attempt, never hidden. One bounded repair
re-prompt follows an invalid first attempt (the Phase 7 setting); the first attempt, the repair and whether it worked are all stored, so strict first-attempt accuracy can be reported.

The LLM judge is a comparator. It is never used as ground truth, and Jev is never scored by agreement with it.
"""
import json
import time

from agent.jev_v2.config import LLM_BASELINE_MAX_TOKENS, LLM_BASELINE_MODEL, LLM_BASELINE_TEMPERATURE, LLM_REPAIR_MAX_ATTEMPTS
from agent.jev_v2.llm_baseline import _call_together, _classify_response, _repair_instruction
from agent.trace_eval_v2 import questions
from agent.trace_eval_v2.guard import assert_request_clean

SYSTEM = "You are a precise reviewer of completed diagnostic-agent investigations. Respond with strict, valid JSON only -- no prose, no markdown fences."


def build_messages(judgment: str, state: dict, question: dict) -> list:
    spec = questions.QUESTIONS[judgment]
    if spec["primitive"] == "noul":
        meaning = f'YES means: {spec["yes"]}\nNO means: {spec["no"]}\n\n'
        schema = 'Respond with ONLY a JSON object of the exact form {"probability": <float 0.0-1.0>} -- the probability that the answer to the question is YES.'
        options = ""
    else:
        meaning = ""
        schema = ('Respond with ONLY a JSON object of the exact form {"selected": "<one option key>", "confidence": <float 0.0-1.0>}. "selected" MUST be exactly one of the option keys '
                  "given below -- never invent a new key or answer in free text.")
        options = "\n\nOPTIONS:\n" + json.dumps(question["criteria"])
    user = f"REVIEW PACKET:\n{json.dumps(state, default=str, ensure_ascii=False)}\n\nQUESTION:\n{spec['instructions']}\n\n{meaning}{schema}{options}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _timed_call(messages: list) -> tuple:
    t0 = time.time()
    text, usage = _call_together(messages)
    return text, usage or {}, (time.time() - t0) * 1000


def ask(judgment: str, state: dict) -> dict:
    question = questions.jev_question(judgment)
    assert_request_clean(state, question)
    primitive = questions.primitive(judgment)
    options = question.get("criteria") if primitive == "choice" else None
    messages = build_messages(judgment, state, question)
    base = {"judge": "llm", "judgment": judgment, "question_version": questions.question_version(judgment), "model": LLM_BASELINE_MODEL, "temperature": LLM_BASELINE_TEMPERATURE}
    attempts = []

    def record(purpose, text, usage, latency_ms, kind, detail):
        attempts.append({"attempt": len(attempts) + 1, "purpose": purpose, "raw_text": text, "provider_usage": usage, "latency_ms": round(latency_ms, 1),
                         "failure_kind": kind, "failure_detail": detail})

    def finish(answer, first_valid, first_failure, final_kind, final_detail):
        repair_required = (not first_valid) and first_failure != "request_failed"
        rec = {**base, "status": "ok", "attempts": attempts,
               "usage": {"input_tokens": sum(a["provider_usage"].get("prompt_tokens", 0) for a in attempts), "output_tokens": sum(a["provider_usage"].get("completion_tokens", 0) for a in attempts)},
               "latency_ms": round(sum(a["latency_ms"] for a in attempts), 1), "first_attempt_valid": first_valid, "first_attempt_failure": first_failure,
               "repair_required": repair_required, "repair_succeeded": (answer is not None) if repair_required else None, "unrecoverable_failure": answer is None,
               "contract_failure": None if answer is not None else (final_kind or "unrecoverable"), "contract_failure_detail": final_detail}
        if answer is not None:
            rec["answer"] = answer
        return rec

    try:
        text, usage, latency_ms = _timed_call(messages)
    except Exception as e:  # noqa: BLE001
        return {**base, "status": "error", "error": str(e)[:300], "contract_failure": "request_failed", "attempts": [], "first_attempt_valid": False,
                "first_attempt_failure": "request_failed", "repair_required": False, "repair_succeeded": None, "unrecoverable_failure": True}
    answer, kind, detail = _classify_response(primitive, text, options)
    record("initial", text, usage, latency_ms, kind, detail)
    if answer is not None:
        return finish(answer, True, None, None, None)
    first_failure = kind
    for _ in range(LLM_REPAIR_MAX_ATTEMPTS):
        repair = messages + [{"role": "assistant", "content": text if isinstance(text, str) else ""}, {"role": "user", "content": _repair_instruction(primitive, detail, options)}]
        try:
            text, usage, latency_ms = _timed_call(repair)
        except Exception as e:  # noqa: BLE001
            record("repair", None, {}, 0.0, "request_failed", str(e)[:200])
            return finish(None, False, first_failure, "request_failed", str(e)[:200])
        answer, kind, detail = _classify_response(primitive, text, options)
        record("repair", text, usage, latency_ms, kind, detail)
        if answer is not None:
            return finish(answer, False, first_failure, None, None)
    return finish(None, False, first_failure, kind, detail)
