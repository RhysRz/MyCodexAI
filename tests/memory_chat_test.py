"""Keep chat-memory behavior testable without a slow local inference call."""

from app.agents.ollama_agent import OllamaAgent
from app.services.chat_service import ChatService


def test_memory_is_scoped_to_the_signed_in_user():
    original_ask = OllamaAgent.ask
    ChatService._histories.clear()
    OllamaAgent.ask = classmethod(lambda _cls, *_args, **_kwargs: "ตอบแล้วครับ")
    try:
        assert ChatService.chat("จำข้อความนี้", owner_id="memory-user-a") == "ตอบแล้วครับ"
        assert ChatService.history("memory-user-a") == [
            {"role": "user", "content": "จำข้อความนี้"},
            {"role": "assistant", "content": "ตอบแล้วครับ"},
        ]
        assert ChatService.history("memory-user-b") == []
    finally:
        OllamaAgent.ask = original_ask
        ChatService._histories.clear()
