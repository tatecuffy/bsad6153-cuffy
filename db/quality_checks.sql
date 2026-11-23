-- Milestone 3 Part E. Run as app_reader. Audit scope follows ingest/config.json.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

SELECT current_user AS audit_role, now() AS audit_at,
       (SELECT max(finished_at) FROM public.sync_runs WHERE status = 'success') AS last_success,
       (SELECT array_agg(iso3_code ORDER BY iso3_code) FROM public.countries) AS countries,
       (SELECT array_agg(indicator_code ORDER BY indicator_code) FROM public.indicators) AS indicators;

SELECT 'countries' AS table_name, count(*) AS row_count FROM public.countries
UNION ALL SELECT 'indicators', count(*) FROM public.indicators
UNION ALL SELECT 'observations', count(*) FROM public.observations
UNION ALL SELECT 'sync_runs', count(*) FROM public.sync_runs
ORDER BY table_name;

WITH fields AS (
    SELECT 'observations.value' AS field, count(*) AS total, count(value) AS present
    FROM public.observations
    UNION ALL SELECT 'observations.source_last_updated', count(*), count(source_last_updated)
    FROM public.observations
    UNION ALL SELECT 'countries.name', count(*), count(name) FROM public.countries
    UNION ALL SELECT 'indicators.name', count(*), count(name) FROM public.indicators
)
SELECT field, total, total - present AS null_rows,
       round(100.0 * (total - present) / nullif(total, 0), 2) AS null_pct
FROM fields ORDER BY field;

-- Build the expected grid from the configuration, even if metadata is absent.
WITH expected AS (
    SELECT country, indicator, year
    FROM unnest(ARRAY['USA','CAN','MEX','BRA','ARG','CHL','COL','GBR','FRA','DEU',
                      'ITA','ESP','JPN','KOR','AUS','NZL','IND','IDN','ZAF','TUR']) AS c(country)
    CROSS JOIN unnest(ARRAY['FP.CPI.TOTL.ZG','SL.UEM.TOTL.ZS','NY.GDP.MKTP.KD.ZG']) AS i(indicator)
    CROSS JOIN generate_series(2010, 2026) AS y(year)
),
coverage AS (
    SELECT e.*, o.observation_id, o.value
    FROM expected AS e
    LEFT JOIN public.countries AS c ON c.iso3_code = e.country
    LEFT JOIN public.indicators AS i ON i.indicator_code = e.indicator
    LEFT JOIN public.observations AS o ON o.country_id = c.country_id
        AND o.indicator_id = i.indicator_id AND o.observation_year = e.year
)
SELECT country, indicator, year, count(*) AS slots,
       count(value) AS numeric_values,
       count(*) FILTER (WHERE observation_id IS NOT NULL AND value IS NULL) AS explicit_nulls,
       count(*) FILTER (WHERE observation_id IS NULL) AS absent,
       max(year) FILTER (WHERE value IS NOT NULL) AS latest_numeric_year
FROM coverage
GROUP BY GROUPING SETS ((), (indicator), (year), (country), (country, indicator))
ORDER BY country NULLS FIRST, indicator NULLS FIRST, year NULLS FIRST;

-- These checks cover every stored observation, including any outside the grid.
WITH duplicates AS (
    SELECT count(*) AS copies
    FROM public.observations
    GROUP BY country_id, indicator_id, observation_year
    HAVING count(*) > 1
)
SELECT (SELECT count(*) FROM public.observations) AS stored_rows,
       (SELECT count(*) FROM duplicates) AS duplicate_keys,
       (SELECT coalesce(sum(copies - 1), 0) FROM duplicates) AS extra_duplicate_rows,
       count(*) FILTER (WHERE c.country_id IS NULL) AS orphan_country_rows,
       count(*) FILTER (WHERE i.indicator_id IS NULL) AS orphan_indicator_rows
FROM public.observations AS o
LEFT JOIN public.countries AS c ON c.country_id = o.country_id
LEFT JOIN public.indicators AS i ON i.indicator_id = o.indicator_id;

SELECT c.iso3_code AS country, i.indicator_code AS indicator, o.observation_year AS year
FROM public.observations AS o
JOIN public.countries AS c USING (country_id)
JOIN public.indicators AS i USING (indicator_id)
WHERE o.value IS NULL
ORDER BY indicator, country, year;

-- Screening thresholds are review rules, not database constraints.
WITH flagged AS (
    SELECT c.iso3_code AS country, i.indicator_code AS indicator,
           o.observation_year AS year, o.value,
           CASE
               WHEN o.value IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
                   THEN 'non-finite'
               WHEN i.indicator_code = 'SL.UEM.TOTL.ZS' AND (o.value < 0 OR o.value > 100)
                   THEN 'unemployment outside 0–100%'
               WHEN i.indicator_code = 'FP.CPI.TOTL.ZG' AND abs(o.value) >= 50
                   THEN 'absolute inflation at least 50%'
               WHEN i.indicator_code = 'NY.GDP.MKTP.KD.ZG' AND abs(o.value) >= 15
                   THEN 'absolute GDP growth at least 15%'
           END AS flag
    FROM public.observations AS o
    JOIN public.countries AS c USING (country_id)
    JOIN public.indicators AS i USING (indicator_id)
    WHERE o.value IS NOT NULL
)
SELECT country, indicator, year, round(value, 2) AS value_pct, flag
FROM flagged WHERE flag IS NOT NULL
ORDER BY indicator, year, country;

-- Pair only finite, non-NULL inflation observations in the same year.
WITH paired AS (
    SELECT o.observation_year AS year,
           max(o.value) FILTER (WHERE c.iso3_code = 'ARG') AS argentina,
           max(o.value) FILTER (WHERE c.iso3_code = 'USA') AS united_states
    FROM public.observations AS o
    JOIN public.countries AS c USING (country_id)
    JOIN public.indicators AS i USING (indicator_id)
    WHERE c.iso3_code IN ('ARG', 'USA') AND i.indicator_code = 'FP.CPI.TOTL.ZG'
        AND o.observation_year BETWEEN 2010 AND 2026
        AND o.value NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
    GROUP BY o.observation_year
    HAVING count(DISTINCT c.iso3_code) = 2
)
SELECT year, count(*) AS paired_years, round(avg(argentina), 2) AS argentina_pct,
       round(avg(united_states), 2) AS us_pct,
       round(avg(argentina - united_states), 2) AS gap_percentage_points
FROM paired GROUP BY GROUPING SETS ((year), ())
ORDER BY year NULLS LAST;

ROLLBACK;
