# World Bank data quality assessment

## Dataset and missing values

This assessment uses the saved World Development Indicators run
`20261101T050857984242Z`, documented in the [verification report](milestone1_verification.md).
The snapshot covers 20 selected countries and the years 2010–2025 for three
annual indicators: consumer-price inflation (`FP.CPI.TOTL.ZG`), modeled
unemployment (`SL.UEM.TOTL.ZS`), and real GDP growth (`NY.GDP.MKTP.KD.ZG`).

The API returned **960 observations**, including **950 numeric values and 10
nulls**. All 10 nulls are inflation values. Nine are for Argentina (2010–2017
and 2025), and one is for the United States (2025). Unemployment and GDP growth
each have 320 numeric values. The [data dictionary](data_dictionary.md) records
the indicator definitions, source organizations, and missing-value rules.

The request also included 2026, but the API returned no rows for that year. The
**60 absent combinations** (20 countries × 3 indicators) are distinct from the
10 rows that were returned with a null value. Neither type of gap represents zero.

## Fairness check: inflation coverage by country

For each country, I compared the number of numeric inflation values with the
same 16-year window, 2010–2025. Coverage is the number of numeric inflation years
divided by 16. The comparison excludes 2026 because it was absent for all countries
in this snapshot.

| Country | Numeric inflation years | Coverage |
|---|---:|---:|
| Argentina | 7/16 | 43.75% |
| United States | 15/16 | 93.75% |
| Each of the other 18 selected countries | 16/16 | 100% |

Argentina has 50 percentage points less inflation coverage than the United
States. If an AI agent averages each country's available values, the two averages
would summarize different years. The agent could attribute a difference to
economic conditions without accounting for the difference in the periods compared,
then give a business owner a misleading reason to review or defer a budget review.

**Safeguard.** Require cross-country comparisons to use years with numeric data
for every country in the comparison. For Argentina and the United States, the
shared inflation period is **2018–2024**. Show the years used and flag missing or
excluded years. If the overlap is insufficient for the question, say so and ask
the owner to check actual supplier prices and operating expenses before acting.
Before recommending a budget adjustment, the agent should distinguish between an observed economic trend and evidence that the trend is affecting the business's actual expenses.

## Limitations

The check measures the availability of inflation data in one saved snapshot for
the selected countries. It does not identify the cause of the gaps, prove
discrimination, or establish biased agent behavior. No agent recommendations
were tested. National annual inflation provides context for a budget review.
A business's own costs and revenue are needed to decide whether to change its budget.

## Milestone 3 Part E — live audit on November 22, 2026

I ran [the audit SQL](../db/data_quality_audit.sql) against Supabase as
`app_reader` at **9:11:36 p.m. CST** on November 22, 2026
(November 23 at 03:11:36 UTC). All queries used the same repeatable-read,
read-only transaction. The latest successful sync recorded at audit time was
November 22 at 3:55:28 p.m. CST. The latest numeric observation year was 2025.

### Completeness and integrity

The expected grid uses the 20 countries, three indicators, and 17 years
(2010–2026) in [the ingestion configuration](../ingest/config.json).
An explicit NULL is a stored row with no value. An absent slot has no stored
row at all. The sync keeps previously stored rows when the API omits them,
so this audit describes the database at query time.

| Indicator | Expected slots | Numeric | Explicit NULL | Absent |
| --- | ---: | ---: | ---: | ---: |
| Consumer-price inflation | 340 | 310 | 10 | 20 |
| Real GDP growth | 340 | 320 | 0 | 20 |
| Modeled unemployment | 340 | 320 | 0 | 20 |
| **Total** | **1,020** | **950** | **10** | **60** |

All 60 absent slots are in 2026, one for each country and indicator.
The 10 explicit NULLs are all inflation: Argentina in 2010–2017 and 2025,
and the United States in 2025. There were 960 stored observation rows,
zero duplicate country–indicator–year keys, zero extra duplicate rows,
and zero observations with a missing country or indicator reference.

### Suspicious values

The audit flags non-finite values, unemployment outside 0–100%, absolute
inflation of at least 50%, and absolute GDP growth of at least 15%.
These are screening rules chosen for this audit. A flag calls for checking
the source and context before using the observation in a recommendation.

| Indicator | Country | Flagged annual rates |
| --- | --- | --- |
| Inflation | Argentina | 2019: 53.55%, 2022: 72.43%, 2023: 133.49%, 2024: 219.88% |
| Inflation | Türkiye | 2022: 72.31%, 2023: 53.86%, 2024: 58.51% |

All seven flags were high inflation. There were no non-finite values,
out-of-range unemployment values, or GDP growth flags under these rules.
The flagged inflation observations stayed in the shared-year analysis.

### Country coverage and a fair inflation comparison

The coverage table uses 2010–2025, the years with any stored data. Reporting
2026 separately keeps a year with no stored observations for any country
from obscuring gaps that differ by country.

| Country | Numeric observations across all indicators | Numeric inflation years |
| --- | ---: | ---: |
| Argentina | 39/48 (81.25%) | 7/16 (43.75%) |
| United States | 47/48 (97.92%) | 15/16 (93.75%) |
| Each of the other 18 countries | 48/48 (100%) | 16/16 (100%) |

Argentina and the United States both had valid inflation observations for
**2018–2024**. The query includes only those seven paired years.

| Year | Argentina | United States | Gap (percentage points) |
| --- | ---: | ---: | ---: |
| 2018 | 34.28% | 2.44% | 31.83 |
| 2019 | 53.55% | 1.81% | 51.74 |
| 2020 | 42.02% | 1.23% | 40.78 |
| 2021 | 48.41% | 4.70% | 43.71 |
| 2022 | 72.43% | 8.00% | 64.43 |
| 2023 | 133.49% | 4.12% | 129.37 |
| 2024 | 219.88% | 2.95% | 216.93 |
| **Seven-year arithmetic mean** | **86.29%** | **3.61%** | **82.69** |

The query computes gaps before rounding the displayed rates. The mean
summarizes annual rates over a shared window. It cannot establish the
cumulative increase in prices or a particular business's cost experience.
The assistant should state the years used, disclose the excluded years,
and say when gaps leave too little overlap for the requested comparison.
