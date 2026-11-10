"""
Phase 3 dataset orchestrator.

Usage:
    python3 build_phase3.py --full              # full run, all 25,000 cases
    python3 build_phase3.py --pilot 500          # small run, with narratives
    python3 build_phase3.py --skip-narratives    # everything except the LLM narrative stage
    python3 build_phase3.py --full --skip-narratives --investigation-only  # dev/testing

Order: load Phase 1 (raw_v2, read-only) + Phase 2 (phase2, read-only) ->
simulate every case's investigation (generate_investigation.py, no LLM) ->
derive case-level outcomes + hidden ground truth + event quality labels +
ideal-investigation envelope purely from that observable timeline
(derive_outcomes.py) -> narrative fill via Together AI for
escalations.summary / engineering_engagements.finding_summary
(narratives_phase3.py, the only LLM-touching stage) -> write every CSV to
../phase3/.
"""
import argparse
import os
import random
import sys
import time

import derive_outcomes as do
import generate_investigation as gi
import load_phase12 as lp
from csv_io3 import write_csv

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generators"))
import llm_client  # noqa: E402
from llm_client import TogetherAuthError  # noqa: E402

PHASE3_SEED = 2027

HEADERS = {
    "triage_history": ["case_id", "predicted_product_id", "predicted_component_id", "predicted_category_id",
                        "predicted_subcategory_id", "predicted_severity", "predicted_team_id", "confidence",
                        "required_human_confirmation", "timestamp", "event_id"],
    "routing_history": ["case_id", "seq", "from_team_id", "to_team_id", "timestamp", "reason_code",
                         "alternative_teams_considered", "event_id"],
    "assignment_history": ["case_id", "seq", "agent_id", "team_id", "timestamp", "reason_code",
                            "skill_match_score", "accepted", "event_id"],
    "diagnostic_hypotheses": ["id", "case_id", "seq", "suspected_component_id", "suspected_category_id",
                               "suspected_root_cause_name", "confidence_initial", "confidence_current",
                               "disposition", "created_at", "disposition_at", "event_id", "disposition_event_id"],
    "hypothesis_evidence": ["id", "hypothesis_id", "case_id", "evidence_type", "evidence_ref_id", "support_type",
                             "confidence_after", "timestamp", "event_id"],
    "evidence_queries": ["id", "case_id", "seq", "query_type", "timestamp", "target_ref", "result_ref_ids",
                          "result_count", "event_id"],
    "resolution_attempts": ["id", "case_id", "seq", "action", "resolution_type_id", "timestamp", "agent_id",
                             "team_id", "targeted_hypothesis_id", "result", "is_temporary", "is_permanent",
                             "human_approval_flagged", "alternatives_considered", "event_id"],
    "mitigations": ["id", "case_id", "resolution_attempt_id", "timestamp", "description", "event_id"],
    "resolution_verification": ["id", "case_id", "verification_type", "timestamp", "result", "event_id"],
    "case_reopens": ["id", "case_id", "reopen_timestamp", "reason_code", "prior_resolution_event_id", "event_id"],
    "kb_interactions": ["id", "case_id", "seq", "article_id", "interaction_type", "timestamp", "event_id"],
    "similar_case_interactions": ["id", "case_id", "seq", "similar_case_id", "similarity_score", "opened",
                                   "timestamp", "event_id"],
    "escalations": ["id", "case_id", "escalation_type", "from_team_id", "to_team_id", "timestamp", "trigger_code",
                     "summary", "event_id"],
    "engineering_engagements": ["id", "case_id", "activity_type", "timestamp", "finding_summary", "event_id"],
    "customer_interactions": ["id", "case_id", "seq", "interaction_type", "timestamp", "requested_info",
                               "response_delay_hours", "event_id"],
    "collaboration_events": ["case_id", "collaborator_team_id", "collaboration_type", "timestamp", "event_id"],
    "case_lifecycle_events": ["case_id", "seq", "event_id", "event_type", "timestamp", "actor_type", "actor_id",
                               "ref_table", "ref_id", "note"],
}

OUTCOME_HEADERS = [
    "case_id", "is_resolved", "first_touch_resolution", "num_routing_transitions", "num_agents_involved",
    "num_hypotheses", "num_evidence_queries", "num_kb_interactions", "num_similar_case_interactions",
    "num_resolution_attempts", "num_failed_attempts", "num_collaboration_events", "escalated", "num_escalations",
    "engineering_engaged", "reopened", "time_to_triage_minutes",
    "time_to_diagnosis_hours", "time_to_mitigation_hours", "time_to_resolution_hours", "sla_outcome",
]
GROUND_TRUTH_HEADERS = [
    "case_id", "initial_routing_correct", "eventual_routing_correct", "diagnosis_matches_truth",
    "causal_change_identified", "causal_signal_identified", "critical_evidence_ids", "critical_evidence_missed",
    "escalation_warranted", "escalation_occurred", "investigation_efficiency_label", "sla_outcome",
    "expected_confidence_band", "actual_root_cause_name", "time_to_correct_team_hours",
]
EVENT_LABEL_HEADERS = ["event_id", "case_id", "label_name", "label_value"]
IDEAL_HEADERS = ["case_id", "required_evidence_types", "correct_routing_team_id", "correct_hypothesis_root_cause",
                  "key_decision_points", "appropriate_remediation_class"]


def _write_all(tables):
    for name, headers in HEADERS.items():
        write_csv(f"{name}.csv", tables[name], headers)


def _escalation_context(tables, d):
    hyps_by_case = {}
    for h in tables["diagnostic_hypotheses"]:
        hyps_by_case.setdefault(h["case_id"], []).append(h)
    case_by_id = d["case_by_id"]
    ctx = {}
    for e in tables["escalations"]:
        case = case_by_id[e["case_id"]]
        hyps = hyps_by_case.get(e["case_id"], [])
        confirmed = [h for h in hyps if h["disposition"] == "confirmed"]
        leading = confirmed[-1] if confirmed else (hyps[-1] if hyps else None)
        ctx[e["id"]] = {
            "severity": case["gt_severity"],
            "suspected_root_cause": leading["suspected_root_cause_name"] if leading else "",
        }
    return ctx


def _engineering_context(tables, d):
    case_by_id = d["case_by_id"]
    ctx = {}
    for eng in tables["engineering_engagements"]:
        case = case_by_id[eng["case_id"]]
        ctx[eng["id"]] = {
            "root_cause": d["root_cause_id_to_name"][case["gt_root_cause_id"]],
            "component": d["component_id_to_name"].get(case["gt_component_id"], ""),
            "product": d["product_id_to_name"].get(case["gt_product_id"], ""),
        }
    return ctx


def run(n_cases=None, do_narratives=True, stop_after=None, seed=PHASE3_SEED):
    t0 = time.time()
    rng = random.Random(seed)

    print("Loading Phase 1 + Phase 2 (read-only)...")
    d = lp.load_all()
    cases = d["cases"]
    if n_cases:
        cases = cases[:n_cases]
    print(f"  {len(cases):,} cases loaded in {time.time() - t0:.1f}s\n")

    print(f"Simulating investigations for {len(cases):,} cases...")
    t1 = time.time()
    tables = gi.build_investigations(rng, cases, d)
    for name in HEADERS:
        print(f"  {name:<32} {len(tables[name]):>9,} rows")
    print(f"  done in {time.time() - t1:.1f}s\n")
    if stop_after == "investigation":
        _write_all(tables)
        return locals()

    print("Deriving case outcomes + hidden ground truth + event labels + ideal envelope...")
    t2 = time.time()
    case_outcomes, ground_truth, event_labels, ideal_requirements = do.derive(d, tables)
    print(f"  case_outcomes_phase3               {len(case_outcomes):>9,} rows")
    print(f"  phase3_ground_truth                 {len(ground_truth):>9,} rows")
    print(f"  phase3_event_quality_labels          {len(event_labels):>9,} rows")
    print(f"  ideal_investigation_requirements     {len(ideal_requirements):>9,} rows")
    print(f"  done in {time.time() - t2:.1f}s\n")

    _write_all(tables)
    write_csv("case_outcomes_phase3.csv", case_outcomes, OUTCOME_HEADERS)
    write_csv("phase3_ground_truth.csv", ground_truth, GROUND_TRUTH_HEADERS)
    write_csv("phase3_event_quality_labels.csv", event_labels, EVENT_LABEL_HEADERS)
    write_csv("ideal_investigation_requirements.csv", ideal_requirements, IDEAL_HEADERS)

    if do_narratives:
        print("\nGenerating narrative text via Together AI (escalations.summary, "
              "engineering_engagements.finding_summary)...")
        t3 = time.time()
        import narratives_phase3 as np3
        try:
            np3.fill_escalation_summaries(tables["escalations"], _escalation_context(tables, d), seed=seed)
            np3.fill_engineering_findings(tables["engineering_engagements"], _engineering_context(tables, d),
                                          seed=seed)
        except TogetherAuthError as e:
            print(f"\n  ERROR: {e}")
            sys.exit(1)
        llm_client.print_usage_summary()
        write_csv("escalations.csv", tables["escalations"], HEADERS["escalations"])
        write_csv("engineering_engagements.csv", tables["engineering_engagements"],
                  HEADERS["engineering_engagements"])
        print(f"  done in {time.time() - t3:.1f}s\n")
    else:
        print("\nSkipping narrative generation; using template placeholders for summary/finding text.\n")
        import narratives_phase3 as np3
        np3.template_fallback_escalations(tables["escalations"])
        np3.template_fallback_engineering(tables["engineering_engagements"])
        write_csv("escalations.csv", tables["escalations"], HEADERS["escalations"])
        write_csv("engineering_engagements.csv", tables["engineering_engagements"],
                  HEADERS["engineering_engagements"])

    print(f"\nTotal Phase 3 build time: {time.time() - t0:.1f}s")
    return locals()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", type=int, default=0, help="Run on a small subset of N cases, with narratives")
    parser.add_argument("--full", action="store_true", help="Run the full build across all 25,000 cases")
    parser.add_argument("--skip-narratives", action="store_true", help="Skip LLM calls, use template placeholders")
    parser.add_argument("--investigation-only", action="store_true",
                         help="Stop after the investigation-simulation stage (dev/testing)")
    args = parser.parse_args()

    stop_after = "investigation" if args.investigation_only else None

    if args.pilot:
        run(n_cases=args.pilot, do_narratives=True, stop_after=stop_after)
    elif args.full:
        run(n_cases=None, do_narratives=not args.skip_narratives, stop_after=stop_after)
    else:
        parser.print_help()
