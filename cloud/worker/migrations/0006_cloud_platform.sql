PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cloud_workspaces (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    repository TEXT NOT NULL,
    default_branch TEXT NOT NULL DEFAULT 'main',
    instructions TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS cloud_workspaces_user_idx ON cloud_workspaces(user_id, updated_at DESC);

ALTER TABLE agent_runs ADD COLUMN workspace_id TEXT;
ALTER TABLE agent_runs ADD COLUMN workflow_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE agent_runs ADD COLUMN project_plan_json TEXT;
ALTER TABLE agent_runs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_runs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS agent_runs_workspace_idx ON agent_runs(user_id, workspace_id, created_at DESC);

ALTER TABLE cloud_files ADD COLUMN storage_backend TEXT NOT NULL DEFAULT 'd1';
ALTER TABLE cloud_files ADD COLUMN storage_key TEXT;

ALTER TABLE music_jobs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0;
ALTER TABLE music_jobs ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE music_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0;
ALTER TABLE music_jobs ADD COLUMN source_url TEXT NOT NULL DEFAULT '';
ALTER TABLE music_jobs ADD COLUMN source_platform TEXT NOT NULL DEFAULT 'file';
ALTER TABLE music_artifacts ADD COLUMN storage_key TEXT;
ALTER TABLE music_artifacts ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS memory_documents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'note',
    source_file_id TEXT,
    content_preview TEXT NOT NULL DEFAULT '',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'indexing',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS memory_documents_user_idx ON memory_documents(user_id, workspace_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS memory_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES memory_documents(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id TEXT,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS memory_chunks_document_idx ON memory_chunks(document_id, chunk_index);
CREATE INDEX IF NOT EXISTS memory_chunks_user_idx ON memory_chunks(user_id, workspace_id);

CREATE TABLE IF NOT EXISTS user_notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    action_url TEXT,
    read_at INTEGER,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS user_notifications_user_idx ON user_notifications(user_id, read_at, created_at DESC);

CREATE TABLE IF NOT EXISTS backup_snapshots (
    id TEXT PRIMARY KEY,
    created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    encrypted_contents BLOB,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    record_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    error_detail TEXT
    ,storage_key TEXT
);
CREATE INDEX IF NOT EXISTS backup_snapshots_expiry_idx ON backup_snapshots(expires_at);

CREATE TABLE IF NOT EXISTS hybrid_devices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    capabilities_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'offline',
    last_seen_at INTEGER,
    created_at INTEGER NOT NULL,
    revoked_at INTEGER
);
CREATE INDEX IF NOT EXISTS hybrid_devices_user_idx ON hybrid_devices(user_id, last_seen_at DESC);

CREATE TABLE IF NOT EXISTS hybrid_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES hybrid_devices(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    result_json TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    completed_at INTEGER
);
CREATE INDEX IF NOT EXISTS hybrid_jobs_queue_idx ON hybrid_jobs(device_id, status, created_at);
