import test from 'node:test';
import assert from 'node:assert/strict';
import seed from '../src/seed.ts';
import { buildSnapshot } from '../src/core.ts';

test('reviewed public seed retains all 66 advisories and the exact 2/13/51 classification', async () => {
  const r = await buildSnapshot(seed, undefined, seed.catalog);
  assert.equal(r.snapshot.catalog.length, 66);
  assert.deepEqual(r.snapshot.counts, { RESOLVED: 2, NOT_APPLICABLE: 13, PLANNED: 51 });
});
