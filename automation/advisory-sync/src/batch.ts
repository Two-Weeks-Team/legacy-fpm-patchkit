import { buildSnapshot } from './core.ts';
import { collectGithub } from './github.ts';
import { encodeSnapshot } from './storage.ts';
import type { Store, Seed, BatchReport, Fetcher } from './types.ts';
export async function runBatch(store: Store, seed: Seed, options: { trigger: string; fetcher?: Fetcher }): Promise<BatchReport> {
  const runId = crypto.randomUUID(); const now = Date.now(); const startedAt = new Date(now).toISOString();
  if (!await store.acquire(runId, now, now + 120_000)) return { runId, status: 'BUSY', trigger: options.trigger, startedAt, finishedAt: new Date().toISOString() };
  let owned = true;
  try {
    await store.begin(runId, options.trigger, startedAt);
    const previous = await store.load(); const incoming = await collectGithub(options.fetcher);
    const { snapshot, changes } = await buildSnapshot(seed, previous?.snapshot ?? undefined, incoming);
    encodeSnapshot(snapshot);
    const report: BatchReport = { runId, status: 'SUCCESS', trigger: options.trigger, startedAt, finishedAt: new Date().toISOString(),
      revision: snapshot.revision, changed: snapshot.revision !== previous?.snapshot?.revision,
      observedCount: incoming.length, retainedCount: snapshot.catalog.length, changes };
    await store.commit(runId, snapshot, report); owned = false;
    return report;
  } catch (error) {
    // A durable commit can succeed even when its transport acknowledgement or
    // subsequent local lock cleanup fails. Reconcile that identity before fail().
    let committed: BatchReport | null | undefined;
    try { committed = (await store.load())?.lastSuccessReport; } catch { /* storage may still be unavailable */ }
    if (committed?.runId === runId && committed.status === 'SUCCESS') {
      owned = false;
      try { await store.release(runId); } catch {
        return { ...committed, cleanupWarning: 'Snapshot committed; lease/lock cleanup failed. Inspect local lock ownership before recovery.' };
      }
      return committed;
    }
    const report: BatchReport = { runId, status: 'FAILED', trigger: options.trigger, startedAt, finishedAt: new Date().toISOString(),
      error: (error instanceof Error ? error.message : 'Batch failed').slice(0, 400) };
    await store.fail(runId, report); owned = false;
    return report;
  } finally { if (owned) await store.release(runId); }
}
