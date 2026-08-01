"""GitHub handoff and CI helpers that never accept or persist access tokens.

GitHub credentials stay with the user's existing Git Credential Manager or GitHub CLI
session.  This service only runs fixed, argument-list Git/GitHub commands after an
in-memory, user-scoped confirmation token has been issued.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4
import re
import shutil
import subprocess


MAX_OUTPUT_CHARS = 8_000
PENDING_ACTION_TTL = timedelta(minutes=10)
REMOTE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@=-]{0,127}$")
REPOSITORY_PATTERN = re.compile(r"^(?:git@github\.com:|https://github\.com/|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
URL_CREDENTIAL_PATTERN = re.compile(r"(https?://)[^/@\s]+@")
TOKEN_PATTERN = re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9_]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")


class GitHubIntegrationError(ValueError):
    """A safe, user-facing GitHub integration error."""


@dataclass(frozen=True)
class PendingGitHubAction:
    token: str
    owner_id: str
    workspace_id: str
    project_id: str
    workspace: Path
    kind: str
    command: tuple[str, ...] = ()
    filename: str = ""
    content: str = ""
    created_at: datetime = datetime.now(timezone.utc)


class GitHubService:
    _lock = RLock()
    _pending: dict[str, PendingGitHubAction] = {}

    @classmethod
    def status(cls, workspace: Path) -> dict[str, Any]:
        workspace = workspace.resolve()
        is_git_repository = cls._git_ok(workspace, ["rev-parse", "--is-inside-work-tree"])
        base = {
            "is_git_repository": is_git_repository,
            "branch": "",
            "head": "",
            "dirty": False,
            "remote_name": "origin",
            "remote_url": "",
            "repository": "",
            "is_github_remote": False,
            "github_cli_available": bool(shutil.which("gh")),
            "github_cli_authenticated": False,
            "ci_workflow_path": ".github/workflows/mycodexai-ci.yml",
            "ci_workflow_present": (workspace / ".github" / "workflows" / "mycodexai-ci.yml").is_file(),
            "ci_kind": cls._detect_ci_kind(workspace),
        }
        if not is_git_repository:
            return base

        base["branch"] = cls._git_text(workspace, ["branch", "--show-current"])
        base["head"] = cls._git_text(workspace, ["rev-parse", "--short", "HEAD"])
        base["dirty"] = bool(cls._git_text(workspace, ["status", "--porcelain"]))
        raw_remote = cls._git_text(workspace, ["remote", "get-url", "origin"])
        base["remote_url"] = cls._redact(raw_remote)
        repository = cls._github_repository(raw_remote)
        base["repository"] = repository
        base["is_github_remote"] = bool(repository)
        if base["github_cli_available"]:
            completed = cls._run(["gh", "auth", "status", "--hostname", "github.com"], workspace, timeout=10)
            base["github_cli_authenticated"] = completed.returncode == 0
        return base

    @classmethod
    def prepare_push(
        cls,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        workspace: Path,
        remote: str = "origin",
        branch: str = "",
    ) -> dict[str, Any]:
        cls._ensure_repository(workspace)
        remote = cls._remote(remote)
        branch = cls._branch(branch or cls._git_text(workspace, ["branch", "--show-current"]))
        cls._require_head(workspace)
        remote_url = cls._git_text(workspace, ["remote", "get-url", remote])
        if not remote_url:
            raise GitHubIntegrationError(f"Git remote '{remote}' is not configured")
        if not cls._github_repository(remote_url):
            raise GitHubIntegrationError("Only a github.com remote can be pushed from this integration")
        return cls._prepare(
            owner_id,
            workspace_id,
            project_id,
            workspace,
            "push",
            command=("git", "push", remote, branch),
            summary=f"Push branch '{branch}' to {remote}. This sends committed code to GitHub; uncommitted changes are not included.",
        )

    @classmethod
    def prepare_remote(
        cls,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        workspace: Path,
        remote: str,
        url: str,
    ) -> dict[str, Any]:
        cls._ensure_repository(workspace)
        remote = cls._remote(remote)
        url = str(url).strip()
        if not cls._github_repository(url):
            raise GitHubIntegrationError("Repository URL must be a plain github.com HTTPS or SSH URL without credentials")
        current = cls._git_text(workspace, ["remote", "get-url", remote])
        command = ("git", "remote", "set-url", remote, url) if current else ("git", "remote", "add", remote, url)
        verb = "Replace" if current else "Connect"
        return cls._prepare(
            owner_id,
            workspace_id,
            project_id,
            workspace,
            "configure_remote",
            command=command,
            summary=f"{verb} local remote '{remote}' with {cls._github_repository(url)}. No token is saved by MyCodexAI.",
        )

    @classmethod
    def prepare_pull_request(
        cls,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        workspace: Path,
        base: str,
        title: str,
        body: str = "",
    ) -> dict[str, Any]:
        cls._ensure_repository(workspace)
        if not shutil.which("gh"):
            raise GitHubIntegrationError("GitHub CLI (gh) is required to create a pull request")
        if cls._run(["gh", "auth", "status", "--hostname", "github.com"], workspace, timeout=10).returncode != 0:
            raise GitHubIntegrationError("Sign in first with: gh auth login")
        remote_url = cls._git_text(workspace, ["remote", "get-url", "origin"])
        if not cls._github_repository(remote_url):
            raise GitHubIntegrationError("Configure origin as a github.com remote before creating a pull request")
        base = cls._branch(base)
        title = " ".join(str(title).split())
        if not title or len(title) > 160:
            raise GitHubIntegrationError("Pull request title must contain 1-160 characters")
        if len(body) > 12_000:
            raise GitHubIntegrationError("Pull request body must contain at most 12000 characters")
        branch = cls._branch(cls._git_text(workspace, ["branch", "--show-current"]))
        if branch == base:
            raise GitHubIntegrationError("Create a feature branch before opening a pull request against the same branch")
        return cls._prepare(
            owner_id,
            workspace_id,
            project_id,
            workspace,
            "pull_request",
            command=("gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body", body),
            summary=f"Create a GitHub pull request from '{branch}' into '{base}'. The title and description are kept only until this confirmation expires.",
        )

    @classmethod
    def prepare_ci_workflow(
        cls,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        workspace: Path,
    ) -> dict[str, Any]:
        workspace = workspace.resolve()
        filename = ".github/workflows/mycodexai-ci.yml"
        path = workspace / filename
        kind = cls._detect_ci_kind(workspace)
        content = cls._ci_workflow(kind)
        return cls._prepare(
            owner_id,
            workspace_id,
            project_id,
            workspace,
            "ci_workflow",
            filename=filename,
            content=content,
            summary=(
                f"{'Replace' if path.exists() else 'Create'} {filename} for {kind} checks. "
                "It runs only after this repository is pushed to GitHub."
            ),
            preview=content,
        )

    @classmethod
    def execute(
        cls,
        token: str,
        owner_id: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        pending = cls._consume(token, owner_id, workspace_id, project_id)
        if pending.kind == "ci_workflow":
            path = (pending.workspace / pending.filename).resolve()
            if pending.workspace not in path.parents:
                raise GitHubIntegrationError("CI workflow path is invalid")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(pending.content, encoding="utf-8")
            temporary.replace(path)
            return {
                "kind": pending.kind,
                "status": "ok",
                "summary": f"Wrote {pending.filename}. Commit and push it to enable GitHub Actions.",
                "output": "",
            }

        completed = cls._run(list(pending.command), pending.workspace, timeout=120)
        output = cls._redact((completed.stdout or "") + (completed.stderr or ""))
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n... output truncated ..."
        if completed.returncode != 0:
            return {
                "kind": pending.kind,
                "status": "failed",
                "summary": "GitHub action did not complete. No credential was stored by MyCodexAI.",
                "output": output or "Command failed without output.",
            }
        summaries = {
            "configure_remote": "GitHub remote configured locally. Push is still a separate confirmation.",
            "push": "Branch pushed to GitHub.",
            "pull_request": "GitHub pull request created.",
        }
        summary = summaries.get(pending.kind, "GitHub action completed.")
        return {"kind": pending.kind, "status": "ok", "summary": summary, "output": output}

    @classmethod
    def _prepare(
        cls,
        owner_id: str,
        workspace_id: str,
        project_id: str,
        workspace: Path,
        kind: str,
        *,
        command: tuple[str, ...] = (),
        filename: str = "",
        content: str = "",
        summary: str,
        preview: str = "",
    ) -> dict[str, Any]:
        cls._discard_expired()
        token = uuid4().hex
        pending = PendingGitHubAction(
            token=token,
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            workspace=workspace.resolve(),
            kind=kind,
            command=command,
            filename=filename,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        with cls._lock:
            cls._pending[token] = pending
        return {
            "approval_token": token,
            "kind": kind,
            "summary": summary,
            "preview": preview,
            "expires_at": (pending.created_at + PENDING_ACTION_TTL).isoformat(),
        }

    @classmethod
    def _consume(cls, token: str, owner_id: str, workspace_id: str, project_id: str) -> PendingGitHubAction:
        cls._discard_expired()
        with cls._lock:
            pending = cls._pending.pop(token, None)
        if pending is None:
            raise GitHubIntegrationError("This confirmation expired or was already used. Preview the action again.")
        if (pending.owner_id, pending.workspace_id, pending.project_id) != (owner_id, workspace_id, project_id):
            raise GitHubIntegrationError("This confirmation belongs to another user, workspace, or project")
        return pending

    @classmethod
    def _discard_expired(cls) -> None:
        cutoff = datetime.now(timezone.utc) - PENDING_ACTION_TTL
        with cls._lock:
            for token, action in list(cls._pending.items()):
                if action.created_at < cutoff:
                    cls._pending.pop(token, None)

    @staticmethod
    def _run(command: list[str], workspace: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as error:
            raise GitHubIntegrationError(f"Required command is not installed: {command[0]}") from error
        except subprocess.TimeoutExpired as error:
            output = ((error.stdout or "") + (error.stderr or "")).strip()
            raise GitHubIntegrationError(f"GitHub action timed out. {GitHubService._redact(output)[:400]}") from error

    @classmethod
    def _git_ok(cls, workspace: Path, arguments: list[str]) -> bool:
        try:
            return cls._run(["git", *arguments], workspace, timeout=15).returncode == 0
        except GitHubIntegrationError:
            return False

    @classmethod
    def _git_text(cls, workspace: Path, arguments: list[str]) -> str:
        completed = cls._run(["git", *arguments], workspace, timeout=15)
        if completed.returncode != 0:
            return ""
        return (completed.stdout or "").strip()

    @classmethod
    def _ensure_repository(cls, workspace: Path) -> None:
        if not cls._git_ok(workspace, ["rev-parse", "--is-inside-work-tree"]):
            raise GitHubIntegrationError("Initialize Git and create an initial commit before using GitHub sync")

    @classmethod
    def _require_head(cls, workspace: Path) -> None:
        if not cls._git_ok(workspace, ["rev-parse", "--verify", "HEAD"]):
            raise GitHubIntegrationError("Create at least one commit before pushing to GitHub")

    @staticmethod
    def _remote(remote: str) -> str:
        if not isinstance(remote, str) or not REMOTE_PATTERN.fullmatch(remote):
            raise GitHubIntegrationError("Remote name is invalid")
        return remote

    @staticmethod
    def _branch(branch: str) -> str:
        if not isinstance(branch, str) or not BRANCH_PATTERN.fullmatch(branch):
            raise GitHubIntegrationError("Branch name is invalid")
        if branch.startswith((".", "/")) or branch.endswith((".", "/")) or ".." in branch or "//" in branch:
            raise GitHubIntegrationError("Branch name is invalid")
        return branch

    @staticmethod
    def _github_repository(remote_url: str) -> str:
        match = REPOSITORY_PATTERN.fullmatch(remote_url.strip())
        return match.group(1) if match else ""

    @staticmethod
    def _redact(value: str) -> str:
        value = URL_CREDENTIAL_PATTERN.sub(r"\1***@", value or "")
        return TOKEN_PATTERN.sub("[redacted]", value)

    @staticmethod
    def _detect_ci_kind(workspace: Path) -> str:
        kinds: list[str] = []
        if any((workspace / name).is_file() for name in ("pyproject.toml", "requirements.txt", "pytest.ini", "setup.cfg")) or (workspace / "tests").is_dir():
            kinds.append("python")
        if (workspace / "package.json").is_file():
            kinds.append("node")
        if (workspace / "go.mod").is_file():
            kinds.append("go")
        if (workspace / "Cargo.toml").is_file():
            kinds.append("rust")
        return "+".join(kinds) or "generic"

    @classmethod
    def _ci_workflow(cls, kind: str) -> str:
        jobs: list[str] = []
        if "python" in kind:
            jobs.append(
                """  python:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - run: python -m pip install --upgrade pip pytest\n      - run: |\n          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi\n          if [ -f pyproject.toml ]; then pip install -e .; fi\n      - run: pytest -q\n"""
            )
        if "node" in kind:
            jobs.append(
                """  node:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n        with:\n          node-version: '22'\n      - run: |\n          if [ -f package-lock.json ]; then npm ci; else npm install; fi\n      - run: npm run test --if-present\n      - run: npm run build --if-present\n"""
            )
        if "go" in kind:
            jobs.append(
                """  go:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-go@v5\n        with:\n          go-version: stable\n      - run: go test ./...\n"""
            )
        if "rust" in kind:
            jobs.append(
                """  rust:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: cargo test --all-targets\n"""
            )
        if not jobs:
            jobs.append(
                """  verify:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo \"Add this project's test command to .github/workflows/mycodexai-ci.yml\"\n"""
            )
        return (
            "name: MyCodexAI CI\n\n"
            "on:\n  push:\n    branches: [main, master]\n  pull_request:\n\n"
            "permissions:\n  contents: read\n\n"
            "jobs:\n"
            + "\n".join(jobs)
        )
