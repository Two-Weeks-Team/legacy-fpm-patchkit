import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('CLI exports initial reviewed worklist without claiming a live sync or creating state', async () => {
  const state = join(await mkdtemp(join(tmpdir(), 'advisory-cli-')), 'new-state');
  const r = spawnSync(process.execPath, ['--import','tsx','src/cli.ts','export','--state-dir',state,'--kind','backlog'], { encoding:'utf8' });
  assert.equal(r.status, 0, r.stderr);
  const out = JSON.parse(r.stdout);
  assert.equal(out.status.state, 'NEVER_SYNCED'); assert.equal(out.items.length, 50);
  assert.deepEqual(out.status.counts, { RESOLVED:2, NOT_APPLICABLE:14, PLANNED:50 });
  await assert.rejects(access(state));
});
