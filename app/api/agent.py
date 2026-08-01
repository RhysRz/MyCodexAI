from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_user, require_workspace_user
from app.schemas.agent import AgentActivityResponse, AgentResumeRequest, AgentRunRequest, AgentRunResponse, AgentUsageResponse
from app.services.agent_service import AgentService
from app.services.auth_service import AuthenticatedUser
from app.services.operations_service import OperationsService


router = APIRouter(prefix="/api/agent", tags=["Agent"])


def _project_id(request: Request) -> str:
    return request.headers.get("X-MyCodexAI-Project") or "workspace"


@router.post("/runs", response_model=AgentRunResponse)
def start_agent_run(
    request: AgentRunRequest,
    http_request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return AgentService.start(
            task=request.task,
            max_steps=request.max_steps,
            mode=request.mode,
            attachments=request.attachments,
            owner_id=user.id,
            workspace_id=http_request.headers.get("X-MyCodexAI-Worktree") or "main",
            project_id=_project_id(http_request),
            background=request.background,
            review_scope=request.review_scope,
            review_target=request.review_target,
            quota_exempt=user.role == "admin",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(
    run_id: str,
    http_request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return AgentService.get(
            run_id,
            user.id,
            http_request.headers.get("X-MyCodexAI-Worktree") or "main",
            _project_id(http_request),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/runs/{run_id}/resume", response_model=AgentRunResponse)
def resume_agent_run(
    run_id: str,
    request: AgentResumeRequest,
    http_request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return AgentService.resume(
            run_id,
            request.approve,
            user.id,
            http_request.headers.get("X-MyCodexAI-Worktree") or "main",
            _project_id(http_request),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/runs/{run_id}/continue", response_model=AgentRunResponse)
def continue_agent_run(
    run_id: str,
    http_request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    """Resume a durable goal after a restart, budget stop, or failed delivery check."""
    try:
        return AgentService.continue_run(
            run_id,
            user.id,
            http_request.headers.get("X-MyCodexAI-Worktree") or "main",
            _project_id(http_request),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse)
def cancel_agent_run(
    run_id: str,
    http_request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return AgentService.cancel(
            run_id,
            user.id,
            http_request.headers.get("X-MyCodexAI-Worktree") or "main",
            _project_id(http_request),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Agent run not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/usage", response_model=AgentUsageResponse)
def agent_usage(user: AuthenticatedUser = Depends(require_user)):
    return AgentUsageResponse(**OperationsService.usage(user.id, quota_exempt=user.role == "admin"))


@router.get("/activity", response_model=AgentActivityResponse)
def agent_activity(limit: int = 30, user: AuthenticatedUser = Depends(require_user)):
    return AgentActivityResponse(events=OperationsService.activity(user.id, limit))
