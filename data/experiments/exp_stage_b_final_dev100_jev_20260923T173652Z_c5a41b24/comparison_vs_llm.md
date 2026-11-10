# Jev vs. LLM primitive baseline

## causal_change

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 92.0% | 80.0% |
| Macro F1 | 0.7821939586645469 | 0.5967213114754099 |
| Brier | 0.128302 | 0.1386 |
| ECE | 0.16220000000000004 | 0.07400000000000004 |
| False-confident rate | 0.0% | 0.0% |
| Contract failures | 0 | 0 |

## evidence_sufficiency

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 14.0% | 43.0% |
| Macro F1 | 0.09308807134894091 | 0.3693992698307335 |
| Brier | 0.45326299999999997 | 0.28519999999999995 |
| ECE | 0.5045000000000001 | 0.434 |
| False-confident rate | 2.0% | 0.0% |
| Contract failures | 0 | 0 |

## incident_relationship

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 70.6% | 82.4% |
| Macro F1 | None | None |
| Brier | 0.20335882352941176 | 0.17176470588235293 |
| ECE | 0.20764705882352938 | 0.15294117647058822 |
| False-confident rate | 5.9% | 11.8% |
| Contract failures | 0 | 0 |

## issue_category

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 73.0% | 76.0% |
| Macro F1 | 0.5869690089919645 | 0.6454746810283142 |
| Brier | 0.189221 | 0.18330000000000002 |
| ECE | 0.09409999999999996 | 0.06900000000000002 |
| False-confident rate | 6.0% | 4.0% |
| Contract failures | 0 | 0 |

## owning_team

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 36.0% | 11.0% |
| Macro F1 | 0.2616258892887834 | 0.059485538615973395 |
| Brier | 0.329488 | 0.5740000000000002 |
| ECE | 0.24519999999999995 | 0.6900000000000001 |
| False-confident rate | 5.0% | 0.0% |
| Contract failures | 0 | 0 |

## root_cause

| Metric | Jev | LLM |
|---|---|---|
| Accuracy | 48.0% | 24.0% |
| Macro F1 | 0.44545081355426186 | 0.19373626373626374 |
| Brier | 0.291977 | 0.4845000000000001 |
| ECE | 0.2405 | 0.5409999999999999 |
| False-confident rate | 3.0% | 0.0% |
| Contract failures | 0 | 0 |
