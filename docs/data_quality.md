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
