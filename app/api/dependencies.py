"""Shared authentication and user-workspace dependencies for API routes."""

from collections.abc import AsyncGenerator

from fastapi import HTTPException, Request

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser, AuthService
from app.services.project_service import ProjectError, ProjectService
from app.services.worktree_service import WorktreeError, WorktreeService
from app.workspace.file_manager import FileManager


def require_user(request: Request) -> AuthenticatedUser:
    user = AuthService.user_from_session(request.cookies.get(settings.auth_cookie_name))
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in is required")
    return user


def require_admin(request: Request) -> AuthenticatedUser:
    """Allow model-management controls only to the site administrator."""
    user = require_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return user


async def require_workspace_user(request: Request) -> AsyncGenerator[AuthenticatedUser, None]:
    user = require_user(request)
    try:
        worktree = WorktreeService.resolve(user, request.headers.get("X-MyCodexAI-Worktree"))
    except WorktreeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    try:
        project = ProjectService.resolve(worktree.path, request.headers.get("X-MyCodexAI-Project"))
    except ProjectError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    token = FileManager.activate_workspace(project.path)
    try:
        yield user
    finally:
        FileManager.reset_workspace(token)
