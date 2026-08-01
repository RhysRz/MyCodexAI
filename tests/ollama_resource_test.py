"""Verify MyCodexAI sends resource limits without changing model quality settings."""

from app.agents.ollama_agent import OllamaAgent
from app.core.settings import settings


class FakeCompletions:
    def __init__(self):
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = type("Message", (), {"content": "ok"})()
        choice = type("Choice", (), {"message": message})()
        return type("Response", (), {"choices": [choice]})()


class FakeClient:
    def __init__(self):
        self.completions = FakeCompletions()
        self.chat = type("Chat", (), {"completions": self.completions})()


original_client = OllamaAgent.client
original_threads = settings.ollama_inference_threads
original_keep_alive = settings.ollama_keep_alive_seconds
settings.ollama_inference_threads = 2
settings.ollama_keep_alive_seconds = 90
fake_client = FakeClient()
OllamaAgent.client = fake_client

try:
    assert OllamaAgent.ask([{"role": "user", "content": "hello"}]) == "ok"
    assert OllamaAgent.ask_json([{"role": "user", "content": "json"}]) == "ok"
    for call in fake_client.completions.calls:
        assert call["model"] == settings.ollama_model
        assert call["max_tokens"] == settings.ollama_max_tokens
        assert call["extra_body"] == {"options": {"num_thread": 2}, "keep_alive": "90s"}
    assert fake_client.completions.calls[1]["temperature"] == 0
    assert fake_client.completions.calls[1]["response_format"] == {"type": "json_object"}
finally:
    OllamaAgent.client = original_client
    settings.ollama_inference_threads = original_threads
    settings.ollama_keep_alive_seconds = original_keep_alive

print("ollama_resource=ok")
