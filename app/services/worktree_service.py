"""Managed, user-scoped Git worktrees for isolated agent tasks."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess

from app.services.auth_service import AuthenticatedUser, AuthService
from app.workspace import file_manager


WORKTREE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")


class WorktreeError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class ManagedWorktree:
    id: str
    path: Path
    is_main: bool = False


class WorktreeService:
    @classmethod
    def list(cls, user: AuthenticatedUser) -> list[ManagedWorktree]:
        main_workspace = AuthService.workspace_for_user(user)
        worktrees = [ManagedWorktree(id="main", path=main_workspace, is_main=True)]
        root = cls._worktree_root(user)
        if not root.is_dir():
            return worktrees

        for git_entry in root.rglob(".git"):
            if not git_entry.is_file():
                continue
            path = git_entry.parent
            try:
                worktree_id = path.relative_to(root).as_posix()
                cls._validate_id(worktree_id)
            except (ValueError, OSError):
                continue
            worktrees.append(ManagedWorktree(id=worktree_id, path=path))

        return sorted(worktrees, key=lambda item: (not item.is_main, item.id.casefold()))

    @classmethod
    def resolve(cls, user: AuthenticatedUser, worktree_id: str | None) -> ManagedWorktree:
        if not worktree_id or worktree_id == "main":
            return ManagedWorktree(id="main", path=AuthService.workspace_for_user(user), is_main=True)

        normalized_id = cls._validate_id(worktree_id)
        path = (cls._worktree_root(user) / Path(*PurePosixPath(normalized_id).parts)).resolve()
        root = cls._worktree_root(user)
        if root not in path.parents or not path.is_dir() or not (path / ".git").is_file():
            raise WorktreeError(404, "The requested worktree does not exist")
        return ManagedWorktree(id=normalized_id, path=path)

    @classmethod
    def create(cls, user: AuthenticatedUser, branch: str) -> ManagedWorktree:
        normalized_branch = cls._validate_id(branch)
        main_workspace = AuthService.workspace_for_user(user)
        if not (main_workspace / ".git").exists():
            raise WorktreeError(409, "Initialize and commit the main workspace before creating a worktree")

        root = cls._worktree_root(user)
        path = (root / Path(*PurePosixPath(normalized_branch).parts)).resolve()
        if root not in path.parents:
            raise WorktreeError(400, "The worktree path is invalid")
        if path.exists():
            raise WorktreeError(409, "A worktree already exists at that branch path")

        root.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                ["git", "worktree", "add", "-b", normalized_branch, str(path)],
                cwd=main_workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except FileNotFoundError as error:
            raise WorktreeError(503, "Git is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise WorktreeError(504, "Git worktree creation timed out") from error

        if completed.returncode != 0:
            output = ((completed.stdout or "") + (completed.stderr or "")).strip()
            raise WorktreeError(409, output or "Git could not create the worktree")

        return ManagedWorktree(id=normalized_branch, path=path)

    @staticmethod
    def _worktree_root(user: AuthenticatedUser) -> Path:
        return (file_manager.WORKSPACE / ".mycodexai" / "worktrees" / user.id).resolve()

    @staticmethod
    def _validate_id(value: str) -> str:
        if not isinstance(value, str) or not WORKTREE_ID_PATTERN.fullmatch(value):
            raise WorktreeError(400, "Worktree name must contain 1-100 letters, numbers, dots, dashes, underscores, or slashes")
        if value.startswith((".", "/")) or value.endswith((".", "/")) or ".." in value or "//" in value:
            raise WorktreeError(400, "Worktree name is invalid")
        return value
