"""Private Image Studio behavior without contacting Hugging Face."""

from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser
from app.services import image_service
from app.services.image_service import ImageGenerationError, ImageService


class FakeImage:
    def save(self, output, format: str) -> None:
        assert format == "PNG"
        output.write(b"fake-private-png")


class FakeClient:
    def __init__(self, *, provider: str, api_key: str, timeout: float) -> None:
        assert provider == "fal-ai"
        assert api_key == "hf_unit_test"
        assert timeout >= 20

    def text_to_image(self, prompt: str, *, model: str) -> FakeImage:
        assert prompt.startswith("a private test image\n\nImportant output rule: ")
        assert "Do not render any visible words" in prompt
        assert model
        return FakeImage()


def test_image_generation_is_owner_scoped_and_does_not_expose_token():
    original_client = image_service.InferenceClient
    original_token = settings.hf_token
    original_root = settings.agent_state_root
    original_retention = settings.image_retention_per_user
    owner = AuthenticatedUser("image-owner", "owner", "admin")
    other = AuthenticatedUser("image-other", "other", "admin")
    try:
        with TemporaryDirectory() as directory:
            image_service.InferenceClient = FakeClient
            settings.hf_token = "hf_unit_test"
            settings.agent_state_root = str(Path(directory) / "runs")
            settings.image_retention_per_user = 2

            result = ImageService.generate(owner, "  a private   test image ")
            assert result["url"].startswith("/api/images/")
            assert "hf_unit_test" not in str(ImageService.status(owner))
            assert ImageService.path_for(owner, result["image_id"]).read_bytes() == b"fake-private-png"
            assert ImageService.list_for(owner)[0]["image_id"] == result["image_id"]
            try:
                ImageService.path_for(other, result["image_id"])
            except ImageGenerationError:
                pass
            else:
                raise AssertionError("another user must not retrieve the owner's image")
            assert ImageService._generation_prompt("scene", allow_text=True) == "scene"
    finally:
        image_service.InferenceClient = original_client
        settings.hf_token = original_token
        settings.agent_state_root = original_root
        settings.image_retention_per_user = original_retention
