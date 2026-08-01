"""Smoke-test the private Image Studio API without using a Hugging Face token."""

from fastapi.testclient import TestClient

from app.api.dependencies import require_user
from app.core.settings import settings
from app.main import app
from app.services.auth_service import AuthenticatedUser


def test_image_status_is_safe_for_an_authenticated_user():
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser("image-api", "member", "user")
    try:
        client = TestClient(app, base_url=settings.public_origin)
        response = client.get("/api/images/status")
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"configured", "provider", "model", "detail", "used_today", "daily_limit", "remaining_today", "quota_exempt"}
        assert "hf_token" not in payload
        assert "api_key" not in payload
        assert payload["quota_exempt"] is False

        listing = client.get("/api/images")
        assert listing.status_code == 200
        assert isinstance(listing.json().get("images"), list)
    finally:
        app.dependency_overrides.pop(require_user, None)
