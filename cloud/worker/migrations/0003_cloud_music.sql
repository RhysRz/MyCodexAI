PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS music_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL REFERENCES cloud_files(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'dispatching',
    analysis_json TEXT,
    error_detail TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    completed_at INTEGER
);
CREATE INDEX IF NOT EXISTS music_jobs_user_idx ON music_jobs(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS music_artifacts (
    job_id TEXT NOT NULL REFERENCES music_jobs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    file_name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    contents BLOB NOT NULL,
    PRIMARY KEY (job_id, kind)
);
