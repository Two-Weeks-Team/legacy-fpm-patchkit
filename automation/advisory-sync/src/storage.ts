import { canonical } from './core.ts';
import type { Snapshot, BatchReport } from './types.ts';
export function encodeSnapshot(snapshot: Snapshot): string {
  const payload = canonical(snapshot);
  if (new TextEncoder().encode(payload).byteLength > 900_000) throw new Error('Snapshot storage budget exceeded');
  return payload;
}
function isReport(value: unknown): value is BatchReport {
  if (!value || typeof value !== 'object') return false;
  return 'runId' in value && typeof value.runId === 'string' && 'status' in value &&
    ['SUCCESS', 'FAILED', 'BUSY'].includes(String(value.status)) &&
    'trigger' in value && typeof value.trigger === 'string' &&
    'startedAt' in value && typeof value.startedAt === 'string' &&
    'finishedAt' in value && typeof value.finishedAt === 'string';
}
export function decodeReport(encoded: string | null): BatchReport | null {
  if (!encoded) return null;
  const value: unknown = JSON.parse(encoded);
  if (!isReport(value)) throw new Error('Invalid stored run report');
  return value;
}
