CREATE TABLE IF NOT EXISTS oauth_states (
    token_hash TEXT PRIMARY KEY,
    provider TEXT NOT NULL CHECK (provider IN ('google', 'github')),
    action TEXT NOT NULL CHECK (action IN ('login', 'link')),
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    code_verifier TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS oauth_states_expiry_idx ON oauth_states(expires_at);

CREATE TABLE IF NOT EXISTS oauth_identities (
    provider TEXT NOT NULL CHECK (provider IN ('google', 'github')),
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email TEXT,
    linked_at INTEGER NOT NULL,
    PRIMARY KEY (provider, subject),
    UNIQUE (provider, user_id)
);
CREATE INDEX IF NOT EXISTS oauth_identities_user_idx ON oauth_identities(user_id);

CREATE TABLE IF NOT EXISTS oauth_mfa_challenges (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS oauth_mfa_expiry_idx ON oauth_mfa_challenges(expires_at);
