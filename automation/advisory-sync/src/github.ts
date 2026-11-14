import { normalize } from './core.ts';
import type { Advisory, Fetcher } from './types.ts';
export const API_URL = 'https://api.github.com/repos/php/php-src/security-advisories?state=published&per_page=100';
export interface CollectionLimits { timeoutMs?: number; maxPageBytes?: number; maxTotalBytes?: number; maxPages?: number; token?: string }
export class GithubRefusal extends Error {
  constructor(message: string, readonly retryAt: string | undefined, readonly upstreamAuth: 'anonymous' | 'token') { super(message); }
}
function nextLink(header: string | null): string | undefined {
  if (!header) return undefined;
  let next: string | undefined;
  for (const part of header.split(/,(?=\s*<)/)) {
    const match = /^\s*<([^>]+)>(.*)$/.exec(part);
    const rel = match && /;\s*rel=(?:"([^"]+)"|([^;\s]+))/.exec(match[2]);
    if (!match || !rel) throw new Error('Malformed pagination Link');
    if (!(rel[1] ?? rel[2]).split(/\s+/).includes('next')) continue;
    if (next) throw new Error('Ambiguous pagination Link');
    const url = new URL(match[1]);
    if (url.origin !== 'https://api.github.com' || url.pathname !== '/repos/php/php-src/security-advisories' ||
        url.username || url.password || url.hash || url.searchParams.get('state') !== 'published') throw new Error('Unsafe pagination destination');
    next = url.href;
  }
  return next;
}
export async function collectGithub(fetcher: Fetcher = (url, init) => fetch(url, init), limits: CollectionLimits = {}): Promise<Advisory[]> {
  const token = limits.token;
  if (token && (!/^[A-Za-z0-9_.-]{20,512}$/.test(token))) throw new Error('Invalid GitHub read credential format');
  const deadline = Date.now() + (limits.timeoutMs ?? 60_000);
  const maxPage = limits.maxPageBytes ?? 4 * 1024 * 1024;
  const maxTotal = limits.maxTotalBytes ?? 16 * 1024 * 1024;
  const maxPages = limits.maxPages ?? 20;
  const abort = new AbortController();
  async function within<T>(promise: Promise<T>): Promise<T> {
    const remaining = deadline - Date.now();
    if (remaining <= 0) { abort.abort(); throw new Error('Collection deadline exceeded'); }
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([promise, new Promise<never>((_, reject) => {
        timer = setTimeout(() => { abort.abort(); reject(new Error('Collection deadline exceeded')); }, remaining);
      })]);
    } finally { if (timer) clearTimeout(timer); }
  }
  const seenUrls = new Set<string>(); const seenIds = new Set<string>(); const rows: Advisory[] = [];
  let url: string | undefined = API_URL; let total = 0;
  try {
    while (url) {
      if (seenUrls.has(url)) throw new Error('Pagination cycle');
      if (seenUrls.size >= maxPages) throw new Error('Pagination page budget exceeded');
      seenUrls.add(url);
      const response = await within(fetcher(url, { headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'legacy-fpm-advisory-sync', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
        redirect: 'manual', signal: abort.signal }));
      if (!response.ok) {
        void response.body?.cancel().catch(() => {});
        const fields = [['x-ratelimit-remaining','remaining'], ['x-ratelimit-reset','reset'], ['retry-after','retry-after']];
        const diagnostics = fields.flatMap(([header,label]) => {
          const value = response.headers.get(header);
          return value && /^\d{1,16}$/.test(value) ? [label + '=' + value] : [];
        });
        const reset = response.headers.get('x-ratelimit-reset'); const retry = response.headers.get('retry-after');
        const waitUntil = response.headers.get('x-ratelimit-remaining') === '0' && reset && /^\d{1,12}$/.test(reset) ? Number(reset)*1000 :
          (response.status === 429 || response.status === 403) && retry && /^\d{1,8}$/.test(retry) ? Date.now()+Number(retry)*1000 : 0;
        const retryAt = waitUntil > Date.now() && waitUntil < Date.now()+86400_000 ? new Date(waitUntil).toISOString() : undefined;
        throw new GithubRefusal('GitHub HTTP ' + response.status + (diagnostics.length ? ' (' + diagnostics.join(', ') + ')' : ''), retryAt, token ? 'token' : 'anonymous');
      }
      const length = Number(response.headers.get('content-length'));
      if (Number.isFinite(length) && length > maxPage) { void response.body?.cancel().catch(() => {}); throw new Error('Response byte budget exceeded'); }
      if (!response.body) throw new Error('Missing JSON body');
      const reader = response.body.getReader(); const chunks: Uint8Array[] = []; let size = 0;
      try {
        while (true) {
          const part = await within(reader.read());
          if (part.done) break;
          size += part.value.byteLength; total += part.value.byteLength;
          if (size > maxPage || total > maxTotal) throw new Error('Response byte budget exceeded');
          chunks.push(part.value);
        }
      } finally { void reader.cancel().catch(() => {}); try { reader.releaseLock(); } catch { /* pending read already cancelled */ } }
      const bytes = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      let parsed: unknown;
      try { parsed = JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(bytes)); } catch { throw new Error('Invalid JSON response'); }
      if (!Array.isArray(parsed) || parsed.length > 100) throw new Error('Invalid advisory JSON page');
      for (const entry of parsed) {
        const a = normalize(entry);
        if (seenIds.has(a.ghsa_id)) throw new Error('Duplicate upstream GHSA across pages');
        seenIds.add(a.ghsa_id); rows.push(a);
      }
      url = nextLink(response.headers.get('link'));
    }
  } finally { abort.abort(); }
  if (!rows.length) throw new Error('Unexpected empty official catalog');
  return rows.sort((a, b) => a.ghsa_id.localeCompare(b.ghsa_id));
}
