from pathlib import Path


def test_image_studio_is_available_to_signed_in_users_and_has_private_ui_hooks():
    page = Path("templates/index.html").read_text(encoding="utf-8")
    script = Path("static/script.js").read_text(encoding="utf-8")
    remote_page = Path("templates/remote.html").read_text(encoding="utf-8")
    remote_script = Path("static/remote.js").read_text(encoding="utf-8")
    assert 'id="image-studio"' in page
    assert 'id="generate-image"' in page
    assert 'id="image-overlay-text"' in page
    assert 'id="image-export-canva"' in page
    assert "composeThaiOverlay" in script
    assert "exportImageForCanva" in script
    assert "syncCanvaExport" in script
    assert "elements.imageStudio.hidden = false" in script
    assert "request('/api/images/status')" in script
    assert "request('/api/images'" in script
    assert "timeoutMs: 180_000" in script
    assert 'id="remote-images"' in remote_page
    assert 'id="remote-generate-image"' in remote_page
    assert 'id="remote-image-overlay-text"' in remote_page
    assert 'id="remote-image-export-canva"' in remote_page
    assert "composeRemoteThaiOverlay" in remote_script
    assert "exportRemoteImageForCanva" in remote_script
    assert "syncRemoteCanvaExport" in remote_script
    assert "loadRemoteImages()" in remote_script
    assert "timeoutMs: 180_000" in remote_script
