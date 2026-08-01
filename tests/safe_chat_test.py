"""Verify normal chat is side-effect free and keeps user histories isolated."""

from app.agents.ollama_agent import OllamaAgent
from app.services.chat_service import ChatService


original_ask = OllamaAgent.ask
captured: list[list[dict]] = []
ChatService._histories.clear()


def fake_ask(_cls, messages, *, model=None, temperature=None, think=None):
    captured.append(messages)
    return "A normal reply."


OllamaAgent.ask = classmethod(fake_ask)
try:
    assert ChatService.chat("Hello", owner_id="user-a") == "A normal reply."
    assert ChatService.history("user-a") == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "A normal reply."},
    ]
    assert ChatService.history("user-b") == []
    prompt = captured[0][0]["content"]
    assert "Your name is MyCodex" in prompt
    assert "male AI persona" in prompt
    assert prompt.startswith("/no_think")
    assert "Thai is the default" in prompt
    assert "Chat can discuss and draft" in prompt
    assert "cannot inspect local files" in prompt
    assert "ToolPlanner" not in prompt
finally:
    OllamaAgent.ask = original_ask
    ChatService._histories.clear()

print("safe_chat=ok")
