PRAGMA foreign_keys = ON;

ALTER TABLE users ADD COLUMN mfa_secret_encrypted TEXT;
ALTER TABLE users ADD COLUMN mfa_pending_encrypted TEXT;
ALTER TABLE users ADD COLUMN mfa_recovery_hashes_json TEXT NOT NULL DEFAULT '[]';
