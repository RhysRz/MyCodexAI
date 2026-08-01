from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

from app.tools.agent_tools import (
    AgentToolExecutor,
    git_commit,
    git_create_branch,
    git_initialize,
    git_restore_file,
)
from app.workspace.file_manager import FileManager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "workspace"
workspace.mkdir()
token = FileManager.activate_workspace(workspace)

try:
    initialized = git_initialize("main")
    assert initialized["status"] == "ok", initialized

    subprocess.run(["git", "config", "user.name", "MyCodexAI Test"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=workspace, check=True)

    file_path = workspace / "app.txt"
    file_path.write_text("first version\n", encoding="utf-8")
    committed = git_commit("Create app file")
    assert committed["status"] == "ok", committed

    branch = git_create_branch("feature/safe-restore")
    assert branch["status"] == "ok", branch

    file_path.write_text("changed version\n", encoding="utf-8")
    preview = AgentToolExecutor.preview("git_restore_file", {"filename": "app.txt"})
    assert preview["status"] == "preview"
    assert "changed version" in preview["diff"]

    restored = git_restore_file("app.txt")
    assert restored["status"] == "ok", restored
    assert file_path.read_text(encoding="utf-8") == "first version\n"

    try:
        AgentToolExecutor.preview("git_create_branch", {"branch": "../invalid"})
        raise AssertionError("unsafe branch name should be rejected")
    except ValueError:
        pass
finally:
    FileManager.reset_workspace(token)
    temporary_root.cleanup()

print("git_tools=ok")
