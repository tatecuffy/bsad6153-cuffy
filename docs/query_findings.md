# Part D: Analytical SQL query findings

## Purpose and verification

The five queries in `db/queries.sql` examine economic conditions relevant to
small-business revenue forecasts, operating-cost assumptions, staffing, and
risk assessment. They use the `countries`, `indicators`, and `observations`
tables populated from saved World Bank snapshot `20261102T041022160331Z`.

All five queries executed successfully against Supabase in a read-only
transaction. The execution changed no database records or objects. This report
documents those verified results; it does not represent another query run.
All year ranges are inclusive. Averages are arithmetic means of annual rates,
not compounded growth or cumulative inflation. Displayed results are rounded
to two decimal places; sorting and threshold tests use unrounded values.

| Query | Purpose and period | Verified rows returned |
|---|---|---:|
| 1 | Rank countries by average GDP growth, 2021–2025. | 20 |
| 2 | Rank countries by average consumer-price inflation, 2018–2024. | 20 |
| 3 | Show annual modeled unemployment and annual percentage-point changes, 2020–2025. | 120 |
| 4 | Identify countries with average GDP growth above 3% and average inflation below 5%, 2021–2025. | 6 |
| 5 | Rank countries by GDP growth volatility, 2015–2025. | 20 |

## Major findings

### Query 1: Average GDP growth, 2021–2025

India had the highest average GDP growth among the 20 selected countries at
7.84%, followed by Türkiye at 5.85%, Indonesia at 4.84%, Colombia at 4.62%,
and Spain at 4.36%. All 20 countries had five numeric annual values, so none
were excluded for incomplete data.

### Query 2: Average inflation, 2018–2024

Argentina had the highest average inflation at 86.29%, followed by Türkiye
at 35.44%, Colombia at 5.90%, Brazil at 5.31%, and India at 5.25%.
All 20 countries had seven numeric annual values for this window. These
figures describe average annual inflation rates, not cumulative price increases.

### Query 3: Unemployment trends, 2020–2025

The query returned 120 rows: six annual observations for each of 20 countries.
All observations in this window were numeric. As a representative result,
U.S. modeled unemployment fell from 8.06% in 2020 to 3.64% in 2023, then rose
to 4.02% in 2024 and 4.20% in 2025. The latter two annual increases were
0.38 and 0.18 percentage points, respectively.

The 2020 annual-change result is NULL because no preceding year is included
in the query window; this does not mean that the 2020 unemployment rate is
missing. Annual changes are calculated before rounding.

### Query 4: Growth above 3% and inflation below 5%, 2021–2025

Six countries met both strict thresholds with five numeric years for each
indicator:

| Country | Average GDP growth | Average inflation |
|---|---:|---:|
| India | 7.84% | 4.97% |
| Indonesia | 4.84% | 2.71% |
| Spain | 4.36% | 4.09% |
| United Kingdom | 3.29% | 4.88% |
| Canada | 3.28% | 3.71% |
| Italy | 3.20% | 3.64% |

**Argentina and the United States were excluded because their 2025 inflation
observations were NULL.** Each therefore had only four numeric inflation
values in this five-year window. Their exclusion does not establish that they
failed the economic thresholds. The other 12 countries had complete data but
did not meet both conditions. No country was excluded for incomplete data
from Queries 1, 2, 3, or 5 in their respective windows.

### Query 5: GDP growth volatility, 2015–2025

Argentina had the greatest GDP growth volatility at 5.17 percentage points,
followed by Spain at 4.44, the United Kingdom at 4.28, Colombia at 4.18,
and Italy at 4.00. Volatility is the population standard deviation of the
11 annual growth rates. All 20 countries had complete numeric coverage.

## Surprising finding: Argentina's growth depends on the window

Argentina's average GDP growth was **3.53% in 2021–2025**, compared with
**0.60% in 2015–2025**. Its GDP growth volatility over 2015–2025 was
**5.17 percentage points**, the highest among the 20 selected countries.

The difference is striking because the recent five-year average presents a
stronger growth picture than the longer historical window, while the volatility
measure shows substantial variation in annual growth. The two periods overlap;
they are not independent samples. These results do not establish the causes
of the difference or predict future growth.

## Implications for small-business decisions

For revenue forecasting, the Argentina result illustrates why an assistant
should disclose the selected years and show variability alongside an average.
Applying a recent national growth average directly to a firm's sales forecast
could overlook historical fluctuations and differences between national output
and the firm's customers or industry.

For risk assessment, these results can inform questions to investigate and
alternative revenue scenarios. They should be compared with actual sales,
orders, expenses, and cash flow before changing a business budget. Query 4 is
a descriptive screening rule, not a validated measure of business viability
or a recommendation to enter a market. Missing data must be reported as
insufficient evidence rather than interpreted as failure or zero inflation.

## Limitations

- The results describe historical values in one saved snapshot. Later source
  releases may revise those values; no new data were fetched for this analysis.
- The indicators describe national economies, not individual firms, industries,
  local labor markets, supplier costs, or customer demand.
- Averages can hide year-to-year variation and depend on the chosen time window.
  Historical standard deviation is not a forecast of future risk.
- Complete-window requirements improve period comparability but exclude some
  countries when values are missing. NULL values are not treated as zero.
- These descriptive comparisons establish no causal relationships between
  economic indicators and small-business outcomes.
