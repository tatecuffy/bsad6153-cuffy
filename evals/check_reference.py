"""Execute the golden-question reference SQL as app_reader."""

import csv
import os
from collections import Counter
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "evals/golden_questions.csv"
FIELDS = ["id", "question", "category", "reference_sql", "correct_behavior", "source"]


def load_questions():
    with QUESTIONS.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected golden-question columns.")
        questions = list(reader)

    identifiers = set()
    for question in questions:
        if set(question) != set(FIELDS) or any(not question[field] or not question[field].strip()
                                                for field in FIELDS):
            raise ValueError("Each question must populate all six columns.")
        if question["id"] in identifiers:
            raise ValueError("Duplicate golden-question ID.")
        identifiers.add(question["id"])
        if question["reference_sql"].split()[0].upper() not in {"SELECT", "WITH"}:
            raise ValueError("Reference SQL must be a SELECT query.")
    categories = Counter(question["category"] for question in questions)
    if len(questions) < 15 or categories["baseline"] < 8 or categories["decline"] < 3:
        raise ValueError("Expected at least 15 questions, including 8 baseline and 3 decline.")
    return questions


def check_reference(conn, questions):
    failed = 0
    with conn.transaction(force_rollback=True):
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '10s'")
        user, timestamp = conn.execute("SELECT current_user, now()").fetchone()
        if user != "app_reader":
            print("[FAIL] Expected database user app_reader. No references executed.")
            return 1
        print(f"Database user: app_reader | SQL validation started: {timestamp.isoformat()}")

        for question in questions:
            try:
                # Savepoints let a failed reference roll back without stopping the suite.
                # A prepared query accepts a single SQL statement.
                with conn.transaction():
                    rows = conn.execute(question["reference_sql"], prepare=True).fetchall()
            except psycopg.Error as error:
                print(f"[FAIL] {question['id']}: {type(error).__name__} (SQLSTATE {error.sqlstate})")
                failed += 1
            else:
                print(f"[ok] {question['id']} ({question['category']}): {len(rows)} row(s)")

    print(f"Reference SQL: {len(questions) - failed}/{len(questions)} passed, {failed} failed.")
    print("Scope: SQL execution only.")
    return int(failed != 0)


def main():
    try:
        questions = load_questions()
    except (OSError, ValueError, csv.Error) as error:
        print(f"[FAIL] Golden-question input: {type(error).__name__}.")
        return 1

    load_dotenv(ROOT / ".env")
    url = os.environ.get("APP_DATABASE_URL")
    if not url:
        print("[FAIL] Configure APP_DATABASE_URL privately.")
        return 1
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=10) as conn:
            return check_reference(conn, questions)
    except (psycopg.Error, ValueError) as error:
        print(f"[FAIL] Reference check: {type(error).__name__}.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
