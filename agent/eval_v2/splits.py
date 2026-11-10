"""Deterministic dataset splits (spec section 2) over the 2,500 cases the
Phase 4 graph actually contains. Splitting is stratified on (difficulty
archetype, evidence sufficiency) so no split concentrates one archetype or
evidence-richness level -- a fixed-seed shuffle within each stratum makes
the assignment reproducible without needing to store per-case random state.

Usage:
    python3 -m agent.eval_v2.splits --generate         # refuses if a splits
                                                        # file already exists
    python3 -m agent.eval_v2.splits --generate --force # overwrite (rare;
                                                        # splits are meant to
                                                        # be locked once made)
    python3 -m agent.eval_v2.splits --stats            # print current split
"""
import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from agent.eval_v2.config import SPLIT_PROPORTIONS, SPLIT_SEED, SPLIT_VERSION, SPLITS_DIR
from agent.eval_v2.stratify import stratify_case

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW_V2 = PROJECT_ROOT / "data" / "raw_v2"

SPLITS_PATH = SPLITS_DIR / f"case_splits_{SPLIT_VERSION}.json"
MANIFEST_PATH = SPLITS_DIR / f"split_manifest_{SPLIT_VERSION}.json"


def _graph_case_ids(n_cases: int = 2500) -> list:
    """Reproduces agent/graph_v2/build_graph.py::_small_mode_case_ids exactly
    -- the same deterministic 'first N by sorted case id' selection that
    decided which cases actually exist in the standing Neo4j graph. Splits
    must cover exactly this population, not all 25,000 raw cases."""
    with open(DATA_RAW_V2 / "case_observable.csv", newline="", encoding="utf-8") as f:
        ids = sorted(row["id"] for row in csv.DictReader(f))
    return ids[:n_cases]


def generate_splits(force: bool = False) -> dict:
    if SPLITS_PATH.exists() and not force:
        raise FileExistsError(
            f"{SPLITS_PATH} already exists. Splits are locked once generated -- pass force=True "
            "only if you have an explicit, approved reason to regenerate."
        )

    case_ids = _graph_case_ids()
    strata: dict = defaultdict(list)
    for cid in case_ids:
        strata[stratify_case(cid)["stratum_key"]].append(cid)

    rng = random.Random(SPLIT_SEED)
    assignment: dict = {}
    per_stratum_counts: dict = {}
    for stratum_key, ids in strata.items():
        ids = sorted(ids)
        rng.shuffle(ids)
        n = len(ids)
        n_dev = round(n * SPLIT_PROPORTIONS["dev"])
        n_val = round(n * SPLIT_PROPORTIONS["validation"])
        dev_ids = ids[:n_dev]
        val_ids = ids[n_dev:n_dev + n_val]
        test_ids = ids[n_dev + n_val:]
        for cid in dev_ids:
            assignment[cid] = "dev"
        for cid in val_ids:
            assignment[cid] = "validation"
        for cid in test_ids:
            assignment[cid] = "test"
        per_stratum_counts[stratum_key] = {"dev": len(dev_ids), "validation": len(val_ids), "test": len(test_ids)}

    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SPLITS_PATH, "w") as f:
        json.dump({cid: {"split": split} for cid, split in sorted(assignment.items())}, f, indent=2)

    overall = Counter(assignment.values())
    manifest = {
        "split_version": SPLIT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SPLIT_SEED,
        "proportions": SPLIT_PROPORTIONS,
        "stratification_key": "difficulty_archetype|evidence_sufficiency",
        "num_cases": len(case_ids),
        "overall_counts": dict(overall),
        "per_stratum_counts": per_stratum_counts,
        "locked": True,
        "locked_note": "Do not regenerate without an explicit, documented reason -- prompt/tool/agent "
                       "tuning must never be re-run against a changed split. See docs/EVALUATION_SPLITS.md.",
    }
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def load_splits() -> dict:
    if not SPLITS_PATH.exists():
        raise FileNotFoundError(f"{SPLITS_PATH} does not exist -- run `python3 -m agent.eval_v2.splits --generate` first.")
    with open(SPLITS_PATH) as f:
        raw = json.load(f)
    return {cid: v["split"] for cid, v in raw.items()}


def case_ids_for_split(split: str) -> list:
    splits = load_splits()
    return sorted(cid for cid, s in splits.items() if s == split)


def print_stats():
    splits = load_splits()
    by_split_archetype: dict = defaultdict(Counter)
    for cid, split in splits.items():
        by_split_archetype[split][stratify_case(cid)["difficulty_archetype"]] += 1

    print(f"Total cases split: {len(splits)}")
    for split in ("dev", "validation", "test"):
        total = sum(by_split_archetype[split].values())
        print(f"\n{split} ({total} cases):")
        for archetype, count in sorted(by_split_archetype[split].items()):
            print(f"  {archetype:<28} {count:>5}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()
    if args.generate:
        manifest = generate_splits(force=args.force)
        print(json.dumps(manifest, indent=2))
    if args.stats or not args.generate:
        print_stats()
