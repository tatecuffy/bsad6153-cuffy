"""Validate a saved World Bank snapshot; connect only with explicit --load.

Default invocation is local-only and does not read .env. No API calls are made.
"""

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re

if __package__:
    from .fetch import FetchError, validate_observations, validate_page
else:
    from fetch import FetchError, validate_observations, validate_page

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'data/raw/world_bank/20261102T041022160331Z'
UNITS = {
    'FP.CPI.TOTL.ZG': 'annual percent',
    'SL.UEM.TOTL.ZS': 'percent of total labor force',
    'NY.GDP.MKTP.KD.ZG': 'annual percent',
}


class LoadError(ValueError):
    """Local snapshot or loader contract failed validation."""


@dataclass
class Snapshot:
    countries: list
    indicators: list
    observations: list

    def summary(self):
        numeric = sum(row[3] is not None for row in self.observations)
        return dict(countries=len(self.countries), indicators=len(self.indicators),
                    observations=len(self.observations), numeric=numeric,
                    nulls=len(self.observations) - numeric)


def read_json(path):
    def reject_constant(value):
        raise LoadError('Non-finite JSON number rejected.')
    return json.loads(path.read_text(encoding='utf-8'), parse_float=Decimal,
                      parse_constant=reject_constant)


def prepare_snapshot(directory=SNAPSHOT):
    """Read only manifest-listed pages, validate, and build database parameters."""
    directory = Path(directory)
    manifest = read_json(directory / 'manifest.json')
    if manifest['status'] != 'complete':
        raise LoadError('Only a complete snapshot can be loaded.')
    config = manifest['config']
    if (len(config['countries']) != 20 or len(set(config['countries'])) != 20
            or set(config['indicators']) != set(UNITS)
            or len(config['indicators']) != 3):
        raise LoadError('Unexpected country or indicator configuration.')
    retrieved = datetime.fromisoformat(manifest['started_at'])
    if retrieved.utcoffset() is None:
        raise LoadError('Retrieval timestamp must include a timezone.')
    expected_resources = {'countries'} | {
        prefix + code for code in UNITS for prefix in ('indicator_', 'observations_')}
    groups, files = {}, set()
    for entry in manifest['pages']:
        filename = entry['file']
        match = re.fullmatch(r'(.+)_page_(\d{3})\.json', filename)
        if not match or filename in files or match[1] not in expected_resources:
            raise LoadError('Unexpected or duplicate page filename.')
        files.add(filename)
        page = int(match[2])
        if entry['parameters']['page'] != page:
            raise LoadError('Manifest page number mismatch.')
        groups.setdefault(match[1], []).append((page, entry))
    if set(groups) != expected_resources or len(files) != manifest['api_pages']:
        raise LoadError('Manifest resource/page list is incomplete.')
    resources, provenance = {}, {}
    for resource, entries in groups.items():
        signature = None
        rows = []
        for number, (page, entry) in enumerate(sorted(entries), 1):
            if page != number:
                raise LoadError('Missing page in snapshot.')
            payload = read_json(directory / entry['file'])
            signature = validate_page(payload, page, config['per_page'], signature)
            if entry['records'] != len(payload[1]):
                raise LoadError('Manifest page record count mismatch.')
            if resource.startswith('observations_'):
                code = resource.removeprefix('observations_')
                if str(payload[0].get('sourceid')) != str(config['source']):
                    raise LoadError('Observation source mismatch.')
                updated = payload[0].get('lastupdated')
                updated = date.fromisoformat(updated) if updated else None
                for row in payload[1]:
                    if row['indicator']['id'] != code:
                        raise LoadError('Observation indicator/page mismatch.')
                    key = (row['countryiso3code'], code, row['date'])
                    if key in provenance:
                        raise LoadError('Duplicate observation key.')
                    provenance[key] = (updated, entry['file'])
            rows.extend(payload[1])
        if len(entries) != signature[0] or len(rows) != signature[1]:
            raise LoadError('Snapshot resource is missing pages.')
        resources[resource] = rows
    countries = resources['countries']
    indicators = [row for code in UNITS for row in resources['indicator_' + code]]
    observations = [row for code in UNITS for row in resources['observations_' + code]]
    country_ids = {row['id'] for row in countries}
    indicator_ids = {row['id'] for row in indicators}
    if len(countries) != 20 or country_ids != set(config['countries']):
        raise LoadError('Country metadata keys/count mismatch.')
    if len(indicators) != 3 or indicator_ids != set(UNITS):
        raise LoadError('Indicator metadata keys/count mismatch.')
    if any(row.get('region', {}).get('value') == 'Aggregates' for row in countries):
        raise LoadError('Aggregate regions are not selected countries.')
    for row in indicators:
        if str(row['source']['id']) != str(config['source']):
            raise LoadError('Indicator metadata source mismatch.')
    # Existing validator accepts floats, not Decimal. Validate a projection only;
    # the original Decimal values are retained for insertion without rounding.
    projected = []
    for row in observations:
        if not re.fullmatch(r'\d{4}', row['date']):
            raise LoadError('Observation year must be a four-digit year.')
        value = row['value']
        if isinstance(value, Decimal) and not value.is_finite():
            raise LoadError('Non-finite observation rejected.')
        projected.append(dict(row, value=float(value) if isinstance(value, Decimal) else value))
    counts = validate_observations(projected, country_ids, indicator_ids, config)
    if (len(observations), sum(counts.values())) != (960, 950):
        raise LoadError('Expected 960 observations, 950 numeric values and 10 nulls.')
    for field, actual in [('country_records', 20), ('indicator_records', 3),
                          ('observation_records', 960), ('non_missing_total', 950),
                          ('total_resource_records', 983)]:
        if manifest[field] != actual:
            raise LoadError('Manifest totals do not match validated snapshot.')
    if counts != manifest['non_missing_by_indicator']:
        raise LoadError('Manifest numeric counts mismatch.')
    for code in UNITS:
        subset = [row for row in observations if row['indicator']['id'] == code]
        coverage = dict(first_returned_year=min(row['date'] for row in subset),
                        last_returned_year=max(row['date'] for row in subset),
                        absent_country_year_slots=len(countries) *
                        (config['end_year'] - config['start_year'] + 1) - len(subset))
        if coverage != manifest['coverage_by_indicator'][code]:
            raise LoadError('Manifest coverage mismatch.')
    country_params = [(r['id'], r.get('iso2Code'), r.get('name'),
                       r.get('region', {}).get('id'), r.get('incomeLevel', {}).get('id'),
                       r.get('capitalCity')) for r in countries]
    indicator_params = [(r['id'], r.get('name'), int(r['source']['id']),
                         r.get('sourceOrganization'), r.get('sourceNote'), r.get('unit'),
                         UNITS[r['id']], 'annual') for r in indicators]
    observation_params = []
    for row in observations:
        key = (row['countryiso3code'], row['indicator']['id'], row['date'])
        updated, filename = provenance[key]
        precision = row.get('decimal')
        if precision is not None and (type(precision) is not int or precision < 0):
            raise LoadError('Invalid display precision.')
        observation_params.append((key[0], key[1], int(key[2]), row['value'],
                                   row.get('unit'), precision, row.get('obs_status'),
                                   retrieved, updated, directory.name, filename))
    return Snapshot(country_params, indicator_params, observation_params)


def insert_snapshot(conn, snapshot):
    """Atomically insert parents then children; conflicts preserve existing rows.

    Caller supplies a non-autocommit psycopg connection. No connection is opened
    here. Defaults create audit times; DO NOTHING preserves them on repeats.
    """
    if conn.autocommit:
        raise LoadError('Loader requires a non-autocommit connection.')
    inserted = dict(countries=0, indicators=0, observations=0)
    with conn.transaction():
        country_ids, indicator_ids = {}, {}
        for row in snapshot.countries:
            result = conn.execute('''INSERT INTO public.countries
                (iso3_code, iso2_code, name, region_code, income_level_code, capital_city)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (iso3_code) DO NOTHING''', row)
            inserted['countries'] += result.rowcount
            country_ids[row[0]] = conn.execute(
                'SELECT country_id FROM public.countries WHERE iso3_code = %s', (row[0],)).fetchone()[0]
        for row in snapshot.indicators:
            result = conn.execute('''INSERT INTO public.indicators
                (indicator_code, name, source_id, source_organization, source_note,
                 api_unit, measurement_unit, frequency)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (indicator_code) DO NOTHING''', row)
            inserted['indicators'] += result.rowcount
            indicator_ids[row[0]] = conn.execute(
                'SELECT indicator_id FROM public.indicators WHERE indicator_code = %s', (row[0],)).fetchone()[0]
        for row in snapshot.observations:
            params = (country_ids[row[0]], indicator_ids[row[1]]) + row[2:]
            result = conn.execute('''INSERT INTO public.observations
                (country_id, indicator_id, observation_year, value, api_unit, decimal_places,
                 obs_status, source_retrieved_at, source_last_updated, source_snapshot_id, source_page_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (country_id, indicator_id, observation_year) DO NOTHING''', params)
            inserted['observations'] += result.rowcount
    return inserted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--load', action='store_true', help='Explicitly connect and insert; default is local validation only.')
    args = parser.parse_args(argv)
    try:
        snapshot = prepare_snapshot()
        print(json.dumps(snapshot.summary()))
        if not args.load:
            print('Local validation only. No credentials read or database connection opened.')
            return 0
        # Credentials are read only after successful local validation and --load.
        import psycopg
        from dotenv import dotenv_values
        url = dotenv_values(ROOT / '.env').get('DATABASE_URL')
        if not url:
            raise LoadError('DATABASE_URL is unavailable.')
        with psycopg.connect(url, connect_timeout=10) as conn:
            inserted = insert_snapshot(conn, snapshot)
        print('Committed inserted rows: ' + json.dumps(inserted))
        return 0
    except Exception as error:
        # Never print raw exceptions: connection errors can contain secrets.
        print('Load failed; no automatic retry. Error type: ' + type(error).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
