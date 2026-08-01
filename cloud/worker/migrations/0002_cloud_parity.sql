PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS training_examples (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instruction TEXT NOT NULL,
    ideal_response TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS training_examples_created_idx ON training_examples(created_at DESC);

CREATE TABLE IF NOT EXISTS training_evaluations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    expected TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS training_evaluations_created_idx ON training_evaluations(created_at DESC);
