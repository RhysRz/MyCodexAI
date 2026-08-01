"""User-scoped GitHub handoff API with explicit, one-time confirmations."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_workspace_user
from app.schemas.github import (
    GitHubExecuteRequest,
    GitHubExecuteResponse,
    GitHubPreparedActionResponse,
    GitHubPullRequestRequest,
    GitHubPushRequest,
    GitHubRemoteRequest,
    GitHubStatusResponse,
)
from app.services.auth_service import AuthenticatedUser
from app.services.github_service import GitHubIntegrationError, GitHubService
from app.workspace.file_manager import FileManager


router = APIRouter(prefix="/api/integrations/github", tags=["GitHub"])


def _workspace_id(request: Request) -> str:
    return request.headers.get("X-MyCodexAI-Worktree") or "main"


def _project_id(request: Request) -> str:
    return request.headers.get("X-MyCodexAI-Project") or "workspace"


@router.get("/status", response_model=GitHubStatusResponse)
def github_status(_user: AuthenticatedUser = Depends(require_workspace_user)):
    return GitHubStatusResponse(**GitHubService.status(FileManager.workspace()))


@router.post("/push/prepare", response_model=GitHubPreparedActionResponse)
def prepare_push(
    payload: GitHubPushRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return GitHubPreparedActionResponse(
            **GitHubService.prepare_push(user.id, _workspace_id(request), _project_id(request), FileManager.workspace(), payload.remote, payload.branch)
        )
    except GitHubIntegrationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/remote/prepare", response_model=GitHubPreparedActionResponse)
def prepare_remote(
    payload: GitHubRemoteRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return GitHubPreparedActionResponse(
            **GitHubService.prepare_remote(
                user.id, _workspace_id(request), _project_id(request), FileManager.workspace(), payload.remote, payload.url
            )
        )
    except GitHubIntegrationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/pull-requests/prepare", response_model=GitHubPreparedActionResponse)
def prepare_pull_request(
    payload: GitHubPullRequestRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return GitHubPreparedActionResponse(
            **GitHubService.prepare_pull_request(
                user.id, _workspace_id(request), _project_id(request), FileManager.workspace(), payload.base, payload.title, payload.body
            )
        )
    except GitHubIntegrationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ci/prepare", response_model=GitHubPreparedActionResponse)
def prepare_ci_workflow(request: Request, user: AuthenticatedUser = Depends(require_workspace_user)):
    return GitHubPreparedActionResponse(
        **GitHubService.prepare_ci_workflow(user.id, _workspace_id(request), _project_id(request), FileManager.workspace())
    )


@router.post("/execute", response_model=GitHubExecuteResponse)
def execute_github_action(
    payload: GitHubExecuteRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return GitHubExecuteResponse(
            **GitHubService.execute(payload.approval_token, user.id, _workspace_id(request), _project_id(request))
        )
    except GitHubIntegrationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
