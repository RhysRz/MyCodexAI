"""OAuth sign-in for pre-linked Google and GitHub identities.

This module deliberately stores only stable provider identifiers.  Access and refresh
tokens are never persisted, and OAuth is not an account-creation path: an identity
must first be linked by an already authenticated user.
"""

from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import secrets
from typing import Any
from urllib.parse import urlencode

import requests

from app.core.settings import settings
from app.services.auth_service import AuthError, AuthService, AuthenticatedUser
from app.services.mfa_service import MfaError, MfaService


SUPPORTED_PROVIDERS = ("google", "github")


class SocialAuthError(AuthError):
    """An OAuth error with a small, safe code suitable for redirecting to the UI."""

    def __init__(self, status_code: int, detail: str, code: str = "failed"):
        super().__init__(status_code, detail)
        self.code = code


@dataclass(frozen=True)
class OAuthProviderConfig:
    name: str
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    scope: str
    use_pkce: bool


@dataclass(frozen=True)
class OAuthState:
    action: str
    user_id: str | None
    code_verifier: str
    redirect_uri: str


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str | None


class SocialAuthService:
    @classmethod
    def provider_status(cls) -> dict[str, bool]:
        return {provider: cls._provider_config(provider).client_id != "" for provider in SUPPORTED_PROVIDERS}

    @classmethod
    def begin_login(cls, provider: str, callback_origin: str) -> tuple[str, str]:
        return cls._begin(provider, "login", None, callback_origin)

    @classmethod
    def begin_link(cls, provider: str, user: AuthenticatedUser, callback_origin: str) -> tuple[str, str]:
        return cls._begin(provider, "link", user.id, callback_origin)

    @classmethod
    def complete_callback(
        cls,
        provider: str,
        state: str,
        state_cookie: str | None,
        code: str,
    ) -> tuple[str, AuthenticatedUser | None, str | None]:
        saved_state = cls._consume_state(provider, state, state_cookie)
        identity = cls._fetch_identity(provider, code, saved_state)
        if saved_state.action == "link":
            if not saved_state.user_id:
                raise SocialAuthError(400, "OAuth link state is invalid")
            cls._link_identity(saved_state.user_id, identity)
            return "linked", None, None

        user = cls._user_for_identity(identity)
        if user is None:
            raise SocialAuthError(
                403,
                "This social account is not linked to a MyCodexAI account",
                "not_linked",
            )
        mfa_challenge = cls._begin_mfa_challenge(user)
        if mfa_challenge:
            return "mfa_required", user, mfa_challenge
        return "signed_in", user, AuthService.create_session(user)

    @classmethod
    def complete_mfa_challenge(cls, raw_challenge: str | None, code: str) -> tuple[AuthenticatedUser, str]:
        if not raw_challenge:
            raise SocialAuthError(401, "OAuth MFA verification has expired", "mfa_expired")
        token_hash = AuthService._hash_token(raw_challenge)
        with AuthService._connection() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.username, users.role, users.mfa_secret_encrypted,
                       oauth_mfa_challenges.failed_attempt_count, oauth_mfa_challenges.expires_at
                FROM oauth_mfa_challenges JOIN users ON users.id = oauth_mfa_challenges.user_id
                WHERE oauth_mfa_challenges.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row is None or AuthService._parse_timestamp(row["expires_at"]) <= AuthService._now():
                connection.execute("DELETE FROM oauth_mfa_challenges WHERE token_hash = ?", (token_hash,))
                connection.commit()
                raise SocialAuthError(401, "OAuth MFA verification has expired", "mfa_expired")
            try:
                valid_code = MfaService.verify_encrypted_secret(row["mfa_secret_encrypted"], code)
            except MfaError as error:
                raise SocialAuthError(503, str(error)) from error
            if not valid_code:
                attempts = int(row["failed_attempt_count"]) + 1
                if attempts >= settings.auth_login_max_attempts:
                    connection.execute("DELETE FROM oauth_mfa_challenges WHERE token_hash = ?", (token_hash,))
                else:
                    connection.execute(
                        "UPDATE oauth_mfa_challenges SET failed_attempt_count = ? WHERE token_hash = ?",
                        (attempts, token_hash),
                    )
                connection.commit()
                raise SocialAuthError(401, "The verification code is invalid", "mfa_invalid")
            connection.execute("DELETE FROM oauth_mfa_challenges WHERE token_hash = ?", (token_hash,))
            user = AuthenticatedUser(row["id"], row["username"], row["role"])
            return user, AuthService._create_session(connection, user.id)

    @classmethod
    def _begin(
        cls, provider: str, action: str, user_id: str | None, callback_origin: str
    ) -> tuple[str, str]:
        config = cls._configured_provider(provider)
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        redirect_uri = cls._redirect_uri(callback_origin, config.name)
        now = AuthService._now()
        with AuthService._connection() as connection:
            connection.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (AuthService._timestamp(now),))
            connection.execute(
                """
                INSERT INTO oauth_states
                    (token_hash, provider, action, user_id, code_verifier, redirect_uri, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    AuthService._hash_token(state),
                    config.name,
                    action,
                    user_id,
                    code_verifier,
                    redirect_uri,
                    AuthService._timestamp(now + timedelta(seconds=settings.oauth_state_ttl_seconds)),
                    AuthService._timestamp(now),
                ),
            )

        parameters: dict[str, str] = {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": config.scope,
            "state": state,
        }
        if config.name == "google":
            parameters["prompt"] = "select_account"
        if config.use_pkce:
            parameters["code_challenge"] = cls._code_challenge(code_verifier)
            parameters["code_challenge_method"] = "S256"
        return f"{config.authorization_endpoint}?{urlencode(parameters)}", state

    @classmethod
    def _consume_state(cls, provider: str, state: str, state_cookie: str | None) -> OAuthState:
        if not state_cookie or not hmac.compare_digest(state, state_cookie):
            raise SocialAuthError(400, "OAuth state validation failed")
        with AuthService._connection() as connection:
            row = connection.execute(
                """
                SELECT provider, action, user_id, code_verifier, redirect_uri, expires_at
                FROM oauth_states WHERE token_hash = ?
                """,
                (AuthService._hash_token(state),),
            ).fetchone()
            if row is None or row["provider"] != provider or AuthService._parse_timestamp(row["expires_at"]) <= AuthService._now():
                raise SocialAuthError(400, "OAuth state is invalid or expired")
            connection.execute("DELETE FROM oauth_states WHERE token_hash = ?", (AuthService._hash_token(state),))
        return OAuthState(row["action"], row["user_id"], row["code_verifier"], row["redirect_uri"])

    @classmethod
    def _fetch_identity(cls, provider: str, code: str, saved_state: OAuthState) -> OAuthIdentity:
        config = cls._configured_provider(provider)
        token_payload: dict[str, str] = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "redirect_uri": saved_state.redirect_uri,
        }
        if config.name == "google":
            token_payload.update({"grant_type": "authorization_code", "code_verifier": saved_state.code_verifier})
        try:
            token_response = requests.post(
                config.token_endpoint,
                data=token_payload,
                headers={"Accept": "application/json"},
                timeout=settings.oauth_request_timeout_seconds,
            )
            token_data: dict[str, Any] = token_response.json()
            if not token_response.ok or not isinstance(token_data.get("access_token"), str):
                raise SocialAuthError(401, "The provider did not accept the authorization code")
            profile_response = requests.get(
                config.userinfo_endpoint,
                headers={
                    "Authorization": f"Bearer {token_data['access_token']}",
                    "Accept": "application/json",
                    "User-Agent": "MyCodexAI OAuth",
                },
                timeout=settings.oauth_request_timeout_seconds,
            )
            profile: dict[str, Any] = profile_response.json()
        except requests.RequestException as error:
            raise SocialAuthError(502, "The social provider is temporarily unavailable") from error
        except ValueError as error:
            raise SocialAuthError(502, "The social provider returned an invalid response") from error

        if not profile_response.ok:
            raise SocialAuthError(401, "The social provider could not verify this account")
        subject = profile.get("sub") if config.name == "google" else profile.get("id")
        if subject is None or not str(subject).strip():
            raise SocialAuthError(401, "The social provider did not return an account identifier")
        email_value = profile.get("email")
        email = str(email_value).strip().casefold() if isinstance(email_value, str) and email_value.strip() else None
        return OAuthIdentity(config.name, str(subject), email)

    @classmethod
    def _link_identity(cls, user_id: str, identity: OAuthIdentity) -> None:
        with AuthService._connection() as connection:
            owner = connection.execute(
                "SELECT user_id FROM oauth_identities WHERE provider = ? AND subject = ?",
                (identity.provider, identity.subject),
            ).fetchone()
            if owner is not None and owner["user_id"] != user_id:
                raise SocialAuthError(409, "This social account is linked to another MyCodexAI account", "already_linked")
            existing_provider = connection.execute(
                "SELECT subject FROM oauth_identities WHERE provider = ? AND user_id = ?",
                (identity.provider, user_id),
            ).fetchone()
            if existing_provider is not None and existing_provider["subject"] != identity.subject:
                raise SocialAuthError(409, "A different account for this provider is already linked", "provider_already_linked")
            connection.execute(
                """
                INSERT INTO oauth_identities (provider, subject, user_id, email, linked_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider, subject) DO UPDATE SET email = excluded.email, linked_at = excluded.linked_at
                """,
                (identity.provider, identity.subject, user_id, identity.email, AuthService._timestamp(AuthService._now())),
            )

    @classmethod
    def _user_for_identity(cls, identity: OAuthIdentity) -> AuthenticatedUser | None:
        with AuthService._connection() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.username, users.role
                FROM oauth_identities JOIN users ON users.id = oauth_identities.user_id
                WHERE oauth_identities.provider = ? AND oauth_identities.subject = ?
                """,
                (identity.provider, identity.subject),
            ).fetchone()
        if row is None:
            return None
        return AuthenticatedUser(row["id"], row["username"], row["role"])

    @classmethod
    def _begin_mfa_challenge(cls, user: AuthenticatedUser) -> str | None:
        with AuthService._connection() as connection:
            row = connection.execute(
                "SELECT mfa_enabled FROM users WHERE id = ?", (user.id,)
            ).fetchone()
            if row is None:
                raise SocialAuthError(401, "The linked user account no longer exists")
            if not row["mfa_enabled"]:
                if settings.is_production and user.role == "admin" and settings.auth_require_mfa_for_admin:
                    raise SocialAuthError(
                        403,
                        "Administrator MFA enrollment is required before production login",
                        "mfa_required",
                    )
                return None
            raw_challenge = secrets.token_urlsafe(32)
            now = AuthService._now()
            connection.execute("DELETE FROM oauth_mfa_challenges WHERE expires_at <= ?", (AuthService._timestamp(now),))
            connection.execute(
                """
                INSERT INTO oauth_mfa_challenges
                    (token_hash, user_id, failed_attempt_count, expires_at, created_at)
                VALUES (?, ?, 0, ?, ?)
                """,
                (
                    AuthService._hash_token(raw_challenge),
                    user.id,
                    AuthService._timestamp(now + timedelta(seconds=settings.oauth_state_ttl_seconds)),
                    AuthService._timestamp(now),
                ),
            )
        return raw_challenge

    @classmethod
    def _configured_provider(cls, provider: str) -> OAuthProviderConfig:
        config = cls._provider_config(provider)
        if not config.client_id or not config.client_secret:
            raise SocialAuthError(503, f"{config.name.title()} sign-in is not configured", "not_configured")
        return config

    @staticmethod
    def _provider_config(provider: str) -> OAuthProviderConfig:
        if provider == "google":
            return OAuthProviderConfig(
                "google",
                settings.oauth_google_client_id.strip(),
                settings.oauth_google_client_secret.strip(),
                "https://accounts.google.com/o/oauth2/v2/auth",
                "https://oauth2.googleapis.com/token",
                "https://openidconnect.googleapis.com/v1/userinfo",
                "openid email profile",
                True,
            )
        if provider == "github":
            return OAuthProviderConfig(
                "github",
                settings.oauth_github_client_id.strip(),
                settings.oauth_github_client_secret.strip(),
                "https://github.com/login/oauth/authorize",
                "https://github.com/login/oauth/access_token",
                "https://api.github.com/user",
                "read:user user:email",
                False,
            )
        raise SocialAuthError(404, "Unsupported social provider", "unsupported")

    @staticmethod
    def callback_origin(request_origin: str) -> str:
        configured = settings.public_origin.rstrip("/")
        return configured or request_origin.rstrip("/")

    @staticmethod
    def _redirect_uri(callback_origin: str, provider: str) -> str:
        return f"{callback_origin.rstrip('/')}/api/auth/oauth/{provider}/callback"

    @staticmethod
    def _code_challenge(code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return urlsafe_b64encode(digest).decode("ascii").rstrip("=")
