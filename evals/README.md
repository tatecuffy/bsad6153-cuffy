# evals/

How you prove your system gives correct answers.

| Week | File | What it does |
|---|---|---|
| 3 | `golden_questions.csv` | 15+ questions with columns `id, question, category, reference_sql, correct_behavior, source` |
| 3 | `check_reference.py` | Runs every reference query as `app_reader` and confirms each one succeeds |
| 5 | `run_evals.py` | Asks your chatbot every golden question; records answer, tool calls, tokens, cost, time, and the reference result |
| 5&ndash;7 | `results/weekN.csv` | One results file per evaluation run, graded by you |

Reference answers are SQL, not fixed values, because your data keeps syncing.

## Milestone 3 Part F reference checks

The [golden-question set](golden_questions.csv) contains 15 questions: nine
baseline, three coverage, and three decline. The decline queries show the
available countries, indicators, or time resolution. The expected responses
explain why that evidence cannot support an exact business forecast, a local
monthly unemployment figure, or a guarantee of profitability.

From the project root, run the [checker](check_reference.py) with
`APP_DATABASE_URL` configured privately for `app_reader`:

```powershell
.venv/Scripts/python.exe -B evals/check_reference.py
```

### Live results on November 22, 2026

| Run start (CST) | Database user | Queries passed | Failed | Exit code |
| --- | --- | ---: | ---: | ---: |
| 9:14:52.813983 p.m. | `app_reader` | 15/15 | 0 | 0 |
| 9:14:56.623237 p.m. | `app_reader` | 15/15 | 0 | 0 |

Both runs returned the same row counts. The start times in UTC were
November 23 at 03:14:52.813983 and 03:14:56.623237.

| IDs | Category | Rows returned per ID, in order, in both runs |
| --- | --- | --- |
| Q01–Q09 | Baseline | 1, 1, 4, 20, 20, 6, 6, 20, 1 |
| Q10–Q12 | Coverage | 1, 1, 3 |
| Q13–Q15 | Decline | 3, 1, 3 |

A pass means PostgreSQL executed the reference query under the reader login.
The row counts describe these runs and may change as data syncs. The
`correct_behavior` column defines how to grade future assistant answers.
No chatbot has been built or tested, so these results provide no evidence
that a chatbot gives correct answers or declines unsupported questions.
