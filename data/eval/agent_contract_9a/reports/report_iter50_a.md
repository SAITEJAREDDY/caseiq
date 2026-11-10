# Phase 9A report: iter50_a on iter50

Runs: 50 of 50 cases (missing 0). Cohort sha256 `ae2b1e6d3a0f08a3`.

## Engineering targets (spec section 36)

| Target | Required | Measured | Met |
|---|---|---|---|
| valid_registered_tool_name_rate | >= 0.98 | 1.0 | True |
| tool_argument_validity_rate | >= 0.98 | 1.0 | True |
| first_pass_final_valid_rate | >= 0.95 | 0.98 | True |
| final_valid_after_one_repair_rate | >= 0.99 | 1.0 | True |
| invented_canonical_ids | == 0 | 0 | True |
| invalid_evidence_references | == 0 | 0 | True |
| entity_aliases_outside_registry | == 0 | 0 | True |
| unrecoverable_contract_failure_rate | <= 0.02 | 0.0 | True |

## Before / after (same cases)

| Metric | Phase 5 historical | Phase 9A |
|---|---:|---:|
| invalid_tool_call_traces | 100.0% (50/50) | 0.0% (0/50) |
| final_repair_required | 100.0% (50/50) | 2.0% (1/50) |
| structured_id_completion | 0.0% (0/50) | 22.0% (11/50) |
| traces_with_a_citation_violation | 0.0% (0/50) | 0.0% (0/50) |
| first_pass_valid_final | 0.0% (0/50) | 98.0% (49/50) |
| contract_failure_visible | 0.0% (0/50) | 0.0% (0/50) |
| valid_registered_tool_name_rate | 83.3% (249/299) | 100.0% (450/450) |
| tool_argument_validity_rate | 87.3% (261/299) | 100.0% (450/450) |

## Protocol detail

```json
{
 "tool_contract": {
  "model_tool_proposals": 450,
  "rejected_proposals": 0,
  "valid_tool_call_rate": {
   "k": 450,
   "n": 450,
   "rate": 1.0,
   "wilson95": [
    0.9915,
    1.0
   ]
  },
  "valid_registered_tool_name_rate": {
   "k": 450,
   "n": 450,
   "rate": 1.0,
   "wilson95": [
    0.9915,
    1.0
   ]
  },
  "hallucinated_tool_name_rate": {
   "k": 0,
   "n": 450,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0085
   ]
  },
  "tool_argument_validity_rate": {
   "k": 450,
   "n": 450,
   "rate": 1.0,
   "wilson95": [
    0.9915,
    1.0
   ]
  },
  "invalid_argument_rate": {
   "k": 0,
   "n": 450,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0085
   ]
  },
  "hypothesis_state_rejection_rate": {
   "k": 0,
   "n": 450,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0085
   ]
  },
  "tool_contract_repairs_total": 0,
  "traces_with_a_rejected_proposal": {
   "k": 0,
   "n": 50,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0714
   ]
  },
  "rejection_codes": {}
 },
 "final_contract": {
  "runs_reaching_finalization": 50,
  "first_pass_final_valid_rate": {
   "k": 49,
   "n": 50,
   "rate": 0.98,
   "wilson95": [
    0.895,
    0.9965
   ]
  },
  "first_pass_contract_success_run_level": {
   "k": 49,
   "n": 50,
   "rate": 0.98,
   "wilson95": [
    0.895,
    0.9965
   ]
  },
  "final_repairs_used": 1,
  "repaired_valid": {
   "k": 1,
   "n": 1,
   "rate": 1.0,
   "wilson95": [
    0.2065,
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
   "proposed_without_supported_hypothesis": 1
  }
 },
 "grounding": {
  "references_recounted_independently": {
   "entity_total": 275,
   "evidence_total": 283
  },
  "valid_entity_reference_rate": {
   "k": 275,
   "n": 275,
   "rate": 1.0,
   "wilson95": [
    0.9862,
    1.0
   ]
  },
  "valid_evidence_reference_rate": {
   "k": 283,
   "n": 283,
   "rate": 1.0,
   "wilson95": [
    0.9866,
    1.0
   ]
  },
  "invented_canonical_ids": 0,
  "invalid_evidence_references": 0,
  "entity_aliases_outside_registry": 0
 },
 "completion": {
  "final_status_counts": {
   "INSUFFICIENT_EVIDENCE": 19,
   "HUMAN_REVIEW_REQUIRED": 20,
   "DIAGNOSIS_PROPOSED": 11
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
   "k": 39,
   "n": 50,
   "rate": 0.78,
   "wilson95": [
    0.6476,
    0.8725
   ]
  },
  "null_selection_rate_by_field": {
   "issue_category": {
    "k": 39,
    "n": 50,
    "rate": 0.78,
    "wilson95": [
     0.6476,
     0.8725
    ]
   },
   "root_cause": {
    "k": 39,
    "n": 50,
    "rate": 0.78,
    "wilson95": [
     0.6476,
     0.8725
    ]
   },
   "affected_component": {
    "k": 39,
    "n": 50,
    "rate": 0.78,
    "wilson95": [
     0.6476,
     0.8725
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
    "k": 39,
    "n": 50,
    "rate": 0.78,
    "wilson95": [
     0.6476,
     0.8725
    ]
   }
  },
  "diagnosis_proposed_with_a_selection": {
   "k": 11,
   "n": 11,
   "rate": 1.0,
   "wilson95": [
    0.7412,
    1.0
   ]
  }
 },
 "efficiency": {
  "mean_llm_calls": 10.02,
  "mean_total_tokens": 21290,
  "mean_executed_steps": 10.18
 }
}
```

## Diagnostic outcomes (observational; not optimised)

```json
{
 "phase9a": {
  "note": "Observational only. Phase 6 text matching under-counts correct root causes; a contract-valid wrong diagnosis is still wrong, and a correct answer with invalid references is still contract-invalid.",
  "final_outcome_counts": {
   "UNANSWERED": 38,
   "WRONG": 12
  },
  "final_outcome_correct": {
   "k": 0,
   "n": 50,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0714
   ]
  },
  "issue_category": {
   "answered": {
    "k": 11,
    "n": 50,
    "rate": 0.22,
    "wilson95": [
     0.1275,
     0.3524
    ]
   },
   "correct_given_answered": {
    "k": 5,
    "n": 11,
    "rate": 0.4545,
    "wilson95": [
     0.2127,
     0.7199
    ]
   }
  },
  "root_cause_containment": {
   "answered": {
    "k": 11,
    "n": 50,
    "rate": 0.22,
    "wilson95": [
     0.1275,
     0.3524
    ]
   },
   "correct_given_answered": {
    "k": 1,
    "n": 11,
    "rate": 0.0909,
    "wilson95": [
     0.0162,
     0.3774
    ]
   }
  },
  "component": {
   "answered": {
    "k": 11,
    "n": 50,
    "rate": 0.22,
    "wilson95": [
     0.1275,
     0.3524
    ]
   },
   "correct_given_answered": {
    "k": 8,
    "n": 11,
    "rate": 0.7273,
    "wilson95": [
     0.4343,
     0.9025
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
    "k": 4,
    "n": 4,
    "rate": 1.0,
    "wilson95": [
     0.5101,
     1.0
    ]
   }
  },
  "owning_team_acceptable": {
   "answered": {
    "k": 11,
    "n": 50,
    "rate": 0.22,
    "wilson95": [
     0.1275,
     0.3524
    ]
   },
   "correct_given_answered": {
    "k": 8,
    "n": 11,
    "rate": 0.7273,
    "wilson95": [
     0.4343,
     0.9025
    ]
   }
  },
  "outcome_by_stratum": {
   "ambiguous": {
    "UNANSWERED": 6,
    "WRONG": 3
   },
   "clear": {
    "UNANSWERED": 9,
    "WRONG": 3
   },
   "customer_misdiagnosis": {
    "UNANSWERED": 5,
    "WRONG": 4
   },
   "dependency": {
    "UNANSWERED": 8,
    "WRONG": 1
   },
   "low_evidence": {
    "UNANSWERED": 5
   },
   "multi_component": {
    "UNANSWERED": 5,
    "WRONG": 1
   }
  },
  "abstention_on_insufficient_evidence_cases": {
   "k": 5,
   "n": 5,
   "rate": 1.0,
   "wilson95": [
    0.5655,
    1.0
   ]
  },
  "over_abstention_on_sufficient_evidence_cases": {
   "k": 12,
   "n": 34,
   "rate": 0.3529,
   "wilson95": [
    0.2149,
    0.5209
   ]
  },
  "false_confident_root_cause": 0
 },
 "phase5_historical_same_cases": {
  "note": "Observational only. Phase 6 text matching under-counts correct root causes; a contract-valid wrong diagnosis is still wrong, and a correct answer with invalid references is still contract-invalid.",
  "final_outcome_counts": {
   "WRONG": 31,
   "UNANSWERED": 17,
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