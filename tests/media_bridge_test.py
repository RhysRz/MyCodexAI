"""The optional cloud media bridge remains narrow, authenticated, and pinned."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "deploy" / "huggingface" / "media-bridge"


def test_media_bridge_is_pinned_and_does_not_use_youtube_credentials() -> None:
    dockerfile = (BRIDGE / "Dockerfile").read_text(encoding="utf-8")
    requirements = (BRIDGE / "requirements.txt").read_text(encoding="utf-8")
    application = (BRIDGE / "app.py").read_text(encoding="utf-8")
    assert "FROM node:24-bookworm-slim" in dockerfile
    assert "7608dd51ee813b48cf9a6d68c6e42cb197ce10e0" in dockerfile
    assert "yt-dlp[default]==2026.6.9" in requirements
    assert "bgutil-ytdlp-pot-provider==1.3.1" in requirements
    assert "MEDIA_BRIDGE_KEY" in application
    assert "hmac.compare_digest" in application
    assert "VIDEO_PATTERN.fullmatch" in application
    assert "duration > 360" in application
    assert "EXTRACTION_LOCK" in application
    assert "--cookies" not in application


def test_media_bridge_deployment_keeps_generated_key_out_of_output() -> None:
    deployment = (ROOT / "deploy" / "huggingface" / "deploy_media_bridge.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(48)" in deployment
    assert 'api.add_space_secret(repo_id=SPACE_ID, key="MEDIA_BRIDGE_KEY"' in deployment
    assert 'set_github_secret("MYCODEXAI_MEDIA_BRIDGE_KEY"' in deployment
    assert "print(bridge_key)" not in deployment


def test_render_blueprint_keeps_bridge_on_the_free_plan() -> None:
    blueprint = (ROOT / "deploy" / "render" / "render.yaml").read_text(encoding="utf-8")
    assert "runtime: docker" in blueprint
    assert "plan: free" in blueprint
    assert "healthCheckPath: /" in blueprint
    assert "generateValue: true" in blueprint
