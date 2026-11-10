# Phase 9A report: verify100_final on verify100

Runs: 72 of 100 cases (missing 28). Cohort sha256 `2618eb094539906b`.

## Engineering targets (spec section 36)

| Target | Required | Measured | Met |
|---|---|---|---|
| valid_registered_tool_name_rate | >= 0.98 | 1.0 | True |
| tool_argument_validity_rate | >= 0.98 | 0.9969 | True |
| first_pass_final_valid_rate | >= 0.95 | 0.9583 | True |
| final_valid_after_one_repair_rate | >= 0.99 | 1.0 | True |
| invented_canonical_ids | == 0 | 0 | True |
| invalid_evidence_references | == 0 | 0 | True |
| entity_aliases_outside_registry | == 0 | 0 | True |
| unrecoverable_contract_failure_rate | <= 0.02 | 0.0 | True |

## Before / after (same cases)

| Metric | Phase 5 historical | Phase 9A |
|---|---:|---:|
| invalid_tool_call_traces | 100.0% (72/72) | 2.8% (2/72) |
| final_repair_required | 100.0% (72/72) | 4.2% (3/72) |
| structured_id_completion | 0.0% (0/72) | 47.2% (34/72) |
| traces_with_a_citation_violation | 0.0% (0/72) | 0.0% (0/72) |
| first_pass_valid_final | 0.0% (0/72) | 95.8% (69/72) |
| contract_failure_visible | 0.0% (0/72) | 0.0% (0/72) |
| valid_registered_tool_name_rate | 83.3% (363/436) | 100.0% (650/650) |
| tool_argument_validity_rate | 87.8% (383/436) | 99.7% (648/650) |

## Protocol detail

```json
{
 "tool_contract": {
  "model_tool_proposals": 650,
  "rejected_proposals": 2,
  "valid_tool_call_rate": {
   "k": 648,
   "n": 650,
   "rate": 0.9969,
   "wilson95": [
    0.9889,
    0.9992
   ]
  },
  "valid_registered_tool_name_rate": {
   "k": 650,
   "n": 650,
   "rate": 1.0,
   "wilson95": [
    0.9941,
    1.0
   ]
  },
  "hallucinated_tool_name_rate": {
   "k": 0,
   "n": 650,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0059
   ]
  },
  "tool_argument_validity_rate": {
   "k": 648,
   "n": 650,
   "rate": 0.9969,
   "wilson95": [
    0.9889,
    0.9992
   ]
  },
  "invalid_argument_rate": {
   "k": 2,
   "n": 650,
   "rate": 0.0031,
   "wilson95": [
    0.0008,
    0.0111
   ]
  },
  "hypothesis_state_rejection_rate": {
   "k": 0,
   "n": 650,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0059
   ]
  },
  "tool_contract_repairs_total": 2,
  "traces_with_a_rejected_proposal": {
   "k": 2,
   "n": 72,
   "rate": 0.0278,
   "wilson95": [
    0.0077,
    0.0957
   ]
  },
  "rejection_codes": {
   "argument_required": 2
  }
 },
 "final_contract": {
  "runs_reaching_finalization": 72,
  "first_pass_final_valid_rate": {
   "k": 69,
   "n": 72,
   "rate": 0.9583,
   "wilson95": [
    0.8845,
    0.9857
   ]
  },
  "first_pass_contract_success_run_level": {
   "k": 67,
   "n": 72,
   "rate": 0.9306,
   "wilson95": [
    0.8475,
    0.97
   ]
  },
  "final_repairs_used": 3,
  "repaired_valid": {
   "k": 3,
   "n": 3,
   "rate": 1.0,
   "wilson95": [
    0.4385,
    1.0
   ]
  },
  "final_valid_after_one_repair_rate": {
   "k": 72,
   "n": 72,
   "rate": 1.0,
   "wilson95": [
    0.9493,
    1.0
   ]
  },
  "final_contract_success_after_repair_run_level": {
   "k": 72,
   "n": 72,
   "rate": 1.0,
   "wilson95": [
    0.9493,
    1.0
   ]
  },
  "unrecoverable_contract_failure_rate": {
   "k": 0,
   "n": 72,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0507
   ]
  },
  "unrecoverable_by_kind": {
   "tool_contract_repair_budget_exhausted": 0,
   "final_contract_failure": 0
  },
  "first_pass_error_codes": {
   "proposed_without_supported_hypothesis": 1,
   "duplicate_evidence": 1,
   "causal_change_not_cited": 1
  }
 },
 "grounding": {
  "references_recounted_independently": {
   "entity_total": 562,
   "evidence_total": 485
  },
  "valid_entity_reference_rate": {
   "k": 562,
   "n": 562,
   "rate": 1.0,
   "wilson95": [
    0.9932,
    1.0
   ]
  },
  "valid_evidence_reference_rate": {
   "k": 485,
   "n": 485,
   "rate": 1.0,
   "wilson95": [
    0.9921,
    1.0
   ]
  },
  "invented_canonical_ids": 0,
  "invalid_evidence_references": 0,
  "entity_aliases_outside_registry": 0
 },
 "completion": {
  "final_status_counts": {
   "DIAGNOSIS_PROPOSED": 32,
   "INSUFFICIENT_EVIDENCE": 40
  },
  "missing_required_field_rate": {
   "k": 0,
   "n": 72,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0507
   ]
  },
  "runs_with_every_selection_null": {
   "k": 38,
   "n": 72,
   "rate": 0.5278,
   "wilson95": [
    0.414,
    0.6387
   ]
  },
  "null_selection_rate_by_field": {
   "issue_category": {
    "k": 38,
    "n": 72,
    "rate": 0.5278,
    "wilson95": [
     0.414,
     0.6387
    ]
   },
   "root_cause": {
    "k": 39,
    "n": 72,
    "rate": 0.5417,
    "wilson95": [
     0.4274,
     0.6517
    ]
   },
   "affected_component": {
    "k": 38,
    "n": 72,
    "rate": 0.5278,
    "wilson95": [
     0.414,
     0.6387
    ]
   },
   "causal_change": {
    "k": 62,
    "n": 72,
    "rate": 0.8611,
    "wilson95": [
     0.7629,
     0.9228
    ]
   },
   "owning_team": {
    "k": 38,
    "n": 72,
    "rate": 0.5278,
    "wilson95": [
     0.414,
     0.6387
    ]
   }
  },
  "diagnosis_proposed_with_a_selection": {
   "k": 32,
   "n": 32,
   "rate": 1.0,
   "wilson95": [
    0.8928,
    1.0
   ]
  }
 },
 "efficiency": {
  "mean_llm_calls": 10.07,
  "mean_total_tokens": 22068,
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
   "WRONG": 69,
   "CORRECT": 3
  },
  "final_outcome_correct": {
   "k": 3,
   "n": 72,
   "rate": 0.0417,
   "wilson95": [
    0.0143,
    0.1155
   ]
  },
  "issue_category": {
   "answered": {
    "k": 34,
    "n": 72,
    "rate": 0.4722,
    "wilson95": [
     0.3613,
     0.586
    ]
   },
   "correct_given_answered": {
    "k": 19,
    "n": 34,
    "rate": 0.5588,
    "wilson95": [
     0.3945,
     0.7112
    ]
   }
  },
  "root_cause_containment": {
   "answered": {
    "k": 33,
    "n": 72,
    "rate": 0.4583,
    "wilson95": [
     0.3483,
     0.5726
    ]
   },
   "correct_given_answered": {
    "k": 5,
    "n": 33,
    "rate": 0.1515,
    "wilson95": [
     0.0665,
     0.3092
    ]
   }
  },
  "component": {
   "answered": {
    "k": 34,
    "n": 72,
    "rate": 0.4722,
    "wilson95": [
     0.3613,
     0.586
    ]
   },
   "correct_given_answered": {
    "k": 16,
    "n": 34,
    "rate": 0.4706,
    "wilson95": [
     0.3145,
     0.6326
    ]
   }
  },
  "causal_change": {
   "answered": {
    "k": 10,
    "n": 72,
    "rate": 0.1389,
    "wilson95": [
     0.0772,
     0.2371
    ]
   },
   "correct_given_answered": {
    "k": 5,
    "n": 10,
    "rate": 0.5,
    "wilson95": [
     0.2366,
     0.7634
    ]
   }
  },
  "owning_team_acceptable": {
   "answered": {
    "k": 34,
    "n": 72,
    "rate": 0.4722,
    "wilson95": [
     0.3613,
     0.586
    ]
   },
   "correct_given_answered": {
    "k": 11,
    "n": 34,
    "rate": 0.3235,
    "wilson95": [
     0.1913,
     0.4916
    ]
   }
  },
  "outcome_by_stratum": {
   "ambiguous": {
    "WRONG": 16
   },
   "clear": {
    "WRONG": 11,
    "CORRECT": 2
   },
   "customer_misdiagnosis": {
    "WRONG": 12
   },
   "dependency": {
    "WRONG": 13,
    "CORRECT": 1
   },
   "low_evidence": {
    "WRONG": 7
   },
   "multi_component": {
    "WRONG": 10
   }
  },
  "abstention_on_insufficient_evidence_cases": {
   "k": 6,
   "n": 7,
   "rate": 0.8571,
   "wilson95": [
    0.4869,
    0.9743
   ]
  },
  "over_abstention_on_sufficient_evidence_cases": {
   "k": 23,
   "n": 50,
   "rate": 0.46,
   "wilson95": [
    0.3297,
    0.596
   ]
  },
  "false_confident_root_cause": 0
 },
 "phase5_historical_same_cases": {
  "note": "Observational only. Phase 6 text matching under-counts correct root causes; a contract-valid wrong diagnosis is still wrong, and a correct answer with invalid references is still contract-invalid.",
  "final_outcome_counts": {
   "WRONG": 54,
   "UNANSWERED": 13,
   "CORRECT": 5
  },
  "final_outcome_correct": {
   "k": 5,
   "n": 72,
   "rate": 0.0694,
   "wilson95": [
    0.03,
    0.1525
   ]
  },
  "issue_category": {
   "answered": {
    "k": 0,
    "n": 72,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0507
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
    "n": 72,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0507
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
    "n": 72,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0507
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
    "n": 72,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0507
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
    "n": 72,
    "rate": 0.0,
    "wilson95": [
     0.0,
     0.0507
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
    "WRONG": 14,
    "UNANSWERED": 2
   },
   "clear": {
    "CORRECT": 3,
    "WRONG": 10
   },
   "customer_misdiagnosis": {
    "WRONG": 9,
    "UNANSWERED": 2,
    "CORRECT": 1
   },
   "dependency": {
    "UNANSWERED": 3,
    "WRONG": 11
   },
   "low_evidence": {
    "UNANSWERED": 4,
    "WRONG": 3
   },
   "multi_component": {
    "CORRECT": 1,
    "WRONG": 7,
    "UNANSWERED": 2
   }
  },
  "abstention_on_insufficient_evidence_cases": {
   "k": 5,
   "n": 7,
   "rate": 0.7143,
   "wilson95": [
    0.3589,
    0.9178
   ]
  },
  "over_abstention_on_sufficient_evidence_cases": {
   "k": 0,
   "n": 50,
   "rate": 0.0,
   "wilson95": [
    0.0,
    0.0714
   ]
  },
  "false_confident_root_cause": 0
 }
}
```