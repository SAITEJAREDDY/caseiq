"""Validation-only opaque-key control for the causal-change decision (JEV-025).

Question: do Jev or the LLM baseline use the canonical change/deployment ids (`CH030402`) that Stage C showed
as option keys? The one intended difference between the two arms is the option key; everything else is the
Stage C input. Protocol: docs/JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md (pre-registered, sha256 recorded on the runs).

This module is deliberately outside the sealed locked-benchmark source list: it imports the pinned modules and
changes none of them. The hashed keys built here replace the position-coded `option_i` aliases of the dev control,
because `option_i` encodes the candidate's rank. The pinned decision and baseline code already map answers back
through `candidate_meta["alias_to_id"]`, so this module only supplies a different mapping.

It reads only validation cases (taken from the completed Stage C experiment), never the locked split, and it
writes only new experiments and a checkpoint. Usage:

    python3 -m agent.jev_v2.opaque_control --prepare                     # every check, no API call, nothing written
    python3 -m agent.jev_v2.opaque_control --run                         # checks, then Jev + LLM on the opaque arm
    python3 -m agent.jev_v2.opaque_control --replicate jev llm           # conditional canonical replicate (protocol s.6)
"""
import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent.graph_v2.db import get_driver
from agent.jev_v2 import candidates as candidates_mod
from agent.jev_v2 import decisions as decisions_mod
from agent.jev_v2 import frozen_config, llm_baseline, locked_benchmark, questions, state_builder
from agent.jev_v2.aggregate import build_report
from agent.jev_v2.client import JevClient, LeakageGuardError, assert_no_leakage
from agent.jev_v2.config import LLM_BASELINE_MAX_TOKENS, LLM_BASELINE_MODEL, LLM_BASELINE_TEMPERATURE, LLM_REPAIR_MAX_ATTEMPTS, PRICING_VERSION
from agent.jev_v2.registry import create_experiment, load_decisions, load_experiment, persist_experiment
from agent.jev_v2.scoring import NO_CAUSAL_CHANGE_KEY, score_decision

DECISION = "causal_change"
KIND = "validation_control"
KEY_SCHEME = "hashed_opaque_v1"
KEY_SEED = "opaque_key_control_v1"
KEY_PREFIX = "opt_"
KEY_LENGTH = 5
KEY_ALPHABET = "bcdfghjkmnpqrstvwxz23456789"  # 27 symbols: no vowels (no accidental words), no 0/1/l/o look-alikes
KEY_PATTERN = re.compile(rf"^{KEY_PREFIX}[{KEY_ALPHABET}]{{{KEY_LENGTH}}}$")

STAGE_C_JEV = "exp_stage_c_validation_jev_20260923T184036Z_fa984004"
STAGE_C_LLM = "exp_stage_c_validation_llm_20260923T184040Z_9fc75b1a"
RUN_NAME = "stage_c_causal_opaque_control"
REPLICATE_NAME = "stage_c_causal_canonical_replicate"
PROTOCOL = "docs/JEV_OPAQUE_KEY_CONTROL_PROTOCOL.md"
WORKERS = 8
CASE_ATTEMPTS = 3
CHECKPOINT_DIR = frozen_config.PROJECT_ROOT / "data" / "eval" / "jev" / "checkpoints"


# ── the key scheme ────────────────────────────────────────────────────────────────────
def _key_for(case_id: str, canonical_id: str, salt: int) -> str:
    n = int.from_bytes(hashlib.sha256(f"{KEY_SEED}|{case_id}|{canonical_id}|{salt}".encode()).digest()[:8], "big")
    chars = []
    for _ in range(KEY_LENGTH):
        n, r = divmod(n, len(KEY_ALPHABET))
        chars.append(KEY_ALPHABET[r])
    return KEY_PREFIX + "".join(chars)


def opaque_keys(case_id: str, canonical_ids: list) -> dict:
    """canonical id -> opaque key. Deterministic and injective within a decision. A key depends only on the case and the
    canonical id (never on position, time, type or component); ids are visited in sorted order so that the rare
    collision salt does not depend on candidate order."""
    used, mapping = set(), {}
    for canonical_id in sorted(canonical_ids):
        salt = 0
        while True:
            key = _key_for(case_id, canonical_id, salt)
            if key not in used:
                break
            salt += 1
        used.add(key)
        mapping[canonical_id] = key
    return mapping


def apply_key_scheme(case_id: str, cands: dict, cmeta: dict, opaque: bool) -> dict:
    """Candidate metadata as the pinned pipeline should see it. Canonical arm: unchanged. Opaque arm: the same metadata plus
    `alias_to_id` (in candidate order) so `candidates.model_facing_candidates` / `to_canonical_answer` do the mapping."""
    if not opaque:
        return cmeta
    real = [k for k in cands if k != NO_CAUSAL_CHANGE_KEY]
    keys = opaque_keys(case_id, real)
    return {**cmeta, "key_mode": KEY_SCHEME, "alias_to_id": {keys[k]: k for k in real}}


# ── request construction (exactly what each system receives) ──────────────────────────
def build_requests(state: dict, cands: dict, cmeta: dict) -> dict:
    """The Jev body's state/question part and the LLM chat messages, built by the same functions the pinned runners use."""
    model_cands = candidates_mod.model_facing_candidates(cands, cmeta)
    question = questions.build_question(DECISION, model_cands)
    return {"jev": {"state": state, "questions": {DECISION: question}},
            "llm": llm_baseline._build_prompt(DECISION, state, {**questions.build_question(DECISION, cands), "criteria": model_cands}, model_cands),
            "model_cands": model_cands}


def _dump(obj) -> str:
    return json.dumps(obj, default=str)


def equivalence_problems(case_id: str, state: dict, cands: dict, canonical_meta: dict, opaque_meta: dict) -> list:
    """Empty when the two arms differ only in the option keys (protocol s.3, checks 2 to 5)."""
    problems = []
    canonical = build_requests(state, cands, canonical_meta)
    opaque = build_requests(state, cands, opaque_meta)
    alias_to_id = opaque_meta.get("alias_to_id") or {}
    real_ids = [k for k in cands if k != NO_CAUSAL_CHANGE_KEY]

    if set(alias_to_id.values()) != set(real_ids) or len(alias_to_id) != len(real_ids):
        problems.append("alias map does not cover exactly the real candidates")
    for alias in alias_to_id:
        if not KEY_PATTERN.match(alias) or alias == NO_CAUSAL_CHANGE_KEY:
            problems.append(f"malformed opaque key {alias!r}")
    can_items, opq_items = list(canonical["model_cands"].items()), list(opaque["model_cands"].items())
    if len(can_items) != len(opq_items):
        problems.append("candidate count differs")
    else:
        if [alias_to_id.get(k, k) for k, _ in opq_items] != [k for k, _ in can_items]:
            problems.append("candidate membership or order differs after mapping the keys back")
        if [v for _, v in opq_items] != [v for _, v in can_items]:
            problems.append("candidate descriptions differ")
        if NO_CAUSAL_CHANGE_KEY in cands and not (opq_items and can_items and opq_items[-1][0] == can_items[-1][0] == NO_CAUSAL_CHANGE_KEY):
            problems.append("the none option moved or changed")
    for label in ("jev", "llm"):
        text_can, text_opq = _dump(canonical[label]), _dump(opaque[label])
        restored = text_opq
        for alias, canonical_id in alias_to_id.items():
            restored = restored.replace(alias, canonical_id)
        if restored != text_can:
            problems.append(f"{label} request differs from the canonical one by more than the option keys")
        for canonical_id in alias_to_id.values():
            if canonical_id in text_opq:
                problems.append(f"{label} opaque request still contains canonical id {canonical_id}")
        for alias in alias_to_id:
            if alias in text_can:
                problems.append(f"{label} canonical request contains opaque key {alias}")
    try:
        assert_no_leakage(opaque["jev"])
    except LeakageGuardError as e:
        problems.append(f"leakage guard: {e}")
    return problems


def reference_problems(case_id: str, as_of: str, state: dict, cands: dict, cmeta: dict, stored_jev: dict, stored_llm: dict) -> list:
    """The rebuilt canonical input must equal what Stage C stored for both systems (protocol s.3, check 1)."""
    problems = []
    for label, stored in (("Jev", stored_jev), ("LLM", stored_llm)):
        if stored is None:
            problems.append(f"no stored Stage C {label} causal-change record")
            continue
        if json.dumps(state, sort_keys=True, default=str) != json.dumps(stored["state"], sort_keys=True, default=str):
            problems.append(f"state differs from the stored Stage C {label} record")
        if list(cands.items()) != list((stored["candidates"] or {}).items()):
            problems.append(f"candidates or their order differ from the stored Stage C {label} record")
        if json.dumps(cmeta, sort_keys=True, default=str) != json.dumps(stored["candidate_meta"], sort_keys=True, default=str):
            problems.append(f"candidate metadata differs from the stored Stage C {label} record")
        if as_of != stored["as_of"]:
            problems.append(f"as_of differs from the stored Stage C {label} record")
    return problems


def is_nontrivial(cands: dict) -> bool:
    return any(k != NO_CAUSAL_CHANGE_KEY for k in cands)


# ── one case ──────────────────────────────────────────────────────────────────────────
def _inputs(driver, case_id: str, settings: dict) -> tuple:
    with driver.session() as session:
        ctx = state_builder.get_case_context(session, case_id)
        if "error" in ctx:
            raise RuntimeError(f"case context unavailable: {ctx['error']}")
        as_of = ctx["created_date"]
        state, cands, cmeta = decisions_mod.build_inputs(session, case_id, DECISION, as_of, settings["context_version"],
                                                         {DECISION: settings["candidate_version"]}, "canonical")
    return as_of, state, cands, cmeta


def _process_case(driver, case_id, settings, reference, opaque, systems, jev_client, dry):
    """Returns (case_id, integrity_dict, jev_raw_or_None, llm_raw_or_None). Raises on graph/API failure."""
    as_of, state, cands, cmeta = _inputs(driver, case_id, settings)
    meta = apply_key_scheme(case_id, cands, cmeta, opaque)
    problems = reference_problems(case_id, as_of, state, cands, cmeta, reference["jev"].get(case_id), reference["llm"].get(case_id))
    if opaque:
        problems += equivalence_problems(case_id, state, cands, cmeta, meta)
    alias_to_id = meta.get("alias_to_id") or {}
    integrity = {"case_id": case_id, "nontrivial": is_nontrivial(cands), "n_real": len(alias_to_id) if opaque else sum(1 for k in cands if k != NO_CAUSAL_CHANGE_KEY),
                 "problems": problems, "aliases": list(alias_to_id) if opaque else [], "canonical_ids_in_order": [k for k in cands if k != NO_CAUSAL_CHANGE_KEY]}
    if dry or problems:
        return case_id, integrity, None, None
    jev_raw = llm_raw = None
    if "jev" in systems:
        question = questions.build_question(DECISION, candidates_mod.model_facing_candidates(cands, meta))
        jev_raw = decisions_mod._call_one(jev_client, case_id, DECISION, state, question, cands, meta, as_of, settings["context_version"])
    if "llm" in systems:
        llm_raw = llm_baseline.run_llm_decision(DECISION, case_id, state, questions.build_question(DECISION, cands), cands, meta, as_of, settings["context_version"])
    return case_id, integrity, jev_raw, llm_raw


def _worker(driver, case_id, *args):
    last = None
    for attempt in range(1, CASE_ATTEMPTS + 1):
        try:
            return _process_case(driver, case_id, *args), None
        except Exception as e:  # transient graph/network problem: retry the whole case in a fresh session
            last = f"{type(e).__name__}: {str(e)[:300]}"
            time.sleep(2.0 * attempt)
    return (case_id, None, None, None), last


# ── cohort and reference ──────────────────────────────────────────────────────────────
def load_reference() -> dict:
    """The authoritative Stage C experiments: cohort, settings and the canonical causal-change records."""
    jev_exp, llm_exp = load_experiment(STAGE_C_JEV), load_experiment(STAGE_C_LLM)
    if jev_exp["dataset_split"] != "validation" or llm_exp["dataset_split"] != "validation":
        raise SystemExit("the reference experiments are not validation experiments")
    if jev_exp["case_ids"] != llm_exp["case_ids"]:
        raise SystemExit("the Stage C Jev and LLM experiments do not share one ordered cohort")
    case_ids = list(jev_exp["case_ids"])
    locked_benchmark.assert_not_locked_ids(case_ids)  # keeps only dev+validation ids in memory; the test ids are dropped at once
    pins = frozen_config.load_manifest(locked_benchmark.NAME)["pinned_files"]
    for label in ("stage_c_jev_experiment", "stage_c_llm_experiment", "stage_c_jev_decisions", "stage_c_llm_decisions"):
        if frozen_config.sha256_file(locked_benchmark.PROJECT_ROOT / pins[label]["path"]) != pins[label]["sha256"]:
            raise SystemExit(f"{label} no longer matches the digest pinned by the locked freeze")
    config = jev_exp["config"]
    settings = {"context_version": config["context_version"], "candidate_version": config["candidate_generation_versions"][DECISION],
                "jev_model": config["jev_model_requested"], "case_ids_sha256": config["case_ids_sha256"]}
    if frozen_config.sha256_json(case_ids) != settings["case_ids_sha256"]:
        raise SystemExit("the cohort does not match the case-id digest recorded on Stage C")
    by = lambda exp_id: {r["case_id"]: r for r in load_decisions(exp_id) if r["decision_type"] == DECISION}
    return {"case_ids": case_ids, "settings": settings, "jev": by(STAGE_C_JEV), "llm": by(STAGE_C_LLM)}


def _pre_run_guards() -> list:
    problems = []
    if locked_benchmark.read_run_state() is not None:
        problems.append("a locked-benchmark run state exists")
    problems += locked_benchmark.verify() + locked_benchmark.verify_environment()
    return problems


# ── the run ───────────────────────────────────────────────────────────────────────────
def prepare(opaque: bool = True, systems=("jev", "llm")) -> dict:
    """Every check and no API call. Returns the reference bundle, the per-case integrity rows and the plan."""
    guard = _pre_run_guards()
    if guard:
        raise SystemExit("pre-run guards failed:\n  - " + "\n  - ".join(guard))
    reference = load_reference()
    case_ids = reference["case_ids"]
    driver = get_driver()
    rows, failed = {}, []
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(_worker, driver, cid, reference["settings"], reference, opaque, systems, None, True) for cid in case_ids]
            for fut in as_completed(futures):
                (case_id, integrity, _, _), error = fut.result()
                if error:
                    failed.append((case_id, error))
                else:
                    rows[case_id] = integrity
    finally:
        driver.close()
    ordered = [rows[c] for c in case_ids if c in rows]
    bad = [r for r in ordered if r["problems"]]
    plan = {
        "cases": len(case_ids), "checked": len(ordered), "failed_to_build": failed[:5], "cases_with_problems": len(bad),
        "problems": [(r["case_id"], r["problems"][:3]) for r in bad[:5]],
        "nontrivial": sum(1 for r in ordered if r["nontrivial"]), "trivial": sum(1 for r in ordered if not r["nontrivial"]),
        "opaque_keys": sum(len(r["aliases"]) for r in ordered), "case_ids_sha256": reference["settings"]["case_ids_sha256"],
        "key_order_integrity": key_order_integrity(ordered) if opaque else None,
        "ok": not bad and not failed and len(ordered) == len(case_ids),
    }
    return {"reference": reference, "rows": ordered, "plan": plan}


def key_order_integrity(rows: list) -> dict:
    """Evidence that the opaque keys carry no order: within each decision, the rank correlation between the key's
    alphabetical order and (a) the canonical id number and (b) the list position. Pooled over every within-decision pair."""
    num = lambda cid: int(re.sub(r"\D", "", cid))
    concordant_id = discordant_id = concordant_pos = discordant_pos = 0
    for r in rows:
        keys, ids = r["aliases"], r["canonical_ids_in_order"]
        if len(keys) < 2:
            continue
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                s_id = (keys[i] > keys[j]) - (keys[i] < keys[j])
                s_num = (num(ids[i]) > num(ids[j])) - (num(ids[i]) < num(ids[j]))
                concordant_id += s_id * s_num > 0
                discordant_id += s_id * s_num < 0
                concordant_pos += s_id < 0  # position i comes before j; concordant when key i sorts first
                discordant_pos += s_id > 0
    tau = lambda c, d: (c - d) / (c + d) if c + d else None
    return {"pairs": concordant_id + discordant_id, "kendall_tau_key_vs_canonical_id_number": tau(concordant_id, discordant_id),
            "kendall_tau_key_vs_list_position": tau(concordant_pos, discordant_pos)}


def _load_checkpoint(path: Path) -> dict:
    done = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    done[row["case_id"]] = row
    return done


def run(opaque: bool, systems: tuple, name: str, resume: bool = False, only_nontrivial: bool = False) -> dict:
    prepared = prepare(opaque, systems)
    plan = prepared["plan"]
    print(json.dumps({k: v for k, v in plan.items() if k != "problems"}, default=str), flush=True)
    if not plan["ok"]:
        raise SystemExit(f"input checks failed; no API call was made: {plan['problems']}")
    reference, rows = prepared["reference"], {r["case_id"]: r for r in prepared["rows"]}
    case_ids = [c for c in reference["case_ids"] if (rows[c]["nontrivial"] or not only_nontrivial)]

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = CHECKPOINT_DIR / f"{name}.jsonl"
    if checkpoint.exists() and not resume:
        raise SystemExit(f"{checkpoint} already exists; pass --resume to continue that run (a control is not repeated to keep the better result)")
    done = {c: r for c, r in _load_checkpoint(checkpoint).items() if c in set(case_ids)} if resume else {}
    pending = [c for c in case_ids if c not in done]
    if done:
        print(f"resuming: {len(done)} of {len(case_ids)} cases already complete", flush=True)

    jev_client = JevClient() if "jev" in systems else None
    driver, failed, started = get_driver(), [], time.time()
    ckpt = open(checkpoint, "a")
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(_worker, driver, cid, reference["settings"], reference, opaque, systems, jev_client, False) for cid in pending]
            completed = 0
            for fut in as_completed(futures):
                (case_id, integrity, jev_raw, llm_raw), error = fut.result()
                completed += 1
                if error or integrity["problems"]:
                    failed.append((case_id, error or integrity["problems"]))
                    print(f"  FAILED {case_id}: {error or integrity['problems']}", flush=True)
                else:
                    # Scoring reads hidden truth, so it happens here on the main thread after the models answered.
                    row = {"case_id": case_id, "jev": score_decision(jev_raw) if jev_raw else None, "llm": score_decision(llm_raw) if llm_raw else None,
                           "aliases": integrity["aliases"]}
                    done[case_id] = row
                    ckpt.write(json.dumps(row, default=str) + "\n")
                    ckpt.flush()
                if completed % 25 == 0 or completed == len(pending):
                    elapsed = time.time() - started
                    print(f"  {len(done)}/{len(case_ids)} cases done ({completed}/{len(pending)} this session, {len(failed)} failed), "
                          f"elapsed {elapsed / 60:.1f} min, eta {elapsed / completed * (len(pending) - completed) / 60:.1f} min", flush=True)
    finally:
        driver.close()
        ckpt.close()
    if failed:
        raise SystemExit(f"{len(failed)} case(s) failed: {failed[:5]}. Nothing was persisted; rerun with --resume to retry only those cases.")

    guard = _pre_run_guards()  # the sealed locked configuration must be exactly as it was before the control ran
    if guard:
        raise SystemExit("post-run guards failed:\n  - " + "\n  - ".join(guard))
    return persist(name, opaque, systems, case_ids, [done[c] for c in case_ids], reference, plan)


def persist(name, opaque, systems, case_ids, done_rows, reference, plan) -> dict:
    protocol_path = locked_benchmark.PROJECT_ROOT / PROTOCOL
    manifest = frozen_config.load_manifest(locked_benchmark.NAME)
    settings = reference["settings"]
    common = {
        "context_version": settings["context_version"], "candidate_generation_versions": {DECISION: settings["candidate_version"]},
        "causal_key_mode": KEY_SCHEME if opaque else "canonical", "jev_model_requested": settings["jev_model"], "pricing_version": PRICING_VERSION,
        "orchestration": {"runner": "opaque_control_v1", "workers": WORKERS, "failed_cases": []},
        "case_ids_sha256": frozen_config.sha256_json(case_ids),
        "pre_registered_protocol": {"path": PROTOCOL, "sha256": frozen_config.sha256_file(protocol_path)},
        "control": {
            "purpose": "JEV-025 causal-change opaque-key control on the Stage C validation cohort" if opaque else "canonical replicate: run-to-run noise floor for the opaque-key control",
            "key_scheme": {"name": KEY_SCHEME, "prefix": KEY_PREFIX, "length": KEY_LENGTH, "alphabet": KEY_ALPHABET, "seed": KEY_SEED} if opaque else None,
            "reference_experiments": {"jev": STAGE_C_JEV, "llm": STAGE_C_LLM}, "cohort": "non-trivial decisions only" if len(case_ids) != len(reference["case_ids"]) else "all 750 Stage C cases",
            "input_checks": {k: plan[k] for k in ("cases", "checked", "cases_with_problems", "nontrivial", "trivial", "opaque_keys", "key_order_integrity")},
            "locked_config_sha256_at_run": manifest["config_sha256"], "locked_manifest_sha256_at_run": frozen_config.sha256_file(locked_benchmark.manifest_path(locked_benchmark.NAME)),
            "locked_run_state_at_run": None,
        },
        "frozen_config": {"name": "stage_b_frozen_v1", "config_sha256": frozen_config.sha256_file(frozen_config.config_path("stage_b_frozen_v1")), "status": "verified_against_manifest"},
    }
    out = {}
    if "jev" in systems:
        records = [r["jev"] for r in done_rows]
        exp = create_experiment(f"{name}_jev", KIND, "jev_primitive", [DECISION], case_ids, "validation", common, build_report(records))
        persist_experiment(exp, records)
        out["jev"] = exp["experiment_id"]
    if "llm" in systems:
        records = [r["llm"] for r in done_rows]
        llm_config = {**common, "llm_model": LLM_BASELINE_MODEL, "llm_temperature": LLM_BASELINE_TEMPERATURE, "llm_max_tokens": LLM_BASELINE_MAX_TOKENS,
                      "llm_repair_max_attempts": LLM_REPAIR_MAX_ATTEMPTS}
        exp = create_experiment(f"{name}_llm", KIND, "llm_primitive_baseline", [DECISION], case_ids, "validation", llm_config, build_report(records))
        persist_experiment(exp, records)
        out["llm"] = exp["experiment_id"]
    print(json.dumps(out), flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true", help="every check, no API call, nothing written")
    group.add_argument("--run", action="store_true", help="the opaque arm on all Stage C validation cases, Jev and LLM")
    group.add_argument("--replicate", nargs="+", choices=["jev", "llm"], help="canonical replicate of the non-trivial decisions for the listed systems (protocol s.6)")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepared = prepare(True)
        print(json.dumps(prepared["plan"], indent=2, default=str))
        raise SystemExit(0 if prepared["plan"]["ok"] else 1)
    if args.run:
        run(True, ("jev", "llm"), RUN_NAME, args.resume)
    else:
        run(False, tuple(args.replicate), REPLICATE_NAME, args.resume, only_nontrivial=True)


if __name__ == "__main__":
    main()
