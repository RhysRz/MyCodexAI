from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep, monotonic
import subprocess

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthService, AuthenticatedUser
from app.services.terminal_service import TerminalService
from app.workspace import file_manager


def git(*arguments: str, cwd: Path) -> None:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "workspace"
workspace.mkdir()

original_workspace = file_manager.WORKSPACE
original_database_path = AuthService._database_path
original_bootstrap_token = settings.auth_bootstrap_token
original_sandbox_mode = settings.sandbox_mode
file_manager.WORKSPACE = workspace
AuthService._database_path = Path(temporary_root.name) / "auth.db"
settings.auth_bootstrap_token = "terminal-bootstrap-token"
settings.sandbox_mode = "host"
AuthService._login_attempts.clear()
TerminalService._jobs.clear()

try:
    client = TestClient(app, base_url="https://localhost", headers={"origin": settings.public_origin})
    bootstrap = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "terminal-admin",
            "password": "a very strong test password",
            "bootstrap_token": "terminal-bootstrap-token",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    user = AuthenticatedUser(**bootstrap.json())
    user_workspace = AuthService.workspace_for_user(user)
    user_workspace.mkdir(parents=True, exist_ok=True)
    git("init", cwd=user_workspace)

    unsafe = client.post(
        "/api/terminal/jobs",
        json={"command": ["powershell", "Get-ChildItem"], "working_directory": "."},
    )
    assert unsafe.status_code == 400

    pending = client.post(
        "/api/terminal/jobs",
        json={"command": ["git", "status", "--short"], "working_directory": "."},
    )
    assert pending.status_code == 200, pending.text
    job = pending.json()
    assert job["status"] == "awaiting_approval"

    duplicate = client.post(
        "/api/terminal/jobs",
        json={"command": ["git", "status"], "working_directory": "."},
    )
    assert duplicate.status_code == 400

    resumed = client.post(f"/api/terminal/jobs/{job['job_id']}/resume", json={"approve": True})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "running"

    deadline = monotonic() + 10
    while monotonic() < deadline:
        current = client.get(f"/api/terminal/jobs/{job['job_id']}")
        assert current.status_code == 200, current.text
        result = current.json()
        if result["status"] not in {"running", "cancelling"}:
            break
        sleep(0.1)
    else:
        raise AssertionError("terminal job did not finish")

    assert result["status"] == "completed", result
    assert "$ git status --short" in result["output"]
    assert result["exit_code"] == 0

    no_escape = client.post(
        "/api/terminal/jobs",
        json={"command": ["git", "status"], "working_directory": "../outside"},
    )
    assert no_escape.status_code == 400
finally:
    TerminalService._jobs.clear()
    file_manager.WORKSPACE = original_workspace
    AuthService._database_path = original_database_path
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    settings.sandbox_mode = original_sandbox_mode
    temporary_root.cleanup()

print("terminal=ok")
