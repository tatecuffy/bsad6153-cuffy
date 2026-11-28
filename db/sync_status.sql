-- Run as app_reader. Uses the deployed count columns before and after migration 005.
SELECT max(finished_at) FILTER (WHERE status = 'success') AS last_successful_update,
       count(*) FILTER (WHERE finished_at >= now() - interval '7 days') AS runs_last_7_days,
       coalesce(sum(inserted_count) FILTER (
           WHERE finished_at >= now() - interval '7 days'), 0) AS inserted_last_7_days,
       coalesce(sum(updated_count) FILTER (
           WHERE finished_at >= now() - interval '7 days'), 0) AS updated_last_7_days
FROM public.sync_runs;

SELECT run_id, finished_at, status, inserted_count, updated_count, unchanged_count
FROM public.sync_runs
WHERE finished_at >= now() - interval '7 days'
ORDER BY finished_at DESC, run_id;
