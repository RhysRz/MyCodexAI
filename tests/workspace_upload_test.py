from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import zipfile

from fastapi.testclient import TestClient

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.main import app
from app.services.agent_service import AgentService
from app.services.auth_service import AuthService, AuthenticatedUser
from app.workspace import file_manager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "workspace"
state_root = Path(temporary_root.name) / "runs"
workspace.mkdir()

original_workspace = file_manager.WORKSPACE
original_state_root = AgentService._state_root
original_database_path = AuthService._database_path
original_bootstrap_token = settings.auth_bootstrap_token
file_manager.WORKSPACE = workspace
AgentService._state_root = state_root
AuthService._database_path = Path(temporary_root.name) / "auth.db"
AuthService._login_attempts.clear()
settings.auth_bootstrap_token = "test-bootstrap-token"

try:
    client = TestClient(app, base_url="https://localhost", headers={"origin": settings.public_origin})
    bootstrap = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "upload-admin",
            "password": "safe test password",
            "bootstrap_token": "test-bootstrap-token",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    user = AuthenticatedUser(**bootstrap.json())
    user_workspace = AuthService.workspace_for_user(user)
    response = client.post(
        "/api/workspace/uploads",
        data={"destination": "uploads", "overwrite": "false"},
        files=[
            ("files", ("starter/src/app.py", b"print('hello')\n", "text/plain")),
            ("files", ("starter/README.md", b"# Starter\n", "text/markdown")),
        ],
    )
    assert response.status_code == 200, response.text
    uploaded = response.json()
    assert [file["path"] for file in uploaded["files"]] == [
        "uploads/starter/src/app.py",
        "uploads/starter/README.md",
    ]
    assert (user_workspace / "uploads" / "starter" / "src" / "app.py").read_text() == "print('hello')\n"

    duplicate = client.post(
        "/api/workspace/uploads",
        data={"destination": "uploads", "overwrite": "false"},
        files=[("files", ("starter/README.md", b"changed\n", "text/markdown"))],
    )
    assert duplicate.status_code == 409

    archive_stream = BytesIO()
    with zipfile.ZipFile(archive_stream, "w") as archive:
        archive.writestr("src/main.js", "console.log('zip');\n")
        archive.writestr("package.json", '{"name":"zip-project"}\n')

    archive_upload = client.post(
        "/api/workspace/uploads",
        data={"destination": "imports", "overwrite": "false"},
        files=[("files", ("zip-project.zip", archive_stream.getvalue(), "application/zip"))],
    )
    assert archive_upload.status_code == 200, archive_upload.text
    assert (user_workspace / "imports" / "zip-project" / "src" / "main.js").read_text() == "console.log('zip');\n"

    original_ask_json = OllamaAgent.ask_json
    responses = iter(
        [
            json.dumps(
                {
                    "action": {
                        "tool": "final",
                        "arguments": {"answer": "Reviewed the uploaded files."},
                    },
                    "summary": "",
                }
            )
        ]
    )
    OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
    try:
        AgentService._runs.clear()
        token = file_manager.FileManager.activate_workspace(user_workspace)
        try:
            run = AgentService.start(
                "Continue the uploaded project",
                max_steps=1,
                mode="project",
                attachments=["uploads/starter/src/app.py", "imports/zip-project/src/main.js"],
                owner_id=user.id,
                quota_exempt=True,
            )
        finally:
            file_manager.FileManager.reset_workspace(token)
        assert run["attachments"] == ["uploads/starter/src/app.py", "imports/zip-project/src/main.js"]
        assert run["status"] == "completed"
        persisted = json.loads(next(state_root.glob("*.json")).read_text(encoding="utf-8"))
        assert "uploads/starter/src/app.py" in persisted["messages"][1]["content"]
    finally:
        OllamaAgent.ask_json = original_ask_json
finally:
    file_manager.WORKSPACE = original_workspace
    AgentService._state_root = original_state_root
    AuthService._database_path = original_database_path
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    temporary_root.cleanup()

print("workspace_upload=ok")
