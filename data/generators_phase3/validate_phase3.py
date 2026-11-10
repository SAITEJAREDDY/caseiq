"""
Phase 3 dataset validator. Run after build_phase3.py --full completes:

    python3 validate_phase3.py

Every check either passes silently (an "OK" line) or prints one FAIL line per
violation found (capped) plus a final summary. Exit code is nonzero if any
check failed.
"""
import csv
import hashlib
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(__file__)
RAW_V1 = os.path.join(HERE, "..", "raw_v2")
PHASE2 = os.path.join(HERE, "..", "phase2")
PHASE3 = os.path.join(HERE, "..", "phase3")
P1_MANIFEST = os.path.join(HERE, ".phase1_checksums.json")
P2_MANIFEST = os.path.join(HERE, ".phase2_checksums.json")

failures = []


def read1(fn):
    with open(os.path.join(RAW_V1, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read2(fn):
    with open(os.path.join(PHASE2, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read3(fn):
    with open(os.path.join(PHASE3, fn), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check(label, bad):
    if bad:
        n = bad if isinstance(bad, int) else len(bad)
        print(f"  FAIL  {label}: {n} violation(s)" + (f", e.g. {bad[:5]}" if isinstance(bad, list) else ""))
        failures.append(label)
    else:
        print(f"  OK    {label}")


def parse_dt(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def checksum_diff(directory, manifest_path):
    with open(manifest_path) as f:
        baseline = json.load(f)
    changed = []
    for fn, expected in baseline.items():
        with open(os.path.join(directory, fn), "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        if actual != expected:
            changed.append(fn)
    return changed


def main():
    print("Checking Phase 1 and Phase 2 immutability (checksum diff)...")
    check("Phase 1 files unchanged since Phase 3 build started", checksum_diff(RAW_V1, P1_MANIFEST))
    check("Phase 2 files unchanged since Phase 3 build started", checksum_diff(PHASE2, P2_MANIFEST))

    print("\nLoading tables...")
    cases = read1("cases.csv")
    case_ids = {c["id"] for c in cases}
    case_by_id = {c["id"]: c for c in cases}
    agents = {a["id"] for a in read1("agents.csv")}
    teams = {t["id"] for t in read1("teams.csv")}
    components = {c["id"] for c in read1("components.csv")}
    products = {p["id"] for p in read1("products.csv")}
    articles = {a["id"] for a in read1("knowledge_articles.csv")}
    resolution_types = {r["id"] for r in read1("resolution_types.csv")}

    change_ids = {c["id"] for c in read2("change_events.csv")}
    change_by_id = {c["id"]: c for c in read2("change_events.csv")}
    signal_ids = {s["id"] for s in read2("case_signals.csv")}
    signal_by_id = {s["id"]: s for s in read2("case_signals.csv")}
    incident_ids = {i["id"] for i in read2("incidents.csv")}
    incident_by_id = {i["id"]: i for i in read2("incidents.csv")}
    config_by_id = {c["id"]: c for c in read2("configuration_snapshots.csv")}
    p2gt_by_case = {r["case_id"]: r for r in read2("phase2_ground_truth.csv")}

    triage = read3("triage_history.csv")
    routing = read3("routing_history.csv")
    assignment = read3("assignment_history.csv")
    hyps = read3("diagnostic_hypotheses.csv")
    hyp_by_id = {h["id"]: h for h in hyps}
    hev = read3("hypothesis_evidence.csv")
    eq = read3("evidence_queries.csv")
    ra = read3("resolution_attempts.csv")
    mit = read3("mitigations.csv")
    ver = read3("resolution_verification.csv")
    reopens = read3("case_reopens.csv")
    kb = read3("kb_interactions.csv")
    sim = read3("similar_case_interactions.csv")
    esc = read3("escalations.csv")
    eng = read3("engineering_engagements.csv")
    ci = read3("customer_interactions.csv")
    collab = read3("collaboration_events.csv")
    events = read3("case_lifecycle_events.csv")
    outcomes = read3("case_outcomes_phase3.csv")
    ground_truth = read3("phase3_ground_truth.csv")
    event_labels = read3("phase3_event_quality_labels.csv")
    ideal = read3("ideal_investigation_requirements.csv")

    print(f"\nRow counts: triage={len(triage):,} routing={len(routing):,} assignment={len(assignment):,} "
          f"hypotheses={len(hyps):,} hyp_evidence={len(hev):,} evidence_queries={len(eq):,} "
          f"resolution_attempts={len(ra):,} mitigations={len(mit):,} verification={len(ver):,} "
          f"reopens={len(reopens):,} kb={len(kb):,} similar_case={len(sim):,} escalations={len(esc):,} "
          f"engineering={len(eng):,} customer={len(ci):,} collaboration={len(collab):,} "
          f"lifecycle_events={len(events):,}\n")

    print("Foreign-key integrity (-> Phase 1)...")
    check("triage_history.case_id -> cases", [r["case_id"] for r in triage if r["case_id"] not in case_ids])
    check("triage_history.predicted_team_id -> teams",
          [r["case_id"] for r in triage if r["predicted_team_id"] not in teams])
    check("triage_history.predicted_component_id -> components",
          [r["case_id"] for r in triage if r["predicted_component_id"] not in components])
    check("routing_history.to_team_id -> teams", [r["case_id"] for r in routing if r["to_team_id"] not in teams])
    check("routing_history.from_team_id -> teams (when set)",
          [r["case_id"] for r in routing if r["from_team_id"] and r["from_team_id"] not in teams])
    check("assignment_history.agent_id -> agents", [r["case_id"] for r in assignment if r["agent_id"] not in agents])
    check("assignment_history.team_id -> teams", [r["case_id"] for r in assignment if r["team_id"] not in teams])
    check("diagnostic_hypotheses.suspected_component_id -> components",
          [r["id"] for r in hyps if r["suspected_component_id"] not in components])
    check("resolution_attempts.resolution_type_id -> resolution_types",
          [r["id"] for r in ra if r["resolution_type_id"] not in resolution_types])
    check("resolution_attempts.targeted_hypothesis_id -> diagnostic_hypotheses",
          [r["id"] for r in ra if r["targeted_hypothesis_id"] and r["targeted_hypothesis_id"] not in hyp_by_id])
    check("kb_interactions.article_id -> knowledge_articles", [r["id"] for r in kb if r["article_id"] not in articles])
    check("similar_case_interactions.similar_case_id -> cases",
          [r["id"] for r in sim if r["similar_case_id"] not in case_ids])
    check("collaboration_events.collaborator_team_id -> teams",
          [r["case_id"] for r in collab if r["collaborator_team_id"] not in teams])

    print("\nForeign-key integrity (-> Phase 2)...")
    bad_eq_refs = []
    for q in eq:
        if q["query_type"] == "query_recent_changes":
            for rid in q["result_ref_ids"].split(";"):
                if rid and rid not in change_ids:
                    bad_eq_refs.append(q["id"])
        elif q["query_type"] == "query_signals":
            for rid in q["result_ref_ids"].split(";"):
                if rid and rid not in signal_ids:
                    bad_eq_refs.append(q["id"])
        elif q["query_type"] == "check_active_incidents":
            for rid in q["result_ref_ids"].split(";"):
                if rid and rid not in incident_ids:
                    bad_eq_refs.append(q["id"])
    check("evidence_queries.result_ref_ids resolve into Phase 2 tables (changes/signals/incidents)", bad_eq_refs)

    print("\nCase coverage...")
    check("triage_history covers every case exactly once", set(case_ids) ^ {r["case_id"] for r in triage})
    check("case_outcomes_phase3 covers every case exactly once", set(case_ids) ^ {r["case_id"] for r in outcomes})
    check("phase3_ground_truth covers every case exactly once", set(case_ids) ^ {r["case_id"] for r in ground_truth})
    check("ideal_investigation_requirements covers every case exactly once",
          set(case_ids) ^ {r["case_id"] for r in ideal})

    print("\nTemporal consistency (no future-information leakage)...")
    bad_change_before_query = []
    for q in eq:
        if q["query_type"] != "query_recent_changes":
            continue
        q_ts = parse_dt(q["timestamp"])
        for rid in q["result_ref_ids"].split(";"):
            if rid and parse_dt(change_by_id[rid]["started_at"]) > q_ts:
                bad_change_before_query.append(q["id"])
    check("a queried change_event's started_at is on/before the query's own timestamp", bad_change_before_query)

    bad_signal_before_query = []
    for q in eq:
        if q["query_type"] != "query_signals":
            continue
        q_ts = parse_dt(q["timestamp"])
        for rid in q["result_ref_ids"].split(";"):
            if rid and parse_dt(signal_by_id[rid]["timestamp"]) > q_ts:
                bad_signal_before_query.append(q["id"])
    check("a queried signal's timestamp is on/before the query's own timestamp", bad_signal_before_query)

    bad_config_before_query = []
    for q in eq:
        if q["query_type"] != "query_configuration":
            continue
        q_ts = parse_dt(q["timestamp"])
        for rid in q["result_ref_ids"].split(";"):
            if rid and parse_dt(config_by_id[rid]["snapshot_at"]) > q_ts:
                bad_config_before_query.append(q["id"])
    check("a queried config snapshot's snapshot_at is on/before the query's own timestamp", bad_config_before_query)

    bad_incident_before_query = []
    for q in eq:
        if q["query_type"] != "check_active_incidents":
            continue
        q_ts = parse_dt(q["timestamp"])
        for rid in q["result_ref_ids"].split(";"):
            if rid and parse_dt(incident_by_id[rid]["started_at"]) > q_ts:
                bad_incident_before_query.append(q["id"])
    check("a queried incident's started_at is on/before the query's own timestamp", bad_incident_before_query)

    def events_nondecreasing(rows, key_field="case_id"):
        by_case = {}
        for r in rows:
            by_case.setdefault(r[key_field], []).append(r)
        bad = []
        for cid, rs in by_case.items():
            rs_sorted = sorted(rs, key=lambda r: int(r["seq"]))
            ts = [parse_dt(r["timestamp"]) for r in rs_sorted]
            if any(ts[i] > ts[i + 1] for i in range(len(ts) - 1)):
                bad.append(cid)
        return bad

    check("case_lifecycle_events timestamps are non-decreasing within each case", events_nondecreasing(events))

    bad_ver_before_ra = []
    ra_by_case, ver_by_case = {}, {}
    for r in ra:
        ra_by_case.setdefault(r["case_id"], []).append(r)
    for r in ver:
        ver_by_case.setdefault(r["case_id"], []).append(r)
    for cid, vrows in ver_by_case.items():
        arows = sorted(ra_by_case.get(cid, []), key=lambda r: int(r["seq"]))
        if not arows:
            bad_ver_before_ra.append(cid)
            continue
    check("every resolution_verification row's case has at least one resolution_attempts row", bad_ver_before_ra)

    bad_reopen_order = []
    for r in reopens:
        cid = r["case_id"]
        arows = sorted(ra_by_case.get(cid, []), key=lambda x: int(x["seq"]))
        if not arows:
            bad_reopen_order.append(cid)
            continue
        first_attempt_ts = parse_dt(arows[0]["timestamp"])
        if parse_dt(r["reopen_timestamp"]) < first_attempt_ts:
            bad_reopen_order.append(cid)
    check("case_reopens occur after at least one prior resolution attempt", bad_reopen_order)

    print("\nConsistency with fixed Phase 1/2 truth...")
    esc_cases = {r["case_id"] for r in esc}
    bad_escalation_flag = [c["id"] for c in cases if (c["gt_escalated"] == "true") != (c["id"] in esc_cases)]
    check("escalations.csv presence exactly matches cases.gt_escalated", bad_escalation_flag)

    reopen_cases = {r["case_id"] for r in reopens}
    bad_reopen_flag = [c["id"] for c in cases if (c["gt_reopened"] == "true") != (c["id"] in reopen_cases)]
    check("case_reopens.csv presence exactly matches cases.gt_reopened", bad_reopen_flag)

    final_ra_by_case = {}
    for r in ra:
        cid = r["case_id"]
        if cid not in final_ra_by_case or int(r["seq"]) > int(final_ra_by_case[cid]["seq"]):
            final_ra_by_case[cid] = r
    bad_final_resolution = []
    for c in cases:
        if c["status"] == "open":
            continue
        final = final_ra_by_case.get(c["id"])
        if not final or final["resolution_type_id"] != c["gt_resolution_type_id"]:
            bad_final_resolution.append(c["id"])
    check("final resolution_attempts row's resolution_type_id matches cases.gt_resolution_type_id", bad_final_resolution)

    bad_final_hypothesis = []
    hyps_by_case = {}
    for h in hyps:
        hyps_by_case.setdefault(h["case_id"], []).append(h)
    root_cause_id_to_name = {r["id"]: r["name"] for r in read1("root_causes.csv")}
    for c in cases:
        confirmed = [h for h in hyps_by_case.get(c["id"], []) if h["disposition"] == "confirmed"]
        if c["status"] == "open":
            continue
        true_name = root_cause_id_to_name[c["gt_root_cause_id"]]
        if not confirmed or confirmed[-1]["suspected_root_cause_name"] != true_name:
            bad_final_hypothesis.append(c["id"])
    check("every non-open case has a confirmed hypothesis matching cases.gt_root_cause_id", bad_final_hypothesis)

    bad_open_has_resolution = [c["id"] for c in cases if c["status"] == "open" and c["id"] in final_ra_by_case]
    check("open-status cases have zero resolution_attempts rows", bad_open_has_resolution)

    print("\nObservable/hidden separation...")
    observable_files = ["triage_history", "routing_history", "assignment_history", "diagnostic_hypotheses",
                         "hypothesis_evidence", "evidence_queries", "resolution_attempts", "mitigations",
                         "resolution_verification", "case_reopens", "kb_interactions",
                         "similar_case_interactions", "escalations", "engineering_engagements",
                         "customer_interactions", "collaboration_events", "case_lifecycle_events",
                         "case_outcomes_phase3"]
    banned_substrings = ["gt_", "_correct", "_warranted", "_appropriate", "mistake", "_missed", "efficiency",
                          "misleading", "_relevant"]
    leaked = []
    for name in observable_files:
        rows = read3(f"{name}.csv")
        cols = set(rows[0].keys()) if rows else set()
        for col in cols:
            if any(b in col for b in banned_substrings):
                leaked.append(f"{name}.{col}")
    check("no observable Phase 3 file has a hidden-judgment-shaped column", leaked)

    print(f"\n{'=' * 60}")
    if failures:
        print(f"VALIDATION FAILED: {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED: all checks OK.")


if __name__ == "__main__":
    main()
