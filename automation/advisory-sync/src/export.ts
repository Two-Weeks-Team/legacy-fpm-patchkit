import { markdown } from './core.ts';
import { seedSnapshot } from './seed.ts';
import type { Store, StoredView, Snapshot } from './types.ts';
export const KINDS = ['status', 'catalog', 'coverage', 'changes', 'backlog'] as const;
export type Kind = typeof KINDS[number];
export type View = Omit<StoredView, 'snapshot'> & { snapshot: Snapshot };
export async function readView(store: Store): Promise<View> {
  const stored = await store.load();
  return { snapshot: stored?.snapshot ?? seedSnapshot, lastSuccessAt: stored?.lastSuccessAt ?? null,
    lastAttempt: stored?.lastAttempt ?? null, lastSuccessReport: stored?.lastSuccessReport ?? null,
    origin: stored?.snapshot ? 'collected' : 'seed' };
}
export function statusFor(view: View) {
  const state = view.lastAttempt?.status === 'FAILED' ? 'FAILED' : view.origin === 'seed' || !view.lastSuccessAt ? 'NEVER_SYNCED' :
    Date.now() - Date.parse(view.lastSuccessAt) > 150 * 60_000 ? 'STALE' : 'HEALTHY';
  return { state, origin: view.origin, lastSuccessAt: view.lastSuccessAt, lastAttempt: view.lastAttempt,
    sourceHash: view.snapshot.sourceHash, revision: view.snapshot.revision, counts: view.snapshot.counts };
}
export function payload(view: View, kind: Kind) {
  const status = statusFor(view);
  const byId = new Map(view.snapshot.catalog.map(a => [a.ghsa_id, a]));
  if (kind === 'status') return { status };
  if (kind === 'catalog') return { status, items: view.snapshot.catalog };
  if (kind === 'changes') return { status, changes: view.lastSuccessReport?.changes ?? { added: [], updated: [], withdrawn: [], missing: [] } };
  const rows = kind === 'backlog' ? view.snapshot.assessments.filter(r => r.status === 'PLANNED') : view.snapshot.assessments;
  return { status, items: rows.map(row => ({ ...row, advisory: byId.get(row.id) })) };
}
export function backlogMarkdown(view: View): string {
  const status = statusFor(view);
  return `Collection state: ${status.state}\nLast successful live collection: ${view.lastSuccessAt ?? 'none (bundled reviewed seed only)'}\n\n` + markdown(view.snapshot);
}
