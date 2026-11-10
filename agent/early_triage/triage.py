"""Early Jev triage: one typed Choice question, asked before any graph investigation, that suggests an issue category for the agent to test.

    ticket fields (allow-list) -> Jev Choice over the 18 taxonomy categories + ABSTAIN -> validation -> plain-code policy -> a triage record

Jev supplies probabilities; this module's plain code decides what to do with them (drop a low-probability or abstaining answer, label the uncertainty). Every non-usable
outcome (abstained, low probability, invalid answer, API error, timeout, Jev not configured) is a FALLBACK: the record says why, and the agent runs exactly as it would
without triage. The one exception is a leakage-guard trip, which is never suppressed.

What Jev sees is built from an allow-list of the case context (ticket text, customer tier/industry/size, product name). The case id, customer id, status, dates, signals,
telemetry and every graph tool are excluded, and nothing here imports an evaluation store or a hidden-truth reader. Reuses the existing direct-HTTP Jev client and its
leakage guard (`agent.jev_v2.client`); the official SDK is never installed.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from agent.early_triage import priorities
from agent.early_triage.config import ABSTAIN_KEY, QUESTION_VERSION, ROLE, STATE_VERSION, TRIAGE_VERSION, TriageConfig
from agent.jev_v2.client import LeakageGuardError, choice_question
from agent.jev_v2.reference_data import all_issue_categories

TICKET_FIELDS = ("title", "description", "reported_symptoms", "environment", "region", "reported_business_impact", "reported_affected_users", "priority")
CUSTOMER_FIELDS = {"tier": "customer_tier", "industry": "customer_industry", "company_size": "customer_company_size"}
KEY = "issue_category_early"

INSTRUCTIONS = ("Using only this support ticket and basic customer/product context (no logs, telemetry, changes or other evidence have been examined yet), which issue "
                "category best describes the problem? This is an early, provisional guess that a later investigation will test. If the ticket alone does not support "
                f"choosing a category, choose {ABSTAIN_KEY}.")
ABSTAIN_DESCRIPTION = "The ticket alone does not support choosing any category; leave this to the investigation"


def build_state(ctx: dict) -> dict:
    """Allow-list projection of the case context. Anything not named here (ids, status, dates, and any field that should never have been in the context) is dropped."""
    return {"ticket": {f: ctx.get(f) for f in TICKET_FIELDS},
            "customer": {k: ctx.get(src) for k, src in CUSTOMER_FIELDS.items()},
            "reported_product": {"name": ctx.get("reported_product_name")}}


def build_question() -> dict:
    cats = dict(all_issue_categories())
    return choice_question(INSTRUCTIONS, {**cats, ABSTAIN_KEY: ABSTAIN_DESCRIPTION})


def parse_answer(answer, options) -> tuple:
    """(choice, {option: probability}, None) for a well-formed typed answer, else (None, None, reason). Nothing is repaired or guessed."""
    if not isinstance(answer, dict):
        return None, None, "the answer is not an object"
    choice, probs = answer.get("choice"), answer.get("probabilities")
    if choice not in options:
        return None, None, f"the choice {str(choice)[:40]!r} is not one of the offered options"
    if not isinstance(probs, dict) or not probs:
        return None, None, "no probability table"
    for k, v in probs.items():
        if k not in options or isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            return None, None, f"invalid probability entry {str(k)[:40]!r}"
    if not 0.9 <= sum(probs.values()) <= 1.1:
        return None, None, f"probabilities sum to {sum(probs.values()):.2f}, not 1"
    if probs.get(choice, 0) < max(probs.values()) - 1e-6:
        return None, None, "the choice is not the highest-probability option"
    return choice, {k: float(v) for k, v in probs.items()}, None


def uncertainty_label(p: float, cfg: TriageConfig) -> str:
    return "low" if p >= cfg.strong_probability else "moderate" if p >= cfg.moderate_probability else "high"


def _record(cfg: TriageConfig, status: str, reason: str = None, **kw) -> dict:
    rec = {"version": TRIAGE_VERSION, "role": ROLE, "source": "jev_early_triage", "question_version": QUESTION_VERSION, "state_version": STATE_VERSION, "status": status,
           "fallback": status != "hint", "fallback_reason": reason, "category_id": None, "category_name": None, "probability": None, "margin": None, "uncertainty": None,
           "alternatives": [], "distribution_top": [], "abstain_probability": None, "suggested_tools": [], "jev_model": None, "input_tokens": 0, "latency_ms": 0.0,
           "error": None, "config": cfg.to_dict()}
    rec.update(kw)
    return rec


def decide(choice: str, probs: dict, names: dict, cfg: TriageConfig) -> dict:
    """The plain-code policy over Jev's typed answer. Returns the decision fields of the record."""
    ranked = sorted(((c, p) for c, p in probs.items() if c != ABSTAIN_KEY), key=lambda x: (-x[1], x[0]))
    top = [{"category_id": c, "name": names.get(c), "probability": round(p, 4)} for c, p in ranked[:cfg.top_alternatives + 1]]
    base = {"distribution_top": top, "abstain_probability": round(probs.get(ABSTAIN_KEY, 0.0), 4)}
    if choice == ABSTAIN_KEY:
        return {**base, "status": "abstained", "reason": "Jev abstained: the ticket alone does not support choosing a category"}
    p = probs[choice]
    if p < cfg.min_probability:
        return {**base, "status": "low_probability", "reason": f"the top category probability {p:.2f} is below the {cfg.min_probability:.2f} minimum"}
    margin = p - (ranked[1][1] if len(ranked) > 1 else 0.0)
    return {**base, "status": "hint", "reason": None, "category_id": choice, "category_name": names.get(choice), "probability": round(p, 4), "margin": round(margin, 4),
            "uncertainty": uncertainty_label(p, cfg), "alternatives": top[1:], "suggested_tools": priorities.suggest(choice)}


def _call(client, state: dict, question: dict, timeout_s: float):
    """One Jev call under a wall-clock budget. The worker thread is not killed on timeout (it cannot be); its late result is discarded."""
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(client.system_one, state, {KEY: question}).result(timeout=timeout_s)
    finally:
        ex.shutdown(wait=False)


class EarlyTriage:
    """The `triage(ctx)` callback for `agent_v3.loop.run_case`. `client` needs `system_one(state, questions)`; None uses the shared Jev client (and falls back if it cannot be built)."""

    def __init__(self, client=None, config: TriageConfig = None):
        self.client, self.cfg = client, config or TriageConfig()

    def _client(self):
        if self.client is None:
            from agent.trace_eval_v2.jev_evaluator import get_client
            self.client = get_client()
        return self.client

    def __call__(self, ctx: dict) -> dict:
        cfg, t0 = self.cfg, time.time()
        lap = lambda: round((time.time() - t0) * 1000, 1)
        try:
            client = self._client()
        except Exception as e:  # noqa: BLE001 - e.g. TYPESAFE_API_KEY is not set: the workflow continues without triage
            return _record(cfg, "unavailable", f"Jev is not configured: {str(e)[:120]}", latency_ms=lap(), error=f"{type(e).__name__}: {str(e)[:200]}")
        state, question = build_state(ctx), build_question()
        try:
            resp = _call(client, state, question, cfg.timeout_s)
        except LeakageGuardError:
            raise                                             # a tripped guard stops the call and the run; it is never downgraded to a warning
        except FutureTimeout:
            return _record(cfg, "timeout", f"the Jev call exceeded {cfg.timeout_s:.0f}s", latency_ms=lap(), error="timeout")
        except Exception as e:  # noqa: BLE001 - transport or API failure after the client's own retries
            return _record(cfg, "error", f"the Jev call failed: {type(e).__name__}", latency_ms=lap(), error=f"{type(e).__name__}: {str(e)[:200]}")
        meta = {"jev_model": (resp or {}).get("model"), "input_tokens": ((resp or {}).get("usage") or {}).get("input_tokens") or 0, "latency_ms": lap()}
        choice, probs, why = parse_answer(((resp or {}).get("answers") or {}).get(KEY), question["criteria"])
        if why:
            return _record(cfg, "invalid", f"Jev's answer failed validation: {why}", error=why, **meta)
        d = decide(choice, probs, all_issue_categories(), cfg)
        return _record(cfg, d.pop("status"), d.pop("reason"), **d, **meta)
