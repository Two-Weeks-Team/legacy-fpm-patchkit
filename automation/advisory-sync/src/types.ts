export type Status = 'RESOLVED' | 'NOT_APPLICABLE' | 'PLANNED';
export interface Vulnerability {
  package: { ecosystem: string; name: string };
  vulnerable_version_range: string | null;
  patched_versions: string | null;
  vulnerable_functions: string[];
}
export interface Advisory {
  ghsa_id: string; cve_id: string | null; summary: string; severity: string;
  html_url: string; published_at: string; updated_at: string; withdrawn_at: string | null;
  vulnerabilities: Vulnerability[];
}
export interface Review {
  id: string; upstreamHash: string; sourceHash: string; status: Status;
  component: string; reason: string; action: string; validation: string;
}
export interface Seed { schema: 1; sourceHash: string; catalog: Advisory[]; reviews: Review[] }
export interface Assessment {
  id: string; status: Status; component: string; reason: string; action: string;
  validation: string; presence: 'present' | 'missing'; upstreamHash: string;
  reviewedStatus?: Status; reviewedUpstreamHash?: string; reviewedSourceHash?: string;
}
export interface Changes { added: string[]; updated: string[]; withdrawn: string[]; missing: string[] }
export interface Snapshot {
  schema: 1; sourceHash: string; catalog: Advisory[]; assessments: Assessment[];
  counts: Record<Status, number>; revision: string;
}
export interface BatchReport {
  runId: string; status: 'SUCCESS' | 'FAILED' | 'BUSY'; trigger: string;
  startedAt: string; finishedAt: string; revision?: string; changed?: boolean;
  observedCount?: number; retainedCount?: number; changes?: Changes; error?: string; cleanupWarning?: string;
}
export interface StoredView { snapshot: Snapshot | null; lastSuccessAt: string | null; lastAttempt: BatchReport | null; lastSuccessReport?: BatchReport | null; origin: 'seed' | 'collected' }
export interface Store {
  acquire(runId: string, now: number, until: number): Promise<boolean>;
  begin(runId: string, trigger: string, startedAt: string): Promise<void>;
  load(): Promise<StoredView | undefined>;
  commit(runId: string, snapshot: Snapshot, report: BatchReport): Promise<void>;
  fail(runId: string, report: BatchReport): Promise<void>;
  release(runId: string): Promise<void>;
}
export type Fetcher = (url: string, init: RequestInit) => Promise<Response>;
