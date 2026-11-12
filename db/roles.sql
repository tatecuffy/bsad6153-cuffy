-- Milestone 2 PROPOSAL ONLY: not applied or permission-tested.
-- Review docs/access_roles.md before execution. No passwords belong here.
-- Requires separate authorization and a provisioning role with sufficient rights.
-- Deliberately stop if app_reader already exists rather than silently reuse it.

BEGIN;

CREATE ROLE app_reader LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;

GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON TABLE public.countries, public.indicators, public.observations
    TO app_reader;

COMMIT;

-- Configure authentication privately after approval, then store its connection
-- in ignored local APP_DATABASE_URL. No owner connection belongs in the app.
-- No write, sequence, role-membership, or future-table grants are proposed.
-- Later milestones may explicitly extend grants for sync or reviewed proposals.
