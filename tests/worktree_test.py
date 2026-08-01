from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess

from fastapi.testclient import TestClient

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.main import app
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService, AuthenticatedUser
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
original_state_root = AgentService._state_root
original_bootstrap_token = settings.auth_bootstrap_token
file_manager.WORKSPACE = workspace
AuthService._database_path = Path(temporary_root.name) / "auth.db"
AgentService._state_root = Path(temporary_root.name) / "runs"
settings.auth_bootstrap_token = "worktree-bootstrap-token"
AuthService._login_attempts.clear()

try:
    client = TestClient(app, base_url="https://localhost", headers={"origin": settings.public_origin})
    bootstrap = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "worktree-admin",
            "password": "a very strong test password",
            "bootstrap_token": "worktree-bootstrap-token",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    user = AuthenticatedUser(**bootstrap.json())
    main_workspace = AuthService.workspace_for_user(user)
    main_workspace.mkdir(parents=True, exist_ok=True)
    (main_workspace / "README.md").write_text("# Main workspace\n", encoding="utf-8")
    git("init", cwd=main_workspace)
    git("config", "user.email", "tests@example.invalid", cwd=main_workspace)
    git("config", "user.name", "MyCodexAI Tests", cwd=main_workspace)
    git("add", "README.md", cwd=main_workspace)
    git("commit", "-m", "Initial workspace", cwd=main_workspace)

    create = client.post("/api/worktrees", json={"branch": "feature/isolated-agent"})
    assert create.status_code == 200, create.text
    assert create.json() == {"id": "feature/isolated-agent", "is_main": False}

    listed = client.get("/api/worktrees")
    assert listed.status_code == 200, listed.text
    assert {item["id"] for item in listed.json()["worktrees"]} == {"main", "feature/isolated-agent"}

    headers = {"X-MyCodexAI-Worktree": "feature/isolated-agent"}
    upload = client.post(
        "/api/workspace/uploads",
        headers=headers,
        data={"destination": "uploads", "overwrite": "false"},
        files=[("files", ("input.txt", b"branch only\n", "text/plain"))],
    )
    assert upload.status_code == 200, upload.text

    worktree_path = workspace / ".mycodexai" / "worktrees" / user.id / "feature" / "isolated-agent"
    assert (worktree_path / "uploads" / "input.txt").read_text(encoding="utf-8") == "branch only\n"
    assert not (main_workspace / "uploads" / "input.txt").exists()

    responses = iter(
        [
            json.dumps(
                {
                    "action": {
                        "tool": "write_file",
                        "arguments": {"filename": "branch.txt", "content": "created in the worktree\n"},
                    },
                    "summary": "Write the isolated result.",
                }
            ),
            json.dumps(
                {
                    "action": {"tool": "final", "arguments": {"answer": "Finished in the worktree."}},
                    "summary": "",
                }
            ),
        ]
    )
    original_ask_json = OllamaAgent.ask_json
    OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
    try:
        AgentService._runs.clear()
        started = client.post(
            "/api/agent/runs",
            headers=headers,
            json={"task": "Create branch.txt", "max_steps": 3},
        )
        assert started.status_code == 200, started.text
        run = started.json()
        assert run["workspace_id"] == "feature/isolated-agent"
        assert run["status"] == "awaiting_approval"

        wrong_worktree = client.post(
            f"/api/agent/runs/{run['run_id']}/resume",
            json={"approve": True},
        )
        assert wrong_worktree.status_code == 409, wrong_worktree.text

        finished = client.post(
            f"/api/agent/runs/{run['run_id']}/resume",
            headers=headers,
            json={"approve": True},
        )
        assert finished.status_code == 200, finished.text
        assert finished.json()["status"] == "completed"
    finally:
        OllamaAgent.ask_json = original_ask_json

    assert (worktree_path / "branch.txt").read_text(encoding="utf-8") == "created in the worktree\n"
    assert not (main_workspace / "branch.txt").exists()
finally:
    file_manager.WORKSPACE = original_workspace
    AuthService._database_path = original_database_path
    AgentService._state_root = original_state_root
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    temporary_root.cleanup()

print("worktree=ok")
