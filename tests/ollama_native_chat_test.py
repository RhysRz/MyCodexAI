"""Verify chat models can disable native Ollama thinking without affecting Agent calls."""

from app.agents.ollama_agent import OllamaAgent


class FakeResponse:
    def raise_for_status(self):
        return None

    @staticmethod
    def json():
        return {"message": {"content": "<think>hidden trace</think>" + chr(10) + "พร้อมช่วยครับ"}}


original_post = OllamaAgent._ask_native_chat.__globals__["requests"].post
captured: dict = {}


def fake_post(url, *, json, timeout):
    captured.update(url=url, payload=json, timeout=timeout)
    return FakeResponse()


OllamaAgent._ask_native_chat.__globals__["requests"].post = fake_post
try:
    answer = OllamaAgent._ask_native_chat(
        [{"role": "user", "content": "สวัสดี"}],
        model="qwen3:4b",
        temperature=0.45,
        think=False,
    )
    assert answer == "พร้อมช่วยครับ"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["model"] == "qwen3:4b"
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"]["temperature"] == 0.45
finally:
    OllamaAgent._ask_native_chat.__globals__["requests"].post = original_post

print("ollama_native_chat=ok")
