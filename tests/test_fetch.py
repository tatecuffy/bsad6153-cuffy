"""Synthetic unit fixtures test behavior; they are never saved as real API data."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from ingest.fetch import (FetchError, fetch_resource, request_page, retry_delay,
                          run, validate_observations)


def page(number=1, total=1, size=100, rows=None):
    """Build a small synthetic World Bank response envelope."""
    return [{"page": number, "pages": (total + size - 1) // size,
             "per_page": size, "total": total},
            [{"id": "USA"}] if rows is None else rows]


def response(payload=None, status=200, headers=None):
    result = Mock(status_code=status, headers=headers or {})
    result.json.return_value = page() if payload is None else payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError("test HTTP error")
    return result


class FetchTests(unittest.TestCase):
    def test_pagination_saves_every_original_page(self):
        first = page(1, 3, 2, [{"id": "USA"}, {"id": "CAN"}])
        last = page(2, 3, 2, [{"id": "MEX"}])
        session = Mock()
        session.get.side_effect = [response(first), response(last)]
        with tempfile.TemporaryDirectory() as folder, patch("ingest.fetch.time.sleep"):
            log = []
            rows = fetch_resource(session, "countries", "/country/USA;CAN;MEX",
                                  {"format": "json", "per_page": 2}, Path(folder), log)
            self.assertEqual([row["id"] for row in rows], ["USA", "CAN", "MEX"])
            self.assertEqual(len(log), 2)
            self.assertEqual(json.loads((Path(folder) / log[1]["file"]).read_text()), last)
        self.assertEqual(session.get.call_args_list[1].kwargs["params"]["page"], 2)

    def test_429_honors_retry_after(self):
        session, sleep = Mock(), Mock()
        session.get.side_effect = [response(status=429, headers={"Retry-After": "2"}), response()]
        request_page(session, "https://example.test", {"page": 1, "per_page": 100}, None, sleep)
        sleep.assert_called_once_with(2.0)

    def test_timeout_connection_and_5xx_retry(self):
        for failure in (requests.Timeout("test"), requests.ConnectionError("test"), response(status=503)):
            with self.subTest(failure=type(failure).__name__):
                session, sleep = Mock(), Mock()
                session.get.side_effect = [failure, response()]
                request_page(session, "https://example.test", {"page": 1, "per_page": 100}, None, sleep)
                self.assertEqual(session.get.call_count, 2)
                self.assertEqual(sleep.call_count, 1)

    def test_retry_exhaustion_is_bounded(self):
        session, sleep = Mock(), Mock()
        session.get.return_value = response(status=500)
        with self.assertRaises(FetchError):
            request_page(session, "https://example.test", {"page": 1, "per_page": 100}, None, sleep)
        self.assertEqual(session.get.call_count, 5)
        self.assertEqual(sleep.call_count, 4)

    def test_404_is_not_retried(self):
        session, sleep = Mock(), Mock()
        session.get.return_value = response(status=404)
        with self.assertRaisesRegex(FetchError, "Permanent"):
            request_page(session, "https://example.test", {"page": 1, "per_page": 100}, None, sleep)
        self.assertEqual(session.get.call_count, 1)
        sleep.assert_not_called()

    def test_bad_json_error_envelope_and_short_page_retry(self):
        bad_json = response()
        bad_json.json.side_effect = ValueError("invalid JSON")
        for bad in (bad_json, response([{"message": "API error"}]),
                    response(page(total=2, rows=[{"id": "USA"}]))):
            with self.subTest(bad=bad):
                session = Mock()
                session.get.side_effect = [bad, response()]
                request_page(session, "https://example.test", {"page": 1, "per_page": 100}, None, Mock())
                self.assertEqual(session.get.call_count, 2)

    def test_changed_totals_wrong_page_and_incomplete_response_fail(self):
        cases = [(page(), (2, 200, None)),
                 (page(number=2), None),
                 (page(total=2, rows=[]), None)]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                session = Mock()
                session.get.return_value = response(payload)
                with self.assertRaises(FetchError):
                    request_page(session, "https://example.test", {"page": 1, "per_page": 100}, expected, Mock())

    def test_duplicate_resource_records_fail(self):
        session = Mock()
        session.get.return_value = response(page(total=2, rows=[{"id": "USA"}, {"id": "USA"}]))
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(FetchError, "Duplicate"):
            fetch_resource(session, "countries", "/country/USA", {"page": 1, "per_page": 100}, Path(folder), [])

    def test_retry_after_http_date_and_long_wait(self):
        self.assertGreaterEqual(retry_delay("invalid", 0), 1)
        self.assertEqual(retry_delay("Thu, 01 Jan 1970 00:00:00 GMT", 0) >= 1, True)
        with self.assertRaises(FetchError):
            retry_delay("120", 0)


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.config = {"indicators": ["TEST"], "start_year": 2010, "end_year": 2026,
                       "minimum_non_missing": 1}
        self.row = {"countryiso3code": "USA", "indicator": {"id": "TEST"},
                    "date": "2010", "value": 0}

    def check(self, rows):
        return validate_observations(rows, {"USA"}, {"TEST"}, self.config)

    def test_null_preserved_and_zero_counts(self):
        missing = dict(self.row, date="2011", value=None)
        self.assertEqual(self.check([self.row, missing]), {"TEST": 1})
        self.assertIsNone(missing["value"])

    def test_duplicate_observations_fail(self):
        with self.assertRaisesRegex(FetchError, "Duplicate"):
            self.check([self.row, self.row])

    def test_missing_values_cannot_satisfy_minimum(self):
        with self.assertRaisesRegex(FetchError, "Fewer"):
            self.check([dict(self.row, value=None)])

    def test_invalid_values_years_and_relationships_fail(self):
        for change in ({"value": ".."}, {"value": float("nan")}, {"value": True},
                       {"date": "2009"}, {"countryiso3code": "XYZ"}):
            with self.subTest(change=change), self.assertRaises(FetchError):
                self.check([dict(self.row, **change)])


class RunTests(unittest.TestCase):
    def test_absent_future_years_are_reported_not_fabricated(self):
        config = {"countries": ["USA"], "indicators": ["TEST"], "source": "2",
                  "start_year": 2010, "end_year": 2026, "per_page": 100,
                  "minimum_non_missing": 1}
        observation = {"countryiso3code": "USA", "indicator": {"id": "TEST"},
                       "date": "2010", "value": 1.5}
        resources = [[{"id": "USA"}], [{"id": "TEST", "source": {"id": "2"}}],
                     [observation]]
        with tempfile.TemporaryDirectory() as folder, patch("ingest.fetch.ROOT", Path(folder)), \
                patch("ingest.fetch.fetch_resource", side_effect=resources), patch("builtins.print"):
            manifest = run(config)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["observation_records"], 1)
            self.assertEqual(manifest["coverage_by_indicator"]["TEST"]["absent_country_year_slots"], 16)
            sample = json.loads((Path(folder) / "data/sample/world_bank_sample.json").read_text())
            self.assertEqual(sample["observations"], [observation])

    def test_failed_run_preserves_previous_sample_and_marks_incomplete(self):
        config = {"countries": ["USA"], "per_page": 100}
        with tempfile.TemporaryDirectory() as folder, patch("ingest.fetch.ROOT", Path(folder)), \
                patch("ingest.fetch.fetch_resource", side_effect=FetchError("test failure")):
            sample = Path(folder) / "data/sample/world_bank_sample.json"
            sample.parent.mkdir(parents=True)
            sample.write_text("previous sample", encoding="utf-8")
            with self.assertRaises(FetchError):
                run(config)
            self.assertEqual(sample.read_text(), "previous sample")
            manifest_path = next((Path(folder) / "data/raw/world_bank").glob("*/manifest.json"))
            self.assertEqual(json.loads(manifest_path.read_text())["status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
