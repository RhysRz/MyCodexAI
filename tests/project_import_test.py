from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
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
workspace.mkdir()

original_workspace = file_manager.WORKSPACE
original_database_path = AuthService._database_path
original_state_root = AgentService._state_root
original_bootstrap_token = settings.auth_bootstrap_token
file_manager.WORKSPACE = workspace
AuthService._database_path = Path(temporary_root.name) / "auth.db"
AgentService._state_root = Path(temporary_root.name) / "runs"
settings.auth_bootstrap_token = "project-bootstrap-token"
AuthService._login_attempts.clear()

try:
    client = TestClient(app, base_url="https://localhost", headers={"origin": settings.public_origin})
    bootstrap = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "project-admin",
            "password": "a very strong test password",
            "bootstrap_token": "project-bootstrap-token",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    user = AuthenticatedUser(**bootstrap.json())

    source_files = [
        ("files", (f"MyCodexAI/app/module_{index:03}.py", f"VALUE = {index}\n".encode(), "text/plain"))
        for index in range(120)
    ]
    source_files.extend(
        [
            ("files", ("MyCodexAI/.env", b"API_KEY=must-not-import\n", "text/plain")),
            ("files", ("MyCodexAI/node_modules/pkg/index.js", b"ignored\n", "text/plain")),
            ("files", ("MyCodexAI/.git/config", b"ignored\n", "text/plain")),
        ]
    )
    imported = client.post(
        "/api/projects/import",
        data={"project_name": "MyCodexAI"},
        files=source_files,
    )
    assert imported.status_code == 200, imported.text
    project = imported.json()
    assert project["id"] == "MyCodexAI"
    assert project["file_count"] == 120
    assert project["ignored_file_count"] == 3
    assert project["secret_file_count"] == 1

    user_workspace = AuthService.workspace_for_user(user)
    project_path = user_workspace / "projects" / "MyCodexAI"
    assert (project_path / "app" / "module_119.py").is_file()
    assert not (project_path / ".env").exists()
    assert not (project_path / "node_modules").exists()

    archive_stream = BytesIO()
    with zipfile.ZipFile(archive_stream, "w") as archive:
        archive.writestr("ZipProject/src/main.py", "print('from zip')\n")
        archive.writestr("ZipProject/.env", "SECRET=not-imported\n")
    imported_zip = client.post(
        "/api/projects/import",
        data={"project_name": "ZipProject"},
        files=[("files", ("ZipProject.zip", archive_stream.getvalue(), "application/zip"))],
    )
    assert imported_zip.status_code == 200, imported_zip.text
    assert imported_zip.json()["file_count"] == 1
    assert imported_zip.json()["secret_file_count"] == 1
    assert (user_workspace / "projects" / "ZipProject" / "src" / "main.py").is_file()

    listed = client.get("/api/projects")
    assert listed.status_code == 200, listed.text
    assert {item["id"] for item in listed.json()["projects"]} == {"workspace", "MyCodexAI", "ZipProject"}

    project_headers = {"X-MyCodexAI-Project": "MyCodexAI"}
    indexed = client.post("/api/projects/index/rebuild", headers=project_headers)
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["file_count"] == 120
    assert indexed.json()["languages"]["Python"] == 120

    upload = client.post(
        "/api/workspace/uploads",
        headers=project_headers,
        data={"destination": "uploads", "overwrite": "false"},
        files=[("files", ("context.txt", b"project scoped\n", "text/plain"))],
    )
    assert upload.status_code == 200, upload.text
    assert (project_path / "uploads" / "context.txt").is_file()
    assert not (user_workspace / "uploads" / "context.txt").exists()

    responses = iter(
        [
            json.dumps(
                {
                    "action": {
                        "tool": "write_file",
                        "arguments": {"filename": "agent-result.txt", "content": "only in project\n"},
                    },
                    "summary": "Write the project-scoped result.",
                }
            ),
            json.dumps(
                {
                    "action": {"tool": "final", "arguments": {"answer": "Project updated."}},
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
            headers=project_headers,
            json={"task": "Create the result file", "max_steps": 3},
        )
        assert started.status_code == 200, started.text
        run = started.json()
        assert run["project_id"] == "MyCodexAI"
        assert run["status"] == "awaiting_approval"

        wrong_project = client.post(
            f"/api/agent/runs/{run['run_id']}/resume",
            json={"approve": True},
        )
        assert wrong_project.status_code == 409, wrong_project.text

        completed = client.post(
            f"/api/agent/runs/{run['run_id']}/resume",
            headers=project_headers,
            json={"approve": True},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"
    finally:
        OllamaAgent.ask_json = original_ask_json

    assert (project_path / "agent-result.txt").read_text(encoding="utf-8") == "only in project\n"
    assert not (user_workspace / "agent-result.txt").exists()
finally:
    file_manager.WORKSPACE = original_workspace
    AuthService._database_path = original_database_path
    AgentService._state_root = original_state_root
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    temporary_root.cleanup()

print("project_import=ok")
