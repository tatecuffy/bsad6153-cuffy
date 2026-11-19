BEGIN;

CREATE TABLE public.sync_runs (
    run_id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL,
    finished_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('success', 'failure')),
    inserted_count integer NOT NULL CHECK (inserted_count >= 0),
    updated_count integer NOT NULL CHECK (updated_count >= 0),
    unchanged_count integer NOT NULL CHECK (unchanged_count >= 0),
    CHECK (finished_at >= started_at),
    CHECK (status = 'success' OR
           (inserted_count = 0 AND updated_count = 0 AND unchanged_count = 0))
);

ALTER TABLE public.sync_runs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.sync_runs FROM PUBLIC;
-- Supabase projects can have explicit default grants to these API roles.
REVOKE ALL ON TABLE public.sync_runs FROM anon, authenticated;

COMMIT;
