import { decodeSnapshot } from './core.ts';
import { encodeSnapshot, decodeReport } from './storage.ts';
import type { Store, Snapshot, BatchReport, StoredView } from './types.ts';

export class D1Store implements Store {
  constructor(private readonly db: Pick<D1Database, 'prepare' | 'batch'>) {}
  async acquire(id: string, now: number, until: number): Promise<boolean> {
    const r = await this.db.prepare('UPDATE sync_control SET lease_token=?,lease_until=? WHERE id=1 AND (lease_token IS NULL OR lease_until<=?)').bind(id, until, now).run();
    return r.meta.changes === 1;
  }
  async begin(id: string, trigger: string, started: string): Promise<void> {
    await this.db.prepare("INSERT INTO runs(id,trigger,started_at,status) VALUES(?,?,?,'RUNNING')").bind(id, trigger, started).run();
  }
  async load(): Promise<StoredView | undefined> {
    const row = await this.db.prepare(`SELECT c.current_revision,c.last_success_at,s.payload,r.report,sr.report AS success_report
      FROM sync_control c LEFT JOIN snapshots s ON s.revision=c.current_revision
      LEFT JOIN runs r ON r.id=c.last_run_id LEFT JOIN runs sr ON sr.id=c.last_success_run_id WHERE c.id=1`).first<{
        current_revision: string | null; last_success_at: string | null; payload: string | null; report: string | null; success_report: string | null;
      }>();
    if (!row) throw new Error('D1 migrations have not initialized sync control');
    const snapshot = row.payload ? await decodeSnapshot(row.payload) : null;
    if (snapshot && snapshot.revision !== row.current_revision) throw new Error('D1 snapshot identity mismatch');
    return { snapshot, lastSuccessAt: row.last_success_at, lastAttempt: decodeReport(row.report), lastSuccessReport: decodeReport(row.success_report), origin: snapshot ? 'collected' : 'seed' };
  }
  async commit(id: string, snapshot: Snapshot, report: BatchReport): Promise<void> {
    const payload = encodeSnapshot(snapshot);
    await this.db.batch([
      this.db.prepare(`INSERT INTO runs(id,trigger,started_at,status,fence) VALUES(?,?,?,'RUNNING',
        CASE WHEN EXISTS(SELECT 1 FROM sync_control WHERE id=1 AND lease_token=? AND lease_until>?) THEN 1 ELSE 0 END)
        ON CONFLICT(id) DO UPDATE SET fence=excluded.fence`).bind(id, report.trigger, report.startedAt, id, Date.now()),
      this.db.prepare('INSERT OR IGNORE INTO snapshots(revision,payload,created_at) VALUES(?,?,?)').bind(snapshot.revision, payload, report.finishedAt),
      this.db.prepare('UPDATE sync_control SET current_revision=?,last_success_at=?,last_run_id=?,last_success_run_id=?,lease_token=NULL,lease_until=NULL WHERE id=1 AND lease_token=?').bind(snapshot.revision, report.finishedAt, id, id, id),
      this.db.prepare("UPDATE runs SET status='SUCCESS',finished_at=?,report=? WHERE id=?").bind(report.finishedAt, JSON.stringify(report), id),
    ]);
  }
  async fail(id: string, report: BatchReport): Promise<void> {
    await this.db.batch([
      this.db.prepare(`INSERT INTO runs(id,trigger,started_at,status,finished_at,report) VALUES(?,?,?,'FAILED',?,?)
        ON CONFLICT(id) DO UPDATE SET status='FAILED',finished_at=excluded.finished_at,report=excluded.report`).bind(id, report.trigger, report.startedAt, report.finishedAt, JSON.stringify(report)),
      this.db.prepare('UPDATE sync_control SET last_run_id=?,lease_token=NULL,lease_until=NULL WHERE id=1 AND lease_token=?').bind(id, id),
    ]);
  }
  async release(id: string): Promise<void> {
    await this.db.prepare('UPDATE sync_control SET lease_token=NULL,lease_until=NULL WHERE id=1 AND lease_token=?').bind(id).run();
  }
}
