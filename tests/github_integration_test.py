"""Exercise GitHub handoff safety without contacting GitHub or storing a token."""

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from app.services.github_service import GitHubIntegrationError, GitHubService


def run(workspace: Path, *arguments: str) -> None:
    completed = subprocess.run(["git", *arguments], cwd=workspace, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


with TemporaryDirectory() as temporary:
    workspace = Path(temporary)
    (workspace / "pyproject.toml").write_text("[project]\nname = 'demo'\nversion = '0.0.1'\n", encoding="utf-8")
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")
    run(workspace, "init", "-b", "main")
    run(workspace, "config", "user.name", "Test User")
    run(workspace, "config", "user.email", "test@example.invalid")
    run(workspace, "add", ".")
    run(workspace, "commit", "-m", "initial")
    run(workspace, "remote", "add", "origin", "https://github.com/example/demo.git")

    status = GitHubService.status(workspace)
    assert status["is_git_repository"] is True
    assert status["is_github_remote"] is True
    assert status["repository"] == "example/demo"
    assert status["ci_kind"] == "python"
    assert "token" not in str(status).casefold()

    prepared_ci = GitHubService.prepare_ci_workflow("user-1", "main", "workspace", workspace)
    assert "pytest -q" in prepared_ci["preview"]
    ci_result = GitHubService.execute(prepared_ci["approval_token"], "user-1", "main", "workspace")
    assert ci_result["status"] == "ok"
    assert (workspace / ".github" / "workflows" / "mycodexai-ci.yml").is_file()

    try:
        GitHubService.execute(prepared_ci["approval_token"], "user-1", "main", "workspace")
        raise AssertionError("a GitHub confirmation token must be single-use")
    except GitHubIntegrationError:
        pass

    prepared_push = GitHubService.prepare_push("user-1", "main", "workspace", workspace)
    assert prepared_push["kind"] == "push"
    try:
        GitHubService.execute(prepared_push["approval_token"], "other-user", "main", "workspace")
        raise AssertionError("a GitHub confirmation token must be owner-scoped")
    except GitHubIntegrationError:
        pass

print("github_integration=ok")
