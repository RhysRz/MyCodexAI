"""Local, project-scoped browser screenshot checks for trusted HTML previews."""

from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
import os
import shutil
import subprocess
from typing import Any
from uuid import UUID, uuid4

from app.core.settings import settings
from app.services.sandbox_service import SandboxError, SandboxService
from app.workspace.file_manager import FileManager


MAX_HTML_BYTES = 5_000_000
MAX_SCREENSHOT_BYTES = 20_000_000
MAX_VIEWPORT_WIDTH = 3_840
MAX_VIEWPORT_HEIGHT = 2_160
DEFAULT_VIEWPORT_WIDTH = 1_440
DEFAULT_VIEWPORT_HEIGHT = 900
DEFAULT_WAIT_MS = 800


class BrowserQaError(ValueError):
    """A validation or rendering failure safe to return to an API caller."""


@dataclass(frozen=True)
class BrowserQaTarget:
    filename: str
    path: Path
    viewport_width: int
    viewport_height: int
    wait_ms: int


class _TitleReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.parts.append(data)


class BrowserQaService:
    """Render a selected local HTML file with Edge or isolated Chromium.

    In Docker mode the browser runs in the Docker sandbox. Host mode remains a
    deliberately explicit local-only workflow rather than a fake sandbox.
    """

    @classmethod
    def preview(
        cls,
        filename: str,
        viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
        viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
        wait_ms: int = DEFAULT_WAIT_MS,
    ) -> dict[str, Any]:
        target = cls._target(filename, viewport_width, viewport_height, wait_ms)
        if not settings.browser_qa_enabled:
            return {"status": "blocked", "reason": "Browser QA is disabled by configuration."}
        if SandboxService.is_docker_mode():
            try:
                SandboxService.prepare(
                    [settings.sandbox_browser_executable, "--version"],
                    FileManager.workspace(),
                    ".",
                    "browserpreview",
                )
            except SandboxError as error:
                return {"status": "blocked", "reason": str(error)}
        elif cls._find_browser() is None:
            return {
                "status": "blocked",
                "reason": "Microsoft Edge or another configured Chromium browser is not available for Browser QA.",
            }
        return {
            "status": "preview",
            "filename": target.filename,
            "viewport": {"width": target.viewport_width, "height": target.viewport_height},
            "diff": (
                "This will load and execute the selected local HTML page in a headless browser, "
                "then save a project-scoped screenshot for review. Only approve this for code you trust.\n"
                f"File: {target.filename}\nViewport: {target.viewport_width}x{target.viewport_height}\n"
                f"Virtual render wait: {target.wait_ms} ms"
            ),
            "truncated": False,
        }

    @classmethod
    def capture(
        cls,
        filename: str,
        viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
        viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
        wait_ms: int = DEFAULT_WAIT_MS,
    ) -> dict[str, Any]:
        if not settings.browser_qa_enabled:
            raise BrowserQaError("Browser QA is disabled by configuration.")
        target = cls._target(filename, viewport_width, viewport_height, wait_ms)
        executable = cls._find_browser()
        if not SandboxService.is_docker_mode() and executable is None:
            raise BrowserQaError("Microsoft Edge or another configured Chromium browser is not available for Browser QA.")

        capture_id = str(uuid4())
        artifact_root = FileManager.workspace() / ".mycodexai" / "browser-qa"
        screenshot_path = artifact_root / f"{capture_id}.png"
        profile_path = artifact_root / "profiles" / capture_id
        artifact_root.mkdir(parents=True, exist_ok=True)

        host_command = [
            executable or "",
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--force-color-profile=srgb",
            f"--user-data-dir={profile_path}",
            f"--virtual-time-budget={target.wait_ms}",
            f"--window-size={target.viewport_width},{target.viewport_height}",
            f"--screenshot={screenshot_path}",
            target.path.as_uri(),
        ]
        environment = "host"
        command = host_command
        if SandboxService.is_docker_mode():
            relative_target = target.path.relative_to(FileManager.workspace()).as_posix()
            screenshot_in_container = f"/workspace/.mycodexai/browser-qa/{capture_id}.png"
            profile_in_container = f"/workspace/.mycodexai/browser-qa/profiles/{capture_id}"
            browser_command = [
                settings.sandbox_browser_executable,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--disable-dev-shm-usage",
                "--force-color-profile=srgb",
                f"--user-data-dir={profile_in_container}",
                f"--virtual-time-budget={target.wait_ms}",
                f"--window-size={target.viewport_width},{target.viewport_height}",
                f"--screenshot={screenshot_in_container}",
                f"file:///workspace/{relative_target}",
            ]
            try:
                launch = SandboxService.prepare(browser_command, FileManager.workspace(), ".", capture_id.replace("-", ""))
            except SandboxError as error:
                raise BrowserQaError(str(error)) from error
            command = launch.command
            environment = launch.environment
        try:
            completed = cls._run_command(
                command,
                cwd=FileManager.workspace(),
                timeout=settings.browser_qa_timeout_seconds,
            )
        except FileNotFoundError as error:
            raise BrowserQaError("The configured Browser QA executable could not be started.") from error
        except subprocess.TimeoutExpired as error:
            raise BrowserQaError("Browser QA exceeded its configured time limit.") from error
        finally:
            shutil.rmtree(profile_path, ignore_errors=True)

        if completed.returncode != 0:
            message = ((completed.stderr or "") + (completed.stdout or "")).strip()
            raise BrowserQaError(f"Browser QA failed: {message[:800] or 'the browser returned a non-zero exit code'}")
        if not screenshot_path.is_file():
            raise BrowserQaError("Browser QA finished without producing a screenshot.")
        if screenshot_path.stat().st_size > MAX_SCREENSHOT_BYTES:
            screenshot_path.unlink(missing_ok=True)
            raise BrowserQaError("Browser QA produced a screenshot that exceeds the 20 MB limit.")

        return {
            "capture_id": capture_id,
            "filename": target.filename,
            "viewport_width": target.viewport_width,
            "viewport_height": target.viewport_height,
            "wait_ms": target.wait_ms,
            "document_title": cls._document_title(target.path),
            "captured_at": datetime.now(UTC).isoformat(),
            "screenshot_bytes": screenshot_path.stat().st_size,
            "execution_environment": environment,
        }

    @classmethod
    def screenshot_path(cls, capture_id: str) -> Path:
        try:
            normalized_id = str(UUID(capture_id))
        except (TypeError, ValueError) as error:
            raise BrowserQaError("Browser QA capture id is invalid.") from error
        return FileManager.workspace() / ".mycodexai" / "browser-qa" / f"{normalized_id}.png"

    @classmethod
    def _target(
        cls,
        filename: str,
        viewport_width: int,
        viewport_height: int,
        wait_ms: int,
    ) -> BrowserQaTarget:
        if not isinstance(filename, str) or not filename.strip():
            raise BrowserQaError("filename must be a non-empty workspace-relative HTML path.")
        path = FileManager._resolve_path(filename.strip())
        if path is None or not path.is_file():
            raise BrowserQaError("The selected HTML file is not available inside the active project.")
        if path.suffix.casefold() not in {".html", ".htm"}:
            raise BrowserQaError("Browser QA only renders .html and .htm files.")
        if path.stat().st_size > MAX_HTML_BYTES:
            raise BrowserQaError("The selected HTML file exceeds the 5 MB Browser QA limit.")
        if not isinstance(viewport_width, int) or not 320 <= viewport_width <= MAX_VIEWPORT_WIDTH:
            raise BrowserQaError(f"viewport_width must be between 320 and {MAX_VIEWPORT_WIDTH}.")
        if not isinstance(viewport_height, int) or not 240 <= viewport_height <= MAX_VIEWPORT_HEIGHT:
            raise BrowserQaError(f"viewport_height must be between 240 and {MAX_VIEWPORT_HEIGHT}.")
        if not isinstance(wait_ms, int) or not 0 <= wait_ms <= 10_000:
            raise BrowserQaError("wait_ms must be between 0 and 10000.")
        return BrowserQaTarget(
            filename=path.relative_to(FileManager.workspace()).as_posix(),
            path=path,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            wait_ms=wait_ms,
        )

    @staticmethod
    def _run_command(command: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    @staticmethod
    def _find_browser() -> str | None:
        configured = settings.browser_qa_executable.strip()
        if configured:
            return configured if Path(configured).is_file() else None
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")

    @staticmethod
    def _document_title(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        parser = _TitleReader()
        try:
            parser.feed(content)
        except ValueError:
            return ""
        return " ".join("".join(parser.parts).split())[:240]
