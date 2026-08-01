from fastapi.testclient import TestClient

from app.agents.ollama_agent import OllamaAgent
from app.api.dependencies import require_workspace_user
from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthenticatedUser
from app.services.chat_service import ChatService


def test_chat_service_streams_visible_chunks_and_persists_completed_answer():
    original_stream = OllamaAgent.stream
    owner_id = "chat-stream-service-test"
    ChatService._histories.pop(owner_id, None)
    OllamaAgent.stream = classmethod(lambda _cls, *_args, **_kwargs: iter(["สวัสดี", "ครับ"]))
    try:
        assert "".join(ChatService.stream("ทดสอบ", owner_id)) == "สวัสดีครับ"
        assert ChatService.history(owner_id)[-1] == {"role": "assistant", "content": "สวัสดีครับ"}
    finally:
        OllamaAgent.stream = original_stream
        ChatService._histories.pop(owner_id, None)


def test_chat_stream_route_emits_sse_chunks_for_authenticated_user():
    original_stream = ChatService.stream

    def fake_user():
        return AuthenticatedUser(id="chat-stream-route-test", username="stream-user", role="user")

    ChatService.stream = classmethod(lambda _cls, _message, owner_id: iter([f"ตอบ {owner_id}", " แล้วครับ"]))
    app.dependency_overrides[require_workspace_user] = fake_user
    try:
        client = TestClient(app, base_url=settings.public_origin)
        response = client.post(
            "/api/chat/stream",
            json={"message": "สวัสดี"},
            headers={"Origin": settings.public_origin},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert '"type": "delta"' in response.text
        assert '"type": "done"' in response.text
        assert '"delta": "ตอบ chat-stream-route-test"' in response.text
        assert '"delta": " แล้วครับ"' in response.text
    finally:
        ChatService.stream = original_stream
        app.dependency_overrides.pop(require_workspace_user, None)
