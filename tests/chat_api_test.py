"""Exercise the authenticated chat route without touching a real account."""

from fastapi.testclient import TestClient

from app.api.dependencies import require_workspace_user
from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthenticatedUser
from app.services.chat_service import ChatService


original_chat = ChatService.chat


def fake_user():
    return AuthenticatedUser(id="chat-test-user", username="chat-test", role="user")


ChatService.chat = classmethod(lambda _cls, message, owner_id: f"ตอบ: {message} ({owner_id})")
app.dependency_overrides[require_workspace_user] = fake_user
try:
    client = TestClient(app, base_url=settings.public_origin)
    response = client.post(
        "/api/chat",
        json={"message": "สวัสดี"},
        headers={"Origin": settings.public_origin},
    )
    assert response.status_code == 200
    assert response.json()["answer"] == "ตอบ: สวัสดี (chat-test-user)"
    history = client.get("/api/chat/history")
    assert history.status_code == 200
    assert history.json() == {"messages": []}
finally:
    ChatService.chat = original_chat
    app.dependency_overrides.pop(require_workspace_user, None)

print("chat_api=ok")
