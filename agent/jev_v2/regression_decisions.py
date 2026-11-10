"""Reuses Phase 6's own fixed 9-case regression suite (spec section 52:
same ecosystem) rather than defining a second, incompatible fixed case
list. See agent/eval_v2/regression_cases.py for how/why these 9 were
picked.
"""
from agent.eval_v2.regression_cases import REGRESSION_CASES, regression_case_ids

__all__ = ["REGRESSION_CASES", "regression_case_ids"]
