"""End-to-end Phase 9 runtime: case -> [optional early Jev triage] -> agent (existing tools) -> proposed diagnosis -> deterministic checks + Jev signals -> policy
-> optional ONE additional investigation round -> final action (ACCEPT / HUMAN_REVIEW / PRIORITY_REVIEW).

Jev has two separate roles here. Early triage (opt-in, `early_triage=True`) is guidance: a provisional category hint from the ticket text, before any graph investigation.
The late verifier is verification of the finished answer and is unchanged. The late verifier's packet is built from the trace and the graph only, never from the hint.

    python3 -m agent.runtime_verifier.run CS00011 CS00042                    # dev cases; late verification only (the Phase 9 workflow)
    python3 -m agent.runtime_verifier.run --early-triage CS00011 CS00042     # early triage + late verification
"""
import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.agent_v3 import config as A
from agent.agent_v3.backend import Neo4jBackend
from agent.agent_v3.llm import TogetherJSONClient
from agent.agent_v3.loop import run_case
from agent.early_triage.config import TriageConfig
from agent.early_triage.triage import EarlyTriage
from agent.runtime_verifier.models import CONTINUE, HUMAN_REVIEW, PRIORITY_REVIEW, VerifierConfig
from agent.runtime_verifier.verifier import RuntimeVerifier

OUT_DIR = A.PROJECT_ROOT / "data" / "runtime_verifier_runs"
TOGETHER_USD_PER_M_TOKENS = 0.88     # labeled estimates, not billing: Llama-3.3-70B-Instruct-Turbo, input and output
JEV_USD_PER_M_INPUT_TOKENS = 0.042   # Jev input pricing (output is free)


def _describe(mp: dict, alias) -> dict:
    e = mp.get(alias) if alias else None
    return None if not e else {"alias": alias, "name": e["display_name"] or e["summary"], "source_id": e["canonical_id"]}


def diagnosis_view(fa: dict, mp: dict) -> dict:
    """Human-readable form of an alias-form final answer (names next to ids; for people, not for models)."""
    if not fa:
        return None
    sel = {k: _describe(mp, fa[k]) for k in ("issue_category", "root_cause", "affected_component", "causal_change", "owning_team")}
    return {"status": fa["status"], "confidence": fa["confidence"], "evidence_sufficiency": fa["evidence_sufficiency"], "human_review_required": fa["human_review_required"],
            "review_reason": fa["review_reason"], "selections": sel, "summary": fa["summary"], "recommended_next_action": fa["recommended_next_action"],
            "hypotheses": [{"label": h["label"], "confidence": h["confidence"], "status": h["status"]} for h in fa["hypotheses"]]}


def review_packet(decision: str, verdict: dict, run: dict) -> dict:
    """What a person needs when the system cannot safely resolve a case."""
    mp = run["alias_mappings"]
    fa = run.get("final_alias_form") or (run.get("initial_result") or {}).get("final_alias_form")
    cited = list((fa or {}).get("evidence_ids") or [])
    if not cited:
        cited = [a for a, e in mp.items() if e["kind"] in ("EVIDENCE", "CHANGE", "INCIDENT")][:5]
    jev = verdict.get("jev") or {}
    return {"decision": decision, "reason": verdict["reason"], "triggers": verdict.get("triggers", []), "agent_diagnosis": diagnosis_view(fa, mp),
            "key_evidence": [{"alias": a, "type": mp[a]["type"], "summary": mp[a]["summary"], "source_id": mp[a]["canonical_id"]} for a in cited if a in mp],
            "missed_evidence_probability": jev.get("missed_evidence_probability"), "distractor_anchor_probability": jev.get("distractor_anchor_probability"),
            "review_signal": jev.get("review"), "contract_failure": run.get("contract_failure")}


def run_verified_case(case_id: str, session, llm, jev_client=None, config: VerifierConfig = None, backend=None, early_triage: bool = False,
                      triage_config: TriageConfig = None) -> dict:
    cfg = config or VerifierConfig()
    tcfg = (triage_config or TriageConfig()) if early_triage else None
    t0 = time.time()
    run = run_case(case_id, backend or Neo4jBackend(session, case_id), llm, verifier=RuntimeVerifier(session, case_id, jev_client, cfg), extra_steps=cfg.extra_steps,
                   triage=EarlyTriage(jev_client, tcfg) if early_triage else None)
    rounds = run["verification_rounds"]
    first = rounds[0] if rounds else None
    mp = run["alias_mappings"]

    if run["contract_failure"]:
        last = {"decision": HUMAN_REVIEW, "reason": f"the agent's answer stayed invalid after its one repair: {run['contract_failure']}", "triggers": ["contract_failure"], "jev": None}
        final_decision = HUMAN_REVIEW
    else:
        last = rounds[-1]
        final_decision = last["decision"]
        if final_decision == CONTINUE:                         # cannot happen (policy never continues on round 2); fail safe
            final_decision, last = HUMAN_REVIEW, {**last, "reason": "still unresolved after the additional round"}

    early = run.get("early_triage")
    jev_tokens = sum(((r.get("jev") or {}).get("input_tokens") or 0) for r in rounds) + ((early or {}).get("input_tokens") or 0)
    agent_tokens = run["token_usage"]["total_tokens"]
    initial = run["initial_result"] if run["additional_investigation_performed"] else {"final_status": run["final_status"], "final_alias_form": run["final_alias_form"]}
    record = {
        "case_id": case_id, "created_at": datetime.now(timezone.utc).isoformat(), "config": cfg.to_dict(),
        "early_triage_used": early_triage, "early_triage_config": tcfg.to_dict() if tcfg else None,
        "early_triage": early, "triage_outcome": run.get("triage_outcome"),
        "triage_outcome_initial": ((run.get("initial_result") or {}).get("triage_outcome") if run["additional_investigation_performed"] else run.get("triage_outcome")),
        "agent_initial_result": diagnosis_view(initial.get("final_alias_form"), mp),
        "verification_rounds": [{"round": r["round"], "deterministic_checks": r["deterministic_checks"], "jev_missed_evidence": (r.get("jev") or {}).get("missed_evidence_probability"),
                                 "jev_distractor_anchor": (r.get("jev") or {}).get("distractor_anchor_probability"),
                                 "jev_review": {"label": (r.get("jev") or {}).get("review"), "probabilities": (r.get("jev") or {}).get("review_probabilities")},
                                 "jev_available": (r.get("jev") or {}).get("available"), "policy_decision": r["decision"], "reason": r["reason"], "triggers": r.get("triggers", []),
                                 "message_to_agent": r.get("message")} for r in rounds],
        "policy_decision": first["decision"] if first else HUMAN_REVIEW,
        "additional_investigation_performed": run["additional_investigation_performed"],
        "agent_final_result": diagnosis_view(run.get("final_alias_form"), mp),
        "final_policy_decision": final_decision, "final_reason": last["reason"],
        "review_packet": review_packet(final_decision, last, run) if final_decision in (HUMAN_REVIEW, PRIORITY_REVIEW) else None,
        "latency_s": round(time.time() - t0, 1),
        "cost_usd_estimate": round(agent_tokens / 1e6 * TOGETHER_USD_PER_M_TOKENS + jev_tokens / 1e6 * JEV_USD_PER_M_INPUT_TOKENS, 5),
        "cost_note": "estimate: agent tokens x Together list price + Jev input tokens x Jev list price",
        "agent_tokens": agent_tokens, "jev_input_tokens": jev_tokens, "agent_run": run,
    }
    return record


def persist(record: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"verified_{record['case_id']}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"
    record = {"run_id": run_id, **record}
    path = OUT_DIR / f"{run_id}.json"
    path.write_text(json.dumps(record, indent=1, default=str))
    with open(OUT_DIR / "index.jsonl", "a") as f:
        f.write(json.dumps({"run_id": run_id, "case_id": record["case_id"], "created_at": record["created_at"], "first_decision": record["policy_decision"],
                            "additional_investigation": record["additional_investigation_performed"], "final_decision": record["final_policy_decision"],
                            "early_triage": (record.get("early_triage") or {}).get("status"), "triage_outcome": (record.get("triage_outcome") or {}).get("outcome"),
                            "latency_s": record["latency_s"], "cost_usd_estimate": record["cost_usd_estimate"]}) + "\n")
    return path


if __name__ == "__main__":
    from agent.graph_v2.db import get_driver

    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="+")
    ap.add_argument("--early-triage", action="store_true", help="add early Jev triage guidance before the investigation (late verification always runs)")
    ap.add_argument("--cohort-check", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    pool = set(json.loads((A.PROJECT_ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json").read_text())["case_ids"])   # the 300 dev cases
    bad = [c for c in a.cases if c not in pool]
    if bad:
        raise SystemExit(f"not dev cases: {bad}. This runtime only runs the dev pool.")
    llm, drv = TogetherJSONClient(os.environ["TOGETHER_API_KEY"]), get_driver()
    for cid in a.cases:
        with drv.session() as s:
            rec = run_verified_case(cid, s, llm, early_triage=a.early_triage)
        p = persist(rec)
        tri = f" triage={(rec['early_triage'] or {}).get('status')}/{(rec['triage_outcome'] or {}).get('outcome')}" if a.early_triage else ""
        print(f"{cid}: first={rec['policy_decision']} additional={rec['additional_investigation_performed']} final={rec['final_policy_decision']}{tri} "
              f"({rec['latency_s']}s, ~${rec['cost_usd_estimate']}) -> {p.name}")
    drv.close()
