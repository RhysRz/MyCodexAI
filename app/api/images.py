"""Admin-only private image generation and retrieval endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from io import BytesIO

from app.api.dependencies import require_user
from app.schemas.image import CanvaExportRequest, ImageGenerationRequest, ImageGenerationResponse, ImageListResponse, ImageStatusResponse
from app.services.auth_service import AuthenticatedUser
from app.services.image_service import ImageGenerationError, ImageService
from app.services.operations_service import OperationsService, UsageLimitError


router = APIRouter(prefix="/api/images", tags=["Images"])


@router.get("/status", response_model=ImageStatusResponse)
def image_status(user: AuthenticatedUser = Depends(require_user)):
    return ImageStatusResponse(**ImageService.status(user))


@router.get("", response_model=ImageListResponse)
def list_images(user: AuthenticatedUser = Depends(require_user)):
    return ImageListResponse(images=[ImageGenerationResponse(**item) for item in ImageService.list_for(user)])


@router.post("", response_model=ImageGenerationResponse)
def generate_image(request: ImageGenerationRequest, user: AuthenticatedUser = Depends(require_user)):
    try:
        OperationsService.reserve_image(user.id, quota_exempt=user.role == "admin")
        result = ImageService.generate(user, request.prompt, allow_text=request.allow_text)
        OperationsService.record(user.id, "image_generated", mode="image", outcome="ok", detail="Hugging Face image generated")
        return ImageGenerationResponse(**result)
    except UsageLimitError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ImageGenerationError as error:
        OperationsService.record(user.id, "image_generated", mode="image", outcome="failed", detail="Hugging Face image request failed")
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/canva-export")
def export_for_canva(request: CanvaExportRequest, user: AuthenticatedUser = Depends(require_user)):
    try:
        payload = ImageService.canva_package(user, request.image_id, request.caption)
        OperationsService.record(user.id, "image_canva_exported", mode="image", outcome="ok", detail="Canva package exported")
    except ImageGenerationError as error:
        OperationsService.record(user.id, "image_canva_exported", mode="image", outcome="failed", detail="Canva package export failed")
        raise HTTPException(status_code=404, detail=str(error)) from error
    filename = f"mycodex-canva-{request.image_id[:8]}.zip"
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{image_id}", include_in_schema=False)
def get_image(image_id: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        path = ImageService.path_for(user, image_id)
    except ImageGenerationError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type="image/png", filename=f"mycodex-{image_id}.png", content_disposition_type="inline")
