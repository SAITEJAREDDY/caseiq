"""
Phase 3 core simulator. For every Phase 1 case, walks forward in simulated
time from its own `created_date` and emits every OBSERVABLE investigation-
history row: triage, routing, assignment, hypotheses + evidence queries,
resolution attempts, mitigations, verification, reopens, KB/similar-case
interactions, escalations, engineering engagements, customer interactions,
collaboration events — plus the `case_lifecycle_events` spine that orders
them.

No hidden/judgment column is ever written here. Every branch point is decided
by comparing the CURRENT simulated focus against Phase 1/2 ground truth
in-memory (so the simulation can tell whether it's "on track"), but the fields
actually written out are only ever what a real investigator would have seen:
a predicted category, a query result, a hypothesis's own stated confidence —
never a "was this correct" label. Those live in derive_outcomes.py, computed
afterward by diffing these observable rows against the same ground truth.

Every new timestamp is an offset from the case's own created_date/
gt_resolution_duration_hours (both already fixed by Phase 1) — there is no
ambient/background generation step here, so unlike Phase 2 there is no need
for a fixed "now" anchor; the wall-clock bug class Phase 2 hit structurally
cannot recur.
"""
from datetime import timedelta

import phase3_taxonomy as pt

MINUTE = timedelta(minutes=1)


def _weighted_choice(rng, pairs):
    """pairs: [(item, weight), ...] with weight > 0 for at least one item."""
    items = [p[0] for p in pairs]
    weights = [max(p[1], 1e-6) for p in pairs]
    return rng.choices(items, weights=weights)[0]


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


class _Case3:
    """Per-case scratch state threaded through one case's simulation."""

    def __init__(self, case, d, cat_id_to_key, rng):
        self.case = case
        self.d = d
        self.cat_id_to_key = cat_id_to_key
        self.rng = rng
        self.seq = 0
        self.events = []  # case_lifecycle_events rows
        self.t_created = case["created_date"] + timedelta(
            hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        if case["is_open"]:
            sev_hours = {"Sev1": (2, 30), "Sev2": (2, 60), "Sev3": (4, 120), "Sev4": (8, 200)}
            lo, hi = sev_hours.get(case["gt_severity"], (4, 96))
            self.window_hours = rng.uniform(lo, hi)
            self.t_end = self.t_created + timedelta(hours=self.window_hours)
        else:
            self.window_hours = case["gt_resolution_duration_hours"]
            self.t_end = self.t_created + timedelta(hours=self.window_hours)
        self.clock = self.t_created

    def advance(self, minutes_lo, minutes_hi):
        step = self.rng.uniform(minutes_lo, minutes_hi)
        self.clock = min(self.clock + timedelta(minutes=step), self.t_end)
        return self.clock

    def advance_hours(self, hours_lo, hours_hi, cap=None):
        step = self.rng.uniform(hours_lo, hours_hi)
        ceiling = cap if cap is not None else self.t_end
        self.clock = min(self.clock + timedelta(hours=step), ceiling)
        return self.clock

    def emit(self, event_type, actor_type, actor_id, ref_table, ref_id, note=""):
        self.seq += 1
        event_id = f"{self.case['id']}-EV{self.seq:03d}"
        self.events.append({
            "case_id": self.case["id"], "seq": self.seq, "event_id": event_id,
            "event_type": event_type, "timestamp": self.clock.strftime("%Y-%m-%d %H:%M:%S"),
            "actor_type": actor_type, "actor_id": actor_id or "",
            "ref_table": ref_table, "ref_id": ref_id or "", "note": note,
        })
        return event_id


class _Counters:
    def __init__(self):
        self.hyp = 0
        self.hev = 0
        self.eq = 0
        self.ra = 0
        self.mit = 0
        self.ver = 0
        self.reopen = 0
        self.kb = 0
        self.sim = 0
        self.esc = 0
        self.eng = 0
        self.ci = 0

    def next(self, name):
        setattr(self, name, getattr(self, name) + 1)
        return getattr(self, name)


# ── Triage ──────────────────────────────────────────────────────────────────

def _predicted_subcategory_and_category(rng, case, d):
    symptom_ids = d["case_symptom_ids"].get(case["id"], [])
    candidates = {}
    for sym in symptom_ids:
        for subcat, weight in d["subcats_by_symptom"].get(sym, []):
            candidates[subcat] = candidates.get(subcat, 0) + weight
    true_subcat = case["gt_issue_subcategory_id"]
    if not candidates:
        return true_subcat, case["gt_issue_category_id"], 1.0
    total = sum(candidates.values())
    accuracy_target = pt.TRIAGE_ACCURACY_BY_ARCHETYPE.get(case["gt_difficulty_archetype"], 0.5)
    wrong_pool = [(s, w) for s, w in candidates.items() if s != true_subcat]
    if rng.random() < accuracy_target or not wrong_pool:
        predicted_subcat = true_subcat
        confidence = _clip(candidates.get(true_subcat, total * 0.6) / total, 0.55, 0.97)
    else:
        predicted_subcat = _weighted_choice(rng, wrong_pool)
        confidence = _clip(dict(wrong_pool)[predicted_subcat] / total, 0.2, 0.55)
    predicted_cat = d["subcat_id_to_cat_id"][predicted_subcat]
    return predicted_subcat, predicted_cat, confidence


def _predicted_component(rng, case, d, predicted_product, predicted_category):
    pool_for_case = d["case_component_ids"].get(case["id"], [case["gt_component_id"]])
    category_ok = predicted_category == case["gt_issue_category_id"]
    product_ok = predicted_product == case["gt_product_id"]
    if category_ok and product_ok:
        return rng.choice(pool_for_case)
    product_pool = d["components_by_product"].get(predicted_product, [])
    if not product_pool:
        return case["gt_component_id"]
    weights = [d["component_category_weights"].get(cid, {}).get(predicted_category, 0.15)
               for cid in product_pool]
    return _weighted_choice(rng, list(zip(product_pool, weights)))


def _predicted_team_for(d, component_id, product_id, subcategory_id):
    # subcategory_id is checked first: Phase 1 verified to derive gt_primary_
    # team_id directly from issue_subcategory_teams.csv's weighted primary
    # team for gt_issue_subcategory_id (100% reproduction rate on a 3,000-case
    # sample), whereas component/product-keyed teams only agree ~51%/32% of
    # the time — using them first would make even a *correct* triage guess
    # look like a routing mistake. component/product are real fallbacks only
    # for when no subcategory signal is available.
    for pool_key, lookup in (("subcategory", d["teams_by_subcategory"]), ("component", d["teams_by_component"]),
                              ("product", d["teams_by_product"])):
        key = {"component": component_id, "product": product_id, "subcategory": subcategory_id}[pool_key]
        pool = lookup.get(key, [])
        primary = [(t, w) for t, role, w in pool if role == "primary"]
        if primary:
            return primary[0][0] if len(primary) == 1 else _weighted_choice_static(primary), pool
    return None, []


def _weighted_choice_static(pairs):
    return max(pairs, key=lambda p: p[1])[0]


def _run_triage(c3, counters):
    case, d, rng = c3.case, c3.d, c3.rng
    predicted_product = case["product_reported_id"]
    predicted_subcat, predicted_cat, confidence = _predicted_subcategory_and_category(rng, case, d)
    predicted_component = _predicted_component(rng, case, d, predicted_product, predicted_cat)
    team, team_pool = _predicted_team_for(d, predicted_component, predicted_product, predicted_subcat)
    if team is None:
        team = case["gt_primary_team_id"]
    sev_pool = pt.PRIORITY_TO_SEVERITY_GUESS.get(case["priority"], [(case["gt_severity"], 1)])
    predicted_severity = _weighted_choice(rng, sev_pool)
    required_human_confirmation = confidence < 0.55 or predicted_severity in ("Sev1", "Sev2")

    c3.emit("case_created", "customer", case["customer_id"], "cases", case["id"])
    c3.advance(2, 20)
    event_id = c3.emit("triage_completed", "system", "triage_classifier", "triage_history", case["id"])
    row = {
        "case_id": case["id"], "predicted_product_id": predicted_product,
        "predicted_component_id": predicted_component, "predicted_category_id": predicted_cat,
        "predicted_subcategory_id": predicted_subcat, "predicted_severity": predicted_severity,
        "predicted_team_id": team, "confidence": round(confidence, 3),
        "required_human_confirmation": str(required_human_confirmation).lower(),
        "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "event_id": event_id,
    }
    return row, predicted_product, predicted_component, predicted_cat, predicted_subcat, team, team_pool


# ── Routing + assignment ───────────────────────────────────────────────────

def _agent_score(d, agent_id, team_id, category_id, component_id, product_id, required_skills):
    skill_ranks = d["agent_skill_rank"].get(agent_id, {})
    skill_score = sum(skill_ranks.get(sk, 0) for sk in required_skills) + 0.5
    exp = d["agent_category_experience"].get(agent_id, {}).get(category_id, 0)
    exp_score = min(exp, 30) / 6.0
    expertise_bonus = (2.0 if component_id in d["agent_component_set"].get(agent_id, set()) else 0.0) + \
                       (1.0 if product_id in d["agent_product_set"].get(agent_id, set()) else 0.0)
    utilization = d["utilization_by_agent"].get(agent_id, 70.0)
    availability_score = max(0.2, (100 - utilization) / 20.0)
    return 0.5 + skill_score + exp_score + expertise_bonus + availability_score


def _pick_agent(rng, d, team_id, category_id, component_id, product_id, required_skills, exclude=None):
    roster = [a for a in d["agents_by_team"].get(team_id, []) if a != exclude]
    if not roster:
        return None, 0.0
    scored = [(a, _agent_score(d, a, team_id, category_id, component_id, product_id, required_skills))
              for a in roster]
    top = sorted(scored, key=lambda t: -t[1])[:min(5, len(scored))]
    agent = _weighted_choice(rng, top)
    score = dict(scored)[agent]
    return agent, score


def _route(c3, counters, routing_rows, assignment_rows, seq_holder, to_team, reason_code, alt_teams,
           category_id, component_id, product_id, required_skills, exclude_agent=None):
    case, d, rng = c3.case, c3.d, c3.rng
    seq_holder[0] += 1
    from_team = seq_holder[1]
    c3.advance(1, 12)
    ev = c3.emit("team_assigned" if seq_holder[0] == 1 else "case_reassigned", "system", "router",
                 "routing_history", f"{case['id']}-R{seq_holder[0]}")
    routing_rows.append({
        "case_id": case["id"], "seq": seq_holder[0], "from_team_id": from_team or "",
        "to_team_id": to_team, "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"),
        "reason_code": reason_code, "alternative_teams_considered": ";".join(alt_teams),
        "event_id": ev,
    })
    seq_holder[1] = to_team

    c3.advance(1, 20)
    agent, score = _pick_agent(rng, d, to_team, category_id, component_id, product_id, required_skills,
                                exclude=exclude_agent)
    if agent is None:
        agent = case["gt_assigned_agent_id"]
        score = 1.0
    a_ev = c3.emit("agent_assigned", "system", "assignment_engine", "assignment_history",
                   f"{case['id']}-A{seq_holder[0]}")
    a_reason = "initial_assignment" if seq_holder[0] == 1 else (
        "escalation_reassignment" if reason_code == "escalation_driven" else "reassignment_team_change")
    assignment_rows.append({
        "case_id": case["id"], "seq": seq_holder[0], "agent_id": agent, "team_id": to_team,
        "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "reason_code": a_reason,
        "skill_match_score": round(score, 2), "accepted": "true", "event_id": a_ev,
    })
    return agent


# ── Evidence queries + hypothesis loop ─────────────────────────────────────

def _root_cause_guess_for_subcategory(rng, d, subcategory_id):
    pool = d["root_causes_by_subcategory"].get(subcategory_id, [])
    if not pool:
        return "unknown"
    rc_id = _weighted_choice(rng, pool)
    return d["root_cause_id_to_name"][rc_id]


def _run_query(c3, query_type, target_component, discovered):
    """Reveals whatever Phase 2 rows already exist for this case+component+
    query type. Only ever returns what generate_evidence.py/generate_changes.py
    actually generated — never invents a result."""
    case, d = c3.case, c3.d
    c3.advance(3, 25)
    result_ids, found = [], False
    if query_type == "get_customer_deployment":
        found = True
    elif query_type == "query_telemetry":
        rows = [t for t in d["telemetry_by_case"].get(case["id"], []) if t["component_id"] == target_component]
        result_ids = [f"{r['metric_code']}@{r['timestamp'].strftime('%H:%M')}" for r in rows[:6]]
        found = any(r["is_anomalous"] == "true" for r in rows)
        if found:
            discovered["telemetry_anomaly_components"].add(target_component)
    elif query_type == "query_signals":
        rows = [s for s in d["signals_by_case"].get(case["id"], []) if s["component_id"] == target_component]
        result_ids = [r["id"] for r in rows]
        found = len(rows) > 0
        discovered["signals"].update(result_ids)
    elif query_type == "query_configuration":
        rows = [s for s in d["config_snapshots_by_case"].get(case["id"], [])
                if s["component_id"] == target_component and s["snapshot_at"] <= c3.clock]
        result_ids = [r["id"] for r in rows]
        found = len(rows) > 0
    elif query_type == "query_recent_changes":
        rows = [ch for ch in d["change_events_by_case"].get(case["id"], [])
                if ch["component_id"] == target_component and ch["started_at"] <= c3.clock]
        result_ids = [r["id"] for r in rows]
        found = len(rows) > 0
        discovered["changes"].update(result_ids)
    elif query_type == "query_dependency_graph":
        deps = d["dependencies_by_component"].get(target_component, [])
        result_ids = [dep_id for dep_id, _w in deps]
        found = len(deps) > 0
        if found:
            discovered["dependency_known"] = True
    elif query_type == "check_active_incidents":
        info = d["incident_case_by_case"].get(case["id"])
        if info:
            inc = d["incident_by_id"][info["incident_id"]]
            if inc["started_at"] <= c3.clock:
                result_ids = [info["incident_id"]]
                found = True
    return result_ids, found


def _evidence_matches_truth(discovered, p2gt, case, target_component, dependency_flavored):
    """A stop is genuinely confirmed only once evidence tying it specifically
    to the TRUE origin has been seen. generate_changes.py always attaches the
    causal change_event to the visible gt_component_id, even for dependency-
    flavored root causes whose symptom evidence (telemetry/signals) lives one
    hop away on causal_component_id — so for those root causes, merely
    finding "a change happened on the visible service" is not, by itself,
    proof the investigation has reached the true origin; it must also find
    the origin-side symptom evidence there."""
    causal_change_id = p2gt.get("causal_change_id") or ""
    causal_signal_ids = {s for s in (p2gt.get("causal_signal_ids") or "").split(";") if s}
    causal_component = p2gt.get("causal_component_id") or case["gt_component_id"]
    has_signal = bool(causal_signal_ids & discovered["signals"]) and target_component == causal_component
    has_telemetry = target_component == causal_component and causal_component in discovered["telemetry_anomaly_components"]
    if dependency_flavored:
        has_change = False  # the change lives on gt_component_id, not proof of the origin by itself
    else:
        has_change = bool(causal_change_id) and causal_change_id in discovered["changes"] and \
            target_component == case["gt_component_id"]
    return has_change or has_signal or has_telemetry


def _new_hypothesis_target_sequence(case, p2gt, predicted_component, predicted_cat, dependency_flavored):
    """The plan of hypothesis 'stops' this case will walk through before
    forced convergence, derived purely from how the initial guess compares to
    fixed truth — never randomly chosen apart from that comparison."""
    stops = [(predicted_component, predicted_cat)]
    category_ok = predicted_cat == case["gt_issue_category_id"]
    component_ok = predicted_component == case["gt_component_id"]
    if not (category_ok and component_ok):
        stops.append((case["gt_component_id"], case["gt_issue_category_id"]))
    causal_component = p2gt.get("causal_component_id") or case["gt_component_id"]
    if dependency_flavored and causal_component != case["gt_component_id"]:
        stops.append((causal_component, case["gt_issue_category_id"]))
    # de-dupe consecutive identical stops (e.g. guess already == truth)
    deduped = [stops[0]]
    for s in stops[1:]:
        if s != deduped[-1]:
            deduped.append(s)
    return deduped


def _run_hypothesis_loop(c3, counters, d, cat_id_to_key, hyp_rows, hev_rows, eq_rows, routing_rows,
                          assignment_rows, seq_holder, current_agent, extra_rounds, terminal_ok):
    """Returns (confirmed_hypothesis_id, confirmed, current_agent, current_team,
    final_target_component, final_target_category)."""
    case, rng = c3.case, c3.rng
    p2gt = d["p2gt_by_case"][case["id"]]
    root_cause_name = d["root_cause_id_to_name"][case["gt_root_cause_id"]]
    pattern = et_pattern(root_cause_name)
    dependency_flavored = bool(pattern and pattern.get("dependency_flavored"))

    triage = c3.triage_result
    stops = _new_hypothesis_target_sequence(case, p2gt, triage["predicted_component"], triage["predicted_cat"],
                                             dependency_flavored)
    if extra_rounds and len(stops) == 1:
        stops = stops + [stops[-1]]  # thin-evidence cases get a re-verification round even if guess was right

    discovered = {"changes": set(), "signals": set(), "telemetry_anomaly_components": set(), "dependency_known": False}
    confirmed_id, confirmed = None, False
    current_team = seq_holder[1]
    final_target_component, final_target_cat = stops[-1]

    for i, (target_component, target_cat) in enumerate(stops):
        is_last = i == len(stops) - 1
        hyp_id = f"HYP{counters.next('hyp'):07d}"
        target_key = cat_id_to_key.get(target_cat, "UNKNOWN")
        true_origin_component = p2gt.get("causal_component_id") or case["gt_component_id"]
        if target_cat == case["gt_issue_category_id"] and target_component == true_origin_component:
            suspected_rc_name = root_cause_name
        else:
            subcat_guess = case["gt_issue_subcategory_id"] if target_cat == case["gt_issue_category_id"] else triage["predicted_subcat"]
            suspected_rc_name = _root_cause_guess_for_subcategory(rng, d, subcat_guess)
        conf_initial = round(rng.uniform(0.3, 0.6) if i == 0 else rng.uniform(0.25, 0.5), 2)

        # Reassignment if this stop's primary team differs from current team.
        target_team, team_pool = _predicted_team_for(d, target_component, case["gt_product_id"], case["gt_issue_subcategory_id"])
        if target_team and target_team != current_team and i > 0:
            alt = [t for t, _r, _w in team_pool if t != target_team][:3]
            reason = "hypothesis_pivot" if not is_last else "hypothesis_pivot"
            current_agent = _route(c3, counters, routing_rows, assignment_rows, seq_holder, target_team, reason,
                                    alt, target_cat, target_component, case["gt_product_id"],
                                    d["case_required_skill_ids"].get(case["id"], []), exclude_agent=current_agent)
            current_team = target_team

        c3.advance(2, 15)
        created_ev = c3.emit("hypothesis_created", "agent", current_agent, "diagnostic_hypotheses", hyp_id)
        hyp_row = {
            "id": hyp_id, "case_id": case["id"], "seq": i + 1, "suspected_component_id": target_component,
            "suspected_category_id": target_cat, "suspected_root_cause_name": suspected_rc_name,
            "confidence_initial": conf_initial, "confidence_current": conf_initial,
            "disposition": "unresolved", "created_at": c3.clock.strftime("%Y-%m-%d %H:%M:%S"),
            "disposition_at": "", "event_id": created_ev, "disposition_event_id": "",
        }
        hyp_rows.append(hyp_row)

        n_queries = 2 if not is_last else 3
        profile = pt.CATEGORY_QUERY_PROFILE.get(target_key, ["query_telemetry", "query_signals"])
        confidence = conf_initial
        for qt in profile[:n_queries]:
            counters.next("eq")
            result_ids, found = _run_query(c3, qt, target_component, discovered)
            eq_ev = c3.emit("evidence_queried", "agent", current_agent, "evidence_queries", f"{case['id']}-Q{counters.eq}")
            eq_rows.append({
                "id": f"EQ{counters.eq:07d}", "case_id": case["id"], "seq": counters.eq, "query_type": qt,
                "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "target_ref": target_component,
                "result_ref_ids": ";".join(result_ids), "result_count": len(result_ids), "event_id": eq_ev,
            })
            support = "supports" if found else "contradicts"
            confidence = _clip(confidence + (0.2 if found else -0.12))
            hev_rows.append({
                "id": f"HEV{counters.next('hev'):07d}", "hypothesis_id": hyp_id, "case_id": case["id"],
                "evidence_type": pt.QUERY_TYPE_TO_EVIDENCE_TYPE.get(qt, "signal"),
                "evidence_ref_id": ";".join(result_ids) if result_ids else "none",
                "support_type": support, "confidence_after": round(confidence, 2),
                "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "event_id": eq_ev,
            })
            if _evidence_matches_truth(discovered, p2gt, case, target_component, dependency_flavored) and \
                    target_cat == case["gt_issue_category_id"]:
                break

        hyp_row["confidence_current"] = round(confidence, 2)
        matched = _evidence_matches_truth(discovered, p2gt, case, target_component, dependency_flavored) and \
            target_cat == case["gt_issue_category_id"]
        should_confirm = matched or (is_last and terminal_ok)
        c3.advance(2, 10)
        if should_confirm:
            disp_ev = c3.emit("hypothesis_confirmed", "agent", current_agent, "diagnostic_hypotheses", hyp_id)
            hyp_row["disposition"] = "confirmed"
            hyp_row["disposition_at"] = c3.clock.strftime("%Y-%m-%d %H:%M:%S")
            hyp_row["disposition_event_id"] = disp_ev
            confirmed_id, confirmed = hyp_id, True
            final_target_component, final_target_cat = target_component, target_cat
            break
        else:
            disp_type = "hypothesis_rejected" if confidence < 0.35 else "hypothesis_updated"
            disp_ev = c3.emit(disp_type, "agent", current_agent, "diagnostic_hypotheses", hyp_id)
            hyp_row["disposition"] = "rejected" if disp_type == "hypothesis_rejected" else "superseded"
            hyp_row["disposition_at"] = c3.clock.strftime("%Y-%m-%d %H:%M:%S")
            hyp_row["disposition_event_id"] = disp_ev

    return confirmed_id, confirmed, current_agent, current_team, final_target_component, final_target_cat


_ET_CACHE = {}


def et_pattern(root_cause_name):
    if not _ET_CACHE:
        import evidence_taxonomy as et
        _ET_CACHE.update(et.ROOT_CAUSE_EVIDENCE_PATTERNS)
    return _ET_CACHE.get(root_cause_name)


# ── KB / similar-case / collaboration ──────────────────────────────────────

def _run_kb_search(c3, counters, kb_rows, suspected_category_id, suspected_component_id, true_root_cause_id,
                    current_agent, is_final_round):
    d, rng = c3.d, c3.rng
    candidates = set(d["articles_by_category"].get(suspected_category_id, [])) | \
        set(d["articles_by_component"].get(suspected_component_id, []))
    if not candidates:
        return
    truly_relevant = set(d["articles_by_root_cause"].get(true_root_cause_id, []))
    scored = []
    for aid in candidates:
        art = d["article_by_id"][aid]
        score = float(art["resolution_rate"]) + (0.2 if art["specificity"] == "narrow" else 0.0) - \
            (0.3 if art["outdated"] == "true" else 0.0) + (0.5 if aid in truly_relevant else 0.0)
        scored.append((aid, score))
    # Tie-break on article id: candidates came from a set (order depends on
    # PYTHONHASHSEED, randomized per process), so without a deterministic
    # secondary key, score ties would silently pick a different article
    # across separate runs with the same seed.
    scored.sort(key=lambda t: (-t[1], t[0]))
    top = scored[:rng.choice([1, 2, 3])]
    for i, (aid, _score) in enumerate(top):
        c3.advance(2, 12)
        interaction = "viewed" if i < 2 else "searched"
        if is_final_round and i == 0 and aid in truly_relevant and rng.random() < 0.5:
            interaction = "applied"
        elif interaction == "viewed" and aid not in truly_relevant and rng.random() < 0.3:
            interaction = "ignored"
        ev_type = {"viewed": "kb_viewed", "applied": "kb_applied", "searched": "kb_searched",
                   "ignored": "kb_ignored"}[interaction]
        ev = c3.emit(ev_type, "agent", current_agent, "kb_interactions", aid)
        kb_rows.append({
            "id": f"KBI{counters.next('kb'):07d}", "case_id": c3.case["id"], "seq": counters.kb,
            "article_id": aid, "interaction_type": interaction,
            "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "event_id": ev,
        })


def _run_similar_case_search(c3, counters, sim_rows, current_agent):
    case, d, rng = c3.case, c3.d, c3.rng
    candidates = d["similar_by_case"].get(case["id"], [])[:5]
    if not candidates:
        return
    n_open = rng.choice([0, 1, 1, 2])
    for i, (other_id, score) in enumerate(candidates[:3]):
        c3.advance(2, 10)
        opened = i < n_open
        ev = c3.emit("similar_case_reviewed" if opened else "similar_case_surfaced", "agent", current_agent,
                     "similar_case_interactions", other_id)
        sim_rows.append({
            "id": f"SIM{counters.next('sim'):07d}", "case_id": case["id"], "seq": i + 1,
            "similar_case_id": other_id, "similarity_score": round(score, 3),
            "opened": str(opened).lower(), "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "event_id": ev,
        })


def _run_collaboration(c3, collab_rows, current_agent, collaborator_team):
    c3.advance(5, 40)
    ev = c3.emit("collaboration_consulted", "agent", current_agent, "collaboration_events", collaborator_team)
    collab_rows.append({
        "case_id": c3.case["id"], "collaborator_team_id": collaborator_team,
        "collaboration_type": c3.rng.choice(pt.COLLABORATION_TYPES),
        "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "event_id": ev,
    })


# ── Customer interactions ──────────────────────────────────────────────────

def _run_customer_interaction(c3, counters, ci_rows, interaction_type, current_agent, requested_info="",
                               response_delay_hours=None, cap=None):
    case = c3.case
    c3.advance(2, 20)
    ev = c3.emit("customer_contacted", "agent", current_agent, "customer_interactions",
                 f"CI{counters.next('ci'):06d}")
    ci_rows.append({
        "id": f"CI{counters.ci:06d}", "case_id": case["id"], "seq": counters.ci,
        "interaction_type": interaction_type, "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"),
        "requested_info": requested_info, "response_delay_hours": response_delay_hours or "",
        "event_id": ev,
    })
    if response_delay_hours:
        c3.advance_hours(response_delay_hours * 0.8, response_delay_hours * 1.2, cap=cap)
        c3.emit("customer_response_received", "customer", case["customer_id"], "customer_interactions",
                f"CI{counters.ci:06d}")


# ── Escalation / engineering ────────────────────────────────────────────────

def _run_escalation(c3, counters, esc_rows, current_team, current_agent, trigger_code):
    case, rng = c3.case, c3.rng
    to_team = case["gt_secondary_team_id"] if (case["gt_secondary_team_id"] and
                                                case["gt_secondary_team_id"] != current_team) else "TM15"
    if trigger_code == "incident_correlation":
        esc_type = "incident_escalation"
    elif trigger_code == "severity_critical":
        esc_type = "severity_escalation"
    elif to_team == "TM15":
        esc_type = "technical_escalation"
    else:
        esc_type = rng.choice(["technical_escalation", "management_escalation"])
    c3.advance(5, 45)
    ev = c3.emit("escalation_initiated", "agent", current_agent, "escalations", f"ESC{counters.next('esc'):05d}")
    esc_rows.append({
        "id": f"ESC{counters.esc:05d}", "case_id": case["id"], "escalation_type": esc_type,
        "from_team_id": current_team, "to_team_id": to_team,
        "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "trigger_code": trigger_code,
        "summary": "", "event_id": ev,
    })
    c3.advance(5, 30)
    c3.emit("escalation_accepted", "team", to_team, "escalations", f"ESC{counters.esc:05d}")
    return to_team


def _run_engineering(c3, counters, eng_rows, current_agent):
    rng = c3.rng
    n = 1 if rng.random() < 0.7 else 2
    acts = rng.sample(pt.ENGINEERING_ACTIVITY_TYPES, k=min(n, len(pt.ENGINEERING_ACTIVITY_TYPES)))
    for act in acts:
        c3.advance_hours(0.5, 4)
        ev = c3.emit("engineering_engaged", "team", "engineering", "engineering_engagements",
                     f"ENG{counters.next('eng'):05d}")
        eng_rows.append({
            "id": f"ENG{counters.eng:05d}", "case_id": c3.case["id"], "activity_type": act,
            "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "finding_summary": "", "event_id": ev,
        })


# ── Resolution / mitigation / verification / reopen ────────────────────────

def _resolution_alternatives(d, root_cause_id, exclude_rt):
    pool = d["resolutions_by_root_cause"].get(root_cause_id, [])
    return [rt for rt, _w in pool if rt != exclude_rt]


def _apply_one_resolution(c3, counters, ra_rows, mit_rows, ver_rows, confirmed_hyp_id, current_agent,
                          current_team, resolution_type_id, is_final, failed_before=None):
    case, d, rng = c3.case, c3.d, c3.rng
    failed_before = failed_before or []
    for rt in failed_before:
        counters.next("ra")
        c3.advance(15, 90)
        action = pt.RESOLUTION_TYPE_TO_ACTION.get(rt, "apply_workaround")
        result = rng.choice(["no_effect", "partial_improvement", "inconclusive"])
        is_temp = rt in pt.MITIGATION_FLAVORED_RESOLUTION_TYPES
        risky = rt in pt.RISKY_RESOLUTION_TYPES
        ev = c3.emit("resolution_attempt_failed", "agent", current_agent, "resolution_attempts",
                     f"RA{counters.ra:07d}")
        row = {
            "id": f"RA{counters.ra:07d}", "case_id": case["id"], "seq": counters.ra, "action": action,
            "resolution_type_id": rt, "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_id": current_agent, "team_id": current_team, "targeted_hypothesis_id": confirmed_hyp_id,
            "result": result, "is_temporary": str(is_temp).lower(), "is_permanent": "false",
            "human_approval_flagged": str(risky).lower(),
            "alternatives_considered": ";".join(_resolution_alternatives(d, case["gt_root_cause_id"], rt)[:2]),
            "event_id": ev,
        }
        ra_rows.append(row)
        if is_temp:
            mit_rows.append({
                "id": f"MIT{counters.next('mit'):06d}", "case_id": case["id"], "resolution_attempt_id": row["id"],
                "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "description": "", "event_id": ev,
            })

    counters.next("ra")
    c3.advance(10, 60)
    action = pt.RESOLUTION_TYPE_TO_ACTION.get(resolution_type_id, "apply_workaround")
    is_temp = resolution_type_id in pt.MITIGATION_FLAVORED_RESOLUTION_TYPES
    risky = resolution_type_id in pt.RISKY_RESOLUTION_TYPES
    ev = c3.emit("resolution_attempt_succeeded", "agent", current_agent, "resolution_attempts",
                 f"RA{counters.ra:07d}")
    final_row = {
        "id": f"RA{counters.ra:07d}", "case_id": case["id"], "seq": counters.ra, "action": action,
        "resolution_type_id": resolution_type_id, "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"),
        "agent_id": current_agent, "team_id": current_team, "targeted_hypothesis_id": confirmed_hyp_id,
        "result": "success", "is_temporary": str(is_temp and not is_final).lower(),
        "is_permanent": str(is_final and not is_temp).lower(),
        "human_approval_flagged": str(risky).lower(),
        "alternatives_considered": ";".join(_resolution_alternatives(d, case["gt_root_cause_id"], resolution_type_id)[:2]),
        "event_id": ev,
    }
    ra_rows.append(final_row)
    if is_temp:
        mit_rows.append({
            "id": f"MIT{counters.next('mit'):06d}", "case_id": case["id"], "resolution_attempt_id": final_row["id"],
            "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "description": "", "event_id": ev,
        })

    c3.advance(10, 90)
    has_telem = d["p2obs_by_case"][case["id"]]["has_telemetry"] == "true"
    v_type = rng.choice(["telemetry_normalized", "error_rate_baseline_restored"]) if has_telem else \
        rng.choice(["customer_confirmed", "no_recurrence_window"])
    v_ev = c3.emit("service_verified", "agent", current_agent, "resolution_verification", f"VER{counters.next('ver'):05d}")
    ver_rows.append({
        "id": f"VER{counters.ver:05d}", "case_id": case["id"], "verification_type": v_type,
        "timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "result": "passed", "event_id": v_ev,
    })
    c3.advance(5, 30)
    c3.emit("case_resolved", "agent", current_agent, "resolution_attempts", final_row["id"])
    c3.advance(2, 20)
    c3.emit("case_closed", "system", "case_management", "resolution_attempts", final_row["id"])
    return final_row


def _n_failed_attempts(rng, archetype, evidence_sufficiency, pool_size):
    if pool_size == 0:
        return 0
    base = {"clear": [70, 25, 5], "vague": [45, 38, 17], "customer_misdiagnosis": [45, 38, 17],
            "wrong_product_mentioned": [50, 35, 15], "multi_component_symptoms": [45, 38, 17],
            "dependency_root_cause": [35, 42, 23]}.get(archetype, [55, 32, 13])
    if evidence_sufficiency == "insufficient":
        base = [max(base[0] - 20, 10), base[1], base[2] + 20]
    n = rng.choices([0, 1, 2], weights=base)[0]
    return min(n, pool_size)


def _run_resolution(c3, counters, tables, confirmed_hyp_id, current_agent, current_team):
    case, d, rng = c3.case, c3.d, c3.rng
    root_cause_id = case["gt_root_cause_id"]
    final_rt = case["gt_resolution_type_id"]
    failed_pool = _resolution_alternatives(d, root_cause_id, final_rt)
    n_failed = _n_failed_attempts(rng, case["gt_difficulty_archetype"], d["p2gt_by_case"][case["id"]]["evidence_sufficiency"],
                                   len(failed_pool))
    chosen_failed = rng.sample(failed_pool, k=n_failed) if n_failed else []

    if case["gt_reopened"]:
        first_rt_pool = [rt for rt in failed_pool if rt not in chosen_failed] or failed_pool or [final_rt]
        first_rt = rng.choice(first_rt_pool) if first_rt_pool != [final_rt] else final_rt
        t_first_close = c3.t_created + timedelta(hours=c3.window_hours * rng.uniform(0.35, 0.65))
        _apply_one_resolution(c3, counters, tables["resolution_attempts"], tables["mitigations"],
                              tables["resolution_verification"], confirmed_hyp_id, current_agent, current_team,
                              first_rt, is_final=False, failed_before=chosen_failed)
        c3.clock = max(c3.clock, t_first_close)
        reason = rng.choice(pt.REOPEN_REASONS)
        c3.advance_hours(1, 48)
        reopen_ev = c3.emit("case_reopened", "customer", case["customer_id"], "case_reopens",
                            f"REOPEN{counters.next('reopen'):05d}")
        tables["case_reopens"].append({
            "id": f"REOPEN{counters.reopen:05d}", "case_id": case["id"],
            "reopen_timestamp": c3.clock.strftime("%Y-%m-%d %H:%M:%S"), "reason_code": reason,
            "prior_resolution_event_id": reopen_ev, "event_id": reopen_ev,
        })
        c3.advance(10, 60)
        c3.emit("hypothesis_updated", "agent", current_agent, "diagnostic_hypotheses", confirmed_hyp_id)
        _apply_one_resolution(c3, counters, tables["resolution_attempts"], tables["mitigations"],
                              tables["resolution_verification"], confirmed_hyp_id, current_agent, current_team,
                              final_rt, is_final=True, failed_before=[])
    else:
        _apply_one_resolution(c3, counters, tables["resolution_attempts"], tables["mitigations"],
                              tables["resolution_verification"], confirmed_hyp_id, current_agent, current_team,
                              final_rt, is_final=True, failed_before=chosen_failed)


# ── Per-case orchestration ──────────────────────────────────────────────────

def _escalation_trigger(rng, case, p2gt):
    if p2gt["incident_relationship"] in ("directly_caused", "partially_influenced"):
        return "incident_correlation"
    if case["gt_severity"] == "Sev1":
        return "severity_critical"
    if p2gt["evidence_sufficiency"] == "insufficient":
        return "evidence_insufficient"
    return rng.choice(["sla_risk", "repeated_failed_attempts", "customer_pressure"])


def _collab_probability(archetype, evidence_sufficiency):
    base = {"clear": 0.10, "vague": 0.35, "customer_misdiagnosis": 0.30, "wrong_product_mentioned": 0.30,
            "multi_component_symptoms": 0.35, "dependency_root_cause": 0.45}.get(archetype, 0.2)
    if evidence_sufficiency == "insufficient":
        base += 0.15
    return min(base, 0.7)


def _new_tables():
    return {k: [] for k in [
        "triage_history", "routing_history", "assignment_history", "diagnostic_hypotheses",
        "hypothesis_evidence", "evidence_queries", "resolution_attempts", "mitigations",
        "resolution_verification", "case_reopens", "kb_interactions", "similar_case_interactions",
        "escalations", "engineering_engagements", "customer_interactions", "collaboration_events",
        "case_lifecycle_events",
    ]}


def _simulate_one_case(case, d, cat_id_to_key, rng, counters, tables):
    c3 = _Case3(case, d, cat_id_to_key, rng)
    root_cause_id = case["gt_root_cause_id"]
    root_cause_name = d["root_cause_id_to_name"][root_cause_id]
    p2gt = d["p2gt_by_case"][case["id"]]
    evidence_sufficiency = p2gt["evidence_sufficiency"]
    archetype = case["gt_difficulty_archetype"]

    triage_row, pred_product, pred_component, pred_cat, pred_subcat, team, team_pool = _run_triage(c3, counters)
    c3.triage_result = {"predicted_component": pred_component, "predicted_cat": pred_cat,
                         "predicted_subcat": pred_subcat}
    tables["triage_history"].append(triage_row)

    seq_holder = [0, None]
    required_skills = d["case_required_skill_ids"].get(case["id"], [])
    alt = [t for t, _r, _w in team_pool if t != team][:3]
    current_agent = _route(c3, counters, tables["routing_history"], tables["assignment_history"], seq_holder,
                            team, "initial_classification", alt, pred_cat, pred_component, pred_product,
                            required_skills)

    # Insufficient-evidence cases realistically stall early waiting on the
    # customer before the investigation can make real progress.
    if evidence_sufficiency == "insufficient" and rng.random() < 0.6:
        _run_customer_interaction(c3, counters, tables["customer_interactions"], "request_logs", current_agent,
                                   requested_info="additional logs / reproduction steps",
                                   response_delay_hours=rng.uniform(1, 20), cap=c3.t_end)

    extra_rounds = evidence_sufficiency in ("insufficient", "partially_sufficient")
    confirmed_hyp_id, confirmed, current_agent, current_team, final_component, final_cat = _run_hypothesis_loop(
        c3, counters, d, cat_id_to_key, tables["diagnostic_hypotheses"], tables["hypothesis_evidence"],
        tables["evidence_queries"], tables["routing_history"], tables["assignment_history"], seq_holder,
        current_agent, extra_rounds, terminal_ok=True)

    _run_kb_search(c3, counters, tables["kb_interactions"], final_cat, final_component, root_cause_id,
                   current_agent, is_final_round=confirmed)
    _run_similar_case_search(c3, counters, tables["similar_case_interactions"], current_agent)

    secondary_team = case["gt_secondary_team_id"]
    if secondary_team and secondary_team != current_team and rng.random() < _collab_probability(archetype, evidence_sufficiency):
        _run_collaboration(c3, tables["collaboration_events"], current_agent, secondary_team)

    if case["gt_escalated"]:
        trigger = _escalation_trigger(rng, case, p2gt)
        current_team = _run_escalation(c3, counters, tables["escalations"], current_team, current_agent, trigger)
        if root_cause_name in pt.ENGINEERING_ENGAGEMENT_ROOT_CAUSES:
            _run_engineering(c3, counters, tables["engineering_engagements"], current_agent)
    elif root_cause_name in pt.ENGINEERING_ENGAGEMENT_ROOT_CAUSES and rng.random() < 0.35:
        _run_engineering(c3, counters, tables["engineering_engagements"], current_agent)

    if not case["is_open"]:
        _run_customer_interaction(c3, counters, tables["customer_interactions"],
                                   "provide_status_update" if rng.random() < 0.5 else "obtain_closure_confirmation",
                                   current_agent)
        _run_resolution(c3, counters, tables, confirmed_hyp_id, current_agent, current_team)
    else:
        # Still open: leave the trajectory mid-investigation. A brief status
        # update is still realistic even for an unresolved case.
        if rng.random() < 0.4:
            _run_customer_interaction(c3, counters, tables["customer_interactions"], "provide_status_update",
                                       current_agent)

    tables["case_lifecycle_events"].extend(c3.events)


def build_investigations(rng, cases, d):
    import evidence_taxonomy as et
    cat_id_to_key = et.category_key_by_name(d["cat_id_to_name"])
    tables = _new_tables()
    counters = _Counters()
    for case in cases:
        _simulate_one_case(case, d, cat_id_to_key, rng, counters, tables)
    return tables
