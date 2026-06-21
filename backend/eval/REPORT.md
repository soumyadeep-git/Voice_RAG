# Evaluation Report

## Metrics

- Retrieval hit-rate: 100% (7/7)
- Answer groundedness: 100% (7/7)
- Refusal accuracy: 50% (1/2)
- Conflict detection: 0% (0/2)

## Per-question results

| id | type | verdict | retrieval | keywords |
| --- | --- | --- | --- | --- |
| q1 | answerable | grounded | hit | ok |
| q2 | answerable | grounded | hit | ok |
| q3 | answerable | grounded | hit | ok |
| q4 | answerable | partially_grounded | hit | ok |
| q5 | answerable | grounded | hit | ok |
| q6 | conflict | grounded | hit | ok |
| q7 | conflict | grounded | hit | ok |
| q8 | unanswerable | grounded | - | ok |
| q9 | unanswerable | refused | - | ok |

## Failures / weaknesses

- [q6] conflict: verdict=grounded — The laws use both opt-in and opt-out models for using personal data. The CCPA operates on an opt-out model, where a busi
- [q7] conflict: verdict=grounded — The penalties for violations under the CCPA can be up to 2,500 US dollars for each unintentional violation and up to 7,5
- [q8] unanswerable: verdict=grounded — I don't know what India's data protection law is called based on the uploaded documents. These passages discuss the Gene