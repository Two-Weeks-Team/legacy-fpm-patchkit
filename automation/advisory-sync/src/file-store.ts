import { constants } from 'node:fs';
import { open, mkdir, lstat, readdir, writeFile, rename, unlink } from 'node:fs/promises';
import { join, dirname, resolve } from 'node:path';
import { decodeSnapshot } from './core.ts';
import { encodeSnapshot, decodeReport } from './storage.ts';
import type { Store, Snapshot, BatchReport, StoredView } from './types.ts';
const OWNER = 'legacy-fpm-advisory-sync-state-v1\n';
function code(error: unknown): string { return error && typeof error === 'object' && 'code' in error ? String(error.code) : ''; }
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function safeId(id: string): string { if (!/^[A-Za-z0-9_-]{1,100}$/.test(id)) throw new Error('Invalid run identity'); return id; }

export class FileStore implements Store {
  private readonly dir: string;
  constructor(dir: string) { this.dir = resolve(dir); }
  private async read(name: string): Promise<string | null> {
    let handle;
    try { handle = await open(join(this.dir, name), constants.O_RDONLY | constants.O_NOFOLLOW); }
    catch (error) { if (code(error) === 'ENOENT') return null; throw error; }
    try {
      const stat = await handle.stat();
      if (!stat.isFile() || stat.nlink !== 1 || stat.size > 1_200_000) throw new Error('Unsafe state file or hardlink');
      return await handle.readFile('utf8');
    } finally { await handle.close(); }
  }
  private async owned(create = false): Promise<boolean> {
    try { const s = await lstat(this.dir); if (!s.isDirectory() || s.isSymbolicLink()) throw new Error('State directory symlink refused'); }
    catch (error) { if (code(error) !== 'ENOENT') throw error; if (!create) return false; await mkdir(this.dir, { recursive: true, mode: 0o700 }); }
    const owner = await this.read('owner.txt');
    if (owner === OWNER) return true;
    if (owner !== null || !create || (await readdir(this.dir)).length) throw new Error('Refusing an unrelated, unowned state directory');
    try { await writeFile(join(this.dir, 'owner.txt'), OWNER, { flag: 'wx', mode: 0o600 }); }
    catch (error) { if (code(error) !== 'EEXIST' || await this.read('owner.txt') !== OWNER) throw error; }
    return true;
  }
  private async folder(name: string): Promise<void> {
    const path = join(this.dir, name);
    try { await mkdir(path, { mode: 0o700 }); } catch (error) { if (code(error) !== 'EEXIST') throw error; }
    const stat = await lstat(path); if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('Unsafe state subdirectory');
  }
  private async write(name: string, data: string): Promise<void> {
    if (new TextEncoder().encode(data).byteLength > 1_200_000) throw new Error('Local state byte budget exceeded');
    const target = join(this.dir, name);
    try { const s = await lstat(target); if (!s.isFile() || s.isSymbolicLink() || s.nlink !== 1) throw new Error('Unsafe state file or symlink'); }
    catch (error) { if (code(error) !== 'ENOENT') throw error; }
    const temp = join(dirname(target), '.' + crypto.randomUUID() + '.tmp');
    await writeFile(temp, data, { flag: 'wx', mode: 0o600 });
    try { await rename(temp, target); } catch (error) { await unlink(temp).catch(() => {}); throw error; }
  }
  private async lease(id: string): Promise<void> {
    const raw = await this.read('lock.json'); const value: unknown = raw ? JSON.parse(raw) : null;
    if (!object(value) || value.id !== id) throw new Error('Local state lease lost');
  }
  async acquire(id: string, now: number, until: number): Promise<boolean> {
    await this.owned(true); safeId(id);
    try { await writeFile(join(this.dir, 'lock.json'), JSON.stringify({ id, pid: process.pid, now, until }), { flag: 'wx', mode: 0o600 }); return true; }
    catch (error) { if (code(error) === 'EEXIST') return false; throw error; }
  }
  async begin(id: string, trigger: string, started: string): Promise<void> {
    await this.lease(id); await this.folder('runs');
    await this.write('runs/' + safeId(id) + '.json', JSON.stringify({ runId: id, trigger, startedAt: started, status: 'RUNNING' }));
  }
  async load(): Promise<StoredView | undefined> {
    if (!await this.owned()) return undefined;
    const current = await this.read('current.json'); const attempt = decodeReport(await this.read('last-attempt.json'));
    if (!current) return { snapshot: null, lastSuccessAt: null, lastAttempt: attempt?.status === 'SUCCESS' ? null : attempt, lastSuccessReport: null, origin: 'seed' };
    const value: unknown = JSON.parse(current);
    if (!object(value) || typeof value.lastSuccessAt !== 'string' || !value.snapshot || !value.report) throw new Error('Invalid local checkpoint');
    const snapshot = await decodeSnapshot(JSON.stringify(value.snapshot));
    const committed = decodeReport(JSON.stringify(value.report));
    if (!committed || committed.status !== 'SUCCESS') throw new Error('Invalid local success record');
    const latest = attempt?.status === 'SUCCESS' && attempt.runId !== committed.runId ? committed : attempt ?? committed;
    return { snapshot, lastSuccessAt: value.lastSuccessAt, lastAttempt: latest, lastSuccessReport: committed, origin: 'collected' };
  }
  async commit(id: string, snapshot: Snapshot, report: BatchReport): Promise<void> {
    await this.lease(id); await this.folder('objects'); await this.folder('runs');
    if (!/^[a-f0-9]{64}$/.test(snapshot.revision)) throw new Error('Invalid snapshot object identity');
    const payload = encodeSnapshot(snapshot);
    const old = await this.read('objects/' + snapshot.revision + '.json');
    if (old && old !== payload) throw new Error('Immutable local object differs');
    if (!old) await this.write('objects/' + snapshot.revision + '.json', payload);
    await this.write('runs/' + safeId(id) + '.json', JSON.stringify(report));
    await this.write('last-attempt.json', JSON.stringify(report));
    await this.write('current.json', JSON.stringify({ schema: 1, snapshot, lastSuccessAt: report.finishedAt, report }));
    await this.release(id);
  }
  async fail(id: string, report: BatchReport): Promise<void> {
    await this.lease(id); await this.folder('runs');
    await this.write('runs/' + safeId(id) + '.json', JSON.stringify(report)); await this.write('last-attempt.json', JSON.stringify(report));
    await this.release(id);
  }
  async release(id: string): Promise<void> { await this.lease(id); await unlink(join(this.dir, 'lock.json')); }
}
