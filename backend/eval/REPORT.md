# Evaluation Report

Pipeline model: `llama-3.1-8b-instant` · corpus: `backend/eval/fixtures/`

## Metrics

- Retrieval hit-rate: 89% (8/9)
- Answer groundedness: 89% (8/9)
- Refusal accuracy: 100% (2/2)
- Conflict detection: 0% (0/2)

## Per-question results

| id | type | verdict | retrieval | keywords |
| --- | --- | --- | --- | --- |
| q1 | answerable | grounded | hit | ok |
| q2 | answerable | grounded | hit | ok |
| q3 | answerable | partially_grounded | hit | ok |
| q4 | answerable | conflict | hit | ok |
| q5 | answerable | grounded | hit | ok |
| q6 | answerable | partially_grounded | hit | ok |
| q7 | answerable | partially_grounded | MISS | ok |
| q8 | conflict | grounded | hit | ok |
| q9 | conflict | refused | hit | MISS |
| q10 | unanswerable | refused | - | ok |
| q11 | unanswerable | refused | - | ok |

## Failures / weaknesses

- [q7] answerable: verdict=partially_grounded — The CCPA allows consumers to recover statutory damages of between 100 and 750 US dollars per consumer per incident for u
- [q8] conflict: verdict=grounded — A business must handle at least 100,000 consumers or households annually to fall under the CCPA, according to passage [2
- [q9] conflict: verdict=refused — We don't know the current consumer-count threshold for covered businesses under the CCPA, as the documents disagree.