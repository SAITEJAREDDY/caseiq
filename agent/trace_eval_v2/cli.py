"""Phase 8 command line.

    python3 -m agent.trace_eval_v2.cli check --stage smoke|main     # build every packet, run the leakage guard on all of them, print sizes; no API call
    python3 -m agent.trace_eval_v2.cli run --stage smoke [--resume]  # Stage A: about a dozen traces plus a few variants, both judges
    python3 -m agent.trace_eval_v2.cli run --stage main [--resume]   # the frozen main dev evaluation: the corpus plus its perturbation variants, both judges
    python3 -m agent.trace_eval_v2.cli analyze --jev EXP --llm EXP   # the capability report for two stored experiments

Dev traces only. Nothing here calls the agent, changes a question or label, or touches the validation or locked splits.
"""
import argparse
import json

from agent.trace_eval_v2 import analysis, corpus, experiments
from agent.trace_eval_v2.config import PROJECT_ROOT, TRACE_EVAL_DIR

PREREG = "docs/TRACE_EVAL_PREREGISTRATION.md"
STAGES = {"smoke": {"name": "trace_eval_smoke_v1", "kind": "smoke"}, "main": {"name": "trace_eval_dev_v1", "kind": "engineering"}}
SMOKE_TARGETS = {"P1": 2, "P2": 2, "P3": 2, "P4": 2, "P5": 2, "P6": 2}


def smoke_run_ids(labels: dict, n: int = 12) -> list:
    """Deterministic: the first trace (by run id) matching each needed situation, then the next unused traces up to n."""
    wants = [
        ("clean correct trace", lambda v: v["quadrant"] == "A"),
        ("correct answer, bad process", lambda v: v["quadrant"] == "B" and v["labels"]["support"]["label"] == "UNSUPPORTED"),
        ("correct answer, partial support", lambda v: v["quadrant"] == "B" and v["labels"]["support"]["label"] == "PARTIALLY_SUPPORTED"),
        ("wrong and false-confident", lambda v: v["labels"]["human_review"]["label"] == "PRIORITY_REVIEW" and v["labels"]["missed_evidence"]["label"]),
        ("missed evidence", lambda v: v["labels"]["missed_evidence"]["label"] and not v["labels"]["premature_close"]["label"]),
        ("distractor anchoring", lambda v: v["labels"]["distractor_anchor"]["label"]),
        ("low-evidence case", lambda v: v["stratification"]["evidence_sufficiency"] == "insufficient"),
        ("inconsistent final answer", lambda v: not v["labels"]["final_consistency"]["label"]),
        ("premature conclusion", lambda v: v["labels"]["premature_close"]["label"]),
        ("supported conclusion", lambda v: v["labels"]["support"]["label"] == "SUPPORTED"),
        ("unanswered", lambda v: v["outcome"]["label"] == "UNANSWERED"),
        ("customer misdiagnosis", lambda v: v["stratification"]["customer_misdiagnosis"]),
    ]
    chosen = []
    for _, pred in wants:
        for rid in sorted(labels):
            if rid not in chosen and pred(labels[rid]):
                chosen.append(rid)
                break
    for rid in sorted(labels):
        if len(chosen) >= n:
            break
        if rid not in chosen:
            chosen.append(rid)
    return chosen[:n]


def _stage_items(stage: str) -> list:
    if stage == "smoke":
        ids = smoke_run_ids(corpus.load_labels())
        corpus.assert_dev_only([json.loads(l)["case_id"] for l in open(corpus.CONTEXT_PATH) if json.loads(l)["run_id"] in ids])
        return experiments.build_items(ids, with_variants=True, variant_targets=SMOKE_TARGETS, only_variants_of=ids)
    c = json.loads(corpus.CORPUS_PATH.read_text())
    corpus.assert_dev_only(c["case_ids"])
    return experiments.build_items(c["run_ids"], with_variants=True)


def _extra_config() -> dict:
    from agent.jev_v2 import frozen_config

    path = PROJECT_ROOT / PREREG
    return {"pre_registration": {"path": PREREG, "sha256": frozen_config.sha256_file(path)} if path.exists() else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("check", "run"):
        p = sub.add_parser(name)
        p.add_argument("--stage", choices=list(STAGES), required=True)
        if name == "run":
            p.add_argument("--resume", action="store_true")
            p.add_argument("--judgments", nargs="+", help="run only these judgments (a Stage A re-check of a corrected question)")
            p.add_argument("--name-suffix", default="", help="appended to the experiment name, e.g. b")
    a = sub.add_parser("analyze")
    a.add_argument("--jev", required=True)
    a.add_argument("--llm", required=True)
    a.add_argument("--out-dir")
    args = parser.parse_args()

    if args.cmd == "analyze":
        report = analysis.build(args.jev, args.llm)
        from pathlib import Path

        out = Path(args.out_dir) if args.out_dir else analysis.OUT_DIR / args.jev
        out.mkdir(parents=True, exist_ok=True)
        (out / "trace_eval_report.json").write_text(json.dumps(report, indent=2, default=str))
        (out / "trace_eval_report.md").write_text(analysis.to_markdown(report))
        print(f"wrote {out}")
        return

    stage = STAGES[args.stage]
    items = _stage_items(args.stage)
    packets = experiments.build_packets(items)  # raises LeakageError before any call if any packet or question is not clean
    tokens = sorted(experiments.approx_tokens(p["state"]) for p in packets)
    print(f"{args.stage}: {len(packets)} packets ({sum(1 for p in packets if not p['variant'])} original, {sum(1 for p in packets if p['variant'])} variants); "
          f"approx tokens min/median/max {tokens[0]}/{tokens[len(tokens) // 2]}/{tokens[-1]}; leakage guard passed on every packet and question")
    if args.cmd == "check":
        return
    name = stage["name"] + args.name_suffix
    rows = experiments.run_judgments(packets, name, judgments=args.judgments, resume=args.resume)
    ids = experiments.persist(name, stage["kind"], packets, rows, extra_config=_extra_config())
    print(json.dumps(ids))


if __name__ == "__main__":
    main()
