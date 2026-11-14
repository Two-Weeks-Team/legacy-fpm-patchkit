import { D1Store } from './d1-store.ts';
import { runBatch } from './batch.ts';
import { readView, payload, backlogMarkdown, statusFor, KINDS } from './export.ts';
import type { Kind } from './export.ts';
import seed from './seed.ts';
type WorkerEnv = Env & { GITHUB_READ_TOKEN?: string };

async function authorized(request: Request, secret: string): Promise<boolean> {
  if (!secret || secret.length < 32) return false;
  const header = request.headers.get('Authorization') ?? '';
  if (!header.startsWith('Bearer ') || header.length > 512) return false;
  const a = new TextEncoder().encode(header.slice(7)); const b = new TextEncoder().encode(secret);
  return a.byteLength === b.byteLength && crypto.subtle.timingSafeEqual(a, b);
}
function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), { status, headers: { 'Content-Type':'application/json; charset=utf-8',
    'Cache-Control':'no-store', 'Access-Control-Allow-Origin':'*', 'X-Content-Type-Options':'nosniff' } });
}
export default {
  async fetch(request, env): Promise<Response> {
    const path = new URL(request.url).pathname;
    if (path === '/internal/sync') {
      if (request.method !== 'POST') return json({error:'POST required'},405);
      if (!env.SYNC_TOKEN || env.SYNC_TOKEN.length < 32) return json({error:'Sync control is not configured'},503);
      if (!await authorized(request,env.SYNC_TOKEN)) return json({error:'Unauthorized'},401);
      try {
        const report = await runBatch(new D1Store(env.DB),seed,{trigger:'manual', githubToken:env.GITHUB_READ_TOKEN});
        console.log(JSON.stringify({event:'advisory_sync',...report}));
        return json({report},report.status==='SUCCESS'?200:report.status==='BUSY'?409:502);
      } catch { console.error(JSON.stringify({event:'advisory_sync_storage_failure'})); return json({error:'Sync storage unavailable'},503); }
    }
    if (!['GET','HEAD'].includes(request.method)) return json({error:'Read-only endpoint'},405);
    if (path === '/') return json({service:'PHP official advisory collector',schedule:'0 * * * * (UTC)',
      endpoints:['/status.json','/catalog.json','/coverage.json','/changes.json','/backlog.json','/backlog.md'],
      purpose:'Collection and implementation worklists; no patch execution or automatic fixed verdicts.'});
    const md = path === '/backlog.md';
    const name = path.replace(/^\//,'').replace(/\.json$/,'');
    const kind = KINDS.find(k=>k===name);
    if (!md && (!kind || path !== '/'+kind+'.json')) return json({error:'Not found'},404);
    try {
      const view = await readView(new D1Store(env.DB));
      const response = md ? new Response(backlogMarkdown(view), {headers:{'Content-Type':'text/markdown; charset=utf-8','Cache-Control':'no-store','Access-Control-Allow-Origin':'*','X-Content-Type-Options':'nosniff'}}) :
        json(payload(view,kind as Kind),kind==='status'&&statusFor(view).state!=='HEALTHY'?503:200);
      return request.method==='HEAD'?new Response(null,{status:response.status,headers:response.headers}):response;
    } catch { console.error(JSON.stringify({event:'advisory_read_storage_failure'})); return json({error:'Stored advisory data unavailable'},503); }
  },
  scheduled(controller,env,ctx): void {
    ctx.waitUntil((async()=>{
      const report=await runBatch(new D1Store(env.DB),seed,{trigger:'cron:'+controller.cron, githubToken:env.GITHUB_READ_TOKEN});
      console.log(JSON.stringify({event:'advisory_sync',...report}));
      if(report.status==='FAILED') throw new Error('Scheduled advisory collection failed');
    })());
  },
} satisfies ExportedHandler<WorkerEnv>;
