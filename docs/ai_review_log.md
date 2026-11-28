# AI review log

## Milestone 2: Removing the fixed source-ID constraint

### Direct: What we asked Codex to do

We asked Codex to inspect the Milestone 1 repository and propose a PostgreSQL
schema before implementation. After reviewing the proposal, we approved the
three-table design but explicitly requested removal of the constraint that
would restrict `indicators.source_id` to one value.

### Read: What we questioned

Codex originally proposed `source_id integer NOT NULL CHECK (source_id = 2)`
for the indicators table. Source ID 2 matches the selected World Development
Indicators snapshot, but we questioned encoding that current dataset choice
as a permanent database restriction. It would unnecessarily prevent storing
indicators associated with another source identifier.

### Decide: What we changed and why

We rejected `CHECK (source_id = 2)`. The final schema retains:

```sql
source_id integer NOT NULL
```

The revised definition still requires an integer source identifier on every
indicator, while allowing another source ID without changing this column's
constraint. This is more flexible than restricting all future records to
source 2.

This change alone does not provide complete multi-source support. The current
design keeps indicator codes globally unique; supporting overlapping codes
or competing measurements from multiple datasets may require further schema
changes, as documented in `schema.md`.

### Verify: Evidence in the project

- `db/schema.sql` defines `indicators.source_id` as `integer NOT NULL` and
  contains no CHECK restricting it to 2.
- `docs/schema.md` documents the unrestricted required integer and the limits
  of the current design's multi-source support.
- `ingest/load.py` checks indicator metadata and observation-page source IDs
  against the selected snapshot manifest's configured source before insertion.

### Tradeoff

The database now permits integer source IDs beyond the one currently used.
It therefore does not, by itself, establish that a supplied source ID is valid
or that it identifies the expected provider. Source validity must be checked
during ingestion or enforced through a future source reference table and
foreign key.

The existing loader's manifest-consistency checks support ingestion validation;
they are not an independent registry of valid source identifiers. A future
reference table would also need a clearly defined identifier namespace when
adding providers beyond the World Bank.

This entry records the actual source-ID constraint decision only. No additional
AI review decisions are asserted.

## Milestone 3

| Work | Direct and read | Verify | Decide and limitations |
| --- | --- | --- | --- |
| Sync, logging, and schedule | Codex helped build the revision-aware sync, run history, and workflow. The project owner prioritized getting scheduled evidence and confirmed the first manual run. | The owner reported 0 inserted, 0 updated, and 960 unchanged for the manual run. Codex matched three schedule-triggered Actions successes to Supabase by run ID and counts. | Fetch the small configured history and only write changes, so older revisions can be detected. The project stores the latest accepted value and does not keep a complete revision archive. |
| Reader permissions and RLS | The project owner questioned the Supabase RLS warning and requested explicit RLS with a SELECT-only policy. Codex updated the migrations and checker. | The owner confirmed the Data API is disabled and configured the reader credential privately. Codex ran the live reader check and recorded a successful SELECT and SQLSTATE 42501 for both INSERT and DELETE. | Keep RLS and a role-specific SELECT policy. Codex's first local credential setup script had a syntax error. A later retry also depended on Git being on PATH in standalone PowerShell. The owner identified that shell issue and configured the credential privately. |
| Data quality and golden questions | Codex drafted the SQL audit, matched-year comparison, CSV, and reference checker. The owner specified the required audit dimensions and minimum question mix. | Codex ran the audit as the reader and executed all 15 references twice. The runs and actual aggregates are saved in the repository. | Use shared valid years for comparisons and keep NULLs distinct from absent rows. Treat anomaly thresholds as review flags. Reference execution provides no evidence of chatbot answer quality. |
| Break-it testing and handoff | The owner required reproducible, isolated failures and asked Codex to use actual evidence in the handoff. Codex added two tests and checked report links and run history. | Codex ran the mocked timeout and corrupt-input tests, checked the two SQL reference results, and recorded the commands and outcomes. | Use mocks and temporary inputs so scheduled runs and production data are unaffected. These checks do not reproduce a real production outage or test an alert channel. |

Supporting evidence is linked in the [Milestone 3 handoff](milestone3.md).
The student should review the final diff and checklist before submission.

### Follow-up against the full Canvas rubric

After the full instructions were supplied, Codex found that the earlier
golden-question format, run-history fields, and test timing differed from
Canvas. The correction uses the prescribed CSV categories and sources,
checks non-empty SQL results, and saves an actual answer baseline. The original
row-count runs remain documented as historical evidence and do not stand in
for the timed comparison. The new upsert and logging migration were exercised
in an isolated PostgreSQL engine, with expected counts asserted before each
scenario. The deployed schedule and production schema were left untouched
during those isolated checks.

For the final follow-up, Tate asked Codex to verify PR #6 without writing to
production. Codex checked the Actions trigger and outcome, reviewed the
reference checker's read-only transaction, and ran it as `app_reader` after
the two qualifying successes. On November 27 at 6:40 p.m. CST, 12/12 SQL
references passed, three decline cases were skipped, and zero answers changed.
The [evaluation notes](../evals/README.md#follow-up-after-two-successful-scheduled-syncs)
record the run links and the failed November 23 step. The 32 passing local
Python tests are separate from GitHub PR checks, which were absent at verification.
