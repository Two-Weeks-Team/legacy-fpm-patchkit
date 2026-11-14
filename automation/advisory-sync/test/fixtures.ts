import { normalize, fingerprint } from '../src/core.ts';
import type { Seed } from '../src/types.ts';

export const raw = (id = 'GHSA-aaaa-bbbb-cccc', summary = 'Example advisory') => ({
  ghsa_id: id, cve_id: 'CVE-2026-1234', summary, severity: 'high',
  html_url: `https://github.com/php/php-src/security/advisories/${id}`,
  published_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z', withdrawn_at: null,
  vulnerabilities: [{ package: { ecosystem: 'php', name: 'ext-standard' },
    vulnerable_version_range: '<8.4.1', patched_versions: '8.4.1', vulnerable_functions: [] }],
});

export async function fixture(): Promise<Seed> {
  const a = normalize(raw());
  return { schema: 1, sourceHash: 'a'.repeat(64), catalog: [a], reviews: [{
    id: a.ghsa_id, upstreamHash: await fingerprint(a), sourceHash: 'a'.repeat(64),
    status: 'RESOLVED', component: 'ext-standard', reason: 'Source protection present.',
    action: '', validation: 'source-only',
  }] };
}
