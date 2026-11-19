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

| Actions run link | Sync run ID | Finished at (UTC) | Inserted | Updated | Unchanged |
| --- | --- | --- | --- | --- | --- |
| Pending deployment | | | | | |

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
