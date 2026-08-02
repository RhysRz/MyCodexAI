from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloud" / "worker"


def test_cloud_worker_has_required_components() -> None:
    required = [
        WORKER / "src" / "index.ts",
        WORKER / "src" / "auth.ts",
        WORKER / "src" / "chat.ts",
        WORKER / "src" / "agent.ts",
        WORKER / "src" / "files.ts",
        WORKER / "src" / "images.ts",
        WORKER / "src" / "learning.ts",
        WORKER / "src" / "admin.ts",
        WORKER / "src" / "music.ts",
        WORKER / "src" / "mfa.ts",
        WORKER / "src" / "oauth.ts",
        WORKER / "migrations" / "0001_initial.sql",
        WORKER / "migrations" / "0002_cloud_parity.sql",
        WORKER / "migrations" / "0003_cloud_music.sql",
        WORKER / "migrations" / "0004_cloud_mfa.sql",
        WORKER / "migrations" / "0005_cloud_oauth.sql",
        ROOT / ".github" / "workflows" / "mycodexai-cloud-agent.yml",
        ROOT / "cloud" / "runner" / "run_job.py",
        ROOT / "cloud" / "runner" / "run_music_job.py",
        ROOT / ".github" / "workflows" / "mycodexai-cloud-music.yml",
    ]
    assert all(path.is_file() for path in required)


def test_cloud_package_and_runner_are_syntactically_valid() -> None:
    package = json.loads((WORKER / "package.json").read_text(encoding="utf-8"))
    assert package["private"] is True
    assert package["scripts"]["check"] == "tsc --noEmit"
    ast.parse((ROOT / "cloud" / "runner" / "run_job.py").read_text(encoding="utf-8"))
    ast.parse((ROOT / "cloud" / "runner" / "run_music_job.py").read_text(encoding="utf-8"))


def test_agent_queue_is_serial_and_pr_reviewed() -> None:
    config = (WORKER / "wrangler.jsonc").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "mycodexai-cloud-agent.yml").read_text(encoding="utf-8")
    runner = (ROOT / "cloud" / "runner" / "run_job.py").read_text(encoding="utf-8")
    assert '"max_batch_size": 1' in config
    assert '"max_concurrency": 1' in config
    assert "cancel-in-progress: false" in workflow
    assert '"draft": not passed' in runner
    assert 'callback("needs_review"' in runner


def test_authenticated_index_asset_does_not_self_redirect() -> None:
    config = (WORKER / "wrangler.jsonc").read_text(encoding="utf-8")
    assert '"html_handling": "none"' in config


def test_cloud_does_not_embed_secret_values() -> None:
    allowed_placeholders = {".dev.vars.example"}
    suspicious_assignments: list[str] = []
    for path in (ROOT / "cloud").rglob("*"):
        if not path.is_file() or "node_modules" in path.parts or path.name in allowed_placeholders:
            continue
        if path.suffix.lower() not in {".ts", ".js", ".json", ".jsonc", ".yml", ".yaml", ".py", ".ps1", ".md", ".sql"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in (
            "GITHUB_TOKEN", "RUNNER_CALLBACK_SECRET", "CLOUD_BOOTSTRAP_TOKEN", "AUTH_ENCRYPTION_KEY",
            "OAUTH_GOOGLE_CLIENT_SECRET", "OAUTH_GITHUB_CLIENT_SECRET",
        ):
            for line in text.splitlines():
                compact = line.strip()
                if compact.startswith(f"{name}=") and "replace-" not in compact:
                    suspicious_assignments.append(f"{path}:{name}")
    assert suspicious_assignments == []


def test_security_headers_and_protected_paths_exist() -> None:
    security = (WORKER / "src" / "security.ts").read_text(encoding="utf-8")
    agent = (WORKER / "src" / "agent.ts").read_text(encoding="utf-8")
    runner = (ROOT / "cloud" / "runner" / "run_job.py").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in security
    assert "Strict-Transport-Security" in security
    assert "SameSite=Strict" in security
    assert 'path.startsWith(".github/workflows/")' in agent
    assert '".github/workflows/"' in runner
    assert '".env"' in agent and '".env"' in runner


def test_password_hashing_uses_cloudflare_supported_iterations() -> None:
    security = (WORKER / "src" / "security.ts").read_text(encoding="utf-8")
    assert "const PASSWORD_ITERATIONS = 100_000;" in security
    assert "const PASSWORD_ITERATIONS = 120_000;" not in security


def test_mobile_ui_uses_external_scripts_and_safe_rendering() -> None:
    index = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    app = (WORKER / "public" / "app.js").read_text(encoding="utf-8")
    style = (WORKER / "public" / "style.css").read_text(encoding="utf-8")
    assert "<script>" not in index
    assert 'src="/app.js' in index
    assert "textContent" in app
    assert "innerHTML" not in app
    assert "@media(max-width:760px)" in style


def test_cloud_parity_features_are_wired_and_role_aware() -> None:
    index_source = (WORKER / "src" / "index.ts").read_text(encoding="utf-8")
    worker_config = (WORKER / "wrangler.jsonc").read_text(encoding="utf-8")
    page = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    images = (WORKER / "src" / "images.ts").read_text(encoding="utf-8")
    learning = (WORKER / "src" / "learning.ts").read_text(encoding="utf-8")
    chat = (WORKER / "src" / "chat.ts").read_text(encoding="utf-8")

    assert "handleImages" in index_source
    assert "handleLearning" in index_source
    assert "handleAdmin" in index_source
    assert "handleMusic" in index_source
    assert '"IMAGE_MODEL": "@cf/black-forest-labs/flux-2-klein-9b"' in worker_config
    assert 'id="view-images"' in page
    assert 'id="view-music"' in page
    assert 'id="view-training"' in page and "admin-only" in page
    assert 'id="view-system"' in page
    assert "USER_DAILY_LIMIT" in images
    assert "prompt omitted" in images
    assert "context.user.role !== \"admin\"" in learning
    assert "training_examples" in chat
    assert 'id="music-form"' in page


def test_cloud_music_uses_private_runner_and_owner_scoped_results() -> None:
    music = (WORKER / "src" / "music.ts").read_text(encoding="utf-8")
    files = (WORKER / "src" / "files.ts").read_text(encoding="utf-8")
    page = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    app = (WORKER / "public" / "app.js").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "mycodexai-cloud-music.yml").read_text(encoding="utf-8")
    runner = (ROOT / "cloud" / "runner" / "run_music_job.py").read_text(encoding="utf-8")
    media_url = (ROOT / "cloud" / "runner" / "media_url.py").read_text(encoding="utf-8")
    assert 'event_type: "mycodexai-music"' in music
    assert "WHERE id = ? AND user_id = ?" in music
    assert "RUNNER_CALLBACK_SECRET" in music
    assert "contents_base64" in music and "3_000_000" in music
    assert "group: mycodexai-cloud-heavy" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "MusicService.analyze" in runner
    assert "download_source" in runner
    assert "Audiveris-5.11.0-ubuntu24.04-x86_64.deb" in workflow
    assert "f20113aaa33b3149ec8d6a09b2a7963360e65fafd92d69389987a85bbc3ec7a3" in workflow
    assert "dpkg-deb --extract" in workflow
    assert "MUSIC_TAB_OCR_EXECUTABLE" in workflow
    assert "tesseract-ocr" in workflow
    assert "Report workflow setup failure" in workflow
    assert ".mycodexai-music-runner-started" in workflow
    assert 'os.environ.setdefault("MUSIC_OMR_EXECUTABLE", "")' in runner
    assert 'STARTED_MARKER.write_text("started\\n"' in runner
    assert '".mp3", ".flac", ".m4a", ".aac", ".ogg"' in music
    assert '"musicxml", "stem_midi"' in music
    assert "htdemucs_6s" in workflow
    assert "basic-pitch==0.4.0" in workflow
    assert "MUSIC_ADVANCED_ENABLED=true" in workflow
    assert '"stem_vocals", "stem_drums"' in runner
    assert "canonicalMediaUrl" in music
    assert "rights_confirmed" in music
    assert music.index("COUNT(*) AS count FROM music_jobs") < music.index("application/x-mycodexai-media-url")
    assert 'source_url: job.source_url || ""' in music
    assert 'AGENT_QUEUE.send({ kind: "music", jobId: id })' in music
    assert "consumeMusicQueue" in music
    assert '"vm.tiktok.com", "vt.tiktok.com"' in music
    assert 'media_type.startsWith("application/x-mycodexai-")' in files
    assert 'id="music-source-url"' in page
    assert 'id="music-rights-confirmed"' in page
    assert "กรุณายืนยันสิทธิ์การใช้เนื้อหาจาก YouTube/TikTok" in app
    assert "canonical_media_url" in runner
    assert "upload_artifacts" in runner
    assert "/api/internal/music/jobs/" in runner
    assert '"vm.tiktok.com", "vt.tiktok.com"' in media_url
    assert '"--no-playlist"' in runner
    assert "duration > 360" in runner
    assert "yt-dlp[default]==2026.6.9" in (ROOT / "requirements-music-social.txt").read_text(encoding="utf-8")
    assert "actions/setup-node@v6" in workflow


def test_cloud_image_caption_is_composed_outside_the_model() -> None:
    page = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    app = (WORKER / "public" / "app.js").read_text(encoding="utf-8")
    images = (WORKER / "src" / "images.ts").read_text(encoding="utf-8")
    assert 'id="image-caption"' in page
    assert "renderGeneratedImage" in app
    assert "exportCanvaSvg" in app
    assert "Do not draw letters" in images
    assert "payload.caption" not in images


def test_cloud_mfa_and_fresh_shell_assets_are_wired() -> None:
    auth = (WORKER / "src" / "auth.ts").read_text(encoding="utf-8")
    mfa = (WORKER / "src" / "mfa.ts").read_text(encoding="utf-8")
    login = (WORKER / "public" / "login.html").read_text(encoding="utf-8")
    login_script = (WORKER / "public" / "login.js").read_text(encoding="utf-8")
    app = (WORKER / "public" / "app.js").read_text(encoding="utf-8")
    service_worker = (WORKER / "public" / "sw.js").read_text(encoding="utf-8")
    assert 'id="mfa-code"' in login
    assert "mfa_required" in login_script
    assert '"/api/auth/mfa/setup"' in auth and '"/api/auth/mfa/enable"' in auth
    assert "AES-GCM" in mfa and "HMAC" in mfa
    assert 'id="mfa-secret"' in (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    assert "new Date(session.last_seen_at)" in app
    assert "skipWaiting" in service_worker and "fetch(event.request)" in service_worker


def test_cloud_oauth_is_link_first_pkce_and_mfa_aware() -> None:
    oauth = (WORKER / "src" / "oauth.ts").read_text(encoding="utf-8")
    worker = (WORKER / "src" / "index.ts").read_text(encoding="utf-8")
    login = (WORKER / "public" / "login.html").read_text(encoding="utf-8")
    page = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    assert "handleOAuth" in worker
    assert 'action: "login" | "link"' in oauth
    assert 'code_challenge_method", "S256"' in oauth
    assert "oauth_identities JOIN users" in oauth
    assert "oauth_mfa_challenges" in oauth
    assert "accessToken" in oauth and "token omitted" in oauth
    assert 'id="oauth-login"' in login
    assert 'id="view-account"' in page
