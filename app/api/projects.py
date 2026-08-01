from typing import Annotated

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import require_user, require_workspace_user
from app.schemas.project import (
    CodebaseIndexResponse,
    BrowserQaRequest,
    BrowserQaResponse,
    ProjectImportResponse,
    ProjectGuidanceRequest,
    ProjectGuidanceResponse,
    ProjectSkillListResponse,
    ProjectSkillRequest,
    ProjectSkillResponse,
    ProjectListResponse,
    ProjectMemoryNoteRequest,
    ProjectMemoryNoteResponse,
    ProjectMemoryResponse,
    ProjectResponse,
)
from app.services.auth_service import AuthenticatedUser
from app.services.browser_qa_service import BrowserQaError, BrowserQaService
from app.services.codebase_index_service import CodebaseIndexService
from app.services.project_guidance_service import ProjectGuidanceService
from app.services.project_memory_service import ProjectMemoryService
from app.services.project_skill_service import ProjectSkillService
from app.services.project_service import (
    MAX_PROJECT_IMPORT_BYTES,
    MAX_PROJECT_IMPORT_FILE_BYTES,
    MAX_PROJECT_IMPORT_FILES,
    ProjectError,
    ProjectImportFile,
    ProjectService,
)
from app.services.worktree_service import WorktreeError, WorktreeService
from app.workspace.file_manager import FileManager


router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _worktree(request: Request, user: AuthenticatedUser):
    try:
        return WorktreeService.resolve(user, request.headers.get("X-MyCodexAI-Worktree"))
    except WorktreeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


def _response(project) -> ProjectResponse:
    return ProjectResponse(id=project.id, is_workspace=project.is_workspace, file_count=project.file_count)


def _screenshot_url(capture_id: str, request: Request) -> str:
    worktree = request.headers.get("X-MyCodexAI-Worktree") or "main"
    project = request.headers.get("X-MyCodexAI-Project") or "workspace"
    return (
        f"/api/projects/browser-qa/{capture_id}/screenshot?"
        f"worktree={quote(worktree, safe='')}&project={quote(project, safe='')}"
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(request: Request, user: AuthenticatedUser = Depends(require_user)):
    worktree = _worktree(request, user)
    return ProjectListResponse(projects=[_response(project) for project in ProjectService.list(worktree.path)])


@router.get("/index", response_model=CodebaseIndexResponse)
def get_project_index(_user: AuthenticatedUser = Depends(require_workspace_user)):
    return CodebaseIndexService.overview()


@router.post("/index/rebuild", response_model=CodebaseIndexResponse)
def rebuild_project_index(_user: AuthenticatedUser = Depends(require_workspace_user)):
    return CodebaseIndexService.overview(rebuild=True)


@router.get("/memory", response_model=ProjectMemoryResponse)
def get_project_memory(_user: AuthenticatedUser = Depends(require_workspace_user)):
    return ProjectMemoryService.get()


@router.post("/memory/notes", response_model=ProjectMemoryNoteResponse)
def add_project_memory_note(
    payload: ProjectMemoryNoteRequest,
    _user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return ProjectMemoryService.add_note(payload.note)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/guidance", response_model=ProjectGuidanceResponse)
def get_project_guidance(
    directory: str = "",
    _user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return ProjectGuidanceService.get(directory)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.put("/guidance", response_model=ProjectGuidanceResponse)
def save_project_guidance(
    payload: ProjectGuidanceRequest,
    _user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return ProjectGuidanceService.save_custom(payload.content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/skills", response_model=ProjectSkillListResponse)
def list_project_skills(_user: AuthenticatedUser = Depends(require_workspace_user)):
    return ProjectSkillListResponse(skills=ProjectSkillService.list())


@router.get("/skills/{skill_id}", response_model=ProjectSkillResponse)
def get_project_skill(skill_id: str, _user: AuthenticatedUser = Depends(require_workspace_user)):
    try:
        return ProjectSkillResponse(**ProjectSkillService.get(skill_id))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/skills/{skill_id}", response_model=ProjectSkillResponse)
def save_project_skill(
    skill_id: str,
    payload: ProjectSkillRequest,
    _user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        return ProjectSkillResponse(
            **ProjectSkillService.save(skill_id, payload.name, payload.description, payload.instructions)
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/browser-qa/capture", response_model=BrowserQaResponse)
def capture_browser_qa(
    payload: BrowserQaRequest,
    http_request: Request,
    _user: AuthenticatedUser = Depends(require_workspace_user),
):
    try:
        result = BrowserQaService.capture(
            payload.filename,
            payload.viewport_width,
            payload.viewport_height,
            payload.wait_ms,
        )
        return BrowserQaResponse(**result, screenshot_url=_screenshot_url(result["capture_id"], http_request))
    except BrowserQaError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/browser-qa/{capture_id}/screenshot", include_in_schema=False)
def get_browser_qa_screenshot(
    capture_id: str,
    request: Request,
    user: AuthenticatedUser = Depends(require_user),
):
    try:
        worktree = WorktreeService.resolve(
            user,
            request.query_params.get("worktree") or request.headers.get("X-MyCodexAI-Worktree"),
        )
    except WorktreeError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    project_id = request.query_params.get("project") or request.headers.get("X-MyCodexAI-Project")
    try:
        project = ProjectService.resolve(worktree.path, project_id)
    except ProjectError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    token = FileManager.activate_workspace(project.path)
    try:
        screenshot = BrowserQaService.screenshot_path(capture_id)
        if not screenshot.is_file():
            raise HTTPException(status_code=404, detail="Browser QA screenshot not found")
        return FileResponse(screenshot, media_type="image/png", filename="browser-qa.png")
    finally:
        FileManager.reset_workspace(token)


@router.post("/import", response_model=ProjectImportResponse)
async def import_project(
    request: Request,
    project_name: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File(...)],
    user: AuthenticatedUser = Depends(require_user),
):
    worktree = _worktree(request, user)
    incoming_files: list[ProjectImportFile] = []
    try:
        if len(files) > MAX_PROJECT_IMPORT_FILES:
            raise ProjectError(400, f"Project imports may contain at most {MAX_PROJECT_IMPORT_FILES} files")
        if len(files) == 1 and (files[0].filename or "").casefold().endswith(".zip"):
            archive = await files[0].read(MAX_PROJECT_IMPORT_FILE_BYTES + 1)
            if len(archive) > MAX_PROJECT_IMPORT_FILE_BYTES:
                raise ProjectError(400, "The project ZIP file is too large")
            incoming_files = ProjectService.archive_files(archive)
        else:
            total_bytes = 0
            for upload in files:
                content = await upload.read(MAX_PROJECT_IMPORT_FILE_BYTES + 1)
                if len(content) > MAX_PROJECT_IMPORT_FILE_BYTES:
                    raise ProjectError(400, f"Imported file is too large: {upload.filename or ''}")
                total_bytes += len(content)
                if total_bytes > MAX_PROJECT_IMPORT_BYTES:
                    raise ProjectError(400, "Project import is too large")
                incoming_files.append(
                    ProjectImportFile(
                        path=ProjectService._safe_relative_path(upload.filename or ""),
                        content=content,
                    )
                )
        project, ignored, secrets = ProjectService.import_files(worktree.path, project_name, incoming_files)
        return ProjectImportResponse(
            id=project.id,
            is_workspace=project.is_workspace,
            file_count=project.file_count,
            ignored_file_count=ignored,
            secret_file_count=secrets,
        )
    except ProjectError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    finally:
        for upload in files:
            await upload.close()
