from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.codebase_index_service import CodebaseIndexService
from app.tools.agent_tools import AgentToolExecutor
from app.workspace.file_manager import FileManager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "project"
(workspace / "app").mkdir(parents=True)
(workspace / "web").mkdir()
(workspace / "app" / "main.py").write_text(
    "from app.service import UserService\n\n\ndef create_app():\n    return UserService()\n",
    encoding="utf-8",
)
(workspace / "app" / "service.py").write_text(
    "class UserService:\n    def get_user(self):\n        return 'user'\n",
    encoding="utf-8",
)
(workspace / "web" / "app.ts").write_text(
    "import { client } from './client';\nexport function renderDashboard() { return client; }\n",
    encoding="utf-8",
)
(workspace / "node_modules").mkdir()
(workspace / "node_modules" / "ignored.js").write_text("export const ignored = true;\n", encoding="utf-8")

token = FileManager.activate_workspace(workspace)
try:
    overview = CodebaseIndexService.overview(rebuild=True)
    assert overview["file_count"] == 3
    assert overview["languages"] == {"Python": 2, "TypeScript": 1}
    assert "app/main.py" in overview["entry_points"]

    symbol_result = CodebaseIndexService.search("create_app")
    assert symbol_result["matches"][0]["path"] == "app/main.py"
    assert "create_app" in symbol_result["matches"][0]["symbols"]

    tool_overview = AgentToolExecutor.execute("inspect_project", {})
    assert tool_overview["file_count"] == 3
    tool_search = AgentToolExecutor.execute("find_code", {"query": "UserService"})
    assert {entry["path"] for entry in tool_search["matches"]} == {"app/service.py"}

    assert AgentToolExecutor.execute("write_file", {"filename": "app/new.py", "content": "VALUE = 1\n"})["status"] == "written"
    assert not (workspace / ".mycodexai" / "codebase-index.json").exists()
    assert CodebaseIndexService.overview()["file_count"] == 4
finally:
    FileManager.reset_workspace(token)
    temporary_root.cleanup()

print("codebase_index=ok")
