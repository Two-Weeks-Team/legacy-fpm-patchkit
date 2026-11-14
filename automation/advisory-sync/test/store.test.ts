import test, { before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';
import { D1Store } from '../src/d1-store.ts';
import { buildSnapshot } from '../src/core.ts';
import { fixture } from './fixtures.ts';
import type { BatchReport } from '../src/types.ts';

let mf: Miniflare;
let store: D1Store;
const report = (id: string, status: 'SUCCESS' | 'FAILED' = 'SUCCESS'): BatchReport => ({
  runId: id, status, trigger: 'test', startedAt: new Date().toISOString(), finishedAt: new Date().toISOString(),
});
before(async () => {
  mf = new Miniflare(convertV4MiniflareOptions({ cf:false, modules: true, script: 'export default { fetch() { return new Response("ok") } }',
    compatibilityDate: '2026-11-14', d1Databases: { DB: 'test-advisory-sync' }, d1Persist: false }));
  const db = await mf.getD1Database('DB');
  await db.exec((await readFile('migrations/0001_init.sql', 'utf8')).replace(/\n/g, ' '));
  store = new D1Store(db);
});
after(async () => { await mf?.dispose(); });
beforeEach(async () => {
  const db = await mf.getD1Database('DB');
  await db.batch([db.prepare('DELETE FROM snapshots'), db.prepare('DELETE FROM runs'),
    db.prepare('UPDATE sync_control SET lease_token=NULL,lease_until=NULL,current_revision=NULL,last_success_at=NULL,last_run_id=NULL,last_success_run_id=NULL')]);
});
async function committed(id = 'first') {
  const seed = await fixture(); const r = await buildSnapshot(seed, undefined, seed.catalog);
  assert.equal(await store.acquire(id, Date.now(), Date.now() + 120_000), true);
  await store.begin(id, 'test', new Date().toISOString()); await store.commit(id, r.snapshot, report(id));
  return r.snapshot;
}

test('real D1 transaction commits a complete snapshot and success watermark', async () => {
  const snapshot = await committed(); const value = await store.load();
  assert.equal(value?.snapshot?.revision, snapshot.revision);
  assert.equal(value?.lastAttempt?.status, 'SUCCESS'); assert.ok(value?.lastSuccessAt);
});

test('failed collection records failure but preserves last complete snapshot and watermark', async () => {
  const snapshot = await committed(); const before = await store.load();
  assert.equal(await store.acquire('second', Date.now(), Date.now() + 120_000), true);
  await store.begin('second', 'test', new Date().toISOString());
  await store.fail('second', { ...report('second', 'FAILED'), error: 'GitHub HTTP 403' });
  const after = await store.load();
  assert.equal(after?.snapshot?.revision, snapshot.revision); assert.equal(after?.lastSuccessAt, before?.lastSuccessAt);
  assert.equal(after?.lastAttempt?.status, 'FAILED');
});

test('duplicate unchanged snapshots are stored once while each run remains auditable', async () => {
  await committed('first'); await committed('second');
  const db = await mf.getD1Database('DB');
  assert.equal((await db.prepare('SELECT count(*) AS n FROM snapshots').first<{n:number}>())?.n, 1);
  assert.equal((await db.prepare('SELECT count(*) AS n FROM runs').first<{n:number}>())?.n, 2);
});

test('overlapping job cannot acquire the lease', async () => {
  assert.equal(await store.acquire('one', Date.now(), Date.now() + 120_000), true);
  assert.equal(await store.acquire('two', Date.now(), Date.now() + 120_000), false);
});

test('stale lease owner cannot publish and the transaction rolls back its attempted snapshot', async () => {
  const original = await committed('base');
  assert.equal(await store.acquire('old', Date.now(), Date.now() + 120_000), true);
  await store.begin('old', 'test', new Date().toISOString());
  const db = await mf.getD1Database('DB'); await db.prepare('UPDATE sync_control SET lease_until=0').run();
  assert.equal(await store.acquire('new', Date.now(), Date.now() + 120_000), true);
  const seed = await fixture(); seed.sourceHash = 'b'.repeat(64);
  const newer = await buildSnapshot(seed, undefined, seed.catalog);
  await assert.rejects(store.commit('old', newer.snapshot, report('old')), /CHECK|fence|lease/);
  assert.equal((await store.load())?.snapshot?.revision, original.revision);
  assert.equal((await db.prepare('SELECT count(*) AS n FROM snapshots').first<{n:number}>())?.n, 1);
});


test('a dangling D1 current revision fails closed instead of silently serving the seed', async () => {
  await committed();
  const db = await mf.getD1Database('DB');
  await db.prepare('DELETE FROM snapshots').run();
  await assert.rejects(store.load(), /missing|incomplete/i);
});
