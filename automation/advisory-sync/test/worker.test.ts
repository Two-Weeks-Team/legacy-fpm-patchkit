import test, { before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { Miniflare, convertV4MiniflareOptions, Response as MFResponse } from 'miniflare';
import seed from '../src/seed.ts';
let mf: Miniflare; let failing = false; let outboundCalls = 0;
const TOKEN = 'local-fixture-control-token-'.repeat(3);
before(async () => {
  const build = spawnSync(process.execPath, ['node_modules/wrangler/bin/wrangler.js','deploy','--dry-run','--outdir','.work/test-bundle'], { encoding:'utf8' });
  assert.equal(build.status, 0, build.stderr);
  mf = new Miniflare(convertV4MiniflareOptions({ cf:false, modules:true, scriptPath:resolve('.work/test-bundle/worker.js'),
    compatibilityDate:'2026-11-14', compatibilityFlags:['nodejs_compat'],
    d1Databases:{DB:'worker-http-test'}, d1Persist:false, bindings:{SYNC_TOKEN:TOKEN},
    outboundService: async (request) => {
      assert.equal(new URL(request.url).hostname, 'api.github.com'); outboundCalls++;
      return failing ? new MFResponse('limited',{status:429}) : new MFResponse(JSON.stringify(seed.catalog));
    },
  }));
  const db = await mf.getD1Database('DB');
  await db.exec((await readFile('migrations/0001_init.sql','utf8')).replace(/\n/g,' '));
});
after(async () => { await mf?.dispose(); });
beforeEach(async () => {
  failing = false; outboundCalls = 0;
  const db = await mf.getD1Database('DB');
  await db.batch([db.prepare('DELETE FROM snapshots'),db.prepare('DELETE FROM runs'),
    db.prepare('UPDATE sync_control SET lease_token=NULL,lease_until=NULL,current_revision=NULL,last_success_at=NULL,last_run_id=NULL,last_success_run_id=NULL')]);
});

function object(value: unknown): Record<string, unknown> {
  assert.ok(value && typeof value === 'object' && !Array.isArray(value));
  return value as Record<string, unknown>;
}
async function body(response: MFResponse) {
  const value=object(await response.json());
  return {status:object(value.status),items:Array.isArray(value.items)?value.items:[]};
}

test('public seed export is read-only and truthfully reports no successful live collection', async () => {
  const status=await mf.dispatchFetch('http://worker/status.json'); assert.equal(status.status,503);
  assert.equal((await body(status)).status.state,'NEVER_SYNCED');
  const backlog=await mf.dispatchFetch('http://worker/backlog.json'); assert.equal(backlog.status,200);
  assert.equal((await body(backlog)).items.length,51); assert.equal(outboundCalls,0);
});

test('unauthorized callers cannot sync and readonly routes reject mutations', async () => {
  assert.equal((await mf.dispatchFetch('http://worker/internal/sync',{method:'POST'})).status,401);
  assert.equal((await mf.dispatchFetch('http://worker/internal/sync')).status,405);
  assert.equal((await mf.dispatchFetch('http://worker/backlog.json',{method:'POST'})).status,405);
  assert.equal(outboundCalls,0);
});

test('authenticated HTTP sync publishes complete fixture data in actual workerd/D1 runtime', async () => {
  const run=await mf.dispatchFetch('http://worker/internal/sync',{method:'POST',headers:{Authorization:'Bearer '+TOKEN}});
  assert.equal(run.status,200,await run.clone().text());
  const status=await mf.dispatchFetch('http://worker/status.json'); assert.equal(status.status,200);
  const out=await body(status); assert.equal(out.status.state,'HEALTHY');
  assert.deepEqual(out.status.counts,{RESOLVED:2,NOT_APPLICABLE:13,PLANNED:51});
  assert.equal((await body(await mf.dispatchFetch('http://worker/catalog.json'))).items.length,66);
});

test('later upstream failure preserves public snapshot and exposes degraded health', async () => {
  const headers={Authorization:'Bearer '+TOKEN};
  assert.equal((await mf.dispatchFetch('http://worker/internal/sync',{method:'POST',headers})).status,200);
  const original=await body(await mf.dispatchFetch('http://worker/catalog.json'));
  failing=true;
  assert.equal((await mf.dispatchFetch('http://worker/internal/sync',{method:'POST',headers})).status,502);
  assert.equal((await mf.dispatchFetch('http://worker/status.json')).status,503);
  const after=await body(await mf.dispatchFetch('http://worker/catalog.json'));
  assert.equal(after.status.revision,original.status.revision); assert.equal(after.status.lastSuccessAt,original.status.lastSuccessAt);
  assert.equal(after.status.state,'FAILED');
});

test('scheduled handler runs the same batch and publishes a successful recorded Cron attempt', async () => {
  const worker=await mf.getWorker(); const result=await worker.scheduled({cron:'0 * * * *',scheduledTime:new Date()});
  assert.equal(result.outcome,'ok');
  const out=await body(await mf.dispatchFetch('http://worker/status.json'));
  assert.equal(out.status.state,'HEALTHY'); assert.equal(object(out.status.lastAttempt).trigger,'cron:0 * * * *');
});
