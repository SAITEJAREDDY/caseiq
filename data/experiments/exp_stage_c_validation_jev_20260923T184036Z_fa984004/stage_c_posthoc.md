# Stage C post-hoc analysis

*post-hoc, not pre-registered; never used for the capability classification.*

## Causal change split by whether a true change exists

| System / split | True change exists: n | accuracy [Wilson 95%] | answered `none` | No change: n | accuracy | false positives |
|---|---:|---:|---:|---:|---:|---:|
| Jev validation | 234 | 76.5% [70.7%, 81.5%] | 53 (22.6%) | 516 | 95.2% | 25 |
| LLM validation | 234 | 91.5% [87.2%, 94.4%] | 18 (7.7%) | 516 | 81.8% | 94 |
| Jev dev-100 | 32 | 87.5% [71.9%, 95.0%] | 4 (12.5%) | 68 | 94.1% | 4 |
| LLM dev-100 | 32 | 90.6% [75.8%, 96.8%] | 3 (9.4%) | 68 | 75.0% | 17 |

## Group B cases on validation (true change older than a visible candidate)

- jev: [{"case_id": "CS00405", "true": "CH030527", "predicted": "CH030527", "confidence": 0.91, "n_real_candidates": 3, "correct": true}, {"case_id": "CS00606", "true": "CH030585", "predicted": "CH030585", "confidence": 0.97, "n_real_candidates": 3, "correct": true}, {"case_id": "CS01028", "true": "CH030713", "predicted": "CH030713", "confidence": 0.92, "n_real_candidates": 2, "correct": true}, {"case_id": "CS01393", "true": "CH030822", "predicted": "CH030822", "confidence": 0.94, "n_real_candidates": 2, "correct": true}, {"case_id": "CS02173", "true": "CH031066", "predicted": "CH031066", "confidence": 0.32, "n_real_candidates": 2, "correct": true}, {"case_id": "CS02460", "true": "CH031145", "predicted": "CH031145", "confidence": 0.91, "n_real_candidates": 3, "correct": true}]
- llm: [{"case_id": "CS00405", "true": "CH030527", "predicted": "CH030527", "confidence": 0.8, "n_real_candidates": 3, "correct": true}, {"case_id": "CS00606", "true": "CH030585", "predicted": "CH030585", "confidence": 0.8, "n_real_candidates": 3, "correct": true}, {"case_id": "CS01028", "true": "CH030713", "predicted": "CH030713", "confidence": 0.8, "n_real_candidates": 2, "correct": true}, {"case_id": "CS01393", "true": "CH030822", "predicted": "CH030822", "confidence": 0.8, "n_real_candidates": 2, "correct": true}, {"case_id": "CS02173", "true": "CH031066", "predicted": "CH031066", "confidence": 0.8, "n_real_candidates": 2, "correct": true}, {"case_id": "CS02460", "true": "CH031145", "predicted": "CH031145", "confidence": 0.8, "n_real_candidates": 3, "correct": true}]

## Change-id artifact (JEV-025) on validation versus dev

- validation: {"true_id_range": [30402, 31157], "n_true": 234, "non_true_id_range": [93, 30383], "n_non_true": 382, "non_true_ids_inside_true_range": 0, "cases_with_visible_deployment_candidate": 110, "of_which_true_cause_is_that_deployment": 68}
- dev-100: {"true_id_range": [30400, 30469], "n_true": 32, "non_true_id_range": [1302, 27899], "n_non_true": 48, "non_true_ids_inside_true_range": 0, "cases_with_visible_deployment_candidate": 7, "of_which_true_cause_is_that_deployment": 6}

## Root cause (Jev, validation)

```
{
 "n": 750,
 "by_evidence_quality": {
  "insufficient": {
   "n": 13,
   "accuracy": 0.0,
   "mean_confidence": 0.6584615384615385,
   "true_is_RC40": 0,
   "predicted_RC40": 9,
   "true_answer_offered": 13
  },
  "partially_sufficient": {
   "n": 40,
   "accuracy": 0.0,
   "mean_confidence": 0.6505,
   "true_is_RC40": 0,
   "predicted_RC40": 34,
   "true_answer_offered": 34
  },
  "sufficient": {
   "n": 697,
   "accuracy": 0.40028694404591103,
   "mean_confidence": 0.6158536585365854,
   "true_is_RC40": 0,
   "predicted_RC40": 260,
   "true_answer_offered": 693
  }
 },
 "predicted_RC40": 303,
 "true_RC40": 0,
 "absent_true_answers": {
  "RC20": 2,
  "RC15": 1,
  "RC32": 1,
  "RC17": 1,
  "RC33": 1,
  "RC24": 3,
  "RC38": 1
 },
 "top_predicted": [
  [
   "RC40",
   303
  ],
  [
   "RC28",
   43
  ],
  [
   "RC07",
   36
  ],
  [
   "RC09",
   34
  ],
  [
   "RC22",
   32
  ]
 ],
 "top_true": [
  [
   "RC17",
   78
  ],
  [
   "RC18",
   73
  ],
  [
   "RC14",
   59
  ],
  [
   "RC01",
   42
  ],
  [
   "RC23",
   39
  ]
 ]
}
```

Root cause accuracy dev vs validation: {"jev": {"dev": 0.48, "validation": 0.372}, "llm": {"dev": 0.24, "validation": 0.20666666666666667}}

## Evidence sufficiency predicted classes

```
{
 "jev": {
  "n": 750,
  "predicted_distribution": {
   "partially_sufficient": 651,
   "sufficient": 63,
   "insufficient": 36
  },
  "by_truth": {
   "sufficient": {
    "partially_sufficient": 616,
    "sufficient": 63,
    "insufficient": 18
   },
   "partially_sufficient": {
    "insufficient": 14,
    "partially_sufficient": 26
   },
   "insufficient": {
    "partially_sufficient": 9,
    "insufficient": 4
   }
  }
 },
 "llm": {
  "n": 750,
  "predicted_distribution": {
   "partially_sufficient": 463,
   "sufficient": 275,
   "insufficient": 12
  },
  "by_truth": {
   "sufficient": {
    "partially_sufficient": 423,
    "sufficient": 273,
    "insufficient": 1
   },
   "partially_sufficient": {
    "partially_sufficient": 34,
    "sufficient": 2,
    "insufficient": 4
   },
   "insufficient": {
    "partially_sufficient": 6,
    "insufficient": 7
   }
  }
 }
}
```

## Incident relationship structure

```
{
 "n_decisions": 132,
 "n_distinct_cases": 132,
 "decisions_per_case": {
  "1": 132
 },
 "true_related": 29,
 "true_related_distinct_cases": 29,
 "jev_true_positives": 8,
 "llm_true_positives": 4,
 "jev_high_confidence_errors": 12,
 "jev_high_confidence_errors_that_are_missed_related": 12,
 "discordant_only_jev": 5,
 "discordant_only_llm": 0,
 "mcnemar_exact_p": 0.0625
}
```

## Causal change on non-trivial decisions (a real change was offered)

```
{
 "jev_validation": {
  "n_all": 750,
  "n_only_none_offered": 307,
  "n_nontrivial": 443,
  "correct_nontrivial": 363,
  "accuracy_nontrivial": 0.8194130925507901,
  "wilson_ci": [
   0.780893873207052,
   0.8524401762637225
  ],
  "baseline_always_none_nontrivial": 0.4717832957110609,
  "baseline_newest_change_nontrivial": 0.5146726862302483,
  "confidence_ge_0.90": {
   "n": 400,
   "chose_none": 349,
   "chose_real_change": 51,
   "wrong": 3,
   "only_none_offered": 307
  }
 },
 "llm_validation": {
  "n_all": 750,
  "n_only_none_offered": 307,
  "n_nontrivial": 443,
  "correct_nontrivial": 329,
  "accuracy_nontrivial": 0.7426636568848759,
  "wilson_ci": [
   0.6999891672354817,
   0.7811656760020327
  ],
  "baseline_always_none_nontrivial": 0.4717832957110609,
  "baseline_newest_change_nontrivial": 0.5146726862302483,
  "confidence_ge_0.90": {
   "n": 294,
   "chose_none": 294,
   "chose_real_change": 0,
   "wrong": 5,
   "only_none_offered": 215
  }
 },
 "jev_dev": {
  "n_all": 100,
  "n_only_none_offered": 39,
  "n_nontrivial": 61,
  "correct_nontrivial": 53,
  "accuracy_nontrivial": 0.8688524590163934,
  "wilson_ci": [
   0.761978875735935,
   0.932020038541319
  ],
  "baseline_always_none_nontrivial": 0.47540983606557374,
  "baseline_newest_change_nontrivial": 0.5245901639344263,
  "confidence_ge_0.90": {
   "n": 44,
   "chose_none": 41,
   "chose_real_change": 3,
   "wrong": 0,
   "only_none_offered": 39
  }
 },
 "llm_dev": {
  "n_all": 100,
  "n_only_none_offered": 39,
  "n_nontrivial": 61,
  "correct_nontrivial": 41,
  "accuracy_nontrivial": 0.6721311475409836,
  "wilson_ci": [
   0.5472157118133126,
   0.7766504481827393
  ],
  "baseline_always_none_nontrivial": 0.47540983606557374,
  "baseline_newest_change_nontrivial": 0.5245901639344263,
  "confidence_ge_0.90": {
   "n": 39,
   "chose_none": 39,
   "chose_real_change": 0,
   "wrong": 0,
   "only_none_offered": 30
  }
 }
}
```

## Root cause: abstention (RC40) versus committed answers

```
{
 "jev_validation": {
  "n": 750,
  "true_answer_is_RC40": 0,
  "answered_RC40": 303,
  "answered_RC40_share": 0.404,
  "committed_n": 447,
  "committed_accuracy": 0.6241610738255033,
  "committed_wilson_ci": [
   0.5783817577880046,
   0.6678244485603004
  ]
 },
 "llm_validation": {
  "n": 750,
  "true_answer_is_RC40": 0,
  "answered_RC40": 381,
  "answered_RC40_share": 0.508,
  "committed_n": 369,
  "committed_accuracy": 0.42005420054200543,
  "committed_wilson_ci": [
   0.3707708642865031,
   0.47098499128326166
  ]
 },
 "jev_dev": {
  "n": 100,
  "true_answer_is_RC40": 0,
  "answered_RC40": 43,
  "answered_RC40_share": 0.43,
  "committed_n": 57,
  "committed_accuracy": 0.8421052631578947,
  "committed_wilson_ci": [
   0.726365780957114,
   0.9146430025068315
  ]
 },
 "llm_dev": {
  "n": 100,
  "true_answer_is_RC40": 0,
  "answered_RC40": 56,
  "answered_RC40_share": 0.56,
  "committed_n": 44,
  "committed_accuracy": 0.5454545454545454,
  "committed_wilson_ci": [
   0.4006593217065349,
   0.6829499221314639
  ]
 }
}
```

## Jev `confidence` versus the chosen option's probability (descriptive)

{"n_choice_answers": 3750, "confidence_within_0.02_of_chosen_probability": 976, "confidence_lower": 2774, "confidence_higher": 0}

## Run totals (validation)

```
{
 "jev": {
  "decisions": 3882,
  "total_cost_usd": 0.190574874,
  "latency_ms": {
   "p50": 195.3,
   "p90": 1010.1,
   "p95": 1170.7
  }
 },
 "llm": {
  "decisions": 3882,
  "total_cost_usd": 3.08600136,
  "latency_ms": {
   "p50": 1003.7,
   "p90": 2299.2,
   "p95": 3615.4
  }
 }
}
```
