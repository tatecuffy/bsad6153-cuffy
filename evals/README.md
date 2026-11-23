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

The [golden-question set](golden_questions.csv) contains 15 questions.
Eight are sourced from the baseline or running list. Three are
`should_decline` cases with empty SQL. Their expected responses explain why
the data cannot support the requested business forecast, local monthly
unemployment figure, or profitability guarantee.

| Baseline IDs | Original evidence |
| --- | --- |
| Q04–Q08 | The five [Milestone 2 business queries](../db/queries.sql). Q06 narrows the unemployment trend to Japan. |
| Q03, Q09, Q11 | The October 31 inflation and combined-indicators entries in the [baseline log](../docs/baseline_log.md). |

From the project root, run the [checker](check_reference.py) with
`APP_DATABASE_URL` configured privately for `app_reader`:

```powershell
.venv/Scripts/python.exe -B evals/check_reference.py
```

### Live results on November 22, 2026

The table below records the original implementation. It ran SQL for the
decline cases and printed row counts. Those two runs were seconds apart and
provide no saved answer baseline or evidence of intervening scheduled syncs.

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

### Corrected reference set and saved baseline

On November 22, 2026 at **10:52:32 p.m. CST** (04:52:32 UTC on November 23),
the corrected checker authenticated as `app_reader`, passed **12/12
non-empty references**, and skipped the three decline cases. The
[saved answers](reference_baseline.json) preserve the actual returned values.

```powershell
.venv/Scripts/python.exe -B evals/check_reference.py --output evals/reference_baseline.json
```

After at least two successful scheduled syncs **after that baseline**,
record their Actions links and run:

```powershell
.venv/Scripts/python.exe -B evals/check_reference.py --compare evals/reference_baseline.json --output evals/reference_followup.json
```

The checker compares answer values and prints the IDs that changed.
The timed follow-up is pending. Earlier equal row counts cannot establish
whether answers changed.

A smoke comparison at 10:59:06 p.m. CST on November 22 passed 12/12,
skipped three, and reported no changed answers. It checked the comparison
feature and took place before two later scheduled runs.

At **11:12:57 p.m. CST on November 22** (November 23 at 05:12:57 UTC),
GitHub reported **zero successful scheduled runs** after the saved baseline.
The workflow remained active. The next nominal schedule slots were
November 23 at 2:17 a.m. and 10:17 a.m. CST. Use the actual completed
scheduled successes to decide when the follow-up qualifies.

A second check at **11:16:38 p.m. CST on November 22** (November 23 at
05:16:38 UTC) again found **zero qualifying scheduled successes**. The
[latest scheduled success](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/45074589596)
started November 22 at 21:53:17 UTC and matched Supabase run
`397092ca-e978-49d6-8ae1-f934ef673fe3`. Both predate the baseline. No
follow-up checker run was performed, so there are no follow-up answer
changes or row-count differences to report.
