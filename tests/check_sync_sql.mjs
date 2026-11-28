// Optional PostgreSQL-engine check. Pass the path to PGlite's dist/index.js.
// Uses a fresh in-memory database, never a network connection or .env.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const { PGlite } = await import(pathToFileURL(resolve(process.argv[2])).href);
const readRepoFile = path => readFile(new URL('../' + path, import.meta.url), 'utf8');
const db = await PGlite.create();
const source = await readRepoFile('ingest/sync.py');

function parameters(sql) {
    let index = 0;
    return sql.replaceAll('%s', () => '$' + ++index);
}

const upsert = parameters(source.split('UPSERT_OBSERVATION = """')[1].split('"""')[0]);
const record = parameters(source.split('def record_run(')[1].split('"""')[1]);
const before = '00000000-0000-0000-0000-000000000001';
const revised = '00000000-0000-0000-0000-000000000002';
const rerun = '00000000-0000-0000-0000-000000000003';
const legacy = '00000000-0000-0000-0000-000000000004';
const failure = '00000000-0000-0000-0000-000000000005';
const timestamp = '2026-01-01T00:00:00Z';

function observation(value, snapshot) {
    return [1, 1, 2024, value, null, null, null, timestamp, null, snapshot, 'synthetic.json'];
}

async function writeRun(client, id, status, counts, fetched, reason = null) {
    await client.query(record, [id, timestamp, timestamp, status, ...counts, 'manual', fetched, reason]);
}

try {
    await db.exec('CREATE ROLE anon; CREATE ROLE authenticated;');
    await db.exec(await readRepoFile('db/schema.sql'));
    await db.exec(await readRepoFile('db/migrations/003_sync_runs.sql'));
    await db.exec(await readRepoFile('db/migrations/004_app_reader.sql'));
    await db.query(`INSERT INTO public.sync_runs (run_id, started_at, finished_at, status,
                     inserted_count, updated_count, unchanged_count)
                     VALUES ($1, $2, $2, 'failure', 0, 0, 0)`, [before, timestamp]);
    await db.exec(await readRepoFile('db/migrations/005_sync_run_details.sql'));
    await db.query(`INSERT INTO public.sync_runs (run_id, started_at, finished_at, status,
                     inserted_count, updated_count, unchanged_count)
                     VALUES ($1, $2, $2, 'failure', 0, 0, 0)`, [legacy, timestamp]);

    await db.exec(`INSERT INTO public.countries (iso3_code) VALUES ('USA');
                   INSERT INTO public.indicators (indicator_code, source_id, measurement_unit)
                   VALUES ('FP.CPI.TOTL.ZG', 2, 'annual percent');`);
    await db.query(upsert, observation('2.5', 'initial'));

    await db.transaction(async tx => {
        assert.equal((await tx.query(upsert, observation('3.5', 'revision'))).affectedRows, 1);
        await writeRun(tx, revised, 'success', [0, 1, 0], 1);
    });
    const result = await db.query('SELECT value, source_snapshot_id, last_updated_at FROM public.observations');
    assert.equal(result.rows[0].value, '3.5');
    assert.equal(result.rows[0].source_snapshot_id, 'revision');

    await db.transaction(async tx => {
        assert.equal((await tx.query(upsert, observation('3.5', 'repeat'))).affectedRows, 0);
        await writeRun(tx, rerun, 'success', [0, 0, 1], 1);
    });
    assert.deepEqual((await db.query('SELECT value, source_snapshot_id, last_updated_at FROM public.observations')).rows,
                     result.rows);

    await assert.rejects(db.transaction(async tx => {
        await tx.query(upsert, observation('4.5', 'rollback'));
        await writeRun(tx, failure, 'invalid_status', [0, 1, 0], 1);
    }), { code: '23514' });
    await writeRun(db, failure, 'failed', [0, 0, 0], 1, 'Synthetic log failure.');
    assert.deepEqual((await db.query('SELECT value, source_snapshot_id, last_updated_at FROM public.observations')).rows,
                     result.rows);

    await db.exec('SET ROLE app_reader');
    const { rows } = await db.query(`SELECT run_id, status, records_fetched, records_inserted,
        records_updated, unchanged_count, "trigger" FROM public.sync_runs ORDER BY run_id`);
    assert.deepEqual(rows.map(r => Object.values(r)), [
        [before, 'failed', null, 0, 0, 0, null],
        [revised, 'success', 1, 0, 1, 0, 'manual'],
        [rerun, 'success', 1, 0, 0, 1, 'manual'],
        [legacy, 'failed', null, 0, 0, 0, null],
        [failure, 'failed', 1, 0, 0, 0, 'manual'],
    ]);
    console.log(JSON.stringify(rows, null, 2));
    console.log('PASS: migration, revision, unchanged rerun, transaction rollback, and reader-visible run history.');
} finally {
    await db.close();
}
