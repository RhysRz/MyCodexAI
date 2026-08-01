from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import require_user
from app.schemas.worktree import WorktreeCreateRequest, WorktreeListResponse, WorktreeResponse
from app.services.auth_service import AuthenticatedUser
from app.services.worktree_service import ManagedWorktree, WorktreeError, WorktreeService


router = APIRouter(prefix="/api/worktrees", tags=["Worktrees"])


def _response(worktree: ManagedWorktree) -> WorktreeResponse:
    return WorktreeResponse(id=worktree.id, is_main=worktree.is_main)


@router.get("", response_model=WorktreeListResponse)
def list_worktrees(user: AuthenticatedUser = Depends(require_user)):
    return WorktreeListResponse(worktrees=[_response(worktree) for worktree in WorktreeService.list(user)])


@router.post("", response_model=WorktreeResponse)
def create_worktree(
    request: WorktreeCreateRequest,
    user: AuthenticatedUser = Depends(require_user),
):
    try:
        return _response(WorktreeService.create(user, request.branch))
    except WorktreeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
