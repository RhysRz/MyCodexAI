"""Music source URLs stay on an explicit, single-video allowlist."""

import pytest

from cloud.runner.media_url import canonical_media_url


@pytest.mark.parametrize(
    ("source", "platform", "source_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=ignored", "youtube", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=12", "youtube", "dQw4w9WgXcQ"),
        ("https://www.tiktok.com/@musician/video/7412345678901234567", "tiktok", "7412345678901234567"),
        ("https://vt.tiktok.com/ZSexample1/", "tiktok", "ZSexample1"),
    ],
)
def test_canonical_media_url_accepts_only_single_video_links(source: str, platform: str, source_id: str):
    canonical, actual_platform, actual_id = canonical_media_url(source)
    assert canonical.startswith("https://")
    assert actual_platform == platform
    assert actual_id == source_id
    assert "list=" not in canonical


@pytest.mark.parametrize(
    "source",
    [
        "http://www.tiktok.com/@user/video/7412345678901234567",
        "https://evil.tiktok.com/@user/video/7412345678901234567",
        "https://youtube.com/playlist?list=PL123",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "file:///etc/passwd",
    ],
)
def test_canonical_media_url_rejects_non_allowlisted_sources(source: str):
    with pytest.raises(ValueError):
        canonical_media_url(source)
