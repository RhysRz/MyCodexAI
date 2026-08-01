"""Canva export keeps the AI background and Thai caption as separate editing assets."""

from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from PIL import Image

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser
from app.services.image_service import ImageService


def test_canva_package_contains_background_pdf_caption_and_layout():
    original_root = settings.agent_state_root
    owner = AuthenticatedUser("canva-owner", "owner", "admin")
    image_id = "a" * 32
    try:
        with TemporaryDirectory() as directory:
            settings.agent_state_root = str(Path(directory) / "runs")
            background_path = ImageService._owner_directory(owner.id) / f"{image_id}.png"
            background_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (640, 480), "#345678").save(background_path, format="PNG")

            package = ImageService.canva_package(owner, image_id, "เปิดรับสมัครงาน วันนี้")

            with ZipFile(BytesIO(package)) as archive:
                assert set(archive.namelist()) == {
                    "background.png",
                    "caption.txt",
                    "layout.json",
                    "poster-canva.pdf",
                    "README-th.txt",
                }
                assert archive.read("caption.txt").decode("utf-8").strip() == "เปิดรับสมัครงาน วันนี้"
                assert archive.read("poster-canva.pdf").startswith(b"%PDF")
                layout = json.loads(archive.read("layout.json"))
                assert layout["caption"] == "เปิดรับสมัครงาน วันนี้"
                assert layout["background"] == "background.png"
    finally:
        settings.agent_state_root = original_root
