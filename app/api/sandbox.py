from fastapi import APIRouter, Depends

from app.api.dependencies import require_user
from app.schemas.sandbox import SandboxStatusResponse
from app.services.auth_service import AuthenticatedUser
from app.services.sandbox_service import SandboxService


router = APIRouter(prefix="/api/sandbox", tags=["Sandbox"])


@router.get("/status", response_model=SandboxStatusResponse)
def sandbox_status(_user: AuthenticatedUser = Depends(require_user)):
    return SandboxStatusResponse(**SandboxService.status())
