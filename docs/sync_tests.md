# Milestone 3 sync tests and deployment

## Run the offline tests

Run `python -B -m unittest discover -s tests -v` from the repository root.
The tests cover revisions, a new observation, explicit NULL in both directions,
duplicate keys, missing required fields, unchanged reruns, and a failure while
recording success. They use synthetic data and a database double. The optional
Milestone 2 snapshot test uses a saved local snapshot when available. These
tests require no database connection or secrets.
Offline migration tests also inspect the SQL for explicit RLS, API role
revocations, and the reader policy's rerun guard. They do not execute SQL.

## Milestone 3 Part G — break-it tests on November 22, 2026

Commands run from the project root:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests -p test_sync.py -k BreakItTests -v
.venv/Scripts/python.exe -B -m unittest discover -s tests -v
```

| Scenario | Expected behavior | Actual behavior | Result |
| --- | --- | --- | --- |
| Every World Bank request times out | Stop after bounded retries, mark the snapshot incomplete, and avoid any data write. | The real fetch code made five mocked request attempts and scheduled four waits. The temporary manifest was incomplete. The sync returned 1, opened no data-write transaction, and sent the database mock one failure-log insert with zero observation counts. | Pass |
| A snapshot contains text in a numeric observation field | Reject the snapshot before opening the data-write transaction. | The real snapshot validator rejected the synthetic page. The sync returned 1 at snapshot validation, opened no data-write transaction, and sent the database mock one failure-log insert with zero observation counts. | Pass |

The focused run passed **2 of 2** tests. The full suite passed **30 of 30**,
including the existing test that checks the rollback path when success
logging fails. The break-it tests use temporary files and mocked HTTP and
database connections. They check the sync's control flow without measuring
live retry timing or exercising a real PostgreSQL rollback. They did not
modify production data or trigger a GitHub Actions run.

### Golden-question references

The Part F command below passed all 15 reference queries in both runs as
`app_reader`. Q10 and Q11 each returned one row in both runs. On November 22
at 9:17:26 p.m. CST, I also executed the two corresponding `reference_sql`
statements from the CSV directly as `app_reader` in a read-only transaction
to confirm the returned values.

```powershell
.venv/Scripts/python.exe -B evals/check_reference.py
```

| Reference | Expected behavior | Actual SQL result | Result |
| --- | --- | --- | --- |
| Q10 — Argentina and U.S. inflation | Compare only years with numeric values for both countries. | One row in each Part F run. The follow-up confirmed seven shared years, 2018–2024, with averages of 86.29% and 3.61%, respectively, and an unrounded-calculation gap of 82.69 percentage points. | Pass |
| Q11 — U.S. inflation in 2025 | Distinguish a stored NULL from an absent row or a numeric zero. | One row in each Part F run. The follow-up returned `reported_null` and SQL NULL for the rate. | Pass |

The [Part F run record](../evals/README.md#live-results-on-november-22-2026)
and [golden-question CSV](../evals/golden_questions.csv) contain the
execution evidence and reference commands. These checks validate SQL
execution and the two returned results. Chatbot behavior remains untested.

### Rubric follow-up: source revision and back-to-back rerun

On November 22, 2026, I used the PostgreSQL engine in
[PGlite 0.5.4](https://pglite.dev/docs/) in a disposable in-memory database.
The test uses the production upsert and run-history SQL with synthetic
observations. It tests the SQL behavior independently of the network and
Python orchestration. It creates no Supabase rows.

```powershell
node tests/check_sync_sql.mjs "PATH_TO_PGLITE/dist/index.js"
```

| Scenario | Expected | Observed in the local engine | Test sync_runs row |
| --- | --- | --- | --- |
| Simulated source revision | Change the one stored value and record one update. | 2.5 became 3.5 and provenance changed to the revision snapshot. Pass. | ID ending `0002`, success, 1 fetched, 0 inserted, 1 updated, 0 unchanged. |
| Immediate identical rerun | Zero inserts and updates. Preserve accepted value, provenance, and audit time. | The repeated upsert affected zero rows. The recorded value, snapshot, and timestamp stayed the same. Pass. | ID ending `0003`, success, 1 fetched, 0 inserted, 0 updated, 1 unchanged. |
| Rejected history write during a data transaction | Roll back the attempted data change and log failure separately. | The history constraint returned SQLSTATE 23514. The attempted 4.5 value rolled back, leaving 3.5. Pass. | ID ending `0005`, failed, 1 fetched, 0 inserted, 0 updated, 0 unchanged. |

The engine test also verified that migration 005 handled historical and
legacy-writer failure rows, and that `app_reader` could read the resulting rows.

Separately, GitHub did cancel a real scheduled sync step on
[November 21 at 07:23 UTC](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/44878781992).
The next [scheduled run](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/44923002530)
succeeded with 0 inserted, 0 updated, and 960 unchanged, matching Supabase run
`360ed30f-39bc-488b-81cb-f52bc05f1997`. No Supabase row matched the cancelled
interval. A process stopped from outside Python may exit before recording
a failure. This was an observed interruption, not an intentional test.

### Rubric follow-up: golden answers across scheduled syncs

The [corrected baseline](../evals/reference_baseline.json) was captured as
`app_reader` at 10:52:32 p.m. CST on November 22. All 12 non-empty
references passed and the three decline cases were skipped. The original
Part F runs above had no intervening scheduled syncs and retained counts
instead of full answers. See the [follow-up command](../evals/README.md#corrected-reference-set-and-saved-baseline).
The first two qualifying scheduled successes and the November 27 read-only
comparison are documented in the [evaluation notes](../evals/README.md#follow-up-after-two-successful-scheduled-syncs).
All 12 executable references passed, three decline cases were skipped, and
zero reference answers changed.

The sync downloads the configured history and extends the upper bound to the
current year when necessary. It compares records by country, indicator, and
year. It updates values or observation metadata only when they differ, including
changes to or from NULL. An omitted record does not delete a stored observation.
The fetch summary reports missing coverage by indicator. Historical revisions
can be detected in the configured window when the API returns the revised row.
Changes to country and indicator descriptions are outside this sync's update
policy. The existing metadata is retained.

## Deploy in order

1. Verify the intended Supabase project has the three Milestone 2 tables.
   Apply [003_sync_runs.sql](../db/migrations/003_sync_runs.sql), then
   [004_app_reader.sql](../db/migrations/004_app_reader.sql), using an authorized
   database administrator who can manage roles and grants and owns the new
   table. Migration 003 explicitly enables RLS and revokes table privileges
   from `PUBLIC`, `anon`, and `authenticated`. Migration 004 requires RLS
   to be enabled and adds the SELECT-only policy for `app_reader`.
   Run 003 once. If an earlier version was applied, inspect the existing
   table and have its owner enable RLS separately if needed before applying
   004. Keep the existing table and history. Migration 004 can be rerun
   with a matching policy and rolls back if the named policy differs.
2. Set the `app_reader` password privately in Supabase. Configure the app and
   the local ignored `.env` with the `APP_DATABASE_URL` for that role. For the
   shared Session pooler, use the custom role username in the form
   `app_reader.<project-ref>`. Verify the effective access as described below.
3. In the GitHub repository, go to **Settings → Secrets and variables →
   Actions → New repository secret**. Name it `DATABASE_URL` and set its value
   to the approved sync writer's PostgreSQL URL from Supabase's **Connect →
   Session pooler** settings (port 5432). Use TLS, for example with
   `sslmode=require`. Keep the URL out of source files, commands saved in shell
   history, screenshots, and logs. Enable Actions if required by repository
   settings. The sync uses a session-level advisory lock, so use a direct
   connection or the Session pooler for local runs as well.
   Verify the writer's RLS behavior below before enabling scheduled runs.
4. Push the reviewed branch, open the PR, and merge it into `main`. Confirm
   that **Actions → World Bank sync** appears. On `main`, use **Run workflow**
   for a smoke test. Compare the run ID and counts from the job log with the
   database row. A second manual run against unchanged source data should show
   zero inserts and updates.
5. Let the schedule run at 00:17, 08:17, and 16:17 UTC. Confirm that the
   assignment accepts this cadence. Collect three successful runs triggered by
   `schedule`, with at least 48 actual hours between the first and last.
   Record their GitHub links, run IDs, UTC timestamps, and counts below.
   Use the recorded timestamps to calculate the span.

## Verify the read-only role

The migration checks effective SELECT access, table and column write grants,
table ownership, public schema privileges, and role attributes and memberships.
It rolls back if these checks fail. After configuring authentication, connect
as `app_reader` and confirm the following queries work against the intended
database and return the rows visible to the app. If row-level security applies,
check that the returned counts match the expected app-visible data.

As the database administrator, confirm that RLS is enabled and inspect the
policies. Expect `sync_runs_app_reader_select` with command `SELECT`,
roles `{app_reader}`, and no write check. Investigate any additional
policies before relying on the expected access.

```sql
SELECT relrowsecurity AS rls_enabled, relforcerowsecurity AS rls_forced
FROM pg_class WHERE oid = 'public.sync_runs'::regclass;

SELECT policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies WHERE schemaname = 'public' AND tablename = 'sync_runs';

SELECT has_table_privilege('app_reader', 'public.sync_runs', 'SELECT') AS can_read,
       has_any_column_privilege('app_reader', 'public.sync_runs', 'INSERT') AS can_insert,
       has_any_column_privilege('app_reader', 'public.sync_runs', 'UPDATE') AS can_update,
       has_table_privilege('app_reader', 'public.sync_runs', 'DELETE') AS can_delete;
```

Expect `can_read` to be true and the three write checks to be false.
The reader's sync history count should match the administrator's count,
including after the first successful sync when there are rows to compare.

```sql
SELECT current_user;
SELECT count(*) FROM public.countries;
SELECT count(*) FROM public.indicators;
SELECT count(*) FROM public.observations;
SELECT count(*) FROM public.sync_runs;
SELECT max(finished_at) FROM public.sync_runs WHERE status = 'success';
```

In the same reader session, run this controlled permission test. Expect a
permission-denied error on the UPDATE. Roll back the transaction even if the
client stops at that error. If UPDATE succeeds, review the effective grants
before using the role in the app.

```sql
BEGIN;
UPDATE public.observations SET value = value WHERE FALSE;
ROLLBACK;
```

## Verify the sync writer

Both success and failure logging use the same `INSERT ... ON CONFLICT (run_id)
DO NOTHING` statement. The current deployment expects the table owner with
ordinary RLS bypass, or an authorized writer that already has RLS bypass.
Connect as the actual writer and use this read-only check. Expect
`rls_applies` to be false and both privilege checks to be true. The writer
also needs its existing access to update the economic tables.

```sql
SELECT current_user,
       row_security_active('public.sync_runs'::regclass) AS rls_applies,
       has_table_privilege(current_user, 'public.sync_runs', 'INSERT') AS can_insert,
       has_column_privilege(current_user, 'public.sync_runs', 'run_id', 'SELECT') AS can_check_run_id;
```

If RLS applies to a dedicated writer, deploy scoped writer grants and
INSERT and SELECT policies in a separate reviewed migration before using
that credential. The SELECT access is needed for the explicit conflict
target. Keep the reader credential separate.

## Scheduled evidence

On November 22, 2026, I verified three successful GitHub Actions runs with
event `schedule` on `main`. I matched the sync ID and counts in each Actions
log to the corresponding Supabase row read as `app_reader`.

| GitHub Actions run | Actions started (UTC) | Supabase finished (UTC) | Sync run ID | Outcome | Inserted / Updated / Unchanged |
| --- | --- | --- | --- | --- | --- |
| [44576559569](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/44576559569) | 2026-11-19 17:22:53 | 2026-11-19 17:25:55.943075 | `75a55ae1-9b7f-4fa6-9228-121f758e8dd9` | Success | 0 / 0 / 960 |
| [44952645046](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/44952645046) | 2026-11-21 21:39:12 | 2026-11-21 21:40:34.875585 | `9f552548-f28a-4ed3-97f0-81debe9e4b16` | Success | 0 / 0 / 960 |
| [45074589596](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/45074589596) | 2026-11-22 21:53:17 | 2026-11-22 21:55:28.415695 | `397092ca-e978-49d6-8ae1-f934ef673fe3` | Success | 0 / 0 / 960 |

The first and last Actions start times span **76 hours, 30 minutes, and
24 seconds**. In CST they are November 19 at 11:22:53 a.m. and November 22
at 3:53:17 p.m. The separate manual smoke test is excluded.

The [manual smoke test](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/44441644826)
ran after PR #4 was merged. Its database run was
`ca0bfdc8-07ba-4096-bc65-a1ed1bce398a` with 0 inserted, 0 updated, and 960 unchanged.

### Status query and migration rollout

[sync_status.sql](../db/sync_status.sql) reports the latest successful check
and summarizes inserts and updates during the last seven days. At the
November 22, 2026 follow-up, the latest successful finish was
`2026-11-22 21:55:28.415695 UTC` and the seven-day totals were nine runs,
zero inserts, and zero updates. This query works on the deployed schema.

[Migration 005](../db/migrations/005_sync_run_details.sql) adds fetched,
inserted, and updated fields, sanitized
failure information, and the trigger. It preserves historical IDs and
counts and leaves unknown past details NULL. It accepts historical-writer
failure entries during rollout and normalizes their status to `failed`.
This pipeline commits atomically, so it reserves `partial` without emitting
that status. A hard cancellation or database outage can prevent a run row.
#### Production deployment evidence

With the project owner's explicit approval, migration 005 committed on
**November 22, 2026 at 11:12:22 p.m. CST** (November 23 at
`05:12:22.362465 UTC`). An Actions preflight just before deployment found
the deployed workflow active, with zero queued, in-progress, requested,
waiting, or pending runs. The [latest completed run](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/45074589596)
was successful. PostgreSQL also showed no active sync advisory lock before
the change or before commit.

The migration ran in one transaction with a five-second lock timeout and
an immediate availability check for the `sync_runs` table lock. Before
committing, I verified the five new columns, the two generated count
expressions, the status/fetched-count/trigger constraints, and the enabled
compatibility trigger. The nine old history rows retained their original
fields, and previously unrecorded details remained NULL.

The row counts and SHA-256 fingerprints below matched before the migration,
before commit, and after commit. The history fingerprint covers the seven
original fields, ordered by run ID. Each economic fingerprint covers all
stored fields, ordered by primary key.

| Table | Rows | Matching SHA-256 fingerprint |
| --- | ---: | --- |
| countries | 20 | `0783572fde9d877490f778a9db41a1abaf89035d7284d331526bf34bb65d17dc` |
| indicators | 3 | `0cc6d8af9a082055323521f00e7d4daf3e187de5db40129bdd91410a443a50c4` |
| observations | 960 | `02888bd8c1490fbfe1dbd43df6d10b3d327463f9c87e28722beb7b80038dd4d9` |
| sync_runs | 9 | `3918d8cfca0211359eb9219bdcf2fcfd867033cca3be7c3aedea2e90d44a2d0e` |

After commit, a new connection authenticated as `app_reader` and read all
nine history rows and the generated counts. The workflow on `main` continues
to use the earlier compatible writer. The [first qualifying scheduled success](https://github.com/tatecuffy/bsad6153-cuffy/actions/runs/45257238579)
on November 23 shows that the earlier writer ran successfully after migration 005.
After PR #6 is deployed, confirm the
renamed `sync.yml` is visible in Actions and verify its runs separately.

The offline suite passed 32/32 after the migration. The live reader check
again succeeded on SELECT and returned SQLSTATE 42501 for the rollback-only
INSERT and DELETE probes. The read-only quality audit again found 950
numeric values, 10 stored NULLs, 60 absent slots, and no duplicate keys or
orphan references. The post-migration Actions check confirmed the workflow
was active and found no later scheduled success yet.

At 05:16:38 UTC on November 23, a second GitHub check still showed the workflow
active and no post-migration scheduled runs. A read-only query of
`sync_runs` as `app_reader` still returned only the nine pre-migration runs,
with the latest matching Actions run `45074589596`. The
[later Actions evidence and timed comparison](../evals/README.md#follow-up-after-two-successful-scheduled-syncs)
are documented separately.

```sql
SELECT run_id, started_at, finished_at, status,
       inserted_count, updated_count, unchanged_count
FROM public.sync_runs
ORDER BY finished_at DESC;
```

Failure rows have zero committed observation counts. If the runner cannot
connect to Supabase, look for the failed stage and generated run ID in the job
log. A successful sync indicates a recent source check. The newest published
economic observation may still be from a previous year.
