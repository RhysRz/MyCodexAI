"""Safe user-uploaded source files for the configured coding workspace."""

from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Annotated
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.dependencies import require_workspace_user
from app.services.auth_service import AuthenticatedUser
from app.services.codebase_index_service import CodebaseIndexService
from app.workspace import file_manager


MAX_UPLOAD_FILES = 100
MAX_UPLOAD_FILE_BYTES = 25_000_000
MAX_UPLOAD_BATCH_BYTES = 100_000_000
MAX_ARCHIVE_FILES = 1_000

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])


class UploadedWorkspaceFile(BaseModel):
    path: str
    bytes: int
    replaced: bool


class WorkspaceUploadResponse(BaseModel):
    files: list[UploadedWorkspaceFile]
    total_bytes: int


def _relative_upload_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} or ":" in part for part in path.parts)
    ):
        raise HTTPException(status_code=400, detail="Upload path must be a safe relative path")

    return Path(*path.parts)


def _workspace_destination(value: str) -> Path:
    path = file_manager.FileManager._resolve_path(value or ".")
    if path is None:
        raise HTTPException(status_code=400, detail="Upload destination must be inside the workspace")
    return path


def _target_path(destination: Path, relative_path: Path) -> Path:
    path = (destination / relative_path).resolve()
    workspace = file_manager.FileManager.workspace()
    if path == workspace or workspace not in path.parents:
        raise HTTPException(status_code=400, detail="Upload path is outside the workspace")
    return path


def _archive_files(content: bytes, destination: Path, archive_name: str) -> list[tuple[Path, bytes]]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            if len(entries) > MAX_ARCHIVE_FILES:
                raise HTTPException(status_code=400, detail=f"ZIP archives may contain at most {MAX_ARCHIVE_FILES} files")

            extracted: list[tuple[Path, bytes]] = []
            total_bytes = 0
            for entry in entries:
                is_link = (entry.external_attr >> 16) & 0o170000 == 0o120000
                if is_link:
                    raise HTTPException(status_code=400, detail="ZIP archives may not contain symbolic links")

                relative_path = _relative_upload_path(entry.filename)
                file_content = archive.read(entry)
                total_bytes += len(file_content)
                if len(file_content) > MAX_UPLOAD_FILE_BYTES or total_bytes > MAX_UPLOAD_BATCH_BYTES:
                    raise HTTPException(status_code=400, detail="ZIP archive is too large after extraction")

                extracted.append(
                    (_target_path(destination, Path(archive_name) / relative_path), file_content)
                )
            return extracted
    except zipfile.BadZipFile as error:
        raise HTTPException(status_code=400, detail="The attached ZIP file is invalid") from error


def _validate_uploads(files: list[tuple[Path, bytes]], overwrite: bool) -> None:
    if not files:
        raise HTTPException(status_code=400, detail="Attach at least one file")
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"Upload at most {MAX_UPLOAD_FILES} files at a time")

    total_bytes = 0
    paths: set[str] = set()
    for path, content in files:
        normalized_path = str(path).casefold()
        if normalized_path in paths:
            raise HTTPException(status_code=400, detail=f"Upload contains the same destination twice: {path.name}")
        if path.exists() and (path.is_dir() or not overwrite):
            raise HTTPException(status_code=409, detail=f"File already exists: {path.name}. Enable replace to overwrite it.")

        paths.add(normalized_path)
        total_bytes += len(content)
        if total_bytes > MAX_UPLOAD_BATCH_BYTES:
            raise HTTPException(status_code=400, detail="Upload batch is too large")


@router.post("/uploads", response_model=WorkspaceUploadResponse)
async def upload_workspace_files(
    files: Annotated[list[UploadFile], File(...)],
    destination: Annotated[str, Form()] = "uploads",
    overwrite: Annotated[bool, Form()] = False,
    _user: AuthenticatedUser = Depends(require_workspace_user),
):
    """Copy user-provided files, folders, or ZIP contents into the workspace."""
    destination_path = _workspace_destination(destination)
    planned_files: list[tuple[Path, bytes]] = []

    try:
        for upload in files:
            filename = upload.filename or ""
            relative_path = _relative_upload_path(filename)
            content = await upload.read(MAX_UPLOAD_FILE_BYTES + 1)
            if len(content) > MAX_UPLOAD_FILE_BYTES:
                raise HTTPException(status_code=400, detail=f"File is too large: {filename}")

            if relative_path.suffix.casefold() == ".zip":
                planned_files.extend(_archive_files(content, destination_path, relative_path.stem))
            else:
                planned_files.append((_target_path(destination_path, relative_path), content))
    finally:
        for upload in files:
            await upload.close()

    _validate_uploads(planned_files, overwrite)
    uploaded_files = []
    for path, content in planned_files:
        replaced = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        uploaded_files.append(
            UploadedWorkspaceFile(
                path=path.relative_to(file_manager.FileManager.workspace()).as_posix(),
                bytes=len(content),
                replaced=replaced,
            )
        )

    CodebaseIndexService.invalidate()

    return WorkspaceUploadResponse(
        files=uploaded_files,
        total_bytes=sum(file.bytes for file in uploaded_files),
    )
