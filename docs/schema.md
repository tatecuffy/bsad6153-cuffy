# Milestone 2 database design

This document describes `../db/schema.sql`, which has been applied and verified
in Supabase. The saved snapshot was successfully loaded: 20 countries, three
indicators, and 960 observations (950 numeric values and ten NULL values).
All five analytical queries executed successfully; results are documented in
`query_findings.md`. These statements report prior verification, not a new run.

## Relationships and row meanings

```mermaid
erDiagram
    COUNTRIES ||--o{ OBSERVATIONS : has
    INDICATORS ||--o{ OBSERVATIONS : measures
    COUNTRIES {
        bigint country_id PK
        text iso3_code UK
        text iso2_code
        text name
        text region_code
        text income_level_code
        text capital_city
        timestamptz first_seen_at
        timestamptz last_updated_at
    }
    INDICATORS {
        bigint indicator_id PK
        text indicator_code UK
        text name
        integer source_id
        text source_organization
        text source_note
        text api_unit
        text measurement_unit
        text frequency
        timestamptz first_seen_at
        timestamptz last_updated_at
    }
    OBSERVATIONS {
        bigint observation_id PK
        bigint country_id FK
        bigint indicator_id FK
        integer observation_year
        numeric value
        text api_unit
        integer decimal_places
        text obs_status
        timestamptz source_retrieved_at
        date source_last_updated
        text source_snapshot_id
        text source_page_file
        timestamptz first_seen_at
        timestamptz last_updated_at
    }
```

Observations additionally have a composite UNIQUE constraint on
`(country_id, indicator_id, observation_year)`. Neither foreign key is unique
individually.

| Table | Meaning of one row | Example |
|---|---|---|
| `countries` | Current downloaded descriptive metadata for one selected country. | United States, source code `USA`. |
| `indicators` | One annual indicator definition with source and unit context. | `FP.CPI.TOTL.ZG`, annual consumer-price inflation. |
| `observations` | Latest accepted returned record for one country, indicator, and measurement year, including a genuinely missing value. | USA / inflation / 2020. |

Each observation references exactly one country and one indicator. Each parent
may have zero or many observations. `ON DELETE RESTRICT` prevents deleting a
parent while observations still reference it.

## Keys, types, and constraints

All primary keys are `bigint GENERATED ALWAYS AS IDENTITY`. Source identifiers
remain required and unique as `iso3_code` and `indicator_code`. The loader
must resolve source `countryiso3code` (`USA`) to country metadata, rather than
joining the nested observation `country.id` (`US`) to the ISO3 key.

Country ISO3 codes must be three uppercase letters. Optional ISO2 codes may be
NULL, blank, or two uppercase letters. Descriptive metadata are nullable so
incomplete labels do not discard usable measurements. Preserve blank API
metadata strings; they do not imply zero or a missing observation.

Indicator `source_id` is an **integer NOT NULL without a fixed-source CHECK**.
The selected snapshot uses source 2, but the schema does not require that value.
Indicator codes and interpreted measurement units must be nonblank. Frequency
is constrained to `annual`, matching this project's observation grain.

Observation country, indicator, year, retrieval timestamp, snapshot ID, and page
filename are required. Snapshot IDs and page filenames must be nonblank.
Years are integers constrained to 1900–2100; the loader must separately
validate each run's requested window. This keeps the schema usable after 2026.
Optional display precision must be nonnegative.

`value` is nullable, unconstrained-precision `numeric`. NaN and positive/negative
infinity are rejected. Zero and negative values remain valid. No universal
0–100 bound is appropriate for inflation and GDP growth. The loader
should parse raw JSON numbers as decimals and avoid rounding to the API's
`decimal` display precision.

The composite observation key rejects duplicate inflation records for one
country and year while allowing unemployment and GDP growth for that same
country and year. It is the loader's insert conflict target.

## Missing data and interpretation

A returned JSON null becomes SQL NULL in an existing observation row. An omitted
country/indicator/year combination creates no row. Neither condition means
zero. The loader must not manufacture rows or fill values. `COUNT(value)`
counts numeric measurements; `COUNT(*)` counts returned records. Expected-grid
queries can identify absent combinations.

`api_unit` preserves provider metadata, including blanks. `measurement_unit`
records the documented interpretation: annual percent for inflation and GDP
growth, and percent of the total labor force for modeled unemployment. Blank
raw units do not mean unitless values. Definitions, providers, and licensing
context are documented in `data_dictionary.md`.

Country region and income metadata are current classifications, not historical
attributes for each measurement year. Cross-country comparisons must use shared
numeric years and disclose exclusions, following `data_quality.md`. Annual
national indicators provide budget-review context, not a business's actual
expenses. These rules require appropriate queries and assistant behavior.

## Audit timestamps and provenance

Every table has required `first_seen_at` and `last_updated_at` columns of type
`timestamptz`, defaulting to `now()`. A CHECK requires `last_updated_at` to be at
least `first_seen_at`. These are database event times, not measurement years or
provider publication dates.

There is no automatic update trigger. The loader must preserve
`first_seen_at`, advance `last_updated_at` when stored source content changes,
and leave both unchanged on an identical repeat load.

For observations, `source_retrieved_at` identifies the accepted snapshot's
retrieval time. Nullable `source_last_updated` stores the provider's page-level
update date. `source_snapshot_id` and `source_page_file` locate the raw evidence.
For unchanged records, retain their accepted provenance; later sync logs can
record repeated checks without implying a content revision.

This model stores latest accepted values, not a full revision archive. Local raw
snapshots retain retrieval evidence. Reconstructing multiple vintages through
SQL would require a future history table. Country and indicator metadata
provenance remains in raw snapshots rather than separate per-row database fields.

## Loaded snapshot

The successful load used
`data/raw/world_bank/20261102T041022160331Z/manifest.json`, the latest complete
local run identified during inspection. Read-only database checks confirmed
the counts below after loading.

| Property | Selected snapshot |
|---|---|
| Status | `complete` |
| Retrieval started | `2026-11-02T04:10:22.160331+00:00` |
| Countries / indicators | 20 / 3 |
| Observation rows | 960 |
| Numeric / null values | 950 / 10 |
| Returned years | 2010–2025 |
| Requested years | 2010–2026 |
| Absent 2026 combinations | 60 |
| Saved API pages | 16 |

The older verification and quality reports cite the November 1 snapshot. The
selected newer run has the same reported counts; equal counts alone do not
establish that every value is identical. Those reports are unchanged here.
The ten-row portable sample is not the full load input.

## Scope and future access roles

Removing the source CHECK does not provide full multi-source support. Indicator
codes remain globally unique. Multiple datasets with overlapping codes or
competing measurements may require a sources table, source-scoped indicator
uniqueness, revised observation keys, and frequency or geography changes.

For Milestone 3, [roles.sql](../db/roles.sql) defines `app_reader` with schema
usage and SELECT on `countries`, `indicators`, `observations`, and `sync_runs`.
It matches deployment migration [004_app_reader.sql](../db/migrations/004_app_reader.sql)
and requires migration 003 first. The reader policy allows SELECT on sync
history under row-level security. The app and reference checker use
`APP_DATABASE_URL`, which is blank in the committed environment template.

The SQL wraps all three table definitions in one transaction. It deliberately
omits `IF NOT EXISTS` so an incompatible existing table cannot be silently
accepted. Reapplying it is not a migration strategy. Loader idempotency was
verified separately: a repeat load inserted zero new rows and preserved existing
records and audit timestamps. Migration 003 adds sync logging separately.

## Access roles

### Milestone 3 Part A access verification

On November 22, 2026, I ran the reader verification command locally:

```powershell
.venv/Scripts/python.exe -B scripts/check_db.py --app --verify-permissions
```

The initial attempt, before the reader credential was configured, returned:

```text
[FAIL] APP_DATABASE_URL is not set. Configure it privately using .env.example.
```

An alternate check attempted `SET LOCAL ROLE app_reader` inside a transaction
configured to roll back. PostgreSQL rejected the role switch with
`InsufficientPrivilege (SQLSTATE 42501)` before any reader SELECT, INSERT, or
DELETE ran. This error is evidence about the role switch only.

In a separate read-only transaction, I checked the deployed role and grants
with these queries:

```sql
SELECT rolcanlogin FROM pg_roles WHERE rolname = 'app_reader';

SELECT relation,
       has_table_privilege('app_reader', relation, 'SELECT'),
       has_any_column_privilege('app_reader', relation, 'INSERT'),
       has_any_column_privilege('app_reader', relation, 'UPDATE'),
       has_table_privilege('app_reader', relation, 'DELETE')
FROM (VALUES ('public.countries'), ('public.indicators'),
             ('public.observations'), ('public.sync_runs')) AS tables(relation);
```

```text
reader_login_enabled: True
relation | select | insert | update | delete
public.countries | True | False | False | False
public.indicators | True | False | False | False
public.observations | True | False | False | False
public.sync_runs | True | False | False | False
```

After configuring the reader credential privately, I reran the same command.
It exited with code 0 and returned:

```text
[ok] Connected using APP_DATABASE_URL
     Database user: app_reader
[ok] SELECT succeeded: countries=20, indicators=3, observations=960, sync_runs=9
[ok] INSERT on public.observations: permission denied for table observations (SQLSTATE 42501)
[ok] DELETE on public.observations: permission denied for table observations (SQLSTATE 42501)
```

The checker ran these two statements as `app_reader`:

```sql
INSERT INTO public.observations (value) SELECT NULL::numeric WHERE FALSE;
DELETE FROM public.observations WHERE FALSE;
```

Each write probe targeted zero rows and ran in a separate rollback-only
transaction. PostgreSQL denied both probes, and the check changed no records.

On November 22, 2026, the project owner confirmed that the Supabase Data API
was disabled in the dashboard under **Integrations → Data API**.
