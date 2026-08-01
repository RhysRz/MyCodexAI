PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    created_at INTEGER NOT NULL,
    disabled_at INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    device_label TEXT NOT NULL DEFAULT 'Cloud browser'
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions(user_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS login_limits (
    client_key TEXT PRIMARY KEY,
    failures INTEGER NOT NULL DEFAULT 0,
    window_started_at INTEGER NOT NULL,
    blocked_until INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invites (
    token_hash TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'แชทใหม่',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_user_idx ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages(conversation_id, created_at ASC);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'agent',
    status TEXT NOT NULL DEFAULT 'queued',
    answer TEXT,
    pull_request_url TEXT,
    branch_name TEXT,
    error_detail TEXT,
    trace_json TEXT NOT NULL DEFAULT '[]',
    attachments_json TEXT NOT NULL DEFAULT '[]',
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER
);
CREATE INDEX IF NOT EXISTS agent_runs_user_idx ON agent_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_runs_queue_idx ON agent_runs(status, created_at ASC);

CREATE TABLE IF NOT EXISTS cloud_files (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'uploading',
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS cloud_files_user_idx ON cloud_files(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS cloud_files_expiry_idx ON cloud_files(expires_at);

CREATE TABLE IF NOT EXISTS cloud_file_chunks (
    file_id TEXT NOT NULL REFERENCES cloud_files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    contents BLOB NOT NULL,
    PRIMARY KEY (file_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    kind TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_events_user_idx ON audit_events(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
