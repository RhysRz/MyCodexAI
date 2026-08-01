"""Keep the context-chat smoke check deterministic and offline."""

from app.agents.ollama_agent import OllamaAgent
from app.services.chat_service import ChatService


def test_context_chat_uses_chat_model_without_a_live_ollama_call():
    original_ask = OllamaAgent.ask
    captured: list[dict] = []
    ChatService._histories.clear()

    def fake_ask(_cls, messages, *, model=None, temperature=None, think=None):
        captured.append({"messages": messages, "model": model, "temperature": temperature, "think": think})
        return "MyCodex พร้อมช่วยครับ"

    OllamaAgent.ask = classmethod(fake_ask)
    try:
        answer = ChatService.chat("ChatService ทำงานอย่างไร", owner_id="context-chat-test")
        assert answer == "MyCodex พร้อมช่วยครับ"
        assert captured[0]["model"]
        assert captured[0]["messages"][-1]["content"] == "ChatService ทำงานอย่างไร"
    finally:
        OllamaAgent.ask = original_ask
        ChatService._histories.clear()
