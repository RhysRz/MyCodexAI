from pathlib import Path
from tempfile import TemporaryDirectory
import json

from fastapi.testclient import TestClient

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.main import app
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService, AuthenticatedUser
from app.workspace import file_manager


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
settings.auth_bootstrap_token = "bootstrap-secret"
AuthService._login_attempts.clear()

try:
    origin_headers = {"origin": settings.public_origin}
    anonymous = TestClient(app, base_url="https://localhost")
    assert "auth-form" in anonymous.get("/").text
    assert anonymous.get("/api/auth/me").status_code == 401
    assert anonymous.post("/api/agent/runs", json={"task": "blocked"}, headers=origin_headers).status_code == 401

    bootstrap = anonymous.post(
        "/api/auth/bootstrap",
        json={
            "username": "admin-user",
            "password": "a very strong password",
            "bootstrap_token": "bootstrap-secret",
        },
        headers=origin_headers,
    )
    assert bootstrap.status_code == 200, bootstrap.text
    assert "httponly" in bootstrap.headers["set-cookie"].lower()
    admin = AuthenticatedUser(**bootstrap.json())
    assert "Agent workspace" in anonymous.get("/").text

    invite_response = anonymous.post("/api/auth/invites", json={"role": "user"}, headers=origin_headers)
    assert invite_response.status_code == 200, invite_response.text

    member_client = TestClient(app, base_url="https://localhost")
    register = member_client.post(
        "/api/auth/register",
        json={
            "username": "member-user",
            "password": "another strong password",
            "invite_token": invite_response.json()["token"],
        },
        headers=origin_headers,
    )
    assert register.status_code == 200, register.text
    member = AuthenticatedUser(**register.json())

    upload = member_client.post(
        "/api/workspace/uploads",
        data={"destination": "uploads", "overwrite": "false"},
        files=[("files", ("project/app.py", b"print('private')\n", "text/plain"))],
        headers=origin_headers,
    )
    assert upload.status_code == 200, upload.text
    member_workspace = AuthService.workspace_for_user(member)
    admin_workspace = AuthService.workspace_for_user(admin)
    assert (member_workspace / "uploads" / "project" / "app.py").is_file()
    assert not (admin_workspace / "uploads" / "project" / "app.py").exists()

    responses = iter(
        [
            json.dumps(
                {
                    "action": {
                        "tool": "final",
                        "arguments": {"answer": "Reviewed the private attachment."},
                    },
                    "summary": "",
                }
            )
        ]
    )
    original_ask_json = OllamaAgent.ask_json
    OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
    try:
        AgentService._runs.clear()
        run_response = member_client.post(
            "/api/agent/runs",
            json={
                "task": "Review the attached file",
                "attachments": ["uploads/project/app.py"],
                "max_steps": 1,
            },
            headers=origin_headers,
        )
        assert run_response.status_code == 200, run_response.text
        run = run_response.json()
        assert run["attachments"] == ["uploads/project/app.py"]
        assert anonymous.get(f"/api/agent/runs/{run['run_id']}").status_code == 404
    finally:
        OllamaAgent.ask_json = original_ask_json

    logout = member_client.post("/api/auth/logout", headers=origin_headers)
    assert logout.status_code == 204
    assert member_client.get("/api/auth/me").status_code == 401
finally:
    file_manager.WORKSPACE = original_workspace
    AuthService._database_path = original_database_path
    AgentService._state_root = original_state_root
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    temporary_root.cleanup()

print("auth=ok")
