"""Inspect the migration security contract without running SQL."""

from pathlib import Path
import unittest


MIGRATIONS = Path(__file__).resolve().parents[1] / "db/migrations"


def migration_sql(filename):
    lines = (MIGRATIONS / filename).read_text(encoding="utf-8").splitlines()
    without_comments = " ".join(line.split("--", 1)[0] for line in lines)
    return " ".join(without_comments.split())


class SyncMigrationTests(unittest.TestCase):
    def test_role_setup_matches_deployment_migration(self):
        self.assertEqual(migration_sql("../roles.sql"), migration_sql("004_app_reader.sql"))

    def test_sync_history_enables_rls_and_keeps_api_revocations(self):
        sql = migration_sql("003_sync_runs.sql")
        statements = (
            "BEGIN;",
            "CREATE TABLE public.sync_runs",
            "ALTER TABLE public.sync_runs ENABLE ROW LEVEL SECURITY;",
            "REVOKE ALL ON TABLE public.sync_runs FROM PUBLIC;",
            "REVOKE ALL ON TABLE public.sync_runs FROM anon, authenticated;",
            "COMMIT;",
        )
        positions = [sql.index(statement) for statement in statements]
        self.assertEqual(positions, sorted(positions))

    def test_reader_policy_is_select_only_and_rerun_checks_existing_definition(self):
        sql = migration_sql("004_app_reader.sql")
        policy = "CREATE POLICY sync_runs_app_reader_select ON public.sync_runs"
        self.assertIn("to_regclass('public.sync_runs') AND relrowsecurity", sql)
        self.assertLess(sql.index("AND relrowsecurity"), sql.index("GRANT SELECT"))
        self.assertEqual(sql.count("CREATE POLICY"), 1)
        self.assertIn(f"{policy} AS PERMISSIVE FOR SELECT TO app_reader USING (true);", sql)
        self.assertIn("policyname = 'sync_runs_app_reader_select' ) THEN " + policy, sql)
        self.assertIn("AND permissive = 'PERMISSIVE' AND cmd = 'SELECT'", sql)
        self.assertIn("AND roles = ARRAY['app_reader'::name] AND qual = 'true' AND with_check IS NULL", sql)
        self.assertIn("'INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'", sql)
        self.assertIn("has_any_column_privilege('app_reader', relation, 'INSERT, UPDATE, REFERENCES')", sql)
        self.assertNotIn("DROP POLICY", sql)
