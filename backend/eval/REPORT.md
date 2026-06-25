# Evaluation Report

Pipeline model: `gpt-oss-120b` · corpus: `backend/eval/fixtures/`

## Metrics

- Retrieval hit-rate: 89% (8/9)
- Answer groundedness: 89% (8/9)
- Refusal accuracy: 100% (2/2)
- Conflict detection: 50% (1/2)

## Per-question results

| id | type | verdict | retrieval | keywords |
| --- | --- | --- | --- | --- |
| q1 | answerable | grounded | hit | ok |
| q2 | answerable | grounded | hit | ok |
| q3 | answerable | grounded | hit | ok |
| q4 | answerable | grounded | hit | ok |
| q5 | answerable | grounded | hit | ok |
| q6 | answerable | grounded | hit | MISS |
| q7 | answerable | unverified | MISS | ok |
| q8 | conflict | conflict | hit | ok |
| q9 | conflict | grounded | hit | ok |
| q10 | unanswerable | refused | - | ok |
| q11 | unanswerable | refused | - | ok |

## Failures / weaknesses

- [q6] answerable: verdict=grounded — The GDPR requires an explicit, freely‑given opt‑in consent before personal data can be processed [2]. The CCPA uses an o
- [q7] answerable: verdict=unverified — The GDPR sets administrative fines that can reach €10 million (or 2 % of global turnover) for less‑serious breaches and 
- [q9] conflict: verdict=grounded — Yes. The original CCPA set the threshold at 50,000 consumers, households or devices [1]. The later version raised it to 