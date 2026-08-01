from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.project_guidance_service import ProjectGuidanceService
from app.tools.agent_tools import AgentToolExecutor
from app.workspace.file_manager import FileManager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "project"
(workspace / "apps" / "web").mkdir(parents=True)
(workspace / "AGENTS.md").write_text("Root rule.\n", encoding="utf-8")
(workspace / "apps" / "AGENTS.md").write_text("App rule.\n", encoding="utf-8")
(workspace / "apps" / "web" / "AGENTS.md").write_text("Ignored web rule.\n", encoding="utf-8")
(workspace / "apps" / "web" / "AGENTS.override.md").write_text("Web override rule.\n", encoding="utf-8")
token = FileManager.activate_workspace(workspace)

try:
    ProjectGuidanceService.save_custom("Saved project rule.")
    guidance = ProjectGuidanceService.get("apps/web")
    assert guidance["sources"] == [
        "AGENTS.md",
        ".mycodexai/instructions.md",
        "apps/AGENTS.md",
        "apps/web/AGENTS.override.md",
    ]
    content = guidance["content"]
    assert content.index("Root rule.") < content.index("Saved project rule.") < content.index("App rule.")
    assert "Web override rule." in content
    assert "Ignored web rule." not in content
    tool_result = AgentToolExecutor.execute("read_project_guidance", {"directory": "apps/web"})
    assert tool_result["sources"] == guidance["sources"]
    try:
        ProjectGuidanceService.get("../outside")
        raise AssertionError("parent directory must be rejected")
    except ValueError:
        pass
finally:
    FileManager.reset_workspace(token)
    temporary_root.cleanup()

print("project_guidance_layers=ok")
