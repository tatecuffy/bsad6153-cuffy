"""Check the configured PostgreSQL login without displaying credentials."""

import argparse
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


SELECT_COUNTS = """
    SELECT (SELECT count(*) FROM public.countries),
           (SELECT count(*) FROM public.indicators),
           (SELECT count(*) FROM public.observations),
           (SELECT count(*) FROM public.sync_runs)
"""

WRITE_PROBES = (
    ("INSERT", "INSERT INTO public.observations (value) SELECT NULL::numeric WHERE FALSE"),
    ("DELETE", "DELETE FROM public.observations WHERE FALSE"),
)


def check_reader(conn, verify_permissions=False):
    user = conn.execute("SELECT current_user").fetchone()[0]
    if user != "app_reader":
        print("[FAIL] Expected database user app_reader.")
        return False

    print("     Database user: app_reader")
    countries, indicators, observations, runs = conn.execute(SELECT_COUNTS).fetchone()
    print(f"[ok] SELECT succeeded: countries={countries}, indicators={indicators}, "
          f"observations={observations}, sync_runs={runs}")

    passed = True
    if verify_permissions:
        for operation, statement in WRITE_PROBES:
            try:
                # The statement targets zero rows even if permissions are wrong.
                # The transaction or savepoint is rolled back in either case.
                with conn.transaction(force_rollback=True):
                    conn.execute(statement)
            except psycopg.errors.InsufficientPrivilege as error:
                print(f"[ok] {operation} on public.observations: {error.diag.message_primary} "
                      f"(SQLSTATE {error.sqlstate})")
            else:
                print(f"[FAIL] {operation} was allowed. The probe was rolled back.")
                passed = False
    return passed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", action="store_true", help="Connect using APP_DATABASE_URL.")
    parser.add_argument("--verify-permissions", action="store_true",
                        help="With --app, verify that zero-row INSERT and DELETE probes are denied.")
    args = parser.parse_args(argv)
    if args.verify_permissions and not args.app:
        parser.error("--verify-permissions requires --app")

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    variable = "APP_DATABASE_URL" if args.app else "DATABASE_URL"
    url = os.environ.get(variable)
    if not url:
        print(f"[FAIL] {variable} is not set. Configure it privately using .env.example.")
        return 1

    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=10) as conn:
            print(f"[ok] Connected using {variable}")
            if args.app:
                return 0 if check_reader(conn, args.verify_permissions) else 1
            version, user = conn.execute("SELECT version(), current_user").fetchone()
            print(f"     Database user: {user}")
            print(f"     Server: {version.split(',')[0]}")
    except (psycopg.Error, ValueError) as error:
        # Driver errors can contain sensitive connection details.
        print(f"[FAIL] Database check using {variable}: {type(error).__name__}.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
