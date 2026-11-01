# World Bank data dictionary — Milestone 1

## Scope and sources

World Development Indicators (source ID `2`), 20 selected countries, 2010–2026.
These are annual national indicators, not monthly measurements or individual
business expenses. Returned null values remain null; entirely absent years are
not manufactured and are counted separately in the manifest. A year label is
not a release date.

| Indicator ID | Meaning / units | Original providers |
|---|---|---|
| FP.CPI.TOTL.ZG | Consumer-price inflation, annual percent | IMF International Financial Statistics |
| SL.UEM.TOTL.ZS | Unemployment, percent of total labor force, modeled ILO estimate | ILO / ILOSTAT |
| NY.GDP.MKTP.KD.ZG | Real GDP growth, annual percent | National statistical organizations/central banks, OECD, World Bank estimates |

Official indicator pages, each labeled CC BY 4.0:
[inflation](https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG),
[unemployment](https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS),
[GDP growth](https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG).

## Resources and future database relationships

The 20 fields below use dot notation for nested JSON fields. Types describe raw
JSON, not an implemented database schema. Missing-value rules describe how this
project should interpret each field; only the key, year, source, and numeric/null
checks described below are enforced by the current fetcher.

| Field name | Data type | Authentic example | Meaning | Missing values allowed? |
|---|---|---|---|---|
| Country `id` | string | `"USA"` | Three-character country key | No; needed for relationships |
| Country `iso2Code` | string | `"US"` | Two-character country code | Yes for descriptive use; do not substitute for the primary key |
| Country `name` | string | `"United States"` | Display name | Yes; use the country key if absent |
| Country `region.id` | string | `"NAC"` | Current regional classification | Yes; retain an empty/absent value as unknown |
| Country `incomeLevel.id` | string | `"HIC"` | Current income classification | Yes; not a historical income classification |
| Country `capitalCity` | string | `"Washington D.C."` | Descriptive capital-city name | Yes; not required for analysis |
| Indicator `id` | string | `"FP.CPI.TOTL.ZG"` | Indicator key | No; must match the requested indicator |
| Indicator `name` | string | `"Inflation, consumer prices (annual %)"` | Display label and unit context | Yes technically; consult the documented definition before interpretation |
| Indicator `source.id` | string | `"2"` | Dataset identifier for WDI | No; must match configured source |
| Indicator `sourceOrganization` | string | `"International Financial Statistics database, International Monetary Fund (IMF)"` | Original provider and attribution | Yes technically; consult source documentation before publication |
| Indicator `unit` | string | `""` | Separate unit label, blank in this response | Yes; blank does not mean unitless |
| Observation `countryiso3code` | string | `"USA"` | Reference to country `id` | No; must resolve to downloaded metadata |
| Observation `country.id` | string | `"US"` | Two-character code embedded in the observation | Yes for joining; the project joins on `countryiso3code` |
| Observation `indicator.id` | string | `"FP.CPI.TOTL.ZG"` | Reference to indicator `id` | No; must resolve to downloaded metadata |
| Observation `date` | string | `"2020"` | Measurement year, not publication date | No; must be an integer year within the requested range |
| Observation `value` | number or null | `1.23358439630629` | U.S. annual consumer-price inflation for 2020, in percent | Yes: JSON `null`; never replace it with zero |
| Observation `unit` | string | `""` | Observation-level unit label | Yes; use indicator definition for units |
| Observation `decimal` | integer | `1` | Returned presentation-precision metadata | Yes; do not use it to alter stored numeric precision |
| Observation `obs_status` | string | `""` | Provider status field | Yes; blank does not establish finality or absence of revisions |
| Page metadata `lastupdated` | date string | `"2026-10-08"` | Provider-reported dataset update date | Yes; if absent, report it as unknown rather than using retrieval time |

Example provenance: country examples are from
`../data/raw/world_bank/20261101T050857984242Z/countries_page_001.json`;
indicator examples are from that run's `indicator_FP.CPI.TOTL.ZG_page_001.json`;
observation examples are the USA/2020 record in
`observations_FP.CPI.TOTL.ZG_page_003.json`. The update date is in that page's
metadata. These ignored local files are the evidence; the portable sample is
available in `../data/sample/world_bank_sample.json` but does not contain every
example in this table.

The natural observation key is `(countryiso3code, indicator.id, date)`.
Many observations reference one country and one indicator. All three resources
are fetched separately. Duplicate keys, unknown references, nonnumeric non-null
values, and out-of-range years fail validation. Nulls do not count toward 500.

Country and indicator metadata are separate resources, not copies invented from
observation labels. In the future database, country `id` and indicator `id`
would be primary keys, and each observation would reference both as foreign
keys. Do not join country `id="USA"` directly to observation `country.id="US"`.
The current run contains 20 countries, three indicators, and 960 observations,
including 950 non-missing measurements. No database tables are implemented yet.

## Updates, revisions, and missing data

All three indicators measure annual outcomes. Observation frequency is different
from database update frequency: the World Bank described its July 2026 WDI
release as a quarterly database update that included revisions. The exact
availability date for each country/indicator is not guaranteed by this project.
See the [official WDI update announcement](https://blogs.worldbank.org/en/opendata/what-s-new-in-the-world-development-indicators--july-2026-update)
and [updates and errata](https://datahelpdesk.worldbank.org/knowledgebase/articles/906522-data-updates-and-errata).

The saved response reports a dataset update date of October 8, 2026; the local
manifest records retrieval on November 1, 2026 UTC. Neither is the observation's
measurement year. A later fetch may revise older values. Retain timestamped raw
snapshots and compare the same country/indicator/year keys before interpreting a
change as a new economic development. A full vintage archive or automated
revision comparison is not implemented.

Preserve returned nulls and empty metadata strings. Exclude null observations
from the valid-record count, and do not interpolate, forward-fill, or treat them
as zero. An omitted country/year combination is different from a returned row
whose value is null. The manifest reports absent combinations separately. A
short API page is an integrity error that triggers retries and then failure;
it must not be silently treated as ordinary missing economic data. Valid zero
and negative measurements remain numeric values.

## Three surprises in the saved fetch

These are observations about this snapshot, not explanations of why a provider
reported a value or left it missing.

1. **Requesting 2026 did not create 2026 records.** The successful manifest
   records a 2010–2026 query, but all three indicators stop at 2025. Each has
   320 returned rows and 20 absent country/year combinations, for 60 absent
   combinations overall. The first attempt's full-grid assumption was wrong;
   the fetcher now reports absence without manufacturing rows. Evidence:
   `../data/raw/world_bank/20261101T050857984242Z/manifest.json` and the page
   files it lists.
2. **Missing inflation values occur inside the history, not just at the end.**
   Argentina's 2017 inflation value is `null` in
   `observations_FP.CPI.TOTL.ZG_page_001.json`. Of the 320 inflation rows, ten
   are null: nine for Argentina (2010–2017 and 2025) and one for the United
   States (2025). Unemployment and GDP growth each have 320 numeric values.
   These gaps should not be interpreted as zero inflation; their causes are
   not established by the saved responses.
3. **Blank unit fields coexist with meaningful units and detailed numbers.**
   The USA/2020 inflation row in `observations_FP.CPI.TOTL.ZG_page_003.json`
   has `unit=""`, `decimal=1`, and `value=1.23358439630629`. Its indicator
   name specifies annual percent. The empty unit field therefore cannot be
   used to infer that the number is unitless, and the original number should
   not be rounded merely because the display metadata says one decimal.

## Provenance and licensing

Raw JSON retains the API's `[pagination_metadata, records]` envelope. Metadata
includes `page`, `pages`, `per_page`, `total`, and, where returned, `lastupdated`.
The local manifest records UTC retrieval timestamps, query parameters, source,
completion status, and actual counts. Retrieval time and provider update date
are different. Re-fetching history may return revised values; these snapshots
record what was retrieved, not a complete historical vintage archive.

Attribution: **The World Bank: World Development Indicators: IMF; ILO/ILOSTAT;
national statistical organizations/central banks; OECD; World Bank estimates.**
Data license: [CC BY 4.0 and World Bank additional terms](https://datacatalog.worldbank.org/public-licenses).
[Dataset terms and third-party exceptions](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets).
The reviewed indicator pages show CC BY 4.0; no additional indicator-specific
restriction was found. Preserve attribution and identify transformations.
The project is not endorsed by the World Bank or the original data providers.

The sample is a subset of authentic API records, with field values preserved.
Include provider attribution, retrieval date, license/terms links, and a
description of any later calculation or transformation when sharing results.
Recheck indicator-specific licensing before adding new indicators; the general
license does not override a separately labeled third-party exception.

## Privacy and potential harms

The selected API records describe national aggregates and country metadata;
the saved resources contain no individual respondents or private business
accounts. This does not authorize collecting customer, employee, or company
financial records later. Keep any future private inputs out of public samples
and logs, collect only what is needed, and obtain permission before sharing.

Misreading nulls as zero could conceal risk. Treating revised historical values
as current events could produce misleading briefings. National averages and
modeled unemployment estimates do not describe a specific firm's customers or
workers. Cross-country comparisons may obscure methodological differences and
should not be used to stereotype populations. An unsupported recommendation
could prompt unnecessary cuts, price increases, or hiring changes; a person
should review evidence and actual business expenses before acting.

## Decision limitations

Annual national inflation, unemployment, and growth provide broad context for
reviewing a budget. They do not establish a firm's actual cost increases or
justify automatic changes. Comparing countries adds context and enough actual
records for the assignment; foreign observations are not local business facts.
