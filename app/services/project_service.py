"""Safe project imports and workspace-local project selection."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


MAX_PROJECT_IMPORT_FILES = 2_000
MAX_PROJECT_IMPORT_FILE_BYTES = 25_000_000
MAX_PROJECT_IMPORT_BYTES = 100_000_000
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
IGNORED_DIRECTORY_NAMES = {".git", ".mycodexai", ".venv", "venv", "node_modules", "__pycache__", "logs"}
IGNORED_FILE_NAMES = {".env", ".env.local", ".env.production", ".env.development", "id_rsa", "id_dsa", "credentials.json"}
IGNORED_FILE_SUFFIXES = {".key", ".pem", ".pyc"}


class ProjectError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ManagedProject:
    id: str
    path: Path
    is_workspace: bool = False
    file_count: int = 0


@dataclass(frozen=True)
class ProjectImportFile:
    path: PurePosixPath
    content: bytes


class ProjectService:
    @classmethod
    def list(cls, workspace_path: Path) -> list[ManagedProject]:
        root = workspace_path.resolve()
        projects = [ManagedProject(id="workspace", path=root, is_workspace=True)]
        project_root = root / "projects"
        if not project_root.is_dir():
            return projects

        for child in project_root.iterdir():
            if not child.is_dir() or not PROJECT_ID_PATTERN.fullmatch(child.name):
                continue
            projects.append(
                ManagedProject(
                    id=child.name,
                    path=child,
                    file_count=sum(1 for item in child.rglob("*") if item.is_file()),
                )
            )
        return sorted(projects, key=lambda item: (not item.is_workspace, item.id.casefold()))

    @classmethod
    def resolve(cls, workspace_path: Path, project_id: str | None) -> ManagedProject:
        root = workspace_path.resolve()
        if not project_id or project_id == "workspace":
            return ManagedProject(id="workspace", path=root, is_workspace=True)

        identifier = cls._validate_project_id(project_id)
        path = (root / "projects" / identifier).resolve()
        if root not in path.parents or not path.is_dir():
            raise ProjectError(404, "The requested project does not exist")
        return ManagedProject(id=identifier, path=path, file_count=sum(1 for item in path.rglob("*") if item.is_file()))

    @classmethod
    def import_files(
        cls,
        workspace_path: Path,
        project_id: str,
        incoming_files: list[ProjectImportFile],
    ) -> tuple[ManagedProject, int, int]:
        identifier = cls._validate_project_id(project_id)
        if not incoming_files:
            raise ProjectError(400, "Choose a folder or ZIP archive to import")
        if len(incoming_files) > MAX_PROJECT_IMPORT_FILES:
            raise ProjectError(400, f"Project imports may contain at most {MAX_PROJECT_IMPORT_FILES} files")

        normalized_files = cls._normalize_root(incoming_files, identifier)
        planned_files: list[ProjectImportFile] = []
        ignored_files = 0
        secret_files = 0
        total_bytes = 0
        seen_paths: set[str] = set()
        for incoming in normalized_files:
            if cls._is_ignored(incoming.path):
                ignored_files += 1
                if cls._is_secret(incoming.path):
                    secret_files += 1
                continue
            if len(incoming.content) > MAX_PROJECT_IMPORT_FILE_BYTES:
                raise ProjectError(400, f"Imported file is too large: {incoming.path.as_posix()}")
            normalized_path = incoming.path.as_posix().casefold()
            if normalized_path in seen_paths:
                raise ProjectError(400, f"Project import contains duplicate file: {incoming.path.as_posix()}")
            seen_paths.add(normalized_path)
            total_bytes += len(incoming.content)
            if total_bytes > MAX_PROJECT_IMPORT_BYTES:
                raise ProjectError(400, "Project import is too large after filtering")
            planned_files.append(incoming)

        if not planned_files:
            raise ProjectError(400, "No importable source files remain after safe exclusions")

        root = workspace_path.resolve()
        destination = (root / "projects" / identifier).resolve()
        if root not in destination.parents:
            raise ProjectError(400, "Project destination is invalid")
        if destination.exists():
            raise ProjectError(409, "A project with this name already exists")

        destination.mkdir(parents=True)
        try:
            for incoming in planned_files:
                target = (destination / Path(*incoming.path.parts)).resolve()
                if destination not in target.parents:
                    raise ProjectError(400, "Project import path is invalid")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(incoming.content)
        except OSError as error:
            shutil.rmtree(destination, ignore_errors=True)
            raise ProjectError(500, f"Could not store imported project: {error}") from error

        return (
            ManagedProject(id=identifier, path=destination, file_count=len(planned_files)),
            ignored_files,
            secret_files,
        )

    @classmethod
    def archive_files(cls, archive_content: bytes) -> list[ProjectImportFile]:
        try:
            with zipfile.ZipFile(BytesIO(archive_content)) as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                if len(entries) > MAX_PROJECT_IMPORT_FILES:
                    raise ProjectError(400, f"ZIP archives may contain at most {MAX_PROJECT_IMPORT_FILES} files")

                files = []
                total_bytes = 0
                for entry in entries:
                    if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ProjectError(400, "ZIP archives may not contain symbolic links")
                    path = cls._safe_relative_path(entry.filename)
                    if entry.file_size > MAX_PROJECT_IMPORT_FILE_BYTES:
                        raise ProjectError(400, f"Imported file is too large: {path.as_posix()}")
                    total_bytes += entry.file_size
                    if total_bytes > MAX_PROJECT_IMPORT_BYTES:
                        raise ProjectError(400, "Project ZIP is too large after extraction")
                    content = archive.read(entry)
                    files.append(ProjectImportFile(path=path, content=content))
                return files
        except zipfile.BadZipFile as error:
            raise ProjectError(400, "The project ZIP file is invalid") from error

    @classmethod
    def _normalize_root(cls, files: list[ProjectImportFile], project_id: str) -> list[ProjectImportFile]:
        first_parts = {file.path.parts[0] for file in files if file.path.parts}
        should_strip = (
            len(first_parts) == 1
            and all(len(file.path.parts) > 1 for file in files)
            and next(iter(first_parts)).casefold() == project_id.casefold()
        )
        if not should_strip:
            return files
        return [ProjectImportFile(path=PurePosixPath(*file.path.parts[1:]), content=file.content) for file in files]

    @staticmethod
    def _safe_relative_path(value: str) -> PurePosixPath:
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or any(part in {"", ".", ".."} or ":" in part for part in path.parts):
            raise ProjectError(400, "Project import path must be a safe relative path")
        return path

    @staticmethod
    def _is_secret(path: PurePosixPath) -> bool:
        name = path.name.casefold()
        return name in IGNORED_FILE_NAMES or name.endswith(".key") or name.endswith(".pem")

    @classmethod
    def _is_ignored(cls, path: PurePosixPath) -> bool:
        if any(part.casefold() in IGNORED_DIRECTORY_NAMES for part in path.parts[:-1]):
            return True
        name = path.name.casefold()
        return name in IGNORED_FILE_NAMES or any(name.endswith(suffix) for suffix in IGNORED_FILE_SUFFIXES)

    @staticmethod
    def _validate_project_id(value: str) -> str:
        if not isinstance(value, str) or not PROJECT_ID_PATTERN.fullmatch(value) or value in {"workspace", ".", ".."}:
            raise ProjectError(400, "Project name must contain 1-80 letters, numbers, dots, dashes, or underscores")
        return value
