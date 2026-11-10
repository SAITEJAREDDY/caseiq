"""The 'LLM primitive baseline' (spec section 28): the exact same
state/candidates/question Jev receives, sent instead to
meta-llama/Llama-3.3-70B-Instruct-Turbo (Together AI) with a
constrained-JSON instruction -- no tool-calling. Contract failures
(malformed JSON, invalid option, missing field) are recorded attempt by
attempt as first-class outcomes, never hidden or silently patched (spec
section 29) -- this comparison is partly about decision-interface
reliability. JEV-018 adds ONE bounded repair re-prompt after an invalid first
attempt (config.LLM_REPAIR_MAX_ATTEMPTS); the first attempt, the repair, and
whether it worked are all stored, and strict first-attempt accuracy is
reported next to the repaired figure so repair can never hide a failure.

Self-contained rather than reusing data/generators/llm_client.py: that
module is tied to a different model constant, a disk response cache, and a
module-global usage counter -- none of which fit a per-decision,
repeatable-on-demand evaluation call. Mirrors the same proven SSE-stream
retry pattern (agent/agent_v2/together_chat.py, data/generators/llm_client.py)
directly over `requests`, which is already a project dependency.
"""
import json
import time
import uuid
from datetime import datetime, timezone

import requests

from agent.jev_v2 import candidates as candidates_mod
from agent.jev_v2 import decisions as decisions_mod
from agent.jev_v2.client import assert_no_leakage
from agent.jev_v2.config import (
    BASE_RETRY_DELAY_SECONDS,
    CANDIDATE_GENERATION_VERSIONS,
    CANDIDATE_STRATEGY_VERSION,
    LLM_BASELINE_MAX_TOKENS,
    LLM_REPAIR_MAX_ATTEMPTS,
    LLM_BASELINE_MODEL,
    LLM_BASELINE_TEMPERATURE,
    MAX_RETRIES,
    TOGETHER_API_KEY,
)
from agent.jev_v2.questions import build_question, primitive_type, question_version

TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"


def _build_prompt(decision_type: str, state: dict, question: dict, candidates) -> list:
    primitive = question["type"]
    instructions = question["instructions"]
    if primitive == "choice":
        schema_hint = (
            'Respond with ONLY a JSON object of the exact form {"selected": "<one candidate key>", '
            '"confidence": <float 0.0-1.0>}. "selected" MUST be exactly one of the candidate keys given below -- '
            "never invent a new key or answer in free text."
        )
        candidates_block = json.dumps(candidates, default=str)
    elif primitive == "noul":
        schema_hint = (
            'Respond with ONLY a JSON object of the exact form {"probability": <float 0.0-1.0>} -- the probability '
            "that the answer to the question is yes/true."
        )
        candidates_block = None
    else:
        raise ValueError(f"unsupported primitive: {primitive}")

    user_content = f"OBSERVABLE STATE:\n{json.dumps(state, default=str)}\n\nQUESTION:\n{instructions}\n\n{schema_hint}"
    if candidates_block:
        user_content += f"\n\nCANDIDATES:\n{candidates_block}"

    return [
        {"role": "system", "content": "You are a precise decision-making assistant. Respond with strict, valid JSON only -- no prose, no markdown fences."},
        {"role": "user", "content": user_content},
    ]


def _call_together(messages: list, max_retries: int = MAX_RETRIES) -> tuple:
    if not TOGETHER_API_KEY:
        raise RuntimeError("TOGETHER_API_KEY is not set -- required for the LLM primitive baseline")
    body = {
        "model": LLM_BASELINE_MODEL,
        "messages": messages,
        "temperature": LLM_BASELINE_TEMPERATURE,
        "max_tokens": LLM_BASELINE_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"}
    delay = BASE_RETRY_DELAY_SECONDS
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(TOGETHER_URL, headers=headers, json=body, timeout=60)
        except requests.RequestException as e:
            last_error = e
            time.sleep(delay)
            delay *= 2
            continue
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return text, usage
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            retry_after = float(resp.headers.get("Retry-After", delay))
            time.sleep(retry_after)
            delay *= 2
            continue
        raise RuntimeError(f"Together API error {resp.status_code}: {resp.text[:500]}")
    raise RuntimeError(f"Together API call failed after {max_retries} retries: {last_error}")


def _classify_response(primitive: str, text, candidates) -> tuple:
    """Returns (answer_or_None, failure_kind_or_None, failure_detail_or_None).
    Failure kinds: malformed_json, missing_answer, invalid_option,
    invalid_confidence, invalid_probability."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, "malformed_json", "response was not valid JSON"
    if not isinstance(parsed, dict):
        return None, "malformed_json", "JSON response was not an object"
    if primitive == "choice":
        selected, confidence = parsed.get("selected"), parsed.get("confidence")
        if selected is None:
            return None, "missing_answer", "missing 'selected' field"
        if candidates is not None and selected not in candidates:
            return None, "invalid_option", "'selected' is not one of the given candidate keys"
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
            return None, "invalid_confidence", "'confidence' missing or outside 0.0-1.0"
        return {"choice": selected, "confidence": float(confidence), "probabilities": None}, None, None
    if primitive == "noul":
        prob = parsed.get("probability")
        if prob is None:
            return None, "missing_answer", "missing 'probability' field"
        if isinstance(prob, bool) or not isinstance(prob, (int, float)) or not (0.0 <= float(prob) <= 1.0):
            return None, "invalid_probability", "'probability' outside 0.0-1.0"
        return {"noul": float(prob)}, None, None
    return None, "missing_answer", f"unsupported primitive {primitive}"


def _repair_instruction(primitive: str, detail: str, candidates) -> str:
    msg = f"Your previous response was invalid ({detail}). Respond again with ONLY the required JSON object, with no commentary."
    if primitive == "choice" and candidates:
        msg += f' "selected" must be exactly one of these keys: {json.dumps(list(candidates))}.'
    return msg


def _timed_call(messages: list) -> tuple:
    t0 = time.time()
    text, usage = _call_together(messages)
    return text, usage or {}, (time.time() - t0) * 1000


def run_llm_decision(decision_type: str, case_id: str, state: dict, question: dict, candidates, candidate_meta: dict, as_of: str, context_version: str) -> dict:
    """`candidates` are the CANONICAL candidates (what scoring sees); the
    model is shown `model_facing_candidates`, which differs only in the
    opaque-key diagnostic control."""
    model_cands = candidates_mod.model_facing_candidates(candidates, candidate_meta) if candidates else candidates
    question = {**question, "criteria": model_cands} if question.get("type") == "choice" else question
    assert_no_leakage({"state": state, "questions": {decision_type: question}})
    decision_id = f"{case_id}__{decision_type}__llm__{uuid.uuid4().hex[:8]}"
    primitive = question["type"]
    messages = _build_prompt(decision_type, state, question, model_cands)

    base = {
        "decision_id": decision_id, "case_id": case_id, "decision_type": decision_type,
        "question_id": decision_type, "question_version": question_version(decision_type),
        "primitive_type": primitive_type(decision_type), "context_version": context_version,
        "candidate_strategy_version": CANDIDATE_STRATEGY_VERSION,
        "candidate_generation_version": (candidate_meta or {}).get("candidate_generation_version") or CANDIDATE_GENERATION_VERSIONS.get(decision_type),
        "candidate_meta": candidate_meta, "candidates": candidates, "state": state, "as_of": as_of,
        "model": LLM_BASELINE_MODEL, "temperature": LLM_BASELINE_TEMPERATURE, "created_at": datetime.now(timezone.utc).isoformat(),
    }

    attempts = []

    def record_attempt(purpose, text, usage, latency_ms, kind, detail):
        attempts.append({"attempt": len(attempts) + 1, "purpose": purpose, "raw_text": text, "provider_usage": usage,
                         "latency_ms": round(latency_ms, 1), "failure_kind": kind, "failure_detail": detail})

    def finish(answer, final_failure_kind, final_failure_detail, first_valid, first_failure):
        input_tokens = sum(a["provider_usage"].get("prompt_tokens", 0) for a in attempts)
        output_tokens = sum(a["provider_usage"].get("completion_tokens", 0) for a in attempts)
        repair_required = (not first_valid) and first_failure != "request_failed"
        repaired_ok = repair_required and answer is not None
        rec = {
            **base, "status": "ok", "attempts": attempts,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "latency_ms": round(sum(a["latency_ms"] for a in attempts), 1),
            "first_attempt_latency_ms": attempts[0]["latency_ms"] if attempts else None,
            "first_attempt_valid": first_valid, "first_attempt_failure": first_failure,
            "repair_required": repair_required, "repair_succeeded": (repaired_ok if repair_required else None),
            "unrecoverable_failure": answer is None,
            "contract_failure": None if answer is not None else (final_failure_kind or "unrecoverable"),
            "contract_failure_detail": final_failure_detail,
        }
        if answer is not None:
            rec["answer"] = candidates_mod.to_canonical_answer(answer, candidate_meta)
        return rec

    try:
        text, usage, latency_ms = _timed_call(messages)
    except Exception as e:
        return {**base, "status": "error", "error": str(e), "contract_failure": "request_failed", "attempts": [],
                "first_attempt_valid": False, "first_attempt_failure": "request_failed", "repair_required": False,
                "repair_succeeded": None, "unrecoverable_failure": True}

    answer, kind, detail = _classify_response(primitive, text, model_cands)
    record_attempt("initial", text, usage, latency_ms, kind, detail)
    if answer is not None:
        return finish(answer, None, None, True, None)

    first_failure = kind
    for _ in range(LLM_REPAIR_MAX_ATTEMPTS):
        repair_messages = messages + [
            {"role": "assistant", "content": text if isinstance(text, str) else ""},
            {"role": "user", "content": _repair_instruction(primitive, detail, model_cands)},
        ]
        try:
            text, usage, latency_ms = _timed_call(repair_messages)
        except Exception as e:
            record_attempt("repair", None, {}, 0.0, "request_failed", str(e)[:200])
            return finish(None, "request_failed", str(e)[:200], False, first_failure)
        answer, kind, detail = _classify_response(primitive, text, model_cands)
        record_attempt("repair", text, usage, latency_ms, kind, detail)
        if answer is not None:
            return finish(answer, None, None, False, first_failure)
    return finish(None, kind, detail, False, first_failure)


def run_llm_decisions(session, case_id: str, decision_type: str, as_of: str, context_version: str, candidate_versions: dict = None, causal_key_mode: str = "canonical") -> list:
    """Mirrors agent.jev_v2.decisions.run_decision's signature/shape, but
    against the LLM baseline instead of Jev -- uses decisions.build_inputs/
    build_incident_inputs so both baselines see byte-identical state and
    candidates for the same (case_id, decision_type, as_of, context_version)."""
    if decision_type == "incident_relationship":
        records = []
        for state, incident_id, meta in decisions_mod.build_incident_inputs(session, case_id, as_of):
            q = build_question(decision_type, None)
            rec = run_llm_decision(decision_type, case_id, state, q, None, meta, as_of, context_version)
            rec["incident_id"] = incident_id
            records.append(rec)
        return records

    state, cands, cmeta = decisions_mod.build_inputs(session, case_id, decision_type, as_of, context_version, candidate_versions, causal_key_mode)
    q = build_question(decision_type, cands)
    return [run_llm_decision(decision_type, case_id, state, q, cands, cmeta, as_of, context_version)]
