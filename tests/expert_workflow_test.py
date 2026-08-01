from pathlib import Path
from tempfile import TemporaryDirectory
import json

from app.agents.ollama_agent import OllamaAgent
from app.services.agent_service import AgentService
from app.services.project_guidance_service import ProjectGuidanceService
from app.tools.agent_tools import AgentToolExecutor
from app.workspace.file_manager import FileManager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "project"
workspace.mkdir()
(workspace / "AGENTS.md").write_text("Run the focused tests before finalizing.\n", encoding="utf-8")
(workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
(workspace / "package.json").write_text('{"scripts":{"test":"vitest run","build":"vite build"}}\n', encoding="utf-8")

original_state_root = AgentService._state_root
AgentService._state_root = Path(temporary_root.name) / "runs"
token = FileManager.activate_workspace(workspace)

try:
    guidance = ProjectGuidanceService.save_custom("Keep API routes backward compatible.")
    assert "AGENTS.md" in guidance["content"]
    assert "backward compatible" in guidance["content"]
    assert AgentToolExecutor.execute("read_project_guidance", {})["has_custom_guidance"] is True

    checks = AgentToolExecutor.execute("detect_project_checks", {})
    assert {tuple(item["command"]) for item in checks["recommended"]} == {
        ("pytest", "-q"),
        ("npm", "run", "test"),
        ("npm", "run", "build"),
    }

    responses = iter(
        [
            json.dumps(
                {
                    "action": {"tool": "final", "arguments": {"answer": "Expert workflow completed."}},
                    "summary": "",
                }
            )
        ]
    )
    captured_messages = []
    original_ask_json = OllamaAgent.ask_json
    OllamaAgent.ask_json = classmethod(
        lambda _cls, messages: (captured_messages.append(messages), next(responses))[1]
    )
    try:
        AgentService._runs.clear()
        run = AgentService.start("Review the project", max_steps=1, mode="expert", owner_id="test-user", quota_exempt=True)
        assert run["mode"] == "expert"
        assert run["status"] == "completed"
    finally:
        OllamaAgent.ask_json = original_ask_json

    system_prompt = captured_messages[0][0]["content"]
    assert "Expert workflow rules" in system_prompt
    assert "Run the focused tests" in system_prompt
    assert "backward compatible" in system_prompt
finally:
    FileManager.reset_workspace(token)
    AgentService._state_root = original_state_root
    temporary_root.cleanup()

print("expert_workflow=ok")
