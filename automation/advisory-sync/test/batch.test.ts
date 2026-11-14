import test from 'node:test';
import assert from 'node:assert/strict';
import { runBatch } from '../src/batch.ts';
import { fixture, raw } from './fixtures.ts';
import type { Store, StoredView, Snapshot, BatchReport } from '../src/types.ts';

class MemoryStore implements Store {
  view: StoredView | undefined;
  busy = false;
  async acquire() { if (this.busy) return false; this.busy = true; return true; }
  async begin() {}
  async load() { return this.view; }
  async commit(_id: string, snapshot: Snapshot, report: BatchReport) {
    this.view = { snapshot, lastSuccessAt: report.finishedAt, lastAttempt: report, origin: 'collected' }; this.busy = false;
  }
  async fail(_id: string, report: BatchReport) {
    this.view = { snapshot: this.view?.snapshot ?? null, lastSuccessAt: this.view?.lastSuccessAt ?? null, lastAttempt: report, origin: this.view?.origin ?? 'seed' }; this.busy = false;
  }
  async release() { this.busy = false; }
}

test('shared batch keeps last complete publication after a later collection error', async () => {
  const store = new MemoryStore(); const seed = await fixture();
  const first = await runBatch(store, seed, { trigger: 'test', fetcher: async () => new Response(JSON.stringify([raw()])) });
  assert.equal(first.status, 'SUCCESS'); const before = store.view;
  const failed = await runBatch(store, seed, { trigger: 'test', fetcher: async () => new Response('limited', { status: 429 }) });
  assert.equal(failed.status, 'FAILED'); assert.equal(store.view?.snapshot, before?.snapshot);
  assert.equal(store.view?.lastSuccessAt, before?.lastSuccessAt); assert.match(failed.error!, /429/);
});

test('busy batch makes no upstream request and does not alter published evidence', async () => {
  const store = new MemoryStore(); store.busy = true;
  const seed = await fixture(); let called = false;
  const result = await runBatch(store, seed, { trigger: 'test', fetcher: async () => { called = true; return new Response('[]'); } });
  assert.equal(result.status, 'BUSY'); assert.equal(called, false); assert.equal(store.view, undefined);
});

test('unchanged scheduled collection advances success time without reporting content changes', async () => {
  const store = new MemoryStore(); const seed = await fixture();
  await runBatch(store, seed, { trigger: 'test', fetcher: async () => new Response(JSON.stringify([raw()])) });
  const second = await runBatch(store, seed, { trigger: 'scheduled', fetcher: async () => new Response(JSON.stringify([raw()])) });
  assert.equal(second.status, 'SUCCESS'); assert.equal(second.changed, false);
  assert.deepEqual(second.changes, { added: [], updated: [], withdrawn: [], missing: [] });
});
