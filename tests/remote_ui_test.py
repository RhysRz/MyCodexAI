"""Verify the authenticated phone control surface is isolated by the normal login boundary."""

from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthService


temporary_root = TemporaryDirectory()
original_database_path = AuthService._database_path
original_bootstrap_token = settings.auth_bootstrap_token
AuthService._database_path = Path(temporary_root.name) / "auth.db"
settings.auth_bootstrap_token = "remote-test-bootstrap"
AuthService._login_attempts.clear()

try:
    anonymous = TestClient(app, base_url="https://localhost")
    redirect = anonymous.get("/remote", follow_redirects=False)
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/?next=/remote"
    assert "auth-form" in anonymous.get("/remote").text

    signed_in = TestClient(app, base_url="https://localhost")
    bootstrap = signed_in.post(
        "/api/auth/bootstrap",
        json={
            "username": "remote-admin",
            "password": "a secure remote test password",
            "bootstrap_token": "remote-test-bootstrap",
        },
        headers={"origin": settings.public_origin},
    )
    assert bootstrap.status_code == 200, bootstrap.text
    remote = signed_in.get("/remote")
    assert remote.status_code == 200
    assert "remote-form" in remote.text
    for identifier in (
        "remote-menu-toggle",
        "remote-menu",
        "remote-menu-close",
        "remote-menu-backdrop",
        "remote-admin-nav",
        "remote-admin-console",
        "remote-training",
        "remote-backups",
        "remote-invites",
        "remote-github",
        "remote-save-learning-example",
        "remote-create-backup",
        "remote-create-invite",
        "remote-github-push",
    ):
        assert f'id="{identifier}"' in remote.text
    assert "/static/remote.js" in remote.text
    assert remote.headers["cache-control"] == "no-store, max-age=0"
finally:
    AuthService._database_path = original_database_path
    settings.auth_bootstrap_token = original_bootstrap_token
    AuthService._login_attempts.clear()
    temporary_root.cleanup()

remote_script = (Path(__file__).resolve().parent.parent / "static" / "remote.js").read_text(encoding="utf-8")
assert "function setRemoteMenu" in remote_script
assert "remoteElements.adminNav.hidden = user.role !== 'admin';" in remote_script
assert "remoteElements.adminConsole.hidden = user.role !== 'admin';" in remote_script
assert "if (user.role === 'admin') await loadRemoteAdmin();" in remote_script
for function_name in ("loadRemoteTraining", "loadRemoteBackups", "createRemoteInvite", "loadRemoteGitHub"):
    assert f"function {function_name}" in remote_script

print("remote_ui=ok")
