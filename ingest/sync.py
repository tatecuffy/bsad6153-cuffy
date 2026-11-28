"""Fetch current World Bank data and sync it to PostgreSQL."""

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from dotenv import dotenv_values

from . import fetch
from .load import ROOT, insert_dimensions, prepare_snapshot


OBSERVATION_EXISTS = """
    SELECT EXISTS (
        SELECT 1 FROM public.observations
        WHERE (country_id, indicator_id, observation_year) = (%s, %s, %s)
    )
"""

UPSERT_OBSERVATION = """
    INSERT INTO public.observations AS stored
        (country_id, indicator_id, observation_year, value, api_unit, decimal_places,
         obs_status, source_retrieved_at, source_last_updated, source_snapshot_id, source_page_file)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (country_id, indicator_id, observation_year) DO UPDATE
    SET value = excluded.value, api_unit = excluded.api_unit,
        decimal_places = excluded.decimal_places, obs_status = excluded.obs_status,
        source_retrieved_at = excluded.source_retrieved_at,
        source_last_updated = excluded.source_last_updated,
        source_snapshot_id = excluded.source_snapshot_id,
        source_page_file = excluded.source_page_file, last_updated_at = now()
    WHERE (stored.value, stored.api_unit, stored.decimal_places, stored.obs_status)
          IS DISTINCT FROM (excluded.value, excluded.api_unit, excluded.decimal_places, excluded.obs_status)
"""


def sync_observations(conn, snapshot):
    """Apply validated rows while the caller holds the sync lock and transaction."""
    _, country_ids, indicator_ids = insert_dimensions(conn, snapshot)
    counts = dict(inserted=0, updated=0, unchanged=0)
    for country, indicator, year, *fields in snapshot.observations:
        key = (country_ids[country], indicator_ids[indicator], year)
        existed = conn.execute(OBSERVATION_EXISTS, key).fetchone()[0]
        if not conn.execute(UPSERT_OBSERVATION, key + tuple(fields)).rowcount:
            counts["unchanged"] += 1
        else:
            counts["updated" if existed else "inserted"] += 1
    return counts


def record_run(conn, run_id, started_at, status, counts, trigger, fetched, error_message=None):
    conn.execute(
        """INSERT INTO public.sync_runs
               (run_id, started_at, finished_at, status,
                inserted_count, updated_count, unchanged_count,
                "trigger", records_fetched, error_message)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (run_id) DO NOTHING""",
        (run_id, started_at, datetime.now(timezone.utc), status,
         counts["inserted"], counts["updated"], counts["unchanged"],
         trigger, fetched, error_message),
    )


def run(database_url, trigger="manual"):
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    stage = "database connection"
    fetched = None
    try:
        with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
            stage = "sync lock"
            # The same session holds the lock from before fetch until disconnect.
            locked = conn.execute("SELECT pg_try_advisory_lock(6153, 3)").fetchone()[0]
            if not locked:
                raise RuntimeError("Another sync holds the database lock.")

            stage = "World Bank fetch"
            config = fetch.load_config(ROOT / "ingest/config.json")
            config["end_year"] = max(config["end_year"], started_at.year)
            manifest = fetch.run(config, write_sample=False)
            fetched = manifest["observation_records"]

            stage = "snapshot validation"
            directory = ROOT / "data/raw/world_bank" / manifest["snapshot_id"]
            snapshot = prepare_snapshot(directory, baseline=False)
            stage = "database transaction"
            with conn.transaction():
                counts = sync_observations(conn, snapshot)
                record_run(conn, run_id, started_at, "success", counts, trigger, fetched)
    except Exception:
        print(f"Sync {run_id} failed during {stage}.")
        try:
            with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
                record_run(conn, run_id, started_at, "failed",
                           dict(inserted=0, updated=0, unchanged=0), trigger, fetched,
                           f"Sync failed during {stage}.")
        except Exception:
            print(f"Could not record failure for sync {run_id} in PostgreSQL.")
        return 1

    print(json.dumps({"run_id": str(run_id), "status": "success", **counts}))
    return 0


def main():
    try:
        url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env").get("DATABASE_URL")
    except Exception:
        print("Could not read local database configuration.")
        return 1
    if not url:
        print("DATABASE_URL is required.")
        return 1
    trigger = "schedule" if os.environ.get("GITHUB_EVENT_NAME") == "schedule" else "manual"
    return run(url, trigger=trigger)


if __name__ == "__main__":
    raise SystemExit(main())
