"""Exercise durable Delivery goals, per-user quotas, and privacy-safe audit records."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings
from app.services.agent_service import AgentService
from app.services.operations_service import OperationsService, UsageLimitError
from app.tools.agent_tools import AGENT_TOOLS
from app.workspace.file_manager import FileManager


temporary = TemporaryDirectory()
root = Path(temporary.name)
workspace = root / "workspace"
workspace.mkdir()
(workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")

original_state_root = AgentService._state_root
original_setting_state_root = settings.agent_state_root
original_run_limit = settings.agent_daily_run_limit
original_step_limit = settings.agent_daily_step_limit
original_ask_json = OllamaAgent.ask_json
original_command = AGENT_TOOLS["run_project_command"].function
token = FileManager.activate_workspace(workspace)

try:
    settings.agent_state_root = str(root / "runs")
    settings.agent_daily_run_limit = 2
    settings.agent_daily_step_limit = 20
    AgentService._state_root = Path(settings.agent_state_root).resolve()
    AgentService._runs.clear()

    responses = iter(
        [
            json.dumps(
                {
                    "action": {"tool": "write_file", "arguments": {"filename": "feature.txt", "content": "ready\n"}},
                    "summary": "Apply the focused implementation.",
                }
            ),
            json.dumps(
                {
                    "action": {"tool": "final", "arguments": {"answer": "Feature implemented."}},
                    "summary": "",
                }
            ),
        ]
    )
    OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
    AGENT_TOOLS["run_project_command"].function = lambda command: {
        "status": "ok",
        "command": command,
        "exit_code": 0,
        "output": "tests passed",
    }

    run = AgentService.start("PRIVATE_TASK_DO_NOT_RECORD", mode="delivery", owner_id="user-1")
    assert run["status"] == "awaiting_approval"
    assert run["pending_action"]["tool"] == "write_file"

    after_write = AgentService.resume(run["run_id"], approve=True, owner_id="user-1")
    assert after_write["status"] == "awaiting_approval"
    assert after_write["pending_action"]["tool"] == "run_project_command"
    assert after_write["delivery_phase"] == "verification_pending"

    completed = AgentService.resume(run["run_id"], approve=True, owner_id="user-1")
    assert completed["status"] == "completed"
    assert completed["delivery_phase"] == "completed"
    assert "Verification passed" in completed["answer"]
    assert any(item["tool"] == "git_review_diff" for item in completed["trace"])

    usage = OperationsService.usage("user-1")
    assert usage["runs"] == 1
    assert usage["steps"] == 2
    events = OperationsService.activity("user-1")
    assert any(event["event"] == "delivery_completed" for event in events)
    audit = (root / "operations.json").read_text(encoding="utf-8")
    assert "PRIVATE_TASK_DO_NOT_RECORD" not in audit

    settings.agent_daily_run_limit = 1
    try:
        OperationsService.reserve_run("user-1")
        raise AssertionError("daily run limit should have blocked another run")
    except UsageLimitError:
        pass

    # Administrators retain an unlimited safety/recovery path.  The configured
    # limits still apply to ordinary signed-in accounts.
    OperationsService.reserve_run("admin-1", quota_exempt=True)
    OperationsService.reserve_run("admin-1", quota_exempt=True)
    OperationsService.consume_step("admin-1", quota_exempt=True)
    OperationsService.consume_step("admin-1", quota_exempt=True)
    admin_usage = OperationsService.usage("admin-1", quota_exempt=True)
    assert admin_usage["quota_exempt"] is True
    assert admin_usage["runs"] == 0
    assert admin_usage["steps"] == 0
    assert admin_usage["runs_limited"] is False
    assert admin_usage["steps_limited"] is False
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["run_project_command"].function = original_command
    settings.agent_state_root = original_setting_state_root
    settings.agent_daily_run_limit = original_run_limit
    settings.agent_daily_step_limit = original_step_limit
    AgentService._state_root = original_state_root
    AgentService._runs.clear()
    FileManager.reset_workspace(token)
    temporary.cleanup()

print("operations_delivery=ok")
