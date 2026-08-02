"""Strict allowlist and canonicalization for public Music Lab media links."""

from __future__ import annotations

import re
import urllib.parse


def canonical_media_url(value: str) -> tuple[str, str, str]:
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").casefold().rstrip(".")
    source_id = ""
    if parsed.scheme == "https" and host == "youtu.be":
        source_id = parsed.path.strip("/").split("/")[0]
    elif parsed.scheme == "https" and host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            source_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        elif re.fullmatch(r"/(shorts|live)/[A-Za-z0-9_-]{6,20}/?", parsed.path):
            source_id = parsed.path.strip("/").split("/")[1]
    if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", source_id):
        return f"https://www.youtube.com/watch?v={source_id}", "youtube", source_id
    if parsed.scheme == "https" and host in {"vm.tiktok.com", "vt.tiktok.com"}:
        source_id = parsed.path.strip("/").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{5,40}", source_id):
            return f"https://{host}/{source_id}/", "tiktok", source_id
    if parsed.scheme == "https" and host in {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}:
        video = re.fullmatch(r"/@[A-Za-z0-9._-]{1,40}/video/(\d{8,30})/?", parsed.path)
        mobile = re.fullmatch(r"/v/(\d{8,30})\.html", parsed.path)
        source_id = (video or mobile).group(1) if (video or mobile) else ""
        if source_id:
            return f"https://{host}{parsed.path}", "tiktok", source_id
    raise ValueError("Only a single public YouTube or TikTok video URL is allowed")
