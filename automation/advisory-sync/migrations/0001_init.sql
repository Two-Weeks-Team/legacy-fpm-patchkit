CREATE TABLE IF NOT EXISTS sync_control (
  id INTEGER PRIMARY KEY CHECK(id=1), lease_token TEXT, lease_until INTEGER,
  current_revision TEXT, last_success_at TEXT, last_run_id TEXT, last_success_run_id TEXT
);
INSERT OR IGNORE INTO sync_control(id) VALUES(1);
CREATE TABLE IF NOT EXISTS snapshots (
  revision TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, trigger TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCESS','FAILED')),
  fence INTEGER NOT NULL DEFAULT 1 CHECK(fence=1), report TEXT
);
CREATE INDEX IF NOT EXISTS runs_started ON runs(started_at);
