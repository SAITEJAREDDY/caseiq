# Phase 9A report: iter50_b on iter50

Runs: 50 of 50 cases (missing 0). Cohort sha256 `ae2b1e6d3a0f08a3`.

## Engineering targets (spec section 36)

| Target | Required | Measured | Met |
|---|---|---|---|
| valid_registered_tool_name_rate | >= 0.98 | 1.0 | True |
| tool_argument_validity_rate | >= 0.98 | 0.9956 | True |
| first_pass_final_valid_rate | >= 0.95 | 0.92 | False |
| final_valid_after_one_repair_rate | >= 0.99 | 1.0 | True |
| invented_canonical_ids | == 0 | 0 | True |
| invalid_evidence_references | == 0 | 0 | True |
| entity_aliases_outside_registry | == 0 | 0 | True |
| unrecoverable_contract_failure_rate | <= 0.02 | 0.0 | True |

## Before / after (same cases)

| Metric | Phase 5 historical | Phase 9A |
|---|---:|---:|
| invalid_tool_call_traces | 100.0% (50/50) | 4.0% (2/50) |
| final_repair_required | 100.0% (50/50) | 8.0% (4/50) |
| structured_id_completion | 0.0% (0/50) | 44.0% (22/50) |
| traces_with_a_citation_violation | 0.0% (0/50) | 0.0% (0/50) |
| first_pass_valid_final | 0.0% (0/50) | 92.0% (46/50) |
| contract_failure_visible | 0.0% (0/50) | 0.0% (0/50) |
| valid_registered_tool_name_rate | 83.3% (249/299) | 100.0% (452/452) |
| tool_argument_validity_rate | 87.3% (261/299) | 99.6% (450/452) |

## Protocol detail

```json
{
 "tool_contract": {
  "model_tool_proposals": 452,
  "rejected_proposals": 2,
  "valid_tool_call_rate": {
   "k": 450,
   "n": 452,
   "rate": 0.9956,
   "wilson95": [
    0.984,
    0.9988
   ]
  },
  "valid_registered_tool_name_rate": {
   "k": 452,
   "n": 452,
   "rate": 1.0,
   "wilson95": [
    0.9916,
    1.0
   ]
  },
  "hallucinated_tool_name_rate": {
   "k": 0,
   "n": 452,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0084
   ]
  },
  "tool_argument_validity_rate": {
   "k": 450,
   "n": 452,
   "rate": 0.9956,
   "wilson95": [
    0.984,
    0.9988
   ]
  },
  "invalid_argument_rate": {
   "k": 2,
   "n": 452,
   "rate": 0.0044,
   "wilson95": [
    0.0012,
    0.016
   ]
  },
  "hypothesis_state_rejection_rate": {
   "k": 0,
   "n": 452,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0084
   ]
  },
  "tool_contract_repairs_total": 2,
  "traces_with_a_rejected_proposal": {
   "k": 2,
   "n": 50,
   "rate": 0.04,
   "wilson95": [
    0.011,
    0.1346
   ]
  },
  "rejection_codes": {
   "missing_field": 1,
   "unknown_field": 1,
   "argument_required": 1
  }
 },
 "final_contract": {
  "runs_reaching_finalization": 50,
  "first_pass_final_valid_rate": {
   "k": 46,
   "n": 50,
   "rate": 0.92,
   "wilson95": [
    0.8116,
    0.9685
   ]
  },
  "first_pass_contract_success_run_level": {
   "k": 44,
   "n": 50,
   "rate": 0.88,
   "wilson95": [
    0.7619,
    0.9438
   ]
  },
  "final_repairs_used": 4,
  "repaired_valid": {
   "k": 4,
   "n": 4,
   "rate": 1.0,
   "wilson95": [
    0.5101,
    1.0
   ]
  },
  "final_valid_after_one_repair_rate": {
   "k": 50,
   "n": 50,
   "rate": 1.0,
   "wilson95": [
    0.9286,
    1.0
   ]
  },
  "final_contract_success_after_repair_run_level": {
   "k": 50,
   "n": 50,
   "rate": 1.0,
   "wilson95": [
    0.9286,
    1.0
   ]
  },
  "unrecoverable_contract_failure_rate": {
   "k": 0,
   "n": 50,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0714
   ]
  },
  "unrecoverable_by_kind": {
   "tool_contract_repair_budget_exhausted": 0,
   "final_contract_failure": 0
  },
  "first_pass_error_codes": {
   "proposed_without_supported_hypothesis": 3,
   "duplicate_evidence": 1
  }
 },
 "grounding": {
  "references_recounted_independently": {
   "entity_total": 395,
   "evidence_total": 266
  },
  "valid_entity_reference_rate": {
   "k": 395,
   "n": 395,
   "rate": 1.0,
   "wilson95": [
    0.9904,
    1.0
   ]
  },
  "valid_evidence_reference_rate": {
   "k": 266,
   "n": 266,
   "rate": 1.0,
   "wilson95": [
    0.9858,
    1.0
   ]
  },
  "invented_canonical_ids": 0,
  "invalid_evidence_references": 0,
  "entity_aliases_outside_registry": 0
 },
 "completion": {
  "final_status_counts": {
   "DIAGNOSIS_PROPOSED": 21,
   "INSUFFICIENT_EVIDENCE": 29
  },
  "missing_required_field_rate": {
   "k": 0,
   "n": 50,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0714
   ]
  },
  "runs_with_every_selection_null": {
   "k": 28,
   "n": 50,
   "rate": 0.56,
   "wilson95": [
    0.4231,
    0.6884
   ]
  },
  "null_selection_rate_by_field": {
   "issue_category": {
    "k": 28,
    "n": 50,
    "rate": 0.56,
    "wilson95": [
     0.4231,
     0.6884
    ]
   },
   "root_cause": {
    "k": 28,
    "n": 50,
    "rate": 0.56,
    "wilson95": [
     0.4231,
     0.6884
    ]
   },
   "affected_component": {
    "k": 28,
    "n": 50,
    "rate": 0.56,
    "wilson95": [
     0.4231,
     0.6884
    ]
   },
   "causal_change": {
    "k": 46,
    "n": 50,
    "rate": 0.92,
    "wilson95": [
     0.8116,
     0.9685
    ]
   },
   "owning_team": {
    "k": 29,
    "n": 50,
    "rate": 0.58,
    "wilson95": [
     0.4423,
     0.7063
    ]
   }
  },
  "diagnosis_proposed_with_a_selection": {
   "k": 21,
   "n": 21,
   "rate": 1.0,
   "wilson95": [
    0.8454,
    1.0
   ]
  }
 },
 "efficiency": {
  "mean_llm_calls": 10.12,
  "mean_total_tokens": 21842,
  "mean_executed_steps": 10.06
 }
}
```

## Diagnostic outcomes (observational; not optimised)

```json
{
 "phase9a": {
  "note": "Observational only. Phase 6 text matching under-counts correct root causes; a contract-valid wrong diagnosis is still wrong, and a correct answer with invalid references is still contract-invalid.",
  "final_outcome_counts": {
   "WRONG": 49,
   "CORRECT": 1
  },
  "final_outcome_correct": {
   "k": 1,
   "n": 50,
   "rate": 0.02,
   "wilson95": [
    0.0035,
    0.105
   ]
  },
  "issue_category": {
   "answered": {
    "k": 22,
    "n": 50,
    "rate": 0.44,
    "wilson95": [
     0.3116,
     0.5769
    ]
   },
   "correct_given_answered": {
    "k": 14,
    "n": 22,
    "rate": 0.6364,
    "wilson95": [
     0.4295,
     0.8027
    ]
   }
  },
  "root_cause_containment": {
   "answered": {
    "k": 22,
    "n": 50,
    "rate": 0.44,
    "wilson95": [
     0.3116,
     0.5769
    ]
   },
   "correct_given_answered": {
    "k": 2,
    "n": 22,
    "rate": 0.0909,
    "wilson95": [
     0.0253,
     0.2782
    ]
   }
  },
  "component": {
   "answered": {
    "k": 22,
    "n": 50,
    "rate": 0.44,
    "wilson95": [
     0.3116,
     0.5769
    ]
   },
   "correct_given_answered": {
    "k": 10,
    "n": 22,
    "rate": 0.4545,
    "wilson95": [
     0.2692,
     0.6534
    ]
   }
  },
  "causal_change": {
   "answered": {
    "k": 4,
    "n": 50,
    "rate": 0.08,
    "wilson95": [
     0.0315,
     0.1884
    ]
   },
   "correct_given_answered": {
    "k": 2,
    "n": 4,
    "rate": 0.5,
    "wilson95": [
     0.15,
     0.85
    ]
   }
  },
  "owning_team_acceptable": {
   "answered": {
    "k": 21,
    "n": 50,
    "rate": 0.42,
    "wilson95": [
     0.2937,
     0.5577
    ]
   },
   "correct_given_answered": {
    "k": 11,
    "n": 21,
    "rate": 0.5238,
    "wilson95": [
     0.3237,
     0.7166
    ]
   }
  },
  "outcome_by_stratum": {
   "ambiguous": {
    "WRONG": 8,
    "CORRECT": 1
   },
   "clear": {
    "WRONG": 12
   },
   "customer_misdiagnosis": {
    "WRONG": 9
   },
   "dependency": {
    "WRONG": 9
   },
   "low_evidence": {
    "WRONG": 5
   },
   "multi_component": {
    "WRONG": 6
   }
  },
  "abstention_on_insufficient_evidence_cases": {
   "k": 3,
   "n": 5,
   "rate": 0.6,
   "wilson95": [
    0.2307,
    0.8824
   ]
  },
  "over_abstention_on_sufficient_evidence_cases": {
   "k": 16,
   "n": 34,
   "rate": 0.4706,
   "wilson95": [
    0.3145,
    0.6326
   ]
  },
  "false_confident_root_cause": 0
 },
 "phase5_historical_same_cases": {
  "note": "Observational only. Phase 6 text matching under-counts correct root causes; a contract-valid wrong diagnosis is still wrong, and a correct answer with invalid references is still contract-invalid.",
  "final_outcome_counts": {
   "UNANSWERED": 17,
   "WRONG": 31,
   "CORRECT": 2
  },
  "final_outcome_correct": {
   "k": 2,
   "n": 50,
   "rate": 0.04,
   "wilson95": [
    0.011,
    0.1346
   ]
  },
  "issue_category": {
   "answered": {
    "k": 0,
    "n": 50,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0714
    ]
   },
   "correct_given_answered": {
    "k": 0,
    "n": 0,
    "rate": null,
    "wilson95": [
     null,
     null
    ]
   }
  },
  "root_cause_containment": {
   "answered": {
    "k": 0,
    "n": 50,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0714
    ]
   },
   "correct_given_answered": {
    "k": 0,
    "n": 0,
    "rate": null,
    "wilson95": [
     null,
     null
    ]
   }
  },
  "component": {
   "answered": {
    "k": 0,
    "n": 50,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0714
    ]
   },
   "correct_given_answered": {
    "k": 0,
    "n": 0,
    "rate": null,
    "wilson95": [
     null,
     null
    ]
   }
  },
  "causal_change": {
   "answered": {
    "k": 0,
    "n": 50,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0714
    ]
   },
   "correct_given_answered": {
    "k": 0,
    "n": 0,
    "rate": null,
    "wilson95": [
     null,
     null
    ]
   }
  },
  "owning_team_acceptable": {
   "answered": {
    "k": 0,
    "n": 50,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0714
    ]
   },
   "correct_given_answered": {
    "k": 0,
    "n": 0,
    "rate": null,
    "wilson95": [
     null,
     null
    ]
   }
  },
  "outcome_by_stratum": {
   "ambiguous": {
    "WRONG": 8,
    "UNANSWERED": 1
   },
   "clear": {
    "UNANSWERED": 4,
    "WRONG": 8
   },
   "customer_misdiagnosis": {
    "UNANSWERED": 3,
    "WRONG": 5,
    "CORRECT": 1
   },
   "dependency": {
    "UNANSWERED": 3,
    "WRONG": 6
   },
   "low_evidence": {
    "UNANSWERED": 3,
    "WRONG": 2
   },
   "multi_component": {
    "WRONG": 2,
    "UNANSWERED": 3,
    "CORRECT": 1
   }
  },
  "abstention_on_insufficient_evidence_cases": {
   "k": 3,
   "n": 5,
   "rate": 0.6,
   "wilson95": [
    0.2307,
    0.8824
   ]
  },
  "over_abstention_on_sufficient_evidence_cases": {
   "k": 0,
   "n": 34,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.1015
   ]
  },
  "false_confident_root_cause": 0
 }
}
```