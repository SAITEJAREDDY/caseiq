"""Versioned confidence-threshold selection policy for the locked benchmark.

The policy is applied to VALIDATION decisions only (never to locked data) and
its output is written into locked_benchmark_frozen_v1.json before the locked
split is opened. The locked run then reports how those frozen thresholds
behave; it does not choose or adjust any threshold.

threshold_policy_v1
-------------------
* Confidence is Jev's `confidence` field as delivered (see JEV-032).
* Candidate thresholds are the project's existing grid
  (config.AUTOMATION_THRESHOLDS: 0.70, 0.80, 0.85, 0.90, 0.95). No finer grid,
  so there is little room to fit noise.
* Population: every validation decision of the primitive, except that for
  causal change decisions that offered only `none` are excluded. Those are
  resolved by candidate generation alone and no primitive call would be made
  for them in any runtime use, so they must not inflate coverage (JEV-028).
* Two operating tiers, each defined by a target error `t`:
      standard: t = 5%   strict: t = 2%
  A grid threshold satisfies a tier when, over the decisions at or above it,
      - at least MIN_AUTOMATED decisions (50) fall in the automated subset,
      - the observed error is <= t, and
      - the Wilson 95% upper bound of the error is <= 2 * t.
* For each tier the selected threshold is the LOWEST grid threshold that
  satisfies it (i.e. the highest coverage that still meets the policy). If no
  grid threshold satisfies a tier, no threshold is selected for that tier;
  the policy never relaxes itself to force one.

The tiers and the factor 2 are engineering choices made before the selection
was computed; they are not derived from the data. The selection is therefore
the most permissive validation operating point under a fixed, stated policy,
not the point that makes accuracy look best.
"""
from agent.jev_v2.config import AUTOMATION_THRESHOLDS
from agent.jev_v2.stage_c_report import wilson

POLICY_VERSION = "threshold_policy_v1"
TIERS = {"standard": 0.05, "strict": 0.02}
UPPER_BOUND_FACTOR = 2.0
MIN_AUTOMATED = 50


def is_trivial_causal(record: dict) -> bool:
    """A causal-change decision whose only option is `none` (no visible change to choose)."""
    return (record.get("candidate_meta") or {}).get("num_real_change_candidates", 0) == 0


def selection_population(records: list, decision_type: str) -> list:
    scored = [r for r in records if r["scoring"].get("predicted_confidence") is not None and r["scoring"].get("correct") is not None]
    if decision_type == "causal_change":
        scored = [r for r in scored if not is_trivial_causal(r)]
    return scored


def threshold_table(records: list, decision_type: str) -> list:
    """Coverage, error and Wilson bound at every grid threshold (descriptive; the policy reads this table)."""
    pop = selection_population(records, decision_type)
    rows = []
    for th in AUTOMATION_THRESHOLDS:
        auto = [r for r in pop if r["scoring"]["predicted_confidence"] >= th]
        errors = sum(1 for r in auto if not r["scoring"]["correct"])
        lo, hi = wilson(errors, len(auto)) if auto else (None, None)
        rows.append({"threshold": th, "population": len(pop), "automated": len(auto), "coverage": (len(auto) / len(pop)) if pop else None,
                     "errors": errors, "observed_error": (errors / len(auto)) if auto else None, "error_upper_95": hi})
    return rows


def select(records: list, decision_type: str) -> dict:
    table = threshold_table(records, decision_type)
    out = {"policy_version": POLICY_VERSION, "population": table[0]["population"] if table else 0, "grid_table": table, "tiers": {}}
    for tier, target in TIERS.items():
        ok = [row for row in table if row["automated"] >= MIN_AUTOMATED and row["observed_error"] is not None
              and row["observed_error"] <= target and row["error_upper_95"] <= UPPER_BOUND_FACTOR * target]
        if ok:
            chosen = min(ok, key=lambda r: r["threshold"])
            out["tiers"][tier] = {"target_error": target, "selected_threshold": chosen["threshold"], "validation_coverage": chosen["coverage"],
                                  "validation_automated": chosen["automated"], "validation_errors": chosen["errors"],
                                  "validation_observed_error": chosen["observed_error"], "validation_error_upper_95": chosen["error_upper_95"]}
        else:
            out["tiers"][tier] = {"target_error": target, "selected_threshold": None,
                                  "reason": f"no grid threshold met observed error <= {target:.0%}, Wilson upper bound <= {UPPER_BOUND_FACTOR * target:.0%} and >= {MIN_AUTOMATED} automated decisions on validation"}
    return out
