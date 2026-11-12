"""Portable synthetic unit tests plus an optional local-snapshot integration check.

Generated fixture records are invented test data, never economic evidence.
No production loader settings or expected totals are patched for parser tests.
"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ingest.fetch import FetchError
from ingest.load import (LoadError, SNAPSHOT, insert_snapshot, main,
                         prepare_snapshot)


def write_synthetic_snapshot(folder):
    """Expand a small synthetic definition to the loader's fixed-size contract."""
    from ingest.load import UNITS
    folder.mkdir()
    codes = ['AA' + chr(ord('A') + n) for n in range(20)]
    manifest = dict(status='complete', started_at='2026-01-01T00:00:00+00:00',
                    config=dict(countries=codes, indicators=list(UNITS), source='2',
                                start_year=2010, end_year=2026, per_page=100,
                                minimum_non_missing=500), pages=[],
                    country_records=20, indicator_records=3, observation_records=960,
                    non_missing_total=950, total_resource_records=983,
                    non_missing_by_indicator={}, coverage_by_indicator={})

    def resource(name, rows, observation=False):
        for start in range(0, len(rows), 100):
            page = start // 100 + 1
            chunk = rows[start:start + 100]
            metadata = dict(page=page, pages=(len(rows) + 99) // 100,
                            per_page=100, total=len(rows))
            if observation:
                metadata.update(sourceid='2', lastupdated='2025-12-31')
            filename = f'{name}_page_{page:03d}.json'
            (folder / filename).write_text(json.dumps([metadata, chunk]), encoding='utf-8')
            manifest['pages'].append(dict(file=filename, parameters=dict(page=page),
                                          records=len(chunk)))

    resource('countries', [dict(id=code, iso2Code='', name=f'Synthetic country {n}',
                               region=dict(id='', value=''), incomeLevel=dict(id=''),
                               capitalCity='') for n, code in enumerate(codes)])
    for code in UNITS:
        resource('indicator_' + code, [dict(id=code, name='Synthetic indicator',
                 source=dict(id='2'), unit='', sourceNote='Synthetic fixture only')])
        rows = [dict(countryiso3code=country, indicator=dict(id=code), date=str(year),
                     value=(-1.25 if year == 2010 else 0 if year == 2011 else 1.125),
                     unit='', decimal=1, obs_status='')
                for country in codes for year in range(2010, 2026)]
        if code == 'FP.CPI.TOTL.ZG':
            for row in rows[:10]:
                row['value'] = None
        resource('observations_' + code, rows, observation=True)
        manifest['non_missing_by_indicator'][code] = sum(r['value'] is not None for r in rows)
        manifest['coverage_by_indicator'][code] = dict(first_returned_year='2010',
                last_returned_year='2025', absent_country_year_slots=20)
    manifest['api_pages'] = len(manifest['pages'])
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')


class Result:
    def __init__(self, rowcount=0, row=None):
        self.rowcount, self.row = rowcount, row

    def fetchone(self):
        return self.row


class MemoryConnection:
    """Small SQL-call double; not a substitute for PostgreSQL integration tests."""
    autocommit = False

    def __init__(self, fail=False):
        self.tables = {name: {} for name in ('countries', 'indicators', 'observations')}
        self.fail = fail
        self.commits = self.rollbacks = 0

    @contextmanager
    def transaction(self):
        before = deepcopy(self.tables)
        try:
            yield
        except Exception:
            self.tables = before
            self.rollbacks += 1
            raise
        else:
            self.commits += 1

    def execute(self, sql, params):
        self_test = sql.strip().startswith('INSERT')
        table = next(name for name in self.tables if 'public.' + name in sql)
        if not self_test:
            return Result(row=(self.tables[table][params[0]][0],))
        if '%s' not in sql or 'ON CONFLICT' not in sql or 'DO NOTHING' not in sql:
            raise AssertionError('Expected parameterized conflict-safe insertion')
        key = params[:3] if table == 'observations' else params[0]
        if table == 'observations':
            if self.fail:
                raise RuntimeError('Synthetic insertion failure')
            if params[0] not in [v[0] for v in self.tables['countries'].values()]:
                raise AssertionError('Missing country parent')
            if params[1] not in [v[0] for v in self.tables['indicators'].values()]:
                raise AssertionError('Missing indicator parent')
        if key in self.tables[table]:
            return Result(0)
        self.tables[table][key] = (len(self.tables[table]) + 1, params)
        return Result(1)


class LoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name) / 'synthetic_fixture'
        write_synthetic_snapshot(cls.folder)
        cls.snapshot = prepare_snapshot(cls.folder)

    def test_synthetic_counts_precision_nulls_absence_and_provenance(self):
        self.assertEqual(self.snapshot.summary(), dict(countries=20, indicators=3,
                         observations=960, numeric=950, nulls=10))
        rows = self.snapshot.observations
        self.assertEqual(len({r[:3] for r in rows}), 960)
        self.assertEqual({r[2] for r in rows}, set(range(2010, 2026)))
        sample = next(r for r in rows if r[:3] == ('AAB', 'FP.CPI.TOTL.ZG', 2020))
        self.assertEqual(sample[3], Decimal('1.125'))
        self.assertEqual(sample[7], datetime.fromisoformat('2026-01-01T00:00:00+00:00'))
        self.assertEqual(sample[8], date(2025, 12, 31))
        self.assertEqual(sample[9], 'synthetic_fixture')
        self.assertTrue(sample[10].startswith('observations_FP.CPI.TOTL.ZG_page_'))
        self.assertTrue(any(r[3] < 0 for r in rows if r[3] is not None))
        self.assertTrue(any(r[3] == 0 for r in rows if r[3] is not None))

    def test_parent_order_idempotency_and_unchanged_parameters(self):
        conn = MemoryConnection()
        self.assertEqual(insert_snapshot(conn, self.snapshot),
                         dict(countries=20, indicators=3, observations=960))
        before = deepcopy(conn.tables)
        self.assertEqual(insert_snapshot(conn, self.snapshot),
                         dict(countries=0, indicators=0, observations=0))
        self.assertEqual(conn.tables, before)
        self.assertEqual(conn.commits, 2)

    def test_failure_rolls_back_parent_inserts(self):
        conn = MemoryConnection(fail=True)
        with self.assertRaises(RuntimeError):
            insert_snapshot(conn, self.snapshot)
        self.assertTrue(all(not values for values in conn.tables.values()))
        self.assertEqual(conn.rollbacks, 1)

    def test_default_cli_never_connects_or_reads_credentials(self):
        with patch('ingest.load.prepare_snapshot', return_value=self.snapshot), \
                patch('psycopg.connect', side_effect=AssertionError('No database')), \
                patch('dotenv.dotenv_values', side_effect=AssertionError('No secrets')), \
                patch('requests.Session', side_effect=AssertionError('No API')), \
                patch('builtins.print'):
            self.assertEqual(main([]), 0)

    def test_corrupt_snapshot_rejected_before_connection(self):
        mutations = ('incomplete', 'missing_page', 'duplicate_key', 'null_count',
                     'unknown_country', 'unsafe_filename', 'invalid_numeric')
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'synthetic_fixture'
                shutil.copytree(self.folder, folder)
                manifest_path = folder / 'manifest.json'
                manifest = json.loads(manifest_path.read_text())
                page_path = folder / 'observations_FP.CPI.TOTL.ZG_page_001.json'
                page = json.loads(page_path.read_text())
                if mutation == 'incomplete':
                    manifest['status'] = 'incomplete'
                elif mutation == 'missing_page':
                    manifest['pages'].pop()
                elif mutation == 'duplicate_key':
                    page[1][1] = deepcopy(page[1][0])
                elif mutation == 'null_count':
                    page[1][0]['value'] = 0
                elif mutation == 'unknown_country':
                    page[1][0]['countryiso3code'] = 'XYZ'
                elif mutation == 'unsafe_filename':
                    manifest['pages'][0]['file'] = '../countries_page_001.json'
                elif mutation == 'invalid_numeric':
                    page[1][0]['value'] = True
                manifest_path.write_text(json.dumps(manifest))
                page_path.write_text(json.dumps(page))
                with self.assertRaises((FetchError, ValueError)):
                    prepare_snapshot(folder)


@unittest.skipUnless((SNAPSHOT / 'manifest.json').is_file(),
                     'Optional integration check: approved local raw snapshot is absent')
class FullSnapshotTests(unittest.TestCase):
    def test_real_snapshot_counts_precision_nulls_and_provenance(self):
        snapshot = prepare_snapshot()
        self.assertEqual(snapshot.summary(), dict(countries=20, indicators=3,
                         observations=960, numeric=950, nulls=10))
        rows = snapshot.observations
        self.assertEqual(len({r[:3] for r in rows}), 960)
        self.assertEqual({r[2] for r in rows}, set(range(2010, 2026)))
        usa = next(r for r in rows if r[:3] == ('USA', 'FP.CPI.TOTL.ZG', 2020))
        self.assertEqual(usa[3], Decimal('1.23358439630629'))
        self.assertEqual(usa[7], datetime.fromisoformat('2026-11-02T04:10:22.160331+00:00'))
        self.assertEqual(usa[8], date(2026, 10, 8))
        self.assertEqual(usa[9], SNAPSHOT.name)
        self.assertTrue(usa[10].startswith('observations_FP.CPI.TOTL.ZG_page_'))
        self.assertTrue(any(r[3] < 0 for r in rows if r[3] is not None))


if __name__ == '__main__':
    unittest.main()
