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
        WORKER / "migrations" / "0001_initial.sql",
        WORKER / "migrations" / "0002_cloud_parity.sql",
        WORKER / "migrations" / "0003_cloud_music.sql",
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
        for name in ("GITHUB_TOKEN", "RUNNER_CALLBACK_SECRET", "CLOUD_BOOTSTRAP_TOKEN"):
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
    assert 'src="/app.js"' in index
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
    workflow = (ROOT / ".github" / "workflows" / "mycodexai-cloud-music.yml").read_text(encoding="utf-8")
    runner = (ROOT / "cloud" / "runner" / "run_music_job.py").read_text(encoding="utf-8")
    assert 'event_type: "mycodexai-music"' in music
    assert "WHERE id = ? AND user_id = ?" in music
    assert "RUNNER_CALLBACK_SECRET" in music
    assert "contents_base64" in music and "3_000_000" in music
    assert "group: mycodexai-cloud-heavy" in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "MusicService.analyze" in runner
    assert "download_source" in runner


def test_cloud_image_caption_is_composed_outside_the_model() -> None:
    page = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    app = (WORKER / "public" / "app.js").read_text(encoding="utf-8")
    images = (WORKER / "src" / "images.ts").read_text(encoding="utf-8")
    assert 'id="image-caption"' in page
    assert "renderGeneratedImage" in app
    assert "exportCanvaSvg" in app
    assert "Do not draw letters" in images
    assert "payload.caption" not in images
