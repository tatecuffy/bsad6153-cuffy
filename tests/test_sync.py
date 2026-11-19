"""Offline tests for the sync's validation, change counts, and transaction flow."""

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from ingest.fetch import FetchError, validate_observations
from ingest.load import Snapshot, prepare_snapshot
from ingest.sync import INSERT_OBSERVATION, UPDATE_OBSERVATION, run, sync_observations
from test_load import MemoryConnection, Result, write_synthetic_snapshot


class SyncConnection(MemoryConnection):
    def execute(self, sql, params):
        table = self.tables["observations"]
        if sql == INSERT_OBSERVATION:
            key, fields = params[:3], params[3:]
            if key in table:
                return Result()
            table[key] = fields
            return Result(rowcount=1)
        if sql == UPDATE_OBSERVATION:
            fields, key, compared = params[:8], params[8:11], params[11:]
            if table[key][:4] == compared:
                return Result()
            table[key] = fields
            return Result(rowcount=1)
        return super().execute(sql, params)


def observation(year, value, snapshot_id):
    return ("USA", "FP.CPI.TOTL.ZG", year, value, "", 1, "",
            datetime(2026, 11, 18, tzinfo=timezone.utc), None, snapshot_id, "page.json")


class SyncTests(unittest.TestCase):
    def test_new_revised_null_and_unchanged_observations(self):
        conn = SyncConnection()
        snapshot = Snapshot(
            [("USA", "US", "United States", None, None, None)],
            [("FP.CPI.TOTL.ZG", "Inflation", 2, None, None, "", "annual percent", "annual")],
            [observation(2022, Decimal("1.20"), "first"),
             observation(2023, None, "first"),
             observation(2024, Decimal("3"), "first")],
        )
        self.assertEqual(sync_observations(conn, snapshot),
                         dict(inserted=3, updated=0, unchanged=0))

        snapshot.observations = [
            observation(2022, Decimal("1.2"), "second"),
            observation(2023, Decimal("2.0301"), "second"),
            observation(2024, None, "second"),
            observation(2025, None, "second"),
        ]
        self.assertEqual(sync_observations(conn, snapshot),
                         dict(inserted=1, updated=2, unchanged=1))
        table = conn.tables["observations"]
        for key, fields in table.items():
            if key[2] == 2022:
                self.assertEqual(fields[6], "first")
            else:
                self.assertEqual(fields[6], "second")
                expected = Decimal("2.0301") if key[2] == 2023 else None
                self.assertEqual(fields[0], expected)
        snapshot.observations = [
            observation(row[2], row[3], "third") for row in snapshot.observations
        ]
        self.assertEqual(sync_observations(conn, snapshot),
                         dict(inserted=0, updated=0, unchanged=4))
        self.assertTrue(all(fields[6] != "third" for fields in table.values()))

    def test_duplicate_and_missing_value_are_rejected(self):
        row = dict(countryiso3code="USA", indicator={"id": "X"}, date="2025", value=None)
        config = dict(indicators=["X"], start_year=2025, end_year=2025, minimum_non_missing=0)
        args = ({"USA"}, {"X"}, config)
        with self.assertRaisesRegex(FetchError, "Duplicate observation"):
            validate_observations([row, row], *args)
        del row["value"]
        with self.assertRaisesRegex(FetchError, "missing/invalid fields"):
            validate_observations([row], *args)

    def test_sync_validator_accepts_revised_baseline_count(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / "snapshot"
            write_synthetic_snapshot(folder)
            page = folder / "observations_FP.CPI.TOTL.ZG_page_001.json"
            payload = json.loads(page.read_text(encoding="utf-8"))
            payload[1][0]["value"] = 2.5
            page.write_text(json.dumps(payload), encoding="utf-8")
            path = folder / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["non_missing_total"] += 1
            manifest["non_missing_by_indicator"]["FP.CPI.TOTL.ZG"] += 1
            path.write_text(json.dumps(manifest), encoding="utf-8")
            snapshot = prepare_snapshot(folder, baseline=False)
            self.assertEqual(snapshot.summary()["numeric"], 951)

    @patch("ingest.sync.prepare_snapshot")
    @patch("ingest.sync.fetch.run", return_value={"snapshot_id": "synthetic"})
    @patch("ingest.sync.sync_observations", return_value=dict(inserted=1, updated=0, unchanged=0))
    @patch("ingest.sync.psycopg.connect")
    def test_failed_success_log_rolls_back_and_records_failure_separately(
        self, connect, write_observations, fetch_run, prepare
    ):
        first, second = MagicMock(), MagicMock()
        connect.side_effect = [first, second]
        primary, fallback = first.__enter__.return_value, second.__enter__.return_value
        primary.execute.return_value.fetchone.return_value = (True,)
        primary.execute.side_effect = [primary.execute.return_value, RuntimeError("synthetic")]
        with patch("builtins.print"):
            self.assertEqual(run("synthetic URL"), 1)
        fetch_run.assert_called_once()
        self.assertFalse(fetch_run.call_args.kwargs["write_sample"])
        prepare.assert_called_once()
        write_observations.assert_called_once_with(primary, prepare.return_value)
        self.assertIs(primary.transaction.return_value.__exit__.call_args.args[0], RuntimeError)
        self.assertEqual(fallback.execute.call_args.args[1][3:], ("failure", 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
