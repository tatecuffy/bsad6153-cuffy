-- Apply after 003 and 004, before deploying the new sync writer from main.
-- Historical runs keep their IDs and counts. Unknown historical details stay NULL.
BEGIN;
SET LOCAL lock_timeout = '5s';

ALTER TABLE public.sync_runs
    ADD COLUMN records_fetched integer CHECK (records_fetched >= 0),
    ADD COLUMN records_inserted integer GENERATED ALWAYS AS (inserted_count) STORED,
    ADD COLUMN records_updated integer GENERATED ALWAYS AS (updated_count) STORED,
    ADD COLUMN error_message text,
    ADD COLUMN "trigger" text CHECK ("trigger" IN ('schedule', 'manual'));

ALTER TABLE public.sync_runs DROP CONSTRAINT sync_runs_status_check;
UPDATE public.sync_runs SET status = 'failed' WHERE status = 'failure';
ALTER TABLE public.sync_runs ADD CONSTRAINT sync_runs_status_check
    CHECK (status IN ('success', 'partial', 'failed'));

-- Allow the currently deployed writer to finish or log a failure during rollout.
CREATE FUNCTION public.normalize_legacy_sync_status()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.status = 'failure' THEN
        NEW.status := 'failed';
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.normalize_legacy_sync_status() FROM PUBLIC, anon, authenticated;

CREATE TRIGGER normalize_legacy_sync_status
    BEFORE INSERT ON public.sync_runs FOR EACH ROW
    EXECUTE FUNCTION public.normalize_legacy_sync_status();
COMMIT;
