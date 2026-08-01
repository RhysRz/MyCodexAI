"""Static Music Lab shell includes the requested private-analysis controls."""

from pathlib import Path


def test_music_lab_exposes_upload_analysis_and_editable_exports():
    page = Path("templates/music.html").read_text(encoding="utf-8")
    script = Path("static/music.js").read_text(encoding="utf-8")
    assert 'id="music-file"' in page
    assert 'id="music-analyze"' in page
    assert 'id="music-midi"' in page
    assert 'id="music-tab"' in page
    assert 'id="music-instrument"' in page
    assert 'application/pdf' in page
    assert "/api/music/tracks" in script
    assert "/analyze" in script
    assert "playNotes" in script
    assert "AudioContext" in script
    assert "scheduleGuitar" in script
    assert "createBufferSource" in script
    assert "/sampled-audio" in script
    assert "new Audio" in script
