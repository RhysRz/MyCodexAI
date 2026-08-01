import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.ollama_agent import OllamaAgent
from app.services.agent_service import AgentService
from app.services.project_skill_service import ProjectSkillService
from app.tools.agent_tools import AgentToolExecutor
from app.workspace.file_manager import FileManager


temporary_root = TemporaryDirectory()
workspace = Path(temporary_root.name) / "project"
workspace.mkdir()
token = FileManager.activate_workspace(workspace)
original_state_root = AgentService._state_root
original_ask_json = OllamaAgent.ask_json
AgentService._state_root = Path(temporary_root.name) / "runs"

try:
    saved = ProjectSkillService.save(
        "frontend-qa",
        "Frontend QA",
        "Use when a user asks to verify a web UI before delivery.",
        "Read the changed UI files. Run the focused checks. Report visual evidence and remaining risks.",
    )
    assert saved["id"] == "frontend-qa"
    assert saved["path"] == ".mycodexai/skills/frontend-qa/SKILL.md"
    assert ProjectSkillService.list() == [
        {
            "id": "frontend-qa",
            "name": "Frontend QA",
            "description": "Use when a user asks to verify a web UI before delivery.",
        }
    ]
    assert "frontend-qa" in ProjectSkillService.context()
    assert "Read the changed UI files" in ProjectSkillService.get("frontend-qa")["instructions"]
    assert AgentToolExecutor.execute("list_project_skills", {})["skills"][0]["id"] == "frontend-qa"
    assert AgentToolExecutor.execute("read_project_skill", {"skill_id": "frontend-qa"})["name"] == "Frontend QA"

    try:
        ProjectSkillService.save("../unsafe", "Unsafe", "Never save", "No")
        raise AssertionError("unsafe skill id should be rejected")
    except ValueError as error:
        assert "skill id" in str(error)

    responses = iter(
        [
            json.dumps(
                {
                    "action": {"tool": "final", "arguments": {"answer": "Skill metadata was available."}},
                    "summary": "",
                }
            )
        ]
    )
    captured_messages = []
    OllamaAgent.ask_json = classmethod(
        lambda _cls, messages: (captured_messages.append(messages), next(responses))[1]
    )
    AgentService._runs.clear()
    run = AgentService.start("Review this UI", max_steps=1, owner_id="test-user", quota_exempt=True)
    assert run["status"] == "completed"
    system_prompt = captured_messages[0][0]["content"]
    assert "frontend-qa" in system_prompt
    assert "Read the changed UI files" not in system_prompt
    assert "read_project_skill" in system_prompt
finally:
    OllamaAgent.ask_json = original_ask_json
    AgentService._state_root = original_state_root
    FileManager.reset_workspace(token)
    temporary_root.cleanup()

print("project_skill=ok")
