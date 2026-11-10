"""Print one verified run as a readable end-to-end trace.   python3 -m agent.runtime_verifier.show CS01031"""
import glob
import json
import sys

from agent.runtime_verifier.run import OUT_DIR

pct = lambda x: "n/a" if x is None else f"{x * 100:.0f}%"


def show(rec: dict) -> str:
    run, mp, L = rec["agent_run"], rec["agent_run"]["alias_mappings"], []
    ctx = next(s["result_summary"] for s in run["trace_steps"] if s["tool_name"] == "get_case_context")
    L += [f"CASE {rec['case_id']}: {ctx['title']}", f"  {ctx['description'][:220]}", "", "AGENT (existing tools, time-gated, validated)"]
    for s in run["trace_steps"]:
        args = ", ".join(f"{k}={(mp.get(v) or {}).get('display_name') or v}" for k, v in (s.get("args_alias") or {}).items())
        n_ev = len([1 for e in mp.values() if e["kind"] in ("EVIDENCE", "CHANGE", "INCIDENT") and e["first_observed_step"] == s["step"]])
        L.append(f"  step {s['step']:>2} {s['tool_name']}({args}) {s['status']}" + (f"  +{n_ev} evidence" if n_ev else ""))
    def dx(d):
        if not d:
            return "  (none)"
        sel = "; ".join(f"{k}={v['name']}" for k, v in d["selections"].items() if v) or "no selection (abstained)"
        return f"  {d['status']}, confidence {d['confidence']}, evidence {d['evidence_sufficiency']}. {sel}"
    L += ["", "PROPOSED DIAGNOSIS", dx(rec["agent_initial_result"])]
    for rd in rec["verification_rounds"]:
        L += ["", f"VERIFICATION PASS {rd['round']}"]
        L += [f"  {c['id']} {c['name']}: {'PASS' if c['passed'] else 'FAIL'}{'' if c['applicable'] else ' (n/a)'} - {c['detail'][:110]}" for k, c in rd["deterministic_checks"].items() if k != "all_passed"]
        L += [f"  Jev: missed evidence {pct(rd['jev_missed_evidence'])}, distractor anchoring {pct(rd['jev_distractor_anchor'])}, review {rd['jev_review']['label']} {rd['jev_review']['probabilities']}",
              f"  POLICY -> {rd['policy_decision']}: {rd['reason']}"]
        if rd.get("message_to_agent"):
            L += ["  message sent to the agent:"] + ["    | " + x for x in rd["message_to_agent"].splitlines()]
    if rec["additional_investigation_performed"]:
        L += ["", "FINAL DIAGNOSIS (after the one additional round)", dx(rec["agent_final_result"])]
    L += ["", f"FINAL ACTION: {rec['final_policy_decision']} - {rec['final_reason']}", f"  {rec['latency_s']}s, about ${rec['cost_usd_estimate']}"]
    if rec.get("review_packet"):
        p = rec["review_packet"]
        L += ["", "REVIEW PACKET", f"  decision {p['decision']}; missed-evidence {pct(p['missed_evidence_probability'])}; distractor {pct(p['distractor_anchor_probability'])}; key evidence: {len(p['key_evidence'])} item(s)"]
    return "\n".join(L)


if __name__ == "__main__":
    for cid in sys.argv[1:]:
        f = sorted(glob.glob(str(OUT_DIR / f"verified_{cid}_*.json")))[-1]
        print(show(json.load(open(f))), "\n" + "=" * 100)
