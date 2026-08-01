from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_workspace_user
from app.schemas.terminal import TerminalJobRequest, TerminalJobResponse, TerminalResumeRequest
from app.services.auth_service import AuthenticatedUser
from app.services.terminal_service import TerminalService
from app.workspace.file_manager import FileManager


router = APIRouter(prefix="/api/terminal", tags=["Terminal"])


def _workspace_id(request: Request) -> str:
    return request.headers.get("X-MyCodexAI-Worktree") or "main"


def _project_id(request: Request) -> str:
    return request.headers.get("X-MyCodexAI-Project") or "workspace"


@router.post("/jobs", response_model=TerminalJobResponse)
def create_terminal_job(
    payload: TerminalJobRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return TerminalService.create(
            user.id,
            _workspace_id(request),
            _project_id(request),
            FileManager.workspace(),
            payload.command,
            payload.working_directory,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/jobs/{job_id}", response_model=TerminalJobResponse)
def get_terminal_job(
    job_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return TerminalService.get(job_id, user.id, _workspace_id(request), _project_id(request))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Terminal job not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/jobs/{job_id}/resume", response_model=TerminalJobResponse)
def resume_terminal_job(
    job_id: str,
    payload: TerminalResumeRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return TerminalService.resume(job_id, payload.approve, user.id, _workspace_id(request), _project_id(request))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Terminal job not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/jobs/{job_id}/cancel", response_model=TerminalJobResponse)
def cancel_terminal_job(
    job_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return TerminalService.cancel(job_id, user.id, _workspace_id(request), _project_id(request))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Terminal job not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
