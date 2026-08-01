from pydantic import BaseModel, Field


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=2, max_length=2_000)
    allow_text: bool = False


class CanvaExportRequest(BaseModel):
    image_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    caption: str = Field(default="", max_length=160)


class ImageGenerationResponse(BaseModel):
    image_id: str
    url: str
    model: str


class ImageStatusResponse(BaseModel):
    configured: bool
    provider: str
    model: str
    detail: str
    used_today: int
    daily_limit: int
    remaining_today: int | None
    quota_exempt: bool


class ImageListResponse(BaseModel):
    images: list[ImageGenerationResponse] = Field(default_factory=list)
