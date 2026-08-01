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
original_review_diff = AGENT_TOOLS["git_review_diff"].function
AgentService._state_root = Path(temporary_state.name).resolve()

responses = iter(
    [
        json.dumps(
            {
                "action": {"tool": "write_file", "arguments": {"filename": "unsafe.txt", "content": "no"}},
                "summary": "Try to change the code.",
            }
        ),
        json.dumps(
            {
                "action": {"tool": "git_review_diff", "arguments": {}},
                "summary": "Read the combined review diff.",
            }
        ),
        json.dumps(
            {
                "action": {
                    "tool": "final",
                    "arguments": {"answer": "No actionable findings. Checked app.py lines 1-3."},
                },
                "summary": "",
            }
        ),
    ]
)
write_called = False


def unexpected_write(filename, content):
    global write_called
    write_called = True
    raise AssertionError(f"review should not write {filename}")


OllamaAgent.ask_json = classmethod(lambda _cls, _messages: next(responses))
AGENT_TOOLS["write_file"].function = unexpected_write
AGENT_TOOLS["git_review_diff"].function = lambda: {"status": "ok", "output": "diff --git a/app.py b/app.py"}

try:
    AgentService._runs.clear()
    run = AgentService.start("Review current changes", mode="review")
    assert run["status"] == "completed"
    assert run["progress"]["max_steps"] == 16
    assert write_called is False
    assert run["trace"][0]["tool"] == "write_file"
    assert run["trace"][0]["status"] == "blocked"
    assert run["trace"][1]["tool"] == "git_review_diff"
    assert run["trace"][1]["status"] == "ok"
    assert "No actionable findings" in run["answer"]
finally:
    OllamaAgent.ask_json = original_ask_json
    AGENT_TOOLS["write_file"].function = original_write
    AGENT_TOOLS["git_review_diff"].function = original_review_diff
    AgentService._state_root = original_state_root
    temporary_state.cleanup()

print("review_mode=ok")
