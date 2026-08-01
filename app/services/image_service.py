"""Private, owner-scoped image generation through Hugging Face Inference Providers."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import re
from threading import BoundedSemaphore
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from huggingface_hub import InferenceClient
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser
from app.services.operations_service import OperationsService


class ImageGenerationError(ValueError):
    """A safe error message suitable for the authenticated UI."""


class ImageService:
    _generation_slot = BoundedSemaphore(1)
    _image_id_pattern = re.compile(r"^[a-f0-9]{32}$")
    _no_text_instruction = (
        "Create a purely visual image. Treat the user's description only as scene direction, never as text to draw. "
        "Do not render any visible words, letters, numbers, captions, typography, logos, watermarks, signs, "
        "user-interface elements, written language, posters, advertisements, flyers, or banners."
    )
    _canva_font_name = "MyCodexThai"
    _canva_font_candidates = (
        Path("C:/Windows/Fonts/LeelawUI.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf"),
    )

    @classmethod
    def status(cls, user: AuthenticatedUser) -> dict[str, object]:
        configured = bool(settings.hf_token.strip())
        quota = OperationsService.image_usage(user.id, quota_exempt=user.role == "admin")
        return {
            "configured": configured,
            "provider": settings.hf_image_provider,
            "model": settings.hf_image_model,
            "detail": (
                "เชื่อมต่อ Hugging Face พร้อมใช้งาน" if configured
                else "ยังไม่ได้ตั้งค่า Hugging Face ในเครื่อง จึงไม่สามารถสร้างภาพได้"
            ),
            **quota,
        }

    @classmethod
    def generate(cls, user: AuthenticatedUser, prompt: str, *, allow_text: bool = False) -> dict[str, str]:
        clean_prompt = " ".join(prompt.split())
        if len(clean_prompt) < 2:
            raise ImageGenerationError("กรุณาระบุรายละเอียดของภาพที่ต้องการ")
        if not settings.hf_token.strip():
            raise ImageGenerationError("Image Studio ยังไม่ได้ตั้งค่า Hugging Face ในเครื่อง")

        try:
            with cls._generation_slot:
                client = InferenceClient(
                    provider=settings.hf_image_provider,
                    api_key=settings.hf_token,
                    timeout=settings.image_generation_timeout_seconds,
                )
                image = client.text_to_image(
                    cls._generation_prompt(clean_prompt, allow_text=allow_text),
                    model=settings.hf_image_model,
                )
                output = BytesIO()
                image.save(output, format="PNG")
                image_bytes = output.getvalue()
        except Exception as error:
            raise ImageGenerationError(
                "สร้างภาพไม่สำเร็จ: โปรดตรวจสอบโควตา Hugging Face สิทธิ์ของโทเค็น แล้วลองใหม่อีกครั้ง"
            ) from error

        if not image_bytes or len(image_bytes) > settings.image_max_output_bytes:
            raise ImageGenerationError("ไฟล์ภาพที่สร้างมีขนาดไม่อยู่ในเกณฑ์ปลอดภัย")

        image_id = uuid4().hex
        target = cls._owner_directory(user.id) / f"{image_id}.png"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(image_bytes)
            cls._trim_history(user.id)
        except OSError as error:
            raise ImageGenerationError("ไม่สามารถบันทึกภาพลงในเครื่องได้") from error
        return {"image_id": image_id, "url": f"/api/images/{image_id}", "model": settings.hf_image_model}

    @classmethod
    def _generation_prompt(cls, clean_prompt: str, *, allow_text: bool) -> str:
        if allow_text:
            return clean_prompt
        return f"{clean_prompt}\n\nImportant output rule: {cls._no_text_instruction}"

    @classmethod
    def canva_package(cls, user: AuthenticatedUser, image_id: str, caption: str) -> bytes:
        """Build a Canva-friendly archive without recording the caption in application logs."""
        background_path = cls.path_for(user, image_id)
        clean_caption = cls._clean_caption(caption)
        background = background_path.read_bytes()
        try:
            with Image.open(BytesIO(background)) as source:
                width, height = source.size
        except Exception as error:
            raise ImageGenerationError("ไม่สามารถเตรียมภาพพื้นหลังสำหรับ Canva ได้") from error

        pdf = cls._build_canva_pdf(background, width, height, clean_caption)
        manifest = {
            "format": "mycodex-canva-pack-v1",
            "background": "background.png",
            "poster_pdf": "poster-canva.pdf",
            "caption_file": "caption.txt",
            "caption": clean_caption,
            "canvas": {"width": width, "height": height},
            "text": {
                "position": "bottom-center",
                "font_family": "Leelawadee UI, Thonburi, Tahoma, sans-serif",
                "font_size_ratio": 0.055,
            },
        }
        readme = (
            "MYCODEX CANVA PACK\n\n"
            "1. อัปโหลด poster-canva.pdf เข้า Canva ผ่าน สร้างงานออกแบบ > นำเข้า PDF\n"
            "   Canva จะพยายามแปลงข้อความและเลย์เอาต์ให้แก้ไขได้\n"
            "2. ถ้าต้องการเริ่มจากพื้นหลังเปล่า ให้อัปโหลด background.png\n"
            "3. คัดลอกข้อความที่ถูกต้องจาก caption.txt แล้วเพิ่มเป็นกล่องข้อความใน Canva\n\n"
            "หมายเหตุ: ภาพที่สร้างด้วย AI เป็นภาพแบน จึงแก้ไขคน วัตถุ หรือฉากภายในภาพเป็นเลเยอร์แยกไม่ได้\n"
            "แต่ข้อความ พื้นหลัง การจัดวาง สี และองค์ประกอบใหม่สามารถแก้ไขต่อใน Canva ได้\n"
        )
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("background.png", background)
            archive.writestr("caption.txt", clean_caption + "\n")
            archive.writestr("layout.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.writestr("poster-canva.pdf", pdf)
            archive.writestr("README-th.txt", readme)
        return output.getvalue()

    @classmethod
    def _build_canva_pdf(cls, background: bytes, width: int, height: int, caption: str) -> bytes:
        output = BytesIO()
        document = canvas.Canvas(output, pagesize=(width, height), pageCompression=1)
        document.setTitle("MyCodex Canva Poster")
        document.drawImage(ImageReader(BytesIO(background)), 0, 0, width=width, height=height, mask="auto")
        if caption:
            font_name = cls._register_canva_font()
            font_size = max(22, min(72, round(width * 0.055)))
            lines = cls._wrap_pdf_text(document, caption, font_name, font_size, width * 0.86)
            line_height = round(font_size * 1.34)
            padding = round(font_size * 0.58)
            panel_height = (len(lines) * line_height) + (padding * 2)
            document.setFillColorRGB(8 / 255, 12 / 255, 20 / 255, alpha=0.76)
            document.rect(0, 0, width, panel_height, stroke=0, fill=1)
            document.setFillColorRGB(1, 1, 1)
            document.setFont(font_name, font_size)
            text_y = panel_height - padding - font_size
            for line in lines:
                document.drawCentredString(width / 2, text_y, line)
                text_y -= line_height
        document.showPage()
        document.save()
        return output.getvalue()

    @classmethod
    def _register_canva_font(cls) -> str:
        if cls._canva_font_name in pdfmetrics.getRegisteredFontNames():
            return cls._canva_font_name
        font_path = next((path for path in cls._canva_font_candidates if path.is_file()), None)
        if font_path is None:
            raise ImageGenerationError("ไม่พบฟอนต์ภาษาไทยสำหรับสร้างไฟล์ Canva")
        try:
            pdfmetrics.registerFont(TTFont(cls._canva_font_name, str(font_path)))
        except Exception as error:
            raise ImageGenerationError("ไม่สามารถเตรียมฟอนต์ภาษาไทยสำหรับ Canva ได้") from error
        return cls._canva_font_name

    @staticmethod
    def _clean_caption(caption: str) -> str:
        return "\n".join(" ".join(line.split()) for line in caption.replace("\r", "").split("\n")).strip()

    @staticmethod
    def _wrap_pdf_text(document, caption: str, font_name: str, font_size: int, maximum_width: float) -> list[str]:
        lines: list[str] = []
        for paragraph in caption.split("\n"):
            line = ""
            for character in paragraph:
                candidate = line + character
                if line and document.stringWidth(candidate, font_name, font_size) > maximum_width:
                    lines.append(line)
                    line = character
                else:
                    line = candidate
            if line:
                lines.append(line)
        return lines or [""]

    @classmethod
    def list_for(cls, user: AuthenticatedUser) -> list[dict[str, str]]:
        directory = cls._owner_directory(user.id)
        images: list[dict[str, str]] = []
        for path in sorted(directory.glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True):
            image_id = path.stem
            if cls._image_id_pattern.fullmatch(image_id):
                images.append({"image_id": image_id, "url": f"/api/images/{image_id}", "model": settings.hf_image_model})
        return images[: settings.image_retention_per_user]

    @classmethod
    def path_for(cls, user: AuthenticatedUser, image_id: str) -> Path:
        if not cls._image_id_pattern.fullmatch(image_id):
            raise ImageGenerationError("ไม่พบภาพที่ร้องขอ")
        path = cls._owner_directory(user.id) / f"{image_id}.png"
        if not path.is_file():
            raise ImageGenerationError("ไม่พบภาพที่ร้องขอ")
        return path

    @classmethod
    def _owner_directory(cls, user_id: str) -> Path:
        return Path(settings.agent_state_root).expanduser().resolve().parent / "images" / user_id

    @classmethod
    def _trim_history(cls, user_id: str) -> None:
        files = sorted(cls._owner_directory(user_id).glob("*.png"), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in files[settings.image_retention_per_user :]:
            try:
                stale.unlink()
            except OSError:
                continue
