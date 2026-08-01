import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.ollama_agent import OllamaAgent
from app.services.agent_service import AgentService
from app.tools import agent_tools


captured_commands = []
original_run_process = agent_tools._run_process
original_ask_json = OllamaAgent.ask_json
original_state_root = AgentService._state_root
temporary_state = TemporaryDirectory()
AgentService._state_root = Path(temporary_state.name).resolve()

try:
    agent_tools._run_process = lambda command: (captured_commands.append(command), {"status": "ok"})[1]
    assert agent_tools.git_review_diff()["status"] == "ok"
    assert agent_tools.git_review_diff("staged")["status"] == "ok"
    assert agent_tools.git_review_diff("commit", "abc123")["status"] == "ok"
    assert agent_tools.git_review_diff("branch", "main")["status"] == "ok"
    assert captured_commands == [
        ["git", "diff", "--no-ext-diff", "HEAD"],
        ["git", "diff", "--cached", "--no-ext-diff"],
        ["git", "show", "--format=", "--no-ext-diff", "abc123"],
        ["git", "diff", "--no-ext-diff", "main...HEAD"],
    ]
    assert agent_tools.git_review_diff("branch", "--unsafe")["status"] == "blocked"
    assert agent_tools.git_review_diff("staged", "main")["status"] == "blocked"

    responses = iter(
        [json.dumps({"action": {"tool": "final", "arguments": {"answer": "Review complete."}}, "summary": ""})]
    )
    captured_messages = []
    OllamaAgent.ask_json = classmethod(lambda _cls, messages: (captured_messages.append(messages), next(responses))[1])
    AgentService._runs.clear()
    run = AgentService.start("Review main", mode="review", max_steps=1, review_scope="branch", review_target="main")
    assert run["status"] == "completed"
    assert run["review_scope"] == "branch"
    assert run["review_target"] == "main"
    assert "Review scope is `branch` target `main`" in captured_messages[0][0]["content"]
    try:
        AgentService.start("Review branch", mode="review", review_scope="branch")
        raise AssertionError("branch review must require a target")
    except ValueError as error:
        assert "required" in str(error)
finally:
    agent_tools._run_process = original_run_process
    OllamaAgent.ask_json = original_ask_json
    AgentService._state_root = original_state_root
    temporary_state.cleanup()

print("review_scope=ok")
