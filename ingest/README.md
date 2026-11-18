# ingest/

Code that moves data from your API into your database. You build it with your AI agent, one piece per week:

| Week | File | What it does |
|---|---|---|
| 1 | `fetch.py` | Calls your API: authentication, pagination, rate limits, retries. Saves raw JSON to `data/raw/`. |
| 2 | `load.py` | Turns the raw JSON into rows in your tables, using parameterized queries. Running it twice must not create duplicates. |
| 3 | `sync.py` | Combines fetch and load into one incremental, idempotent sync that GitHub Actions runs on a schedule and records in `sync_runs`. |

Only the sync connects as the database owner (`DATABASE_URL`). Everything else uses a limited role.

## Milestone 1: World Bank fetch

From the repository root, using the existing Python environment:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe ingest/fetch.py
```

No API key is required. The fetcher never loads `.env` and disables Requests'
environment-based proxy and authentication settings. `config.json` defines the
20 countries, three WDI indicators, years 2010–2026, and page size of 100.
Returned nulls remain null. Entirely absent years remain absent and are counted
separately in the manifest; the fetcher does not invent records.

Each run creates `data/raw/world_bank/<UTC timestamp>/` containing original JSON
pages and `manifest.json`. This directory is ignored by Git. Only a verified
complete run updates `data/sample/world_bank_sample.json`. A failed run exits
with a nonzero code and leaves an `incomplete` manifest for investigation.
The manifest counts observations, non-missing values, metadata records, and
successful API pages; retries are not additional dataset pages.

### Important functions in fetch.py

| Function | Purpose |
|---|---|
| `load_config` | Read the explicit non-secret settings and check basic bounds. |
| `retry_delay` | Interpret Retry-After, or choose exponential backoff with jitter. |
| `validate_page` | Check response shape, page number, counts, and stable dataset metadata. |
| `request_page` | Apply timeouts and bounded retries; reject permanent HTTP errors. |
| `fetch_resource` | Follow all pages, reject duplicate natural keys, and save raw responses. |
| `validate_observations` | Check numeric/null values, uniqueness, years, and metadata relationships. |
| `write_json` | Save readable JSON without converting missing values to zero. |
| `run` | Coordinate resources, completeness checks, manifest, and authentic sample. |

The retry/pacing choices are project policies, not published World Bank quotas.
Retry-After above 60 seconds stops the run for a later retry. Publication may
change while pages are fetched; totals and update dates are checked, but the API
does not provide a transactional snapshot guarantee.

Sources: [authentication](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392),
[pagination](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures),
[dataset terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets).
