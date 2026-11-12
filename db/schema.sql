-- Milestone 2: Small Business Economic Data Assistant. Definition only.
-- Future loader input: data/raw/world_bank/20261102T041022160331Z/manifest.json.
-- Applying this file requires separate authorization. This is not a migration.
-- Audit defaults apply on INSERT; the future loader maintains update timestamps.

BEGIN;

CREATE TABLE public.countries (
    country_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    iso3_code text NOT NULL UNIQUE,
    iso2_code text,
    name text,
    region_code text,
    income_level_code text,
    capital_city text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT countries_iso3_format CHECK (iso3_code ~ '^[A-Z]{3}$'),
    CONSTRAINT countries_iso2_format CHECK (iso2_code = '' OR iso2_code ~ '^[A-Z]{2}$'),
    CONSTRAINT countries_audit_order CHECK (last_updated_at >= first_seen_at)
);

CREATE TABLE public.indicators (
    indicator_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indicator_code text NOT NULL UNIQUE,
    name text,
    source_id integer NOT NULL,
    source_organization text,
    source_note text,
    api_unit text,
    measurement_unit text NOT NULL,
    frequency text NOT NULL DEFAULT 'annual',
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT indicators_code_nonblank CHECK (btrim(indicator_code) <> ''),
    CONSTRAINT indicators_unit_nonblank CHECK (btrim(measurement_unit) <> ''),
    CONSTRAINT indicators_annual_frequency CHECK (frequency = 'annual'),
    CONSTRAINT indicators_audit_order CHECK (last_updated_at >= first_seen_at)
);

CREATE TABLE public.observations (
    observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_id bigint NOT NULL,
    indicator_id bigint NOT NULL,
    observation_year integer NOT NULL,
    value numeric,
    api_unit text,
    decimal_places integer,
    obs_status text,
    source_retrieved_at timestamptz NOT NULL,
    source_last_updated date,
    source_snapshot_id text NOT NULL,
    source_page_file text NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT observations_country_fk FOREIGN KEY (country_id)
        REFERENCES public.countries (country_id) ON DELETE RESTRICT,
    CONSTRAINT observations_indicator_fk FOREIGN KEY (indicator_id)
        REFERENCES public.indicators (indicator_id) ON DELETE RESTRICT,
    CONSTRAINT observations_natural_key UNIQUE (country_id, indicator_id, observation_year),
    CONSTRAINT observations_year_range CHECK (observation_year BETWEEN 1900 AND 2100),
    -- SQL NULL passes this check; special non-finite numbers do not.
    CONSTRAINT observations_value_finite CHECK (
        value NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)
    ),
    CONSTRAINT observations_decimal_nonnegative CHECK (decimal_places >= 0),
    CONSTRAINT observations_snapshot_nonblank CHECK (btrim(source_snapshot_id) <> ''),
    CONSTRAINT observations_page_nonblank CHECK (btrim(source_page_file) <> ''),
    CONSTRAINT observations_audit_order CHECK (last_updated_at >= first_seen_at)
);

COMMIT;
