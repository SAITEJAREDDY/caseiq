"""The runtime verifier: deterministic checks + three Jev signals + the policy, packaged as the callback the agent loop calls after each final answer."""
import time

from agent.runtime_verifier import deterministic_checks, jev_checks, policy
from agent.runtime_verifier.models import VerifierConfig


class RuntimeVerifier:
    def __init__(self, session, case_id: str, jev_client=None, config: VerifierConfig = None):
        self.session, self.case_id, self.jev_client, self.cfg = session, case_id, jev_client, config or VerifierConfig()

    def __call__(self, run: dict, round_no: int) -> dict:
        t0 = time.time()
        det = deterministic_checks.run_all(run, self.cfg)
        jev = None
        if det["D1"]["passed"]:                                     # only a well-formed answer is worth judging
            try:
                jev = jev_checks.signals(jev_checks.build_packet(self.session, run, self.case_id), self.jev_client)
            except Exception as e:  # noqa: BLE001 - a leakage-guard trip or transport failure is recorded; the policy then refuses to auto-accept
                if e.__class__.__name__ == "LeakageError":
                    raise
                jev = {"available": False, "errors": [f"{type(e).__name__}: {str(e)[:200]}"], "missed_evidence_probability": None,
                       "distractor_anchor_probability": None, "review": None, "review_probabilities": None, "input_tokens": 0}
        verdict = policy.decide(run, det, jev, round_no, self.cfg)
        verdict.update(deterministic_checks=det, jev=jev, verifier_latency_ms=round((time.time() - t0) * 1000, 1))
        return verdict
