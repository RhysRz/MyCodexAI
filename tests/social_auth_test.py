"""Smoke tests for invite-preserving Google/GitHub OAuth sign-in."""

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from cryptography.fernet import Fernet

from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthService
from app.services.mfa_service import MfaService
from app.services import social_auth_service


class FakeResponse:
    def __init__(self, payload: dict, ok: bool = True):
        self._payload = payload
        self.ok = ok

    def json(self) -> dict:
        return self._payload


temporary_root = TemporaryDirectory()
original_database_path = AuthService._database_path
original_bootstrap_token = settings.auth_bootstrap_token
original_google_id = settings.oauth_google_client_id
original_google_secret = settings.oauth_google_client_secret
original_mfa_key = settings.auth_mfa_encryption_key
original_cookie_secure = settings.auth_cookie_secure
original_require_mfa_for_admin = settings.auth_require_mfa_for_admin
original_post = social_auth_service.requests.post
original_get = social_auth_service.requests.get
AuthService._database_path = Path(temporary_root.name) / "auth.db"
settings.auth_bootstrap_token = "social-test-bootstrap"
settings.oauth_google_client_id = "google-test-client"
settings.oauth_google_client_secret = "google-test-secret"
settings.auth_mfa_encryption_key = Fernet.generate_key().decode("ascii")
# Cookie attributes are covered by http_security_test. This flow test keeps its
# in-memory OAuth redirect chain independent of the production-only __Host cookie.
settings.auth_cookie_secure = False
settings.auth_require_mfa_for_admin = False
AuthService._login_attempts.clear()


def fake_post(_url, *, data, **_kwargs):
    assert data["code"] == "provider-code"
    assert data["code_verifier"]
    return FakeResponse({"access_token": "short-lived-token"})


def fake_get(_url, **_kwargs):
    return FakeResponse({"sub": "provider-subject-1", "email": "person@example.com"})


social_auth_service.requests.post = fake_post
social_auth_service.requests.get = fake_get

try:
    client = TestClient(app, base_url=settings.public_origin, headers={"origin": settings.public_origin})
    bootstrap = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "social-admin",
            "password": "a secure social test password",
            "bootstrap_token": "social-test-bootstrap",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    assert client.get("/api/auth/oauth/providers").json()["providers"]["google"] is True

    link_start = client.post("/api/auth/oauth/google/link/start")
    assert link_start.status_code == 200, link_start.text
    link_query = parse_qs(urlparse(link_start.json()["authorization_url"]).query)
    assert link_query["code_challenge_method"] == ["S256"]
    assert link_query["state"]
    linked = client.get(
        f"/api/auth/oauth/google/callback?code=provider-code&state={link_query['state'][0]}",
        follow_redirects=False,
    )
    assert linked.status_code == 303
    assert linked.headers["location"] == "/?oauth_success=linked"

    social_client = TestClient(app, base_url=settings.public_origin, headers={"origin": settings.public_origin})
    login_start = social_client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert login_start.status_code == 307
    login_query = parse_qs(urlparse(login_start.headers["location"]).query)
    signed_in = social_client.get(
        f"/api/auth/oauth/google/callback?code=provider-code&state={login_query['state'][0]}",
        follow_redirects=False,
    )
    assert signed_in.status_code == 303
    assert "httponly" in signed_in.headers["set-cookie"].lower()
    assert "Agent workspace" in social_client.get("/").text

    admin = AuthService.user_from_session(client.cookies.get(settings.auth_cookie_name))
    assert admin is not None
    setup = AuthService.begin_mfa_setup(admin)
    AuthService.confirm_mfa_setup(admin, MfaService._totp(setup["secret"], 0))
    mfa_client = TestClient(app, base_url=settings.public_origin, headers={"origin": settings.public_origin})
    mfa_start = mfa_client.get("/api/auth/oauth/google/start", follow_redirects=False)
    mfa_query = parse_qs(urlparse(mfa_start.headers["location"]).query)
    mfa_redirect = mfa_client.get(
        f"/api/auth/oauth/google/callback?code=provider-code&state={mfa_query['state'][0]}",
        follow_redirects=False,
    )
    assert mfa_redirect.headers["location"] == "/?oauth_mfa=required"
    assert f"{settings.auth_cookie_name}=" not in mfa_redirect.headers.get("set-cookie", "")
    mfa_complete = mfa_client.post(
        "/api/auth/oauth/mfa/complete",
        json={"code": MfaService._totp(setup["secret"], 0)},
    )
    assert mfa_complete.status_code == 200, mfa_complete.text
    assert "Agent workspace" in mfa_client.get("/").text
finally:
    social_auth_service.requests.post = original_post
    social_auth_service.requests.get = original_get
    AuthService._database_path = original_database_path
    settings.auth_bootstrap_token = original_bootstrap_token
    settings.oauth_google_client_id = original_google_id
    settings.oauth_google_client_secret = original_google_secret
    settings.auth_mfa_encryption_key = original_mfa_key
    settings.auth_cookie_secure = original_cookie_secure
    settings.auth_require_mfa_for_admin = original_require_mfa_for_admin
    AuthService._login_attempts.clear()
    temporary_root.cleanup()

print("social_auth=ok")
