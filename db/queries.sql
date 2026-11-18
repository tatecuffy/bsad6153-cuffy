-- Milestone 2: Small Business Economic Data Assistant.
-- Indicator codes verified against saved World Bank metadata in snapshot
-- 20261102T041022160331Z. All year ranges below are inclusive.
-- Averages are arithmetic means of annual rates, not compounded growth.
-- NULL values are never treated as zero. Ranked summaries require complete
-- numeric coverage of their stated windows; incomplete countries are excluded.
-- Results provide national economic context, not firm-specific recommendations.
-- All five queries executed successfully against Supabase in a read-only
-- transaction, returning 20, 20, 120, 6, and 20 rows, respectively.
-- Verified findings and the surprising Argentina result are in
-- docs/query_findings.md. This comment reports the prior successful execution.

-- Question 1: Which countries had the highest average real GDP growth during
-- 2021-2025, providing context for reviewing small-business revenue forecasts?
-- Require all five numeric years. Highest averages appear first; retain ties
-- and the complete ranking. Rounding affects display only, not sorting.
SELECT
    c.iso3_code,
    c.name AS country_name,
    2021 AS start_year,
    2025 AS end_year,
    COUNT(o.value) AS numeric_years,
    ROUND(AVG(o.value), 2) AS average_gdp_growth_pct
FROM public.countries AS c
JOIN public.observations AS o ON o.country_id = c.country_id
JOIN public.indicators AS i ON i.indicator_id = o.indicator_id
WHERE i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
  AND o.observation_year BETWEEN 2021 AND 2025
GROUP BY c.country_id, c.iso3_code, c.name
HAVING COUNT(o.value) = 5
ORDER BY AVG(o.value) DESC, c.iso3_code;

-- Question 2: Which countries had the highest average consumer-price inflation
-- during 2018-2024, suggesting a need to examine operating-cost assumptions?
-- Require all seven numeric years to compare an identical period, including
-- the documented Argentina-USA overlap. This is an average rate, not the
-- cumulative price increase over the period.
SELECT
    c.iso3_code,
    c.name AS country_name,
    2018 AS start_year,
    2024 AS end_year,
    COUNT(o.value) AS numeric_years,
    ROUND(AVG(o.value), 2) AS average_inflation_pct
FROM public.countries AS c
JOIN public.observations AS o ON o.country_id = c.country_id
JOIN public.indicators AS i ON i.indicator_id = o.indicator_id
WHERE i.indicator_code = 'FP.CPI.TOTL.ZG'
  AND o.observation_year BETWEEN 2018 AND 2024
GROUP BY c.country_id, c.iso3_code, c.name
HAVING COUNT(o.value) = 7
ORDER BY AVG(o.value) DESC, c.iso3_code;

-- Question 3: How did modeled unemployment change annually during 2020-2025,
-- providing context for reviewing staffing and customer-demand assumptions?
-- Build a reporting grid so absent years remain visible without inserting data.
-- The status distinguishes an absent observation from a returned NULL value.
-- Changes are percentage points, not percent changes. The first year has no
-- prior-year comparison within this window; gaps also yield NULL changes.
WITH annual_unemployment AS (
    SELECT
        c.iso3_code,
        c.name AS country_name,
        y.observation_year,
        o.value AS unemployment_pct,
        CASE
            WHEN o.observation_id IS NULL THEN 'absent'
            WHEN o.value IS NULL THEN 'reported_null'
            ELSE 'numeric'
        END AS observation_status
    FROM public.countries AS c
    CROSS JOIN generate_series(2020, 2025) AS y(observation_year)
    JOIN public.indicators AS i ON i.indicator_code = 'SL.UEM.TOTL.ZS'
    LEFT JOIN public.observations AS o
        ON o.country_id = c.country_id
       AND o.indicator_id = i.indicator_id
       AND o.observation_year = y.observation_year
)
SELECT
    iso3_code,
    country_name,
    observation_year,
    ROUND(unemployment_pct, 2) AS unemployment_pct,
    observation_status,
    ROUND(
        unemployment_pct - LAG(unemployment_pct) OVER (
            PARTITION BY iso3_code ORDER BY observation_year
        ), 2
    ) AS annual_change_percentage_points
FROM annual_unemployment
ORDER BY iso3_code, observation_year;

-- Question 4: Which countries combined average GDP growth above 3% with
-- average inflation below 5% during 2021-2025, warranting closer investigation
-- of growth opportunities and operating-cost conditions?
-- Require five numeric years for EACH indicator. Incomplete countries are
-- excluded, not assumed to fail the economic thresholds. Strict thresholds
-- use unrounded averages. These conditions do not establish business viability.
WITH country_averages AS (
    SELECT
        c.iso3_code,
        c.name AS country_name,
        AVG(o.value) FILTER (
            WHERE i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
        ) AS average_gdp_growth,
        AVG(o.value) FILTER (
            WHERE i.indicator_code = 'FP.CPI.TOTL.ZG'
        ) AS average_inflation,
        COUNT(o.value) FILTER (
            WHERE i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
        ) AS gdp_numeric_years,
        COUNT(o.value) FILTER (
            WHERE i.indicator_code = 'FP.CPI.TOTL.ZG'
        ) AS inflation_numeric_years
    FROM public.countries AS c
    JOIN public.observations AS o ON o.country_id = c.country_id
    JOIN public.indicators AS i ON i.indicator_id = o.indicator_id
    WHERE i.indicator_code IN ('NY.GDP.MKTP.KD.ZG', 'FP.CPI.TOTL.ZG')
      AND o.observation_year BETWEEN 2021 AND 2025
    GROUP BY c.country_id, c.iso3_code, c.name
)
SELECT
    iso3_code,
    country_name,
    2021 AS start_year,
    2025 AS end_year,
    gdp_numeric_years,
    inflation_numeric_years,
    ROUND(average_gdp_growth, 2) AS average_gdp_growth_pct,
    ROUND(average_inflation, 2) AS average_inflation_pct
FROM country_averages
WHERE gdp_numeric_years = 5
  AND inflation_numeric_years = 5
  AND average_gdp_growth > 3
  AND average_inflation < 5
ORDER BY average_gdp_growth DESC, average_inflation ASC, iso3_code;

-- Question 5: Which countries had the greatest variation in annual GDP growth
-- during 2015-2025, suggesting greater uncertainty in revenue planning?
-- Volatility is the population standard deviation of the eleven annual growth
-- rates, expressed in percentage points. Require all eleven numeric years.
-- This describes the selected historical window, not a forecast of future risk.
-- Verified surprising finding: Argentina averaged 3.53% GDP growth in
-- 2021-2025 (Query 1), versus 0.60% in 2015-2025, with volatility of 5.17
-- percentage points here. The stronger recent average hides longer-run
-- variation; these descriptive results do not establish causation.
SELECT
    c.iso3_code,
    c.name AS country_name,
    2015 AS start_year,
    2025 AS end_year,
    COUNT(o.value) AS numeric_years,
    ROUND(AVG(o.value), 2) AS average_gdp_growth_pct,
    ROUND(STDDEV_POP(o.value), 2) AS gdp_growth_volatility_percentage_points
FROM public.countries AS c
JOIN public.observations AS o ON o.country_id = c.country_id
JOIN public.indicators AS i ON i.indicator_id = o.indicator_id
WHERE i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
  AND o.observation_year BETWEEN 2015 AND 2025
GROUP BY c.country_id, c.iso3_code, c.name
HAVING COUNT(o.value) = 11
ORDER BY STDDEV_POP(o.value) DESC, c.iso3_code;
