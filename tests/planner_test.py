"""Validate tool planning without invoking the local model."""

from app.agents.ollama_agent import OllamaAgent
from app.planner.tool_planner import ToolPlanner


def test_tool_planner_parses_model_actions_without_live_ollama():
    original_ask = OllamaAgent.ask
    responses = iter([
        '{"tool":"read_file","arguments":{"filename":"hello.txt"}}',
        '{"tool":"list_files","arguments":{}}',
    ])
    OllamaAgent.ask = classmethod(lambda _cls, _messages: next(responses))
    try:
        assert ToolPlanner.plan("Open hello.txt") == {"tool": "read_file", "arguments": {"filename": "hello.txt"}}
        assert ToolPlanner.plan("Show files") == {"tool": "list_files", "arguments": {}}
    finally:
        OllamaAgent.ask = original_ask
