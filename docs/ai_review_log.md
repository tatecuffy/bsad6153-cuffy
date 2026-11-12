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
