import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.ollama_agent import OllamaAgent
from app.services.agent_service import AgentService
from app.tools.agent_tools import AGENT_TOOLS


temporary_state = TemporaryDirectory()
original_state_root = AgentService._state_root
original_ask_json = OllamaAgent.ask_json
original_write = AGENT_TOOLS["write_file"].function
original_git_diff = AGENT_TOOLS["git_diff"].function
AgentService._state_root = Path(temporary_state.name).resolve()

responses = iter(
    [
        json.dumps(
            {
                "action": {"tool": "final", "arguments": {"answer": "Found the entry point and a focused plan."}},
                "summary": "",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "write_file", "arguments": {"filename": "app.txt", "content": "updated\n"}},
                "summary": "Apply the planned change.",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "final", "arguments": {"answer": "Changed app.txt; review the diff."}},
                "summary": "",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "git_diff", "arguments": {}},
                "summary": "Inspect the resulting diff.",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "final", "arguments": {"answer": "Review complete: diff matches the task."}},
                "summary": "",
            }
        ),
    ]
)

OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
AGENT_TOOLS["write_file"].function = lambda filename, content: {
    "status": "written",
    "filename": filename,
    "characters_written": len(content),
}
AGENT_TOOLS["git_diff"].function = lambda: {"status": "ok", "output": "diff --git a/app.txt b/app.txt"}

try:
    AgentService._runs.clear()
    run = AgentService.start("Implement a focused update", mode="team")
    assert run["status"] == "awaiting_approval"
    assert run["pending_action"]["tool"] == "write_file"
    assert run["pending_action"]["team_member_id"] == "implementer"
    assert run["team_members"][0]["status"] == "completed"
    assert run["team_members"][1]["status"] == "awaiting_approval"
    assert run["team_members"][0]["summary"] == "Found the entry point and a focused plan."

    completed = AgentService.resume(run["run_id"], approve=True)
    assert completed["status"] == "completed"
    assert completed["answer"] == "Review complete: diff matches the task."
    assert [member["status"] for member in completed["team_members"]] == ["completed", "completed", "completed"]
    assert any(entry.get("team_member_id") == "reviewer" and entry["tool"] == "git_diff" for entry in completed["trace"])

    AgentService._runs.clear()
    restored = AgentService.get(completed["run_id"])
    assert restored["team_members"][2]["summary"] == "Review complete: diff matches the task."
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["write_file"].function = original_write
    AGENT_TOOLS["git_diff"].function = original_git_diff
    AgentService._state_root = original_state_root
    temporary_state.cleanup()

print("team_workflow=ok")
