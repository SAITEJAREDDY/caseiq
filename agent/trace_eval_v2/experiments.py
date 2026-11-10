"""Runs the Phase 8 judgments over a set of trace items and persists the results in the shared experiment registry (data/experiments/).

An *item* is one packet to review: an original trace or a synthetic perturbation variant. For every item and every judgment, Jev and the LLM judge each get one call with the identical
packet (`trace_projection_v1`) and the identical question. All judge inputs are built and leak-checked before the first API call. Results are appended to a checkpoint as they finish so an
interrupted run resumes without re-sending. Two experiments are registered per run (one per judge), tagged `trace_eval_jev` / `trace_eval_llm`, plus the stored packets that were sent.

Evaluator-side orchestration: it may hold reference labels, but they are never passed to a judge; scoring happens afterwards in `scorer.py`.
"""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from agent.eval_v2.registry import REGISTRY_PATH, dataset_checksum_digest, new_experiment_id
from agent.jev_v2.config import LLM_BASELINE_MAX_TOKENS, LLM_BASELINE_MODEL, LLM_BASELINE_TEMPERATURE, LLM_REPAIR_MAX_ATTEMPTS, PRICING_VERSION
from agent.trace_eval_v2 import jev_evaluator, llm_evaluator, questions
from agent.trace_eval_v2.config import (
    ALIAS_SCHEME, CORPUS_VERSION, EXPERIMENTS_DIR, JUDGE_WORKERS, JUDGMENTS, PERTURBATION_VERSION, PROJECTION_VERSION, QUESTION_VERSIONS, REFERENCE_LABEL_VERSION,
    REVIEW_POLICY_VERSION, TRACE_EVAL_DIR, jev_model,
)
from agent.trace_eval_v2.guard import assert_request_clean
from agent.trace_eval_v2.trace_projection import approx_tokens, project, state_json

CHECKPOINT_DIR = TRACE_EVAL_DIR / "checkpoints"
KIND_TYPE = {"jev": "trace_eval_jev", "llm": "trace_eval_llm"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_items(run_ids: list, with_variants: bool = True, variant_targets: dict = None, only_variants_of: list = None) -> list:
    """Originals (and, optionally, their synthetic perturbation variants) as items: trace, observable context, evaluation-only labels and observable baselines. Reads stored runs, the
    stored pool context and labels, and hidden truth for the variants' reference labels; calls no API."""
    from agent.eval_v2.ground_truth import get_hidden_truth
    from agent.trace_eval_v2 import corpus, labels as L, perturbations, scorer
    from agent.trace_eval_v2.trace_loader import load_trace, load_run

    ctx_all = corpus.load_context()
    stored_labels = corpus.load_labels()
    items, bases = [], []
    for rid in run_ids:
        trace = load_trace(load_run(rid))
        ctx = ctx_all[rid]
        inv_ids = {i["id"] for i in ctx["inventory"]}
        truth = get_hidden_truth(trace.case_id)
        labels = stored_labels[rid]
        f = L.trace_facts(trace, inv_ids, truth)
        items.append({"trace_key": rid, "run_id": rid, "case_id": trace.case_id, "variant": None, "base_key": None, "trace": trace, "context": ctx, "labels": labels,
                      "baselines": scorer.observable_baselines(trace, ctx["inventory"]), "alias_salt": "0"})
        bases.append((trace, f, labels["labels"], ctx["inventory"], ctx, truth))
    if with_variants:
        allowed = set(only_variants_of) if only_variants_of is not None else None
        chosen = [b for b in bases if allowed is None or b[0].run_id in allowed]
        for v in perturbations.build_variants([b[:4] for b in chosen], targets=variant_targets):
            base = next(b for b in bases if b[0].run_id == v["base_run_id"])
            vt = v["trace"]
            inv_ids = {i["id"] for i in base[4]["inventory"]}
            labels = L.compute_labels(vt, inv_ids, base[5])
            key = vt.run_key
            items.append({"trace_key": key, "run_id": vt.run_id, "case_id": vt.case_id, "variant": v["perturbation"], "base_key": vt.run_id, "trace": vt, "context": base[4], "labels": labels,
                          "baselines": scorer.observable_baselines(vt, base[4]["inventory"]), "alias_salt": v["alias_salt"], "expected": v["expected"], "variant_meta": vt.variant})
    return items


def build_packets(items: list) -> list:
    """Adds `state` (the exact model-facing packet) and `alias_reverse` (evaluator-only) to every item, and runs the leakage guard on every (packet, question)."""
    out = []
    for it in items:
        state, aliaser = project(it["trace"], it["context"], it.get("alias_salt", "0"))
        for j in JUDGMENTS:
            assert_request_clean(state, questions.jev_question(j))
        out.append({**it, "state": state, "state_sha256": _sha(state_json(state)), "alias_reverse": aliaser.reverse})
    return out


def _tasks(packets: list, judges: tuple, judgments: list) -> list:
    return [(p["trace_key"], j, judge) for p in packets for j in judgments for judge in judges]


def _call(packet_by_key: dict, key: str, judgment: str, judge: str) -> dict:
    packet = packet_by_key[key]
    raw = jev_evaluator.ask(judgment, packet["state"]) if judge == "jev" else llm_evaluator.ask(judgment, packet["state"])
    return {"trace_key": key, "run_id": packet["run_id"], "case_id": packet["case_id"], "variant": packet.get("variant"), **raw}


def run_judgments(packets: list, name: str, judges: tuple = ("jev", "llm"), judgments: list = None, resume: bool = False, workers: int = JUDGE_WORKERS) -> list:
    judgments = judgments or JUDGMENTS
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"{name}.jsonl"
    if path.exists() and not resume:
        raise SystemExit(f"{path.name} exists; pass --resume to continue that run (a run is not repeated to keep a better result)")
    done = {}
    if path.exists():
        for line in open(path):
            if line.strip():
                row = json.loads(line)
                done[(row["trace_key"], row["judgment"], row["judge"])] = row
    by_key = {p["trace_key"]: p for p in packets}
    pending = [t for t in _tasks(packets, judges, judgments) if t not in done]
    print(f"{name}: {len(packets)} packets x {len(judgments)} judgments x {len(judges)} judges = {len(_tasks(packets, judges, judgments))} calls; {len(done)} done, {len(pending)} to run", flush=True)
    started, failures = time.time(), 0
    with open(path, "a") as ckpt, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_call, by_key, *t): t for t in pending}
        for i, fut in enumerate(as_completed(futures), start=1):
            row = fut.result()
            done[(row["trace_key"], row["judgment"], row["judge"])] = row
            ckpt.write(json.dumps(row, default=str) + "\n")
            ckpt.flush()
            failures += row.get("status") != "ok"
            if i % 100 == 0 or i == len(pending):
                elapsed = time.time() - started
                print(f"  {i}/{len(pending)} calls ({failures} not ok), {elapsed / 60:.1f} min, eta {elapsed / i * (len(pending) - i) / 60:.1f} min", flush=True)
    return [done[t] for t in _tasks(packets, judges, judgments)]


def _agent_versions(packets: list) -> dict:
    from agent.trace_eval_v2.trace_loader import load_run

    runs = [load_run(p["run_id"]) for p in packets if not p.get("variant")]
    keys = ["model_provider", "model_name", "temperature", "prompt_version", "toolset_version", "output_schema_version", "agent_loop_version", "repair_layer_version", "graph_version"]
    distinct = {k: sorted({str(r.get(k)) for r in runs}) for k in keys}
    return {"homogeneous": all(len(v) <= 1 for v in distinct.values()), "distinct_values": distinct}


def persist(name: str, kind: str, packets: list, rows: list, split_label: str = "dev", extra_config: dict = None) -> dict:
    """Writes one registered experiment per judge. Returns {"jev": experiment_id, "llm": experiment_id}."""
    ids = {}
    case_ids = sorted({p["case_id"] for p in packets})
    originals = [p for p in packets if not p.get("variant")]
    variants = [p for p in packets if p.get("variant")]
    agent = _agent_versions(packets)
    for judge in sorted({r["judge"] for r in rows}):
        judge_rows = [r for r in rows if r["judge"] == judge]
        exp_id = new_experiment_id(f"{name}_{judge}")
        exp_dir = EXPERIMENTS_DIR / exp_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "projection_version": PROJECTION_VERSION, "alias_scheme": ALIAS_SCHEME, "reference_label_version": REFERENCE_LABEL_VERSION, "review_policy_version": REVIEW_POLICY_VERSION,
            "perturbation_version": PERTURBATION_VERSION, "corpus_version": CORPUS_VERSION, "question_versions": QUESTION_VERSIONS, "pricing_version": PRICING_VERSION,
            "judgments": sorted({r["judgment"] for r in judge_rows}), "judge": judge, "workers": JUDGE_WORKERS,
            **({"jev_model_requested": jev_model(), "jev_models_resolved": sorted({r.get("jev_model") for r in judge_rows if r.get("jev_model")})} if judge == "jev" else
               {"llm_model": LLM_BASELINE_MODEL, "llm_temperature": LLM_BASELINE_TEMPERATURE, "llm_max_tokens": LLM_BASELINE_MAX_TOKENS, "llm_repair_max_attempts": LLM_REPAIR_MAX_ATTEMPTS}),
            "agent": agent, **(extra_config or {}),
        }
        record = {
            "experiment_id": exp_id, "name": f"{name}_{judge}", "created_at": datetime.now(timezone.utc).isoformat(), "kind": kind, "experiment_type": KIND_TYPE[judge],
            "dataset_split": split_label, "case_ids": case_ids, "num_cases": len(case_ids), "run_ids": sorted({p["run_id"] for p in originals}),
            "trace_keys": [p["trace_key"] for p in packets], "n_original_traces": len(originals), "n_variants": len(variants),
            "variants": [{"trace_key": p["trace_key"], **(p["trace"].variant or {})} for p in variants],
            "dataset_checksum_digest": dataset_checksum_digest(), "config": config,
        }
        (exp_dir / "experiment.json").write_text(json.dumps(record, indent=2, default=str))
        with open(exp_dir / "judgments.jsonl", "w") as f:
            for r in judge_rows:
                f.write(json.dumps(r, default=str) + "\n")
        with open(exp_dir / "reference_labels.jsonl", "w") as f:  # EVALUATION ONLY: reference labels and observable baselines per item; never given to a judge
            for p in packets:
                f.write(json.dumps({"trace_key": p["trace_key"], "run_id": p["run_id"], "case_id": p["case_id"], "variant": p.get("variant"), "base_key": p.get("base_key"),
                                    "expected": p.get("expected"), "variant_meta": p.get("variant_meta"), "labels": p["labels"], "baselines": p["baselines"],
                                    "approx_tokens": approx_tokens(p["state"]), "state_sha256": p["state_sha256"]}, default=str) + "\n")
        with open(exp_dir / "packets.jsonl", "w") as f:  # the exact model-facing input of every item (observable content, aliased ids); no labels, no alias map
            for p in packets:
                f.write(json.dumps({"trace_key": p["trace_key"], "state_sha256": p["state_sha256"], "state": p["state"]}, default=str) + "\n")
        with open(REGISTRY_PATH, "a") as f:
            f.write(json.dumps({"experiment_id": exp_id, "name": record["name"], "created_at": record["created_at"], "kind": kind, "experiment_type": KIND_TYPE[judge],
                                "dataset_split": split_label, "num_cases": len(case_ids)}) + "\n")
        ids[judge] = exp_id
    return ids


def load_judgments(experiment_id: str) -> list:
    return [json.loads(line) for line in open(EXPERIMENTS_DIR / experiment_id / "judgments.jsonl") if line.strip()]


def load_experiment_record(experiment_id: str) -> dict:
    return json.loads((EXPERIMENTS_DIR / experiment_id / "experiment.json").read_text())
