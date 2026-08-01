from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import CsrfOriginMiddleware
from app.core.settings import Settings, settings
from app.main import app


client = TestClient(app, base_url="https://localhost")
root = client.get("/")
assert root.status_code == 200
assert root.headers["content-security-policy"].startswith("default-src 'self'")
assert root.headers["x-frame-options"] == "DENY"
assert root.headers["cache-control"] == "no-store, max-age=0"
assert root.headers["permissions-policy"] == "camera=(), microphone=(self), geolocation=(), payment=(), usb=()"
assert client.get("/", headers={"host": "attacker.example"}).status_code == 400

original_environment = settings.environment
original_origin = settings.public_origin
try:
    settings.environment = "production"
    settings.public_origin = "https://ai.example.com"
    csrf_app = FastAPI()
    csrf_app.add_middleware(CsrfOriginMiddleware)

    @csrf_app.post("/api/unsafe")
    def unsafe():
        return {"ok": True}

    csrf_client = TestClient(csrf_app)
    assert csrf_client.post("/api/unsafe").status_code == 403
    assert csrf_client.post("/api/unsafe", headers={"origin": "https://ai.example.com"}).status_code == 200
finally:
    settings.environment = original_environment
    settings.public_origin = original_origin

production = Settings(
    environment="production",
    debug=False,
    auth_cookie_secure=True,
    auth_cookie_name="__Host-mycodexai_session",
    auth_bootstrap_token="",
    auth_mfa_encryption_key=Fernet.generate_key().decode("ascii"),
    auth_require_mfa_for_admin=True,
    allowed_hosts="ai.example.com",
    public_origin="https://ai.example.com",
    force_https=True,
    browser_qa_enabled=False,
    sandbox_mode="docker",
    sandbox_allow_network=False,
)
assert production.is_production is True

try:
    Settings(
        environment="production",
        debug=True,
        auth_cookie_secure=True,
        auth_cookie_name="__Host-mycodexai_session",
        auth_bootstrap_token="",
        auth_mfa_encryption_key=Fernet.generate_key().decode("ascii"),
        auth_require_mfa_for_admin=True,
        allowed_hosts="ai.example.com",
        public_origin="https://ai.example.com",
        force_https=True,
        browser_qa_enabled=False,
        sandbox_mode="docker",
        sandbox_allow_network=False,
    )
    raise AssertionError("unsafe production settings must be rejected")
except ValueError:
    pass

print("http_security=ok")
