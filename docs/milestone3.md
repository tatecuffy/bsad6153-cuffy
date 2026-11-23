# Milestone 3 handoff

## Data lineage

1. The **World Bank Indicators API** supplies annual consumer-price inflation,
   modeled unemployment, and real GDP growth for the 20 configured countries.
   The configuration starts at 2010 and the sync extends the upper year to the
   current UTC year when needed.
2. [Ingestion](../ingest/README.md) fetches and validates paginated responses.
   It saves raw pages and a run manifest under ignored `data/raw/world_bank/`.
   GitHub-hosted runners use temporary storage. The workflow currently does
   not upload those raw files as artifacts.
3. [Supabase PostgreSQL](schema.md) stores country and indicator metadata,
   economic observations, and sync history. Each observation has a stable
   country–indicator–year key and keeps a snapshot ID, page filename, and
   retrieval time for the accepted version. The sync inserts new observations
   and updates revisions while preserving unchanged rows. It keeps explicit
   NULLs and retains existing observations omitted by a later response.
4. The [Streamlit starter](../app/streamlit_app.py) uses `app_reader` for the
   freshness query. The reference checker also uses that role. Public dashboard
   views, chatbot answers, and agent behavior are planned for later milestones.
   The current evidence covers the database and SQL, including expected
   behavior for future answers.

The [data dictionary](data_dictionary.md) records indicator definitions and
source attribution. The [Part E audit](data_quality.md) shows missingness,
coverage, and how to compare countries using the same years.

## Freshness and scheduled sync

The deployed GitHub Actions workflow on `main` schedules checks at 00:17,
08:17, and 16:17 UTC and supports manual dispatch. The review branch renames
it to the rubric's [sync.yml](../.github/workflows/sync.yml), with the same
schedule and triggers. The eight-hour cadence is a target. Use the actual start
timestamps and outcomes in the [scheduled-run evidence](sync_tests.md#scheduled-evidence).

The application reads the most recent successful `sync_runs.finished_at`.
The starter caches successful lookups for ten minutes and warns when that
timestamp is more than 24 hours old by default. A recent successful run shows
the source was checked. The latest available annual observation can be from
a prior year or unavailable for a particular country and indicator. The
November 22 audit recorded 2025 as the latest numeric observation year.

## Ownership, failure handling, and alerts

| Responsibility | Owner and action |
| --- | --- |
| Source definitions and publication | The World Bank and the listed indicator providers publish the underlying series. The project maintainer reviews source changes and questionable values before drawing conclusions. |
| Pipeline and database | Tate Cuffy, project owner, reviews workflow failures, maintains Supabase and GitHub configuration, and keeps the sync writer separate from the app reader. |
| Automated failure handling | The fetcher retries transient failures within a fixed limit. Invalid or incomplete input stops before data writes. Data updates and success history commit together. If a run fails, the sync attempts to log a separate failure with zero committed observation counts. |
| Monitoring and response | The maintainer checks GitHub Actions for failed or missing runs and compares run IDs with `sync_runs`. If the job fails before the sync starts or Supabase is unreachable, use the Actions log. After diagnosing and fixing an issue, run a manual smoke test and verify the next scheduled run. |

Current signals are the GitHub Actions job outcome, Supabase run history
when reachable, and the app starter's stale-data warning. Delivery to email,
Slack, or a pager has not been verified. The repository has no custom
notification step. The maintainer is responsible for monitoring until a
notification channel is configured and tested.

## Pull request and submission checklist

Use this checklist with the [repository PR template](../.github/pull_request_template.md).
The items below follow the Part A and E–H requirements supplied by the
project owner and the repository's documented sync and evaluation requirements.

- [ ] **A. Read-only access.** Link [live role evidence](schema.md#milestone-3-part-a-access-verification), including the successful login and SELECT, denied INSERT and DELETE, and owner-confirmed disabled Supabase Data API.
- [ ] **B–D. Sync, logging, and schedule.** Link [the deployed implementation PR](https://github.com/tatecuffy/bsad6153-cuffy/pull/4) and [three scheduled successes](sync_tests.md#scheduled-evidence) with matching Supabase IDs, timestamps, counts, and a span of more than 48 hours.
- [ ] **E. Quality audit.** Link the [dated results](data_quality.md) and [reproducible SQL](../db/quality_checks.sql), including the shared-year Argentina–U.S. inflation comparison.
- [ ] **F. Golden questions.** Link the [15-question CSV](../evals/golden_questions.csv), [reference checker](../evals/check_reference.py), and [two actual runs](../evals/README.md). Describe them as SQL checks.
- [ ] **G. Break-it tests.** Link [the two failure tests and two reference checks](sync_tests.md#milestone-3-part-g--break-it-tests-on-november-22-2026) and include the final local test result.
- [ ] **H. Handoff.** Link this page, the [README](../README.md#milestone-3--automated-sync-and-data-quality), and the [AI review log](ai_review_log.md#milestone-3). Explain which app features are planned.
- [ ] Review the diff and verify screenshots, recordings, and Git changes are free of credentials. Record any further AI review decisions in the PR.
- [ ] Add the Milestone 3 screencast link to the PR and submit the required links in Canvas.

### Final verification on November 22, 2026

- The offline test suite passed 30 of 30.
- The live check authenticated as `app_reader`, read all four tables, and
  received SQLSTATE 42501 for both rollback-only write probes.
- A final read-only run passed all 15 SQL references, repeating the two
  documented Part F passes.
- Local documentation links, the whitespace check, and the candidate-file
  credential-pattern scan passed.

The subsequent full-rubric audit passed 32 offline tests and the isolated
PostgreSQL migration, upsert, rerun, and rollback checks. The corrected
golden set passed all 12 executable references and saved the actual
answers. The three decline cases contain no SQL. The later comparison
required by Canvas still needs two scheduled successes after that baseline.

## Screencast outline — 5 minutes

| Time | Show and explain |
| --- | --- |
| 0:00–0:35 | Open the README, state the small-business budget question, and show the four stages in the lineage above. Explain that the chatbot and dashboard views are future work. |
| 0:35–1:35 | Show the workflow file, cron schedule, and the secret reference that supplies the writer URL. Open Actions and show three scheduled successes over 76 hours. Match one run ID to Supabase, then show `sync_status.sql` and its last-success and seven-day results. |
| 1:35–2:20 | Run the read-only checker and show `app_reader`, successful SELECT, and the DELETE and INSERT denials with SQLSTATE 42501. Show the Data API toggle if the screen contains no credentials. |
| 2:20–3:20 | Open the Part E report and then the SQL. Explain 950 numeric values, 10 NULLs, and 60 absent 2026 slots. Show the seven shared Argentina–U.S. years and explain why pairing the years matters. |
| 3:20–4:20 | Run `check_reference.py`. Show the saved baseline and, when available, the later comparison after two scheduled syncs. Explain a changed answer, or why none did. Show the local source revision or identical-rerun test and its run-history row. |
| 4:20–5:00 | Explain the natural key and edited-value check in the upsert. Close with the 24-hour warning and who responds when a run fails. |

Keep `.env`, password managers, connection dialogs, and secrets settings
closed while recording. Use the saved sanitized outputs if you prefer to keep
the demonstration free of live writes and workflow dispatches.
