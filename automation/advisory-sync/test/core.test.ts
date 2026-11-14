import test from 'node:test';
import assert from 'node:assert/strict';
import { normalize, fingerprint, buildSnapshot, markdown } from '../src/core.ts';

import { raw, fixture } from './fixtures.ts';

test('initial reviewed verdict is retained only for matching source and upstream identity', async () => {
  const seed = await fixture();
  const { snapshot, changes } = await buildSnapshot(seed, undefined, seed.catalog);
  assert.equal(snapshot.assessments[0].status, 'RESOLVED');
  assert.equal(snapshot.assessments[0].validation, 'source-only');
  assert.deepEqual(changes.added, []);
});

test('new advisory gets concrete planned work, never an automatic fixed verdict', async () => {
  const seed = await fixture();
  const b = normalize(raw('GHSA-dddd-eeee-ffff'));
  const r = await buildSnapshot(seed, undefined, [...seed.catalog, b]);
  const row = r.snapshot.assessments.find(x => x.id === b.ghsa_id)!;
  assert.equal(row.status, 'PLANNED'); assert.match(row.action, /source|implement/i);
  assert.deepEqual(r.changes.added, [b.ghsa_id]);
});

test('updated advisory loses stale fixed credit while preserving its reviewed revision', async () => {
  const seed = await fixture(); const a = normalize({ ...raw(), summary: 'New root cause' });
  const r = await buildSnapshot(seed, undefined, [a]);
  assert.equal(r.snapshot.assessments[0].status, 'PLANNED');
  assert.equal(r.snapshot.assessments[0].reviewedStatus, 'RESOLVED');
  assert.deepEqual(r.changes.updated, [a.ghsa_id]);
});

test('a different source revision cannot inherit a human fixed verdict', async () => {
  const seed = await fixture(); seed.sourceHash = 'b'.repeat(64);
  const r = await buildSnapshot(seed, undefined, seed.catalog);
  assert.equal(r.snapshot.assessments[0].status, 'PLANNED');
});

test('missing entries remain in the snapshot and become explicit review work', async () => {
  const seed = await fixture(); const r = await buildSnapshot(seed, undefined, []);
  assert.equal(r.snapshot.catalog.length, 1);
  assert.equal(r.snapshot.assessments[0].presence, 'missing');
  assert.equal(r.snapshot.assessments[0].status, 'PLANNED');
  assert.deepEqual(r.changes.missing, [seed.catalog[0].ghsa_id]);
});

test('withdrawal is retained as a revision and does not imply fixed protection', async () => {
  const seed = await fixture();
  const a = normalize({ ...raw(), withdrawn_at: '2026-11-10T00:00:00Z' });
  const r = await buildSnapshot(seed, undefined, [a]);
  assert.equal(r.snapshot.assessments[0].status, 'PLANNED');
  assert.deepEqual(r.changes.withdrawn, [a.ghsa_id]);
});

test('unchanged batches produce identical snapshot identities', async () => {
  const seed = await fixture(); const first = await buildSnapshot(seed, undefined, seed.catalog);
  const second = await buildSnapshot(seed, first.snapshot, seed.catalog);
  assert.equal(second.snapshot.revision, first.snapshot.revision);
  assert.deepEqual(second.changes.updated, []);
});

test('normalization rejects nonofficial URLs and malformed identifiers', () => {
  assert.throws(() => normalize({ ...raw(), html_url: 'https://evil.example/x' }));
  assert.throws(() => normalize({ ...raw(), ghsa_id: 'bad' }));
});

test('official blank package metadata is retained without dropping its advisory', () => {
  const a = raw(); a.vulnerabilities[0].package = { ecosystem: '', name: '' };
  const result = normalize(a);
  assert.equal(result.vulnerabilities[0].package.name, '');
  assert.equal(result.ghsa_id, a.ghsa_id);
});

test('Markdown output escapes advisory-supplied formatting and HTML', async () => {
  const seed = await fixture(); seed.catalog = [normalize(raw(undefined, '<img src=x> | [click](javascript:x)\n# header'))];
  const r = await buildSnapshot(seed, undefined, seed.catalog);
  const out = markdown(r.snapshot);
  assert.doesNotMatch(out, /<img|\]\(javascript:/); assert.match(out, /&lt;img/);
});

test('stored snapshots require matching content identity and complete assessment rows', async () => {
  const { decodeSnapshot } = await import('../src/core.ts');
  const seed = await fixture(); const r = await buildSnapshot(seed, undefined, seed.catalog);
  assert.equal((await decodeSnapshot(JSON.stringify(r.snapshot))).revision, r.snapshot.revision);
  await assert.rejects(decodeSnapshot(JSON.stringify({ ...r.snapshot, counts: { RESOLVED: 999, NOT_APPLICABLE: 0, PLANNED: 0 } })), /identity|counts/);
});
