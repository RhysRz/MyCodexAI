from pathlib import Path
"""Ensure Image Studio is private per user while available to signed-in members."""


def test_image_studio_requires_sign_in_but_not_administrator_access():
    root = Path(__file__).resolve().parent.parent
    image_api = (root / "app" / "api" / "images.py").read_text(encoding="utf-8")
    image_service = (root / "app" / "services" / "image_service.py").read_text(encoding="utf-8")
    assert image_api.count("Depends(require_user)") >= 4
    assert "require_admin" not in image_api
    assert "hf_token" not in image_api
    assert '"detail": (' in image_service
    assert "เชื่อมต่อ Hugging Face พร้อมใช้งาน" in image_service
