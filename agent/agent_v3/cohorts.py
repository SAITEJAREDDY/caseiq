"""Deterministic dev cohorts for Phase 9A (evaluator-side: reads stratification metadata, which the agent never sees).

Two disjoint cohorts, both drawn from the 300-case Phase 8 dev pool so a historical Phase 5 trace exists for every case (paired before/after):
  iter50   the 50-case contract-iteration cohort
  verify100  the 100-case verification cohort, fixed NOW, before any hardened run, so no verification case is chosen after outcomes are known
Strata are contract-relevant situations, not diagnostic targets. A case takes the first category it matches, in priority order.

    python3 -m agent.agent_v3.cohorts --build     # writes both files once; refuses to overwrite different ids
    python3 -m agent.agent_v3.cohorts --show
"""
import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict

from agent.agent_v3.config import COHORT_DIR, PROJECT_ROOT

SEED = 20260925
POOL_PATH = PROJECT_ROOT / "data" / "eval" / "trace_eval" / "pool_v1.json"
PRIORITY = ("low_evidence", "multi_component", "dependency", "customer_misdiagnosis", "ambiguous", "clear")
QUOTAS = {
    "iter50": {"clear": 12, "ambiguous": 9, "customer_misdiagnosis": 9, "dependency": 9, "multi_component": 6, "low_evidence": 5},
    "verify100": {"clear": 24, "ambiguous": 18, "customer_misdiagnosis": 18, "dependency": 18, "multi_component": 12, "low_evidence": 10},
}
PATHS = {name: COHORT_DIR / f"cohort_{name}_v1.json" for name in QUOTAS}


def _sha(ids) -> str:
    return hashlib.sha256(json.dumps(list(ids)).encode()).hexdigest()


def category(s: dict) -> str:
    flags = {"low_evidence": s["low_evidence"], "multi_component": s["multi_component"], "dependency": s["dependency_driven"],
             "customer_misdiagnosis": s["customer_misdiagnosis"], "ambiguous": s["ambiguous"], "clear": True}
    return next(c for c in PRIORITY if flags[c])


def build() -> dict:
    from agent.eval_v2.splits import case_ids_for_split
    from agent.eval_v2.stratify import stratify_case

    dev = set(case_ids_for_split("dev"))
    pool = sorted(json.loads(POOL_PATH.read_text())["case_ids"])
    if not set(pool) <= dev:
        raise SystemExit("the Phase 8 pool contains a non-dev case; refusing to build cohorts")
    by_cat = defaultdict(list)
    for cid in pool:
        by_cat[category(stratify_case(cid))].append(cid)
    rng = random.Random(SEED)
    for c in by_cat:
        rng.shuffle(by_cat[c])
    out, taken = {}, defaultdict(int)
    for name, quota in QUOTAS.items():
        ids, strata = [], {}
        for c in PRIORITY:
            k = quota[c]
            chosen = by_cat[c][taken[c]: taken[c] + k]
            if len(chosen) < k:
                raise SystemExit(f"not enough {c} cases in the dev pool for {name}: need {k}, have {len(chosen)}")
            taken[c] += k
            ids += chosen
            strata.update({x: c for x in chosen})
        ids = sorted(ids)
        out[name] = {"cohort": name, "version": "v1", "split": "dev", "seed": SEED, "n_cases": len(ids), "quotas": quota, "case_ids": ids,
                     "stratum": {x: strata[x] for x in ids}, "case_ids_sha256": _sha(ids),
                     "source": "data/eval/trace_eval/pool_v1.json (Phase 8 dev pool); historical Phase 5 traces exist for every case",
                     "method": "seeded shuffle within contract-relevant strata (first matching category in priority order "
                               f"{list(PRIORITY)}); iter50 and verify100 are disjoint; fixed before any hardened-agent run"}
    a, b = set(out["iter50"]["case_ids"]), set(out["verify100"]["case_ids"])
    assert not a & b and len(a) == 50 and len(b) == 100
    return out


def write(cohorts: dict) -> None:
    COHORT_DIR.mkdir(parents=True, exist_ok=True)
    for name, c in cohorts.items():
        p = PATHS[name]
        if p.exists():
            if json.loads(p.read_text())["case_ids_sha256"] != c["case_ids_sha256"]:
                raise SystemExit(f"{p.name} exists with different case ids; cohorts are fixed once written")
            continue
        p.write_text(json.dumps(c, indent=1))


def load(name: str) -> dict:
    c = json.loads(PATHS[name].read_text())
    if c["split"] != "dev" or _sha(c["case_ids"]) != c["case_ids_sha256"]:
        raise SystemExit(f"cohort {name} failed its integrity check")
    return c


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.build:
        cohorts = build()
        write(cohorts)
    for name in QUOTAS:
        c = load(name)
        print(name, c["n_cases"], "cases, sha256", c["case_ids_sha256"][:16], dict(Counter(c["stratum"].values())))
