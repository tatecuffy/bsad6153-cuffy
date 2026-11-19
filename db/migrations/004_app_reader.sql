BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_class
        WHERE oid = to_regclass('public.sync_runs') AND relrowsecurity
    ) THEN
        RAISE EXCEPTION 'Apply 003_sync_runs.sql and verify RLS before granting reader access';
    END IF;
END;
$$;

-- An existing role must pass the same checks as a newly created role.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_reader') THEN
        CREATE ROLE app_reader LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    END IF;
END;
$$;

GRANT USAGE ON SCHEMA public TO app_reader;
GRANT SELECT ON TABLE public.countries, public.indicators,
    public.observations, public.sync_runs TO app_reader;

-- A failed check rolls back every change above, including role creation.
DO $$
DECLARE
    reader_oid oid;
    relation regclass;
BEGIN
    SELECT oid INTO reader_oid FROM pg_roles
    WHERE rolname = 'app_reader' AND rolcanlogin AND NOT
        (rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);
    IF reader_oid IS NULL OR EXISTS (SELECT FROM pg_auth_members WHERE member = reader_oid) THEN
        RAISE EXCEPTION 'app_reader has unexpected role attributes or memberships';
    END IF;
    IF NOT has_schema_privilege('app_reader', 'public', 'USAGE')
        OR has_schema_privilege('app_reader', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'app_reader has unexpected public schema privileges';
    END IF;
    FOREACH relation IN ARRAY ARRAY[
        'public.countries'::regclass, 'public.indicators'::regclass,
        'public.observations'::regclass, 'public.sync_runs'::regclass
    ] LOOP
        IF NOT has_table_privilege('app_reader', relation, 'SELECT')
            OR has_table_privilege('app_reader', relation, 'SELECT WITH GRANT OPTION')
            OR has_table_privilege('app_reader', relation, 'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')
            OR has_any_column_privilege('app_reader', relation, 'INSERT, UPDATE, REFERENCES')
            OR EXISTS (SELECT FROM pg_class WHERE oid = relation AND relowner = reader_oid) THEN
            RAISE EXCEPTION 'app_reader has unexpected privileges on %', relation;
        END IF;
    END LOOP;
END;
$$;

-- Keep an existing matching policy. Fail closed if the named policy was changed.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'sync_runs'
            AND policyname = 'sync_runs_app_reader_select'
    ) THEN
        CREATE POLICY sync_runs_app_reader_select ON public.sync_runs
            AS PERMISSIVE FOR SELECT TO app_reader USING (true);
    END IF;
    IF NOT EXISTS (
        SELECT FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'sync_runs'
            AND policyname = 'sync_runs_app_reader_select'
            AND permissive = 'PERMISSIVE' AND cmd = 'SELECT'
            AND roles = ARRAY['app_reader'::name]
            AND qual = 'true' AND with_check IS NULL
    ) THEN
        RAISE EXCEPTION 'sync_runs_app_reader_select has an unexpected definition';
    END IF;
END;
$$;

COMMIT;
