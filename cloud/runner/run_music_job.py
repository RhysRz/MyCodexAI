"""Analyze one private MyCodexAI Music Lab file on a GitHub-hosted runner."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
JOB_ID = os.environ["MYCODEXAI_MUSIC_JOB_ID"]
FILE_ID = os.environ["MYCODEXAI_MUSIC_FILE_ID"]
FILE_NAME = Path(os.environ.get("MYCODEXAI_MUSIC_FILE_NAME", "music.pdf")).name
USER_ID = os.environ["MYCODEXAI_MUSIC_USER_ID"]
CLOUD_URL = os.environ["MYCODEXAI_CLOUD_URL"].rstrip("/")
RUNNER_SECRET = os.environ["MYCODEXAI_RUNNER_SECRET"]
STATE_ROOT = ROOT / ".mycodexai-music-job" / "runs"
STARTED_MARKER = ROOT / ".mycodexai-music-runner-started"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# app.core.settings is strict even though MusicService does not use Ollama.
os.environ.setdefault("APP_NAME", "MyCodexAI Cloud Music")
os.environ.setdefault("OLLAMA_URL", "http://127.0.0.1:11434")
os.environ.setdefault("OLLAMA_MODEL", "unused")
os.environ.setdefault("OLLAMA_API_KEY", "unused")
os.environ["AGENT_STATE_ROOT"] = str(STATE_ROOT)
os.environ.setdefault("MUSIC_OMR_EXECUTABLE", "")
os.environ.setdefault("MUSIC_TAB_OCR_EXECUTABLE", "")
os.environ.setdefault("MUSIC_ADVANCED_ENABLED", "false")
os.environ.setdefault("MUSIC_FFMPEG_EXECUTABLE", "ffmpeg")

from app.services.music_service import MusicService  # noqa: E402


@dataclass(frozen=True)
class CloudMusicUser:
    id: str
    username: str
    role: str


def request_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{CLOUD_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {RUNNER_SECRET}",
            "Content-Type": "application/json",
            "User-Agent": "MyCodexAI-Music-Runner/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:2_000]
        raise RuntimeError(f"Cloud API {error.code}: {detail}") from error


def callback(status: str, **payload: Any) -> None:
    request_json("/api/internal/music/callback", {"job_id": JOB_ID, "status": status, **payload})


def download_source() -> bytes:
    request = urllib.request.Request(
        f"{CLOUD_URL}/api/internal/files/{urllib.parse.quote(FILE_ID)}",
        headers={"Authorization": f"Bearer {RUNNER_SECRET}", "User-Agent": "MyCodexAI-Music-Runner/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        contents = response.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024:
        raise RuntimeError("Music source exceeds the 10 MB cloud limit")
    return contents


def encoded_artifacts(user: CloudMusicUser, music_id: str) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for kind in (
        "analysis", "midi", "chords", "tab", "musicxml", "stem_midi",
        "stem_vocals", "stem_drums", "stem_bass", "stem_guitar", "stem_piano", "stem_other",
    ):
        try:
            path, media_type, file_name = MusicService.artifact_for(user, music_id, kind)
        except Exception:
            continue
        contents = path.read_bytes()
        if len(contents) > 1_500_000:
            continue
        output.append({
            "kind": kind,
            "file_name": file_name,
            "media_type": media_type,
            "contents_base64": base64.b64encode(contents).decode("ascii"),
        })
    return output


def main() -> int:
    STARTED_MARKER.write_text("started\n", encoding="utf-8")
    callback("running")
    try:
        user = CloudMusicUser(USER_ID, "cloud-music-user", "user")
        track = MusicService.create(user, FILE_NAME, download_source())
        music_id = str(track["music_id"])
        analysis = MusicService.analyze(user, music_id)
        callback("completed", analysis=analysis, artifacts=encoded_artifacts(user, music_id))
        print(f"Music analysis completed: {JOB_ID}")
        return 0
    except Exception as error:
        try:
            callback("failed", error_detail=str(error)[:3_000])
        except Exception as callback_error:
            print(f"::warning::Cloud callback failed: {callback_error}")
        print(f"::error::{error}")
        return 1
    finally:
        job_root = STATE_ROOT.parent.resolve()
        expected = (ROOT / ".mycodexai-music-job").resolve()
        if job_root == expected and job_root.is_dir():
            shutil.rmtree(job_root)


if __name__ == "__main__":
    raise SystemExit(main())
