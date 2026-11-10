# Jev vs. LLM primitive baseline

## causal_change

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 89.3% | 84.8% |
| Macro F1 | 0.6867420423448077 | 0.64919288576521 |
| Brier | 0.10165733333333332 | 0.11997333333333333 |
| ECE | 0.10578666666666667 | 0.03546666666666672 |
| False-confident rate | 0.4% | 0.7% |
| Contract failures | 0 | 0 |

## evidence_sufficiency

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 12.4% | 41.9% |
| Macro F1 | 0.13476934531905535 | 0.4189724206203111 |
| Brier | 0.46555466666666667 | 0.29528 |
| ECE | 0.5277066666666667 | 0.44026666666666664 |
| False-confident rate | 4.5% | 0.1% |
| Contract failures | 0 | 0 |

## incident_relationship

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 82.6% | 78.8% |
| Macro F1 | None | None |
| Brier | 0.146125 | 0.17515151515151517 |
| ECE | 0.0834090909090909 | 0.1393939393939394 |
| False-confident rate | 9.1% | 8.3% |
| Contract failures | 0 | 0 |

## issue_category

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 78.4% | 79.3% |
| Macro F1 | 0.7062239082648577 | 0.7476581458462213 |
| Brier | 0.12819013333333334 | 0.15901333333333334 |
| ECE | 0.02968000000000002 | 0.05653333333333336 |
| False-confident rate | 0.9% | 2.7% |
| Contract failures | 0 | 0 |

## owning_team

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 37.6% | 14.5% |
| Macro F1 | 0.26525789073589967 | 0.11600451243407424 |
| Brier | 0.28933373333333334 | 0.5524400000000002 |
| ECE | 0.23876 | 0.6545333333333334 |
| False-confident rate | 5.3% | 0.3% |
| Contract failures | 0 | 0 |

## root_cause

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 37.2% | 20.7% |
| Macro F1 | 0.4055545228102029 | 0.24500469423495902 |
| Brier | 0.2721054666666667 | 0.49998666666666675 |
| ECE | 0.24644000000000002 | 0.5638666666666666 |
| False-confident rate | 2.9% | 1.1% |
| Contract failures | 0 | 0 |
