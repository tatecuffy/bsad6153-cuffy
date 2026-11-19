"""Fetch current World Bank data and sync it to PostgreSQL."""

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from dotenv import dotenv_values

from . import fetch
from .load import ROOT, insert_dimensions, prepare_snapshot


INSERT_OBSERVATION = """
    INSERT INTO public.observations
        (country_id, indicator_id, observation_year, value, api_unit, decimal_places,
         obs_status, source_retrieved_at, source_last_updated, source_snapshot_id, source_page_file)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (country_id, indicator_id, observation_year) DO NOTHING
"""

UPDATE_OBSERVATION = """
    UPDATE public.observations AS stored
    SET value = %s, api_unit = %s, decimal_places = %s, obs_status = %s,
        source_retrieved_at = %s, source_last_updated = %s,
        source_snapshot_id = %s, source_page_file = %s, last_updated_at = now()
    WHERE (country_id, indicator_id, observation_year) = (%s, %s, %s)
      AND (stored.value, stored.api_unit, stored.decimal_places, stored.obs_status)
          IS DISTINCT FROM (%s, %s, %s, %s)
"""


def sync_observations(conn, snapshot):
    """Apply the validated snapshot inside the caller's transaction."""
    _, country_ids, indicator_ids = insert_dimensions(conn, snapshot)
    counts = dict(inserted=0, updated=0, unchanged=0)
    for country, indicator, year, *fields in snapshot.observations:
        key = (country_ids[country], indicator_ids[indicator], year)
        fields = tuple(fields)
        if conn.execute(INSERT_OBSERVATION, key + fields).rowcount:
            counts["inserted"] += 1
        elif conn.execute(UPDATE_OBSERVATION, fields + key + fields[:4]).rowcount:
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    return counts


def record_run(conn, run_id, started_at, status, counts):
    conn.execute(
        """INSERT INTO public.sync_runs
               (run_id, started_at, finished_at, status,
                inserted_count, updated_count, unchanged_count)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (run_id) DO NOTHING""",
        (run_id, started_at, datetime.now(timezone.utc), status,
         counts["inserted"], counts["updated"], counts["unchanged"]),
    )


def run(database_url):
    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    stage = "database connection"
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

            stage = "snapshot validation"
            directory = ROOT / "data/raw/world_bank" / manifest["snapshot_id"]
            snapshot = prepare_snapshot(directory, baseline=False)
            stage = "database transaction"
            with conn.transaction():
                counts = sync_observations(conn, snapshot)
                record_run(conn, run_id, started_at, "success", counts)
    except Exception:
        print(f"Sync {run_id} failed during {stage}.")
        try:
            with psycopg.connect(database_url, autocommit=True, connect_timeout=10) as conn:
                record_run(conn, run_id, started_at, "failure",
                           dict(inserted=0, updated=0, unchanged=0))
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
    return run(url)


if __name__ == "__main__":
    raise SystemExit(main())
