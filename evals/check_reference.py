"""Execute the golden-question reference SQL as app_reader."""

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "evals/golden_questions.csv"
FIELDS = ["id", "question", "category", "reference_sql", "correct_behavior", "source"]
CATEGORIES = {"lookup", "aggregate", "trend", "compare", "should_decline"}


def load_questions():
    with QUESTIONS.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError("Unexpected golden-question columns.")
        questions = list(reader)

    identifiers = set()
    for question in questions:
        if set(question) != set(FIELDS) or any(
            not question[field] or not question[field].strip()
            for field in FIELDS if field != "reference_sql"
        ):
            raise ValueError("Each question must populate every non-SQL column.")
        if question["category"] not in CATEGORIES or question["source"] not in {"baseline", "other"}:
            raise ValueError("Unexpected question category or source.")
        if question["id"] in identifiers:
            raise ValueError("Duplicate golden-question ID.")
        identifiers.add(question["id"])
        sql = (question["reference_sql"] or "").split()
        if question["category"] == "should_decline":
            if sql:
                raise ValueError("Decline questions must have empty reference SQL.")
        elif not sql or sql[0].upper() not in {"SELECT", "WITH"}:
            raise ValueError("Reference SQL must be a SELECT query.")
    baseline = sum(question["source"] == "baseline" for question in questions)
    categories = Counter(question["category"] for question in questions)
    if len(questions) < 15 or baseline < 8 or categories["should_decline"] < 3:
        raise ValueError("Expected at least 15 questions, including 8 baseline and 3 decline.")
    return questions


def check_reference(conn, questions, output=None, previous=None):
    failed = 0
    answers = {}
    declined = 0
    with conn.transaction(force_rollback=True):
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '10s'")
        user, timestamp = conn.execute("SELECT current_user, now()").fetchone()
        if user != "app_reader":
            print("[FAIL] Expected database user app_reader. No references executed.")
            return 1
        print(f"Database user: app_reader | SQL validation started: {timestamp.isoformat()}")

        for question in questions:
            if question["category"] == "should_decline":
                declined += 1
                print(f"[skip] {question['id']}: should_decline, no reference SQL")
                continue
            try:
                # Savepoints let a failed reference roll back without stopping the suite.
                # A prepared query accepts a single SQL statement.
                with conn.transaction():
                    rows = conn.execute(question["reference_sql"], prepare=True).fetchall()
            except psycopg.Error as error:
                print(f"[FAIL] {question['id']}: {type(error).__name__} (SQLSTATE {error.sqlstate})")
                failed += 1
            else:
                if not rows:
                    print(f"[FAIL] {question['id']}: reference returned zero rows")
                    failed += 1
                    continue
                answers[question["id"]] = rows
                print(f"[ok] {question['id']} ({question['category']}): {len(rows)} row(s)")

    print(f"Reference SQL: {len(answers)}/{len(questions) - declined} passed, "
          f"{failed} failed, {declined} decline cases skipped.")
    if not failed:
        # Serialize PostgreSQL numeric values as decimal strings and preserve NULLs.
        normalized = json.loads(json.dumps(answers, default=str))
        if previous is not None:
            if previous.keys() != normalized.keys():
                print("[FAIL] Baseline question IDs differ from this run.")
                return 1
            changed = [key for key, rows in normalized.items() if previous[key] != rows]
            print("Changed reference answers: " + (", ".join(changed) or "none"))
        if output is not None:
            with output.open("x", encoding="utf-8") as file:
                json.dump({"recorded_at": timestamp.isoformat(), "answers": normalized},
                          file, indent=2, ensure_ascii=False)
                file.write("\n")
    print("Scope: SQL execution only.")
    return int(failed != 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save successful answers to a new JSON file.")
    parser.add_argument("--compare", type=Path, help="Compare answers with a saved JSON run.")
    args = parser.parse_args()
    try:
        questions = load_questions()
        previous = json.loads(args.compare.read_text(encoding="utf-8"))["answers"] if args.compare else None
        if previous is not None and not isinstance(previous, dict):
            raise ValueError("Baseline answers must be an object.")
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as error:
        print(f"[FAIL] Golden-question input: {type(error).__name__}.")
        return 1

    load_dotenv(ROOT / ".env")
    url = os.environ.get("APP_DATABASE_URL")
    if not url:
        print("[FAIL] Configure APP_DATABASE_URL privately.")
        return 1
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=10) as conn:
            return check_reference(conn, questions, args.output, previous)
    except (psycopg.Error, ValueError, OSError) as error:
        print(f"[FAIL] Reference check: {type(error).__name__}.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
