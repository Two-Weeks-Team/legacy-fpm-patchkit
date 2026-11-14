import type { Advisory, Vulnerability, Seed, Snapshot, Assessment, Changes, Status } from './types.ts';

function record(v: unknown): v is Record<string, unknown> { return typeof v === 'object' && v !== null && !Array.isArray(v); }
function text(v: unknown, field: string, max = 4096): string {
  if (typeof v !== 'string' || !v.trim() || v.length > max) throw new Error('Invalid upstream field: ' + field);
  return v.trim();
}
function optionalText(v: unknown, field: string, max = 4096): string {
  if (typeof v !== 'string' || v.length > max) throw new Error('Invalid upstream field: ' + field);
  return v.trim();
}
function nullable(v: unknown, field: string): string | null { return v === null ? null : optionalText(v, field); }
function date(v: unknown, field: string): string {
  const s = text(v, field, 64);
  if (!/^\d{4}-\d\d-\d\dT/.test(s) || !Number.isFinite(Date.parse(s))) throw new Error('Invalid upstream date: ' + field);
  return new Date(s).toISOString();
}
export function normalize(value: unknown): Advisory {
  if (!record(value)) throw new Error('Invalid advisory object');
  const id = text(value.ghsa_id, 'ghsa_id', 32);
  if (!/^GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}$/.test(id)) throw new Error('Invalid GHSA identifier');
  const cve = nullable(value.cve_id, 'cve_id');
  if (cve !== null && !/^CVE-\d{4}-\d{4,}$/.test(cve)) throw new Error('Invalid CVE identifier');
  const url = text(value.html_url, 'html_url');
  if (url !== 'https://github.com/php/php-src/security/advisories/' + id) throw new Error('Nonofficial advisory URL');
  if (!Array.isArray(value.vulnerabilities) || value.vulnerabilities.length > 100) throw new Error('Invalid affected packages');
  const vulnerabilities: Vulnerability[] = value.vulnerabilities.map(v => {
    if (!record(v) || !record(v.package)) throw new Error('Invalid affected package');
    const funcs = v.vulnerable_functions ?? [];
    if (!Array.isArray(funcs) || funcs.length > 200) throw new Error('Invalid vulnerable functions');
    return { package: { ecosystem: optionalText(v.package.ecosystem, 'ecosystem', 100), name: optionalText(v.package.name, 'package', 200) },
      vulnerable_version_range: nullable(v.vulnerable_version_range, 'range'),
      patched_versions: nullable(v.patched_versions, 'patched_versions'),
      vulnerable_functions: [...new Set(funcs.map(f => text(f, 'function', 500)))].sort() };
  }).sort((a, b) => canonical(a).localeCompare(canonical(b)));
  return { ghsa_id: id, cve_id: cve, summary: text(value.summary, 'summary', 2000),
    severity: text(value.severity, 'severity', 32), html_url: url,
    published_at: date(value.published_at, 'published_at'), updated_at: date(value.updated_at, 'updated_at'),
    withdrawn_at: value.withdrawn_at === null ? null : date(value.withdrawn_at, 'withdrawn_at'), vulnerabilities };
}
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (record(value)) return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  const result = JSON.stringify(value);
  if (result === undefined) throw new Error('Nonserializable canonical value');
  return result;
}
export async function fingerprint(value: unknown): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical(value)));
  return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, '0')).join('');
}
export async function buildSnapshot(seed: Seed, previous: Snapshot | undefined, incoming: Advisory[]): Promise<{ snapshot: Snapshot; changes: Changes }> {
  const old = new Map((previous?.catalog ?? seed.catalog).map(a => [a.ghsa_id, a]));
  const seen = new Map<string, Advisory>();
  for (const a of incoming) {
    if (seen.has(a.ghsa_id)) throw new Error('Duplicate upstream GHSA');
    seen.set(a.ghsa_id, a);
  }
  const changes: Changes = { added: [], updated: [], withdrawn: [], missing: [] };
  const merged = new Map(old);
  for (const [id, a] of seen) {
    const prev = old.get(id);
    if (!prev) changes.added.push(id);
    else if (await fingerprint(prev) !== await fingerprint(a)) changes.updated.push(id);
    if (a.withdrawn_at && a.withdrawn_at !== prev?.withdrawn_at) changes.withdrawn.push(id);
    merged.set(id, a);
  }
  for (const id of old.keys()) if (!seen.has(id)) changes.missing.push(id);
  for (const key of Object.keys(changes) as (keyof Changes)[]) changes[key].sort();
  const reviews = new Map(seed.reviews.map(r => [r.id, r]));
  const catalog = [...merged.values()].sort((a, b) => a.ghsa_id.localeCompare(b.ghsa_id));
  const assessments: Assessment[] = [];
  const counts: Record<Status, number> = { RESOLVED: 0, NOT_APPLICABLE: 0, PLANNED: 0 };
  for (const a of catalog) {
    const review = reviews.get(a.ghsa_id); const hash = await fingerprint(a);
    const present = seen.has(a.ghsa_id);
    const valid = present && !a.withdrawn_at && review?.sourceHash === seed.sourceHash && review.upstreamHash === hash;
    const status: Status = valid ? review.status : 'PLANNED';
    const component = review?.component ?? (a.vulnerabilities.map(v => v.package.name).filter(Boolean).join(', ') || 'PHP source');
    const reason = valid ? review.reason : !present ? 'Missing from the latest complete listing; retained for explicit review.' :
      a.withdrawn_at ? 'Upstream withdrew this advisory; retain its history and review the disposition.' :
      review ? 'Upstream or source revision differs from the reviewed evidence; previous verdict is not credited.' : 'New official advisory; no implementation is credited yet.';
    const action = valid ? review.action : 'Compare the advisory and official fix with the exact PHP 7.0 source, implement relevant protection and run isolated regressions.';
    assessments.push({ id: a.ghsa_id, status, component, reason, action,
      validation: valid ? review.validation : 'not-run', presence: present ? 'present' : 'missing', upstreamHash: hash,
      ...(review ? { reviewedStatus: review.status, reviewedUpstreamHash: review.upstreamHash, reviewedSourceHash: review.sourceHash } : {}) });
    counts[status]++;
  }
  const body = { schema: 1 as const, sourceHash: seed.sourceHash, catalog, assessments, counts };
  return { snapshot: { ...body, revision: await fingerprint(body) }, changes };
}
function escapeMarkdown(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/[\\`*_\[\]()|#]/g, '\\$&').replace(/[\r\n]+/g, ' ');
}
export function markdown(snapshot: Snapshot): string {
  const byId = new Map(snapshot.catalog.map(a => [a.ghsa_id, a]));
  const lines = ['# PHP advisory implementation worklist', '',
    'Source identity: `' + snapshot.sourceHash + '`', 'Snapshot: `' + snapshot.revision + '`', '',
    'Automated collection does not implement patches or grant a security pass. New, revised, withdrawn or missing advisories require source review.', '',
    '| Advisory | Status | Component | Work / evidence |', '|---|---|---|---|'];
  for (const row of snapshot.assessments) {
    const a = byId.get(row.id)!;
    lines.push(`| [${row.id}](${a.html_url}) ${escapeMarkdown(a.cve_id ?? 'No CVE assigned')}: ${escapeMarkdown(a.summary)} | ${row.status} | ${escapeMarkdown(row.component)} | ${escapeMarkdown(row.reason)} ${escapeMarkdown(row.action)} |`);
  }
  return lines.join('\n') + '\n';
}
