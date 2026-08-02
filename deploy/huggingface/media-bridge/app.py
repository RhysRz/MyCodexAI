"""Narrow, authenticated YouTube audio egress for MyCodexAI Music Lab."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask


app = FastAPI(title="MyCodexAI Media Bridge", docs_url=None, redoc_url=None)
EXTRACTION_LOCK = asyncio.Lock()
API_KEY = os.environ.get("MEDIA_BRIDGE_KEY", "").strip()
POT_PROVIDER_HOME = os.environ.get("POT_PROVIDER_HOME", "").strip()
VIDEO_PATTERN = re.compile(r"^https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{6,20})$")


class ExtractRequest(BaseModel):
    url: str = Field(min_length=30, max_length=100)


def authorize(value: str) -> None:
    supplied = value[7:] if value.startswith("Bearer ") else ""
    if len(API_KEY) < 32 or not hmac.compare_digest(supplied, API_KEY):
        raise HTTPException(status_code=401, detail="invalid bridge credential")


def strategies() -> list[tuple[str, list[str]]]:
    values = [
        ("default", []),
        ("web-embedded", ["--extractor-args", "youtube:player_client=web_embedded"]),
        ("web-safari-hls", ["--extractor-args", "youtube:player_client=web_safari"]),
        ("tv-simply", ["--extractor-args", "youtube:player_client=tv_simply"]),
        ("android-vr", ["--extractor-args", "youtube:player_client=android_vr"]),
    ]
    if POT_PROVIDER_HOME:
        values.append(("mweb-pot", [
            "--extractor-args", "youtube:player_client=mweb",
            "--extractor-args", f"youtubepot-bgutilscript:server_home={POT_PROVIDER_HOME}",
        ]))
    return values


def extract(url: str) -> tuple[Path, dict[str, object], Path]:
    match = VIDEO_PATTERN.fullmatch(url)
    if not match:
        raise HTTPException(status_code=400, detail="only one canonical YouTube video is accepted")
    root = Path(tempfile.mkdtemp(prefix="mycodexai-media-"))
    target = root / "source.%(ext)s"
    base = [
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist", "--force-ipv4",
        "--js-runtimes", "node", "--socket-timeout", "20", "--retries", "2",
    ]
    try:
        for name, arguments in strategies():
            inspected = subprocess.run(
                [*base, *arguments, "--dump-single-json", "--skip-download", url],
                capture_output=True, text=True, timeout=120, check=False,
            )
            if inspected.returncode != 0:
                continue
            try:
                metadata = json.loads(inspected.stdout)
                duration = float(metadata.get("duration") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if duration < 2 or duration > 360 or metadata.get("is_live"):
                raise HTTPException(status_code=400, detail="video must be 2 seconds to 6 minutes and not live")
            completed = subprocess.run([
                *base, *arguments, "--format", "bestaudio[filesize<=80M]/bestaudio", "--max-filesize", "80M",
                "--extract-audio", "--audio-format", "wav", "--audio-quality", "0", "--output", str(target), url,
            ], capture_output=True, text=True, timeout=600, check=False)
            candidates = sorted(root.glob("source*.wav"))
            if completed.returncode != 0 or not candidates:
                continue
            audio = candidates[0]
            if audio.stat().st_size < 1 or audio.stat().st_size > 80 * 1024 * 1024:
                continue
            title = " ".join(str(metadata.get("title") or match.group(1)).split())[:240]
            return audio, {"title": title, "duration": duration, "strategy": name}, root
        raise HTTPException(status_code=502, detail="YouTube refused this cloud egress")
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


@app.get("/")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "mycodexai-media-bridge", "configured": len(API_KEY) >= 32}


@app.post("/extract")
async def extract_audio(payload: ExtractRequest, authorization: str = Header(default="")) -> FileResponse:
    authorize(authorization)
    async with EXTRACTION_LOCK:
        audio, metadata, root = await asyncio.to_thread(extract, payload.url)
    headers = {
        "X-Media-Title": quote(str(metadata["title"]), safe=""),
        "X-Media-Duration": str(metadata["duration"]),
        "X-Media-Strategy": str(metadata["strategy"]),
        "Cache-Control": "no-store",
    }
    return FileResponse(
        audio, media_type="audio/wav", filename="mycodexai-source.wav", headers=headers,
        background=BackgroundTask(shutil.rmtree, root, ignore_errors=True),
    )
