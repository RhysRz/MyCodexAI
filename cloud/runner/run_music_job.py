"""Analyze one private MyCodexAI Music Lab file on a GitHub-hosted runner."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
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
SOURCE_URL = (os.environ.get("MYCODEXAI_MUSIC_SOURCE_URL") or os.environ.get("MYCODEXAI_MUSIC_YOUTUBE_URL") or "").strip()
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
from cloud.runner.media_url import canonical_media_url  # noqa: E402


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


def download_media_source() -> tuple[bytes, dict[str, Any]]:
    url, platform, source_id = canonical_media_url(SOURCE_URL)
    yt_dlp = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--no-warnings", "--socket-timeout", "20", "--retries", "2"]
    inspected = subprocess.run(
        [*yt_dlp, "--dump-single-json", "--skip-download", url],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if inspected.returncode != 0:
        raise RuntimeError(f"ไม่สามารถอ่านวิดีโอ {platform.title()} นี้ได้ อาจเป็นวิดีโอส่วนตัว จำกัดประเทศ หรือแพลตฟอร์มปฏิเสธ Runner")
    try:
        metadata = json.loads(inspected.stdout)
        duration = float(metadata.get("duration") or 0)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("แพลตฟอร์มไม่ส่งข้อมูลความยาววิดีโอที่อ่านได้") from error
    extractor = str(metadata.get("extractor_key") or metadata.get("extractor") or "").casefold()
    if platform not in extractor:
        raise RuntimeError("ตัวดึงข้อมูลตอบกลับมาจากแพลตฟอร์มที่ไม่ตรงกับลิงก์")
    if metadata.get("is_live") or metadata.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise RuntimeError("Music Lab ไม่รองรับวิดีโอ Live")
    if duration <= 1 or duration > 360:
        raise RuntimeError("วิดีโอต้องยาวระหว่าง 2 วินาทีถึง 6 นาที")

    download_root = ROOT / ".mycodexai-media-source"
    download_root.mkdir(parents=True, exist_ok=True)
    target = download_root / "media.%(ext)s"
    completed = subprocess.run([
        *yt_dlp, "--format", "bestaudio[filesize<=80M]/bestaudio", "--max-filesize", "80M",
        "--extract-audio", "--audio-format", "wav", "--audio-quality", "0",
        "--output", str(target), url,
    ], capture_output=True, text=True, timeout=600, check=False)
    candidates = sorted(download_root.glob("media*.wav"))
    if completed.returncode != 0 or not candidates:
        raise RuntimeError(f"ดาวน์โหลดเสียงจาก {platform.title()} ไม่สำเร็จ อาจถูกแพลตฟอร์มจำกัด กรุณาอัปโหลดไฟล์เสียงแทน")
    with candidates[0].open("rb") as handle:
        contents = handle.read(80 * 1024 * 1024 + 1)
    if len(contents) > 80 * 1024 * 1024:
        raise RuntimeError("เสียงจากวิดีโอมีขนาดเกิน 80 MB หลังแปลง")
    extracted_id = re.sub(r"[^A-Za-z0-9_-]", "", str(metadata.get("id") or ""))[:40] or source_id
    title = " ".join(str(metadata.get("title") or f"{platform.title()} {extracted_id}").split())[:240]
    return contents, {
        "type": platform, "video_id": extracted_id, "title": title,
        "url": url, "duration_seconds": round(duration, 2),
    }


def upload_artifacts(user: CloudMusicUser, music_id: str) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for kind in (
        "analysis", "midi", "chords", "tab", "musicxml", "stem_midi",
        "stem_vocals", "stem_drums", "stem_bass", "stem_guitar", "stem_piano", "stem_other",
    ):
        try:
            path, media_type, file_name = MusicService.artifact_for(user, music_id, kind)
        except Exception:
            continue
        size = path.stat().st_size
        if size <= 0 or size > 80 * 1024 * 1024:
            continue
        request = urllib.request.Request(
            f"{CLOUD_URL}/api/internal/music/jobs/{urllib.parse.quote(JOB_ID)}/artifacts/{kind}",
            data=path.read_bytes(), method="PUT",
            headers={
                "Authorization": f"Bearer {RUNNER_SECRET}",
                "Content-Type": media_type,
                "Content-Length": str(size),
                "X-MyCodexAI-File-Name": urllib.parse.quote(file_name),
                "User-Agent": "MyCodexAI-Music-Runner/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                response.read()
            output.append({"kind": kind, "file_name": file_name, "media_type": media_type, "size_bytes": size})
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            print(f"::warning::Could not upload {kind}: HTTP {error.code} {detail}")
    return output


def main() -> int:
    STARTED_MARKER.write_text("started\n", encoding="utf-8")
    callback("running")
    try:
        user = CloudMusicUser(USER_ID, "cloud-music-user", "user")
        media_metadata: dict[str, Any] | None = None
        if SOURCE_URL:
            source_contents, media_metadata = download_media_source()
            source_name = f"{media_metadata['type']}-{media_metadata['video_id']}.wav"
        else:
            source_contents, source_name = download_source(), FILE_NAME
        track = MusicService.create(user, source_name, source_contents)
        music_id = str(track["music_id"])
        analysis = MusicService.analyze(user, music_id)
        if media_metadata:
            analysis["source"] = media_metadata
            MusicService._write_json(MusicService._track_directory(user.id, music_id) / "analysis.json", analysis)
        uploaded = upload_artifacts(user, music_id)
        analysis["cloud_artifacts"] = uploaded
        callback("completed", analysis=analysis)
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
        media_root = (ROOT / ".mycodexai-media-source").resolve()
        if media_root.is_dir() and media_root.parent == ROOT:
            shutil.rmtree(media_root)


if __name__ == "__main__":
    raise SystemExit(main())
