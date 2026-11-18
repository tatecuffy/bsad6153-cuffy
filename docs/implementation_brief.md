# Milestone 2 implementation brief

## Project and database

The Small Business Economic Data Assistant supports the question: should a
small business review its operating budget based on changing economic conditions?
Milestone 2 implements the PostgreSQL foundation in Supabase; the future AI
assistant, scheduled synchronization, and public data views remain later work.

The database has three related tables: `countries` stores country metadata,
`indicators` stores definitions and source context, and `observations` stores
one returned country–indicator–year record. Identity primary keys, foreign keys,
source-code uniqueness, and a unique observation triple protect relationships
and prevent duplicates. Every table has `first_seen_at` and `last_updated_at`.
See [schema and ER diagram](schema.md).

## Ingestion and verified results

`ingest/load.py` reads complete saved snapshot `20261102T041022160331Z` without
fetching the API. It validates manifest-listed pages and keys, preserves Decimal
precision and source provenance, and inserts parents before observations using
parameterized SQL in one transaction. Returned nulls remain SQL NULL; omitted
combinations create no rows. The default command validates locally; `--load`
is required for a database connection through the command-line entry point.

Prior live verification confirmed 20 countries, three indicators, and 960
observations for 2010–2025: 950 numeric values and ten NULLs, with no duplicate
observation triples or broken foreign keys. The request included 2026, but its
60 combinations were absent. Repeat loading inserted zero rows. A prior
before-and-after comparison verified unchanged records and audit timestamps.
These are recorded results, not claims of another live run during preparation.

All five analytical queries succeeded, returning 20, 20, 120, 6, and 20 rows.
Argentina averaged 3.53% GDP growth in 2021–2025 versus 0.60% in 2015–2025,
with 5.17 percentage points of longer-window volatility. Query 4 excluded
Argentina and the United States because their 2025 inflation values were NULL,
not because the available data established failure of the thresholds.
See [verified findings](query_findings.md).

## Testing and reproducibility

Run `python -B -m unittest discover -s tests -v` in the project environment.
Portable unit tests generate clearly labeled synthetic pages in temporary
directories and use an in-memory database double. They test parsing, missing
values, provenance, duplicate prevention, rollback, and the offline CLI guard.
They never publish synthetic records as economic data or patch production
snapshot counts. The optional full-snapshot integration test retains the
actual-data checks and is skipped when the ignored snapshot is unavailable.
Neither test mode connects to Supabase. Live PostgreSQL behavior was verified
separately as described above.

Submission-preparation verification: all 21 tests passed locally, including the
real-snapshot integration check. In a temporary clean-source copy with no `.env`
or `data/raw`, 20 tests passed and the optional integration check was skipped.
Both runs used the existing installed dependencies; no fresh dependency install
was claimed. Whitespace checks passed, and the candidate-file secret-pattern
scan found no potential matches. Private `.env` files were not read.

## AI review decision

We rejected Codex's proposed `CHECK (source_id = 2)` because it unnecessarily
restricted every indicator to one source identifier. The final column is
`source_id integer NOT NULL`. Ingestion must validate source IDs, or a future
reference table must enforce them. This permits other IDs but does not alone
provide complete multi-source support. See [AI review log](ai_review_log.md).

## Access proposal and limitations

`db/roles.sql` now contains a proposed password-free `app_reader` role with
schema usage and SELECT on the three data tables. It has not been applied or
permission-tested. Private authentication setup and verification of effective
permissions require separate authorization; this requirement remains pending.
See [access-role proposal](access_roles.md).

The data is historical and national, not firm-level evidence. Averages can
hide annual variation; differing windows and missingness affect comparisons.
These descriptive findings establish no causation. Business owners should
compare them with actual expenses, sales, and cash flow. `DO NOTHING` preserves
existing rows but does not apply source revisions. Raw snapshots are ignored
by Git and must be supplied locally for the full integration check. No complete
vintage archive or automated sync is implemented.

## Screencast

[Milestone 2 Loom screencast](https://www.loom.com/share/8d7ebcd1a555424c8294d346c0a7cfa7)
