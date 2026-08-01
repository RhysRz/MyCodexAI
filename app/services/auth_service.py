"""Invite-only authentication and workspace ownership for MyCodexAI."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
import re
import secrets
import sqlite3
import json
from threading import RLock
from uuid import uuid4
import hashlib
import hmac
from typing import Iterator

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.settings import settings
from app.services.mfa_service import MfaError, MfaService
from app.workspace import file_manager


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
MIN_PASSWORD_LENGTH_WITHOUT_MFA = 15


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    username: str
    role: str


class AuthService:
    _database_path = Path(settings.auth_database_path).expanduser().resolve()
    _passwords = PasswordHasher()
    _lock = RLock()
    _login_attempts: dict[str, list[datetime]] = {}

    @classmethod
    def bootstrap_admin(cls, username: str, password: str, bootstrap_token: str) -> AuthenticatedUser:
        configured_token = settings.auth_bootstrap_token
        if not configured_token or not hmac.compare_digest(bootstrap_token, configured_token):
            raise AuthError(403, "A valid bootstrap token is required")

        with cls._connection() as connection:
            admin_exists = connection.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone()
            if admin_exists:
                raise AuthError(409, "An administrator already exists; use an invite instead")
            return cls._create_user(connection, username, password, "admin")

    @classmethod
    def create_invite(cls, owner: AuthenticatedUser, role: str = "user") -> dict[str, str]:
        if owner.role != "admin":
            raise AuthError(403, "Only an administrator can create an invite")
        if role not in {"user", "admin"}:
            raise AuthError(400, "Invite role must be user or admin")

        raw_token = secrets.token_urlsafe(32)
        expires_at = cls._now() + timedelta(days=7)
        with cls._connection() as connection:
            connection.execute(
                "INSERT INTO invites (token_hash, role, expires_at, created_by) VALUES (?, ?, ?, ?)",
                (cls._hash_token(raw_token), role, cls._timestamp(expires_at), owner.id),
            )

        return {"token": raw_token, "role": role, "expires_at": cls._timestamp(expires_at)}

    @classmethod
    def register_with_invite(cls, username: str, password: str, invite_token: str) -> AuthenticatedUser:
        token_hash = cls._hash_token(invite_token)
        with cls._connection() as connection:
            invite = connection.execute(
                "SELECT token_hash, role, expires_at FROM invites WHERE token_hash = ?", (token_hash,)
            ).fetchone()
            if invite is None or cls._parse_timestamp(invite["expires_at"]) <= cls._now():
                raise AuthError(400, "The invite is invalid or expired")

            user = cls._create_user(connection, username, password, invite["role"])
            connection.execute("DELETE FROM invites WHERE token_hash = ?", (token_hash,))
            return user

    @classmethod
    def login(
        cls, username: str, password: str, client_key: str, mfa_code: str | None = None, device_label: str = "Unknown device"
    ) -> tuple[AuthenticatedUser, str]:
        cls._check_login_rate(client_key)
        with cls._connection() as connection:
            user = connection.execute(
                """
                SELECT id, username, password_hash, role, failed_login_count, lockout_until,
                       mfa_enabled, mfa_secret_encrypted
                FROM users WHERE username = ? COLLATE NOCASE
                """,
                (username.strip(),),
            ).fetchone()
            if user is not None and user["lockout_until"]:
                if cls._parse_timestamp(user["lockout_until"]) > cls._now():
                    cls._record_failed_login(client_key)
                    raise AuthError(429, "Too many login attempts; try again later")
                cls._clear_account_failures(connection, user["id"])
            if user is None or not cls._verify_password(user["password_hash"], password):
                cls._record_failed_login(client_key)
                account_locked = user is not None and cls._record_account_failure(connection, user["id"])
                # AuthError triggers the context manager's rollback, so persist the
                # failure counter before returning an authentication error.
                connection.commit()
                if account_locked:
                    raise AuthError(429, "Too many login attempts; try again later")
                raise AuthError(401, "Invalid username or password")

            if user["mfa_enabled"]:
                try:
                    valid_mfa = MfaService.verify_encrypted_secret(user["mfa_secret_encrypted"], mfa_code)
                except MfaError as error:
                    raise AuthError(503, str(error)) from error
                if not valid_mfa and not cls._consume_recovery_code(connection, user["id"], mfa_code):
                    cls._record_failed_login(client_key)
                    account_locked = cls._record_account_failure(connection, user["id"])
                    connection.commit()
                    if account_locked:
                        raise AuthError(429, "Too many login attempts; try again later")
                    raise AuthError(401, "Invalid username, password, or verification code")
            elif settings.is_production and user["role"] == "admin" and settings.auth_require_mfa_for_admin:
                raise AuthError(403, "Administrator MFA enrollment is required before production login")

            cls._login_attempts.pop(client_key, None)
            cls._clear_account_failures(connection, user["id"])
            authenticated_user = AuthenticatedUser(user["id"], user["username"], user["role"])
            return authenticated_user, cls._create_session(connection, authenticated_user.id, device_label)

    @classmethod
    def create_session(cls, user: AuthenticatedUser, device_label: str = "Signed-in device") -> str:
        with cls._connection() as connection:
            return cls._create_session(connection, user.id, device_label)

    @classmethod
    def sessions(cls, user: AuthenticatedUser, raw_token: str | None) -> list[dict[str, object]]:
        current_hash = cls._hash_token(raw_token) if raw_token else ""
        with cls._connection() as connection:
            rows = connection.execute(
                "SELECT token_hash, device_label, created_at, last_seen_at FROM sessions WHERE user_id = ? ORDER BY last_seen_at DESC",
                (user.id,),
            ).fetchall()
        return [
            {
                "device_label": row["device_label"] or "Unknown device",
                "created_at": row["created_at"],
                "last_seen_at": row["last_seen_at"],
                "current": hmac.compare_digest(row["token_hash"], current_hash),
            }
            for row in rows
        ]

    @classmethod
    def revoke_other_sessions(cls, user: AuthenticatedUser, raw_token: str | None) -> int:
        if not raw_token:
            raise AuthError(401, "Sign in is required")
        current_hash = cls._hash_token(raw_token)
        with cls._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user.id, current_hash)
            )
        return max(0, int(cursor.rowcount))

    @classmethod
    def mfa_status(cls, user: AuthenticatedUser) -> dict[str, bool]:
        with cls._connection() as connection:
            row = connection.execute("SELECT mfa_enabled FROM users WHERE id = ?", (user.id,)).fetchone()
        if row is None:
            raise AuthError(401, "Sign in is required")
        return {
            "enabled": bool(row["mfa_enabled"]),
            "required": settings.is_production and user.role == "admin" and settings.auth_require_mfa_for_admin,
        }

    @classmethod
    def begin_mfa_setup(cls, user: AuthenticatedUser) -> dict[str, str]:
        secret = MfaService.create_secret()
        try:
            encrypted_secret = MfaService.encrypt_secret(secret)
        except MfaError as error:
            raise AuthError(503, str(error)) from error
        with cls._connection() as connection:
            connection.execute(
                "UPDATE users SET mfa_pending_secret_encrypted = ? WHERE id = ?",
                (encrypted_secret, user.id),
            )
        return {"secret": secret, "provisioning_uri": MfaService.provisioning_uri(secret, user.username)}

    @classmethod
    def confirm_mfa_setup(cls, user: AuthenticatedUser, code: str) -> dict[str, bool]:
        with cls._connection() as connection:
            row = connection.execute(
                "SELECT mfa_pending_secret_encrypted FROM users WHERE id = ?", (user.id,)
            ).fetchone()
            if row is None or not row["mfa_pending_secret_encrypted"]:
                raise AuthError(400, "Start MFA setup before confirming it")
            try:
                valid_code = MfaService.verify_encrypted_secret(row["mfa_pending_secret_encrypted"], code)
            except MfaError as error:
                raise AuthError(503, str(error)) from error
            if not valid_code:
                raise AuthError(400, "The verification code is invalid")
            connection.execute(
                """
                UPDATE users
                SET mfa_secret_encrypted = mfa_pending_secret_encrypted,
                    mfa_pending_secret_encrypted = NULL,
                    mfa_enabled = 1
                WHERE id = ?
                """,
                (user.id,),
            )
        return {
            "enabled": True,
            "required": settings.is_production and user.role == "admin" and settings.auth_require_mfa_for_admin,
        }

    @classmethod
    def generate_mfa_recovery_codes(cls, user: AuthenticatedUser, code: str) -> list[str]:
        with cls._connection() as connection:
            row = connection.execute(
                "SELECT mfa_enabled, mfa_secret_encrypted FROM users WHERE id = ?", (user.id,)
            ).fetchone()
            if row is None or not row["mfa_enabled"]:
                raise AuthError(400, "Enable MFA before generating recovery codes")
            try:
                valid_code = MfaService.verify_encrypted_secret(row["mfa_secret_encrypted"], code)
            except MfaError as error:
                raise AuthError(503, str(error)) from error
            if not valid_code:
                raise AuthError(400, "The verification code is invalid")
            codes = [f"MCAI-{secrets.token_hex(4).upper()}" for _ in range(settings.auth_recovery_code_count)]
            connection.execute(
                "UPDATE users SET mfa_recovery_code_hashes = ? WHERE id = ?",
                (json.dumps([cls._passwords.hash(item) for item in codes]), user.id),
            )
        return codes

    @classmethod
    def user_from_session(cls, raw_token: str | None) -> AuthenticatedUser | None:
        if not raw_token:
            return None

        with cls._connection() as connection:
            session = connection.execute(
                """
                SELECT users.id, users.username, users.role, sessions.expires_at, sessions.last_seen_at
                FROM sessions JOIN users ON sessions.user_id = users.id
                WHERE sessions.token_hash = ?
                """,
                (cls._hash_token(raw_token),),
            ).fetchone()
            if session is None:
                return None
            now = cls._now()
            last_seen = cls._parse_timestamp(session["last_seen_at"])
            idle_limit = timedelta(minutes=settings.auth_session_idle_minutes)
            if cls._parse_timestamp(session["expires_at"]) <= now or now - last_seen > idle_limit:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (cls._hash_token(raw_token),))
                return None
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                (cls._timestamp(now), cls._hash_token(raw_token)),
            )
            return AuthenticatedUser(session["id"], session["username"], session["role"])

    @classmethod
    def logout(cls, raw_token: str | None) -> None:
        if not raw_token:
            return
        with cls._connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (cls._hash_token(raw_token),))

    @staticmethod
    def workspace_for_user(user: AuthenticatedUser) -> Path:
        return (file_manager.WORKSPACE / "users" / user.id).resolve()

    @classmethod
    def _create_user(
        cls, connection: sqlite3.Connection, username: str, password: str, role: str
    ) -> AuthenticatedUser:
        normalized_username = cls._validate_credentials(username, password)
        user = AuthenticatedUser(str(uuid4()), normalized_username, role)
        try:
            connection.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    user.id,
                    user.username,
                    cls._passwords.hash(password),
                    user.role,
                    cls._timestamp(cls._now()),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise AuthError(409, "That username is already in use") from error
        return user

    @classmethod
    def _create_session(cls, connection: sqlite3.Connection, user_id: str, device_label: str = "Unknown device") -> str:
        raw_token = secrets.token_urlsafe(32)
        now = cls._now()
        expires_at = now + timedelta(days=settings.auth_session_days)
        connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (cls._timestamp(now),))
        existing = connection.execute(
            "SELECT token_hash FROM sessions WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        for row in existing[max(0, settings.auth_max_active_sessions - 1) :]:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
        connection.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at, created_at, last_seen_at, device_label) VALUES (?, ?, ?, ?, ?, ?)",
            (
                cls._hash_token(raw_token),
                user_id,
                cls._timestamp(expires_at),
                cls._timestamp(now),
                cls._timestamp(now),
                cls._device_label(device_label),
            ),
        )
        return raw_token

    @classmethod
    @contextmanager
    def _connection(cls) -> Iterator[sqlite3.Connection]:
        with cls._lock:
            cls._database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(cls._database_path)
            connection.row_factory = sqlite3.Row
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    failed_login_count INTEGER NOT NULL DEFAULT 0,
                    lockout_until TEXT,
                    mfa_secret_encrypted TEXT,
                    mfa_pending_secret_encrypted TEXT,
                    mfa_enabled INTEGER NOT NULL DEFAULT 0,
                    mfa_recovery_code_hashes TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    device_label TEXT NOT NULL DEFAULT 'Unknown device',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS invites (
                    token_hash TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_states (
                    token_hash TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    action TEXT NOT NULL,
                    user_id TEXT,
                    code_verifier TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS oauth_states_expiry_idx ON oauth_states (expires_at);
                CREATE TABLE IF NOT EXISTS oauth_identities (
                    provider TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    email TEXT,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY (provider, subject),
                    UNIQUE (user_id, provider),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS oauth_mfa_challenges (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    failed_attempt_count INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS oauth_mfa_challenges_expiry_idx ON oauth_mfa_challenges (expires_at);
                """
            )
            cls._migrate_schema(connection)
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _validate_credentials(username: str, password: str) -> str:
        normalized_username = username.strip()
        if not USERNAME_PATTERN.fullmatch(normalized_username):
            raise AuthError(400, "Username must use 3-64 letters, numbers, dots, dashes, or underscores")
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH_WITHOUT_MFA:
            raise AuthError(400, f"Password must be at least {MIN_PASSWORD_LENGTH_WITHOUT_MFA} characters")
        return normalized_username

    @classmethod
    def _check_login_rate(cls, client_key: str) -> None:
        now = cls._now()
        window = timedelta(minutes=settings.auth_login_window_minutes)
        attempts = [attempt for attempt in cls._login_attempts.get(client_key, []) if now - attempt < window]
        cls._login_attempts[client_key] = attempts
        if len(attempts) >= settings.auth_login_max_attempts:
            raise AuthError(429, "Too many failed login attempts; try again later")

    @classmethod
    def _record_failed_login(cls, client_key: str) -> None:
        cls._login_attempts.setdefault(client_key, []).append(cls._now())

    @classmethod
    def _record_account_failure(cls, connection: sqlite3.Connection, user_id: str) -> bool:
        row = connection.execute(
            "SELECT failed_login_count FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        failures = int(row["failed_login_count"] if row is not None else 0) + 1
        locked = failures >= settings.auth_login_max_attempts
        lockout_until = (
            cls._timestamp(cls._now() + timedelta(minutes=settings.auth_login_lockout_minutes)) if locked else None
        )
        connection.execute(
            "UPDATE users SET failed_login_count = ?, lockout_until = ? WHERE id = ?",
            (0 if locked else failures, lockout_until, user_id),
        )
        return locked

    @staticmethod
    def _clear_account_failures(connection: sqlite3.Connection, user_id: str) -> None:
        connection.execute(
            "UPDATE users SET failed_login_count = 0, lockout_until = NULL WHERE id = ?", (user_id,)
        )

    @staticmethod
    def _migrate_schema(connection: sqlite3.Connection) -> None:
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        session_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)")}
        if "failed_login_count" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0")
        if "lockout_until" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN lockout_until TEXT")
        if "mfa_secret_encrypted" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_secret_encrypted TEXT")
        if "mfa_pending_secret_encrypted" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_pending_secret_encrypted TEXT")
        if "mfa_enabled" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0")
        if "mfa_recovery_code_hashes" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_recovery_code_hashes TEXT")
        if "last_seen_at" not in session_columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN last_seen_at TEXT")
            connection.execute("UPDATE sessions SET last_seen_at = created_at WHERE last_seen_at IS NULL")
        if "device_label" not in session_columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN device_label TEXT NOT NULL DEFAULT 'Unknown device'")

    @classmethod
    def _consume_recovery_code(cls, connection: sqlite3.Connection, user_id: str, supplied_code: str | None) -> bool:
        if not isinstance(supplied_code, str) or not supplied_code.startswith("MCAI-"):
            return False
        row = connection.execute("SELECT mfa_recovery_code_hashes FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None or not row["mfa_recovery_code_hashes"]:
            return False
        try:
            hashes = json.loads(row["mfa_recovery_code_hashes"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        if not isinstance(hashes, list):
            return False
        for index, stored_hash in enumerate(hashes):
            if isinstance(stored_hash, str) and cls._verify_password(stored_hash, supplied_code):
                del hashes[index]
                connection.execute(
                    "UPDATE users SET mfa_recovery_code_hashes = ? WHERE id = ?", (json.dumps(hashes), user_id)
                )
                return True
        return False

    @staticmethod
    def _device_label(value: str) -> str:
        candidate = str(value).casefold()
        if "iphone" in candidate or "ipad" in candidate:
            return "iPhone / iPad"
        if "android" in candidate:
            return "Android"
        if "windows" in candidate:
            return "Windows browser"
        if "macintosh" in candidate or "mac os" in candidate:
            return "Mac browser"
        if "linux" in candidate:
            return "Linux browser"
        return "Unknown device"

    @classmethod
    def _verify_password(cls, password_hash: str, password: str) -> bool:
        try:
            return cls._passwords.verify(password_hash, password)
        except (InvalidHashError, VerificationError):
            return False

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.isoformat()

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value)
