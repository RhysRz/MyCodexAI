from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthService, AuthenticatedUser
from app.services.browser_qa_service import BrowserQaService
from app.tools.agent_tools import AgentToolExecutor
from app.workspace import file_manager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "workspace"
workspace.mkdir()

original_workspace = file_manager.WORKSPACE
original_database_path = AuthService._database_path
original_bootstrap_token = settings.auth_bootstrap_token
original_enabled = settings.browser_qa_enabled
original_sandbox_mode = settings.sandbox_mode
original_find_browser = BrowserQaService._find_browser
original_run_command = BrowserQaService._run_command
file_manager.WORKSPACE = workspace
AuthService._database_path = Path(temporary_root.name) / "auth.db"
settings.auth_bootstrap_token = "browser-qa-bootstrap-token"
settings.browser_qa_enabled = True
settings.sandbox_mode = "host"
AuthService._login_attempts.clear()


def fake_find_browser() -> str:
    return "fake-edge"


def fake_run_command(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    screenshot_option = next(item for item in command if item.startswith("--screenshot="))
    screenshot_path = Path(screenshot_option.split("=", 1)[1])
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nmock screenshot")
    return subprocess.CompletedProcess(command, 0, "", "")


try:
    BrowserQaService._find_browser = staticmethod(fake_find_browser)
    BrowserQaService._run_command = staticmethod(fake_run_command)
    client = TestClient(app, base_url="https://localhost", headers={"origin": settings.public_origin})
    bootstrap = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "browser-qa-admin",
            "password": "a very strong test password",
            "bootstrap_token": "browser-qa-bootstrap-token",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    user = AuthenticatedUser(**bootstrap.json())
    project_path = AuthService.workspace_for_user(user) / "projects" / "WebProject"
    project_path.mkdir(parents=True)
    (project_path / "index.html").write_text("<title>QA Demo</title><main>Hello</main>", encoding="utf-8")
    (project_path / "notes.txt").write_text("not html", encoding="utf-8")
    headers = {"X-MyCodexAI-Project": "WebProject"}

    token = file_manager.FileManager.activate_workspace(project_path)
    try:
        preview = AgentToolExecutor.preview("capture_browser_qa", {"filename": "index.html"})
    finally:
        file_manager.FileManager.reset_workspace(token)
    assert preview and preview["status"] == "preview"
    assert AgentToolExecutor.get("capture_browser_qa").requires_approval is True

    captured = client.post("/api/projects/browser-qa/capture", headers=headers, json={"filename": "index.html"})
    assert captured.status_code == 200, captured.text
    result = captured.json()
    assert result["document_title"] == "QA Demo"
    assert "project=WebProject" in result["screenshot_url"]

    screenshot = client.get(result["screenshot_url"])
    assert screenshot.status_code == 200, screenshot.text
    assert screenshot.headers["content-type"].startswith("image/png")
    assert screenshot.content.startswith(b"\x89PNG")

    non_html = client.post("/api/projects/browser-qa/capture", headers=headers, json={"filename": "notes.txt"})
    assert non_html.status_code == 400
    escaped = client.post("/api/projects/browser-qa/capture", headers=headers, json={"filename": "../outside.html"})
    assert escaped.status_code == 400
finally:
    BrowserQaService._find_browser = original_find_browser
    BrowserQaService._run_command = original_run_command
    file_manager.WORKSPACE = original_workspace
    AuthService._database_path = original_database_path
    AuthService._login_attempts.clear()
    settings.auth_bootstrap_token = original_bootstrap_token
    settings.browser_qa_enabled = original_enabled
    settings.sandbox_mode = original_sandbox_mode
    temporary_root.cleanup()

print("browser_qa=ok")
