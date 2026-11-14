import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runBatch } from '../src/batch.ts';
import { raw } from './fixtures.ts';
import { FileStore } from '../src/file-store.ts';
import { buildSnapshot } from '../src/core.ts';
import { fixture } from './fixtures.ts';
import type { BatchReport } from '../src/types.ts';
const report = (id: string, status: 'SUCCESS' | 'FAILED' = 'SUCCESS'): BatchReport => ({ runId: id, status, trigger: 'test', startedAt: new Date().toISOString(), finishedAt: new Date().toISOString() });
async function folder() { return join(await mkdtemp(join(tmpdir(), 'advisory-store-')), 'state'); }

test('local atomic checkpoint preserves complete result and records later failure', async () => {
  const dir = await folder(); const store = new FileStore(dir); const seed = await fixture();
  const { snapshot } = await buildSnapshot(seed, undefined, seed.catalog);
  assert.equal(await store.acquire('first', Date.now(), Date.now() + 120000), true);
  await store.begin('first', 'test', new Date().toISOString()); await store.commit('first', snapshot, report('first'));
  const before = await store.load();
  assert.equal(await store.acquire('second', Date.now(), Date.now() + 120000), true);
  await store.fail('second', report('second', 'FAILED'));
  const after = await new FileStore(dir).load();
  assert.equal(after?.snapshot?.revision, snapshot.revision); assert.equal(after?.lastSuccessAt, before?.lastSuccessAt);
  assert.equal(after?.lastAttempt?.status, 'FAILED');
});

test('separate local processes cannot both own the same state lock', async () => {
  const dir = await folder(); const a = new FileStore(dir), b = new FileStore(dir);
  assert.equal(await a.acquire('one', Date.now(), Date.now() + 120000), true);
  assert.equal(await b.acquire('two', Date.now(), Date.now() + 120000), false);
  await a.release('one'); assert.equal(await b.acquire('two', Date.now(), Date.now() + 120000), true);
  await b.release('two');
});

test('an existing unrelated directory is refused without changing its files', async () => {
  const dir = await folder(); await mkdir(dir); await writeFile(join(dir, 'keep.txt'), 'original');
  await assert.rejects(new FileStore(dir).acquire('one', Date.now(), Date.now()+120000), /owned|unrelated/);
  assert.equal(await readFile(join(dir, 'keep.txt'), 'utf8'), 'original');
});

test('state symlinks are rejected without reading or overwriting their target', async () => {
  const dir = await folder(); const store = new FileStore(dir);
  assert.equal(await store.acquire('one', Date.now(), Date.now()+120000), true); await store.release('one');
  const outside = join(dir, '..', 'outside.json'); await writeFile(outside, 'original');
  await symlink(outside, join(dir, 'current.json'));
  await assert.rejects(store.load(), /symbolic|symlink|link|ELOOP/);
  assert.equal(await readFile(outside, 'utf8'), 'original');
});


test('a committed local checkpoint stays successful when lock cleanup fails', async () => {
  const dir = await folder();
  class CleanupFailureStore extends FileStore {
    override async release(_id: string): Promise<void> { throw new Error('simulated local lock cleanup failure'); }
  }
  const result = await runBatch(new CleanupFailureStore(dir), await fixture(), {
    trigger: 'cleanup-failure', fetcher: async () => new Response(JSON.stringify([raw()])),
  });
  assert.equal(result.status,'SUCCESS');
  assert.match(result.cleanupWarning ?? '', /lock|lease/i);
  const view = await new FileStore(dir).load();
  assert.equal(view?.lastSuccessReport?.status,'SUCCESS');
  assert.equal(view?.lastAttempt?.status,'SUCCESS');
});
