"""Check reference evaluation rules without connecting to PostgreSQL."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from evals.check_reference import check_reference, load_questions


class ReferenceCheckerTests(TestCase):
    def test_golden_set_matches_rubric(self):
        questions = load_questions()
        self.assertGreaterEqual(len(questions), 15)
        self.assertGreaterEqual(sum(row["source"] == "baseline" for row in questions), 8)
        declines = [row for row in questions if row["category"] == "should_decline"]
        self.assertGreaterEqual(len(declines), 3)
        self.assertTrue(all(row["reference_sql"] == "" for row in declines))

    def test_empty_result_fails_and_decline_does_not_execute(self):
        conn = MagicMock()
        query = MagicMock()
        identity = MagicMock()
        identity.fetchone.return_value = ("app_reader", datetime.now(timezone.utc))
        query.fetchall.return_value = []
        conn.execute.side_effect = [MagicMock(), MagicMock(), identity, query]
        questions = [
            {"id": "Q01", "category": "lookup", "reference_sql": "SELECT 1 WHERE FALSE"},
            {"id": "Q02", "category": "should_decline", "reference_sql": ""},
        ]
        with patch("builtins.print") as report:
            self.assertEqual(check_reference(conn, questions), 1)
        self.assertEqual(conn.execute.call_count, 4)
        report.assert_any_call("[FAIL] Q01: reference returned zero rows")
        report.assert_any_call("[skip] Q02: should_decline, no reference SQL")
