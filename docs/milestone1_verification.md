# Milestone 1 verification

## Git starting point

Before implementation, `main` was clean and local `main`, `origin/main`, and the
live GitHub `main` all resolved to `ab8114a3965015b37b61c7b88c523e7b59d4bfb7`.
Created `milestone-1`. No commit or push was performed.

## Automated checks

Command: `.venv\Scripts\python.exe -m unittest discover -s tests -v`

Actual result: **15 tests passed**. The tests use explicitly synthetic fixtures;
they are not observations and are not included in the published data sample.
Coverage includes page traversal and original-page persistence, HTTP 429 and
Retry-After, timeouts, connection failures, 5xx retry exhaustion, permanent 404,
invalid JSON/API envelopes, short pages, changed totals, wrong page numbers,
duplicate resource/observation keys, null versus zero, numeric validation,
year/foreign-key validation, absent future years, and failed-run manifests.

No dependencies were installed. The existing Python environment required
execution outside the sandbox; it was used with approval. No `.env` file or API
credentials were accessed.

## Controlled live fetch

Command: `.venv\Scripts\python.exe ingest/fetch.py`

Successful run: `20261101T050857984242Z` (UTC).
The manifest records start `2026-11-01T05:08:57.984242+00:00` and finish
`2026-11-01T05:09:04.967966+00:00`. Saved provider metadata reports
`lastupdated=2026-10-08`.

| Resource | Returned records | Non-missing observations | Pages |
|---|---:|---:|---:|
| Inflation FP.CPI.TOTL.ZG | 320 | 310 | 4 |
| Unemployment SL.UEM.TOTL.ZS | 320 | 320 | 4 |
| GDP growth NY.GDP.MKTP.KD.ZG | 320 | 320 | 4 |
| Countries | 20 | Not applicable | 1 |
| Indicator metadata | 3 | Not applicable | 3 |
| Total | 983 | 950 | 16 |

The 960 observations have 960 unique `(country, indicator, year)` keys.
Ten observations have null values. The API returned 2010–2025 despite the
requested 2010–2026 range: 60 possible country/indicator/year combinations for
2026 were absent, not manufactured. All 20 countries and three indicators have
metadata, and all observation references passed validation.

Raw pages and manifest are in ignored
`data/raw/world_bank/20261101T050857984242Z/`.
An independent read of these files confirmed 960 observations, 950 non-missing
values, 10 nulls, and 16 page files. All 10 sample observations matched exactly
one raw observation with identical original field values. The sample has nine
numeric observations (three per indicator) and one actual null-valued row.

`git diff --check` passed. `git check-ignore -v` confirmed the actual raw manifest
is protected by `.gitignore` line 12. `git ls-files -- data/raw/` returned no
tracked raw files.

## Observed failure and correction

The first live attempt, `20261101T050714033612Z`, stopped because the initial
implementation incorrectly required a full 2010–2026 Cartesian grid. The API
omitted 2026 instead of returning null rows. Six validated pages from that
attempt remain in its ignored directory with an `incomplete` manifest. No
sample was published by the failed run.

The correction uses API totals to verify page completeness, checks all requested
countries, and reports absent year slots separately without fabricating rows.
Two regression tests cover absent years and failed-run sample preservation.
The subsequent test run and live fetch succeeded.

The live run validates normal API behavior; transient HTTP failures were tested
with mocks, not deliberately triggered against the provider. Successful page
counts describe dataset pages, not an audit of every HTTP retry.

## Remaining concerns

- Annual national data are context, not a weekly early-warning system or a firm's
  actual operating costs.
- API paging is not a transactional snapshot. Totals/update dates are checked,
  but changes that do not alter those fields may remain undetectable.
- Raw snapshots preserve retrieval history; they do not supply earlier vintages
  that were never downloaded.
- The README proposal is complete and identifies BLS as a proposed backup API.
  The data dictionary documents 20 individual fields with authentic examples,
  missing-value rules, relationships, data surprises, and interpretation risks.
  The baseline log contains five populated entries; Codex verified six fields
  per entry and preservation of the original entry and reflections. Personal
  review, instructor acceptance of the dataset structure, exact Canvas
  requirements, screencast, and submission checklist remain pending.
- Database loading, scheduled sync, public website integration, and AI-agent
  behavior remain later milestone work.
