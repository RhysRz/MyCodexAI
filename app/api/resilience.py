"""Authenticated recovery, host-status, and encrypted workspace backup endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import require_user
from app.schemas.resilience import BackupListResponse, BackupRequest, BackupResponse, ResilienceStatusResponse, RestoreRequest
from app.services.agent_service import AgentService
from app.services.auth_service import AuthenticatedUser
from app.services.backup_service import BackupError, BackupService
from app.services.operations_service import OperationsService
from app.services.resource_service import ResourceService
from app.services.sandbox_service import SandboxService


router = APIRouter(prefix="/api/resilience", tags=["Resilience"])


@router.get("/status", response_model=ResilienceStatusResponse)
def resilience_status(user: AuthenticatedUser = Depends(require_user)):
    return ResilienceStatusResponse(
        status="ok",
        recovery={"active_runs": AgentService.active_run_count(user.id), "restart_behavior": "active background runs require review after restart"},
        resource_guard=ResourceService.snapshot(),
        sandbox=SandboxService.status(),
    )


@router.get("/backups", response_model=BackupListResponse)
def list_backups(user: AuthenticatedUser = Depends(require_user)):
    return BackupListResponse(backups=BackupService.list(user))


@router.post("/backups", response_model=BackupResponse)
def create_backup(request: BackupRequest, user: AuthenticatedUser = Depends(require_user)):
    try:
        result = BackupService.create(user, request.passphrase)
        OperationsService.record(user.id, "backup_created", outcome="ok", detail="encrypted workspace snapshot")
        return BackupResponse(**result)
    except BackupError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/backups/{backup_id}/restore")
def restore_backup(backup_id: str, request: RestoreRequest, user: AuthenticatedUser = Depends(require_user)):
    if AgentService.active_run_count(user.id):
        raise HTTPException(status_code=409, detail="Stop or finish active agent runs before restoring a workspace")
    try:
        result = BackupService.restore(user, backup_id, request.passphrase, request.confirmation)
        OperationsService.record(user.id, "backup_restored", outcome="ok", detail="workspace restore point preserved")
        return result
    except BackupError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
