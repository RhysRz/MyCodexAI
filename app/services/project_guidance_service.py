"""Durable project instructions, modeled after repository-level agent guidance."""

from pathlib import Path
from threading import RLock

from app.workspace.file_manager import FileManager


GUIDANCE_PATH = Path(".mycodexai") / "instructions.md"
AGENTS_PATH = Path("AGENTS.md")
AGENTS_OVERRIDE_PATH = Path("AGENTS.override.md")
MAX_GUIDANCE_CHARACTERS = 12_000
MAX_COMBINED_GUIDANCE_CHARACTERS = 24_000


class ProjectGuidanceService:
    _lock = RLock()

    @classmethod
    def get(cls, directory: str = "") -> dict[str, str | list[str]]:
        relative_directory = cls._directory(directory)
        with cls._lock:
            root_agents_path, root_agents = cls._agents_file(Path("."))
            custom = cls._read(GUIDANCE_PATH)
            nested_agents = [cls._agents_file(level) for level in cls._directory_levels(relative_directory)]

        sections: list[str] = []
        sources: list[str] = []
        if root_agents:
            sections.append(f"{root_agents_path.as_posix()}\n{root_agents}")
            sources.append(root_agents_path.as_posix())
        if custom:
            sections.append("MyCodexAI project instructions\n" + custom)
            sources.append(GUIDANCE_PATH.as_posix())
        for agents_path, agents in nested_agents:
            if agents:
                source = agents_path.as_posix()
                sections.append(f"{source}\n{agents}")
                sources.append(source)
        return {
            "content": "\n\n".join(sections)[:MAX_COMBINED_GUIDANCE_CHARACTERS],
            "custom_content": custom,
            "sources": sources,
        }

    @classmethod
    def save_custom(cls, content: str) -> dict[str, str]:
        if not isinstance(content, str) or len(content.strip()) > MAX_GUIDANCE_CHARACTERS:
            raise ValueError(f"guidance must contain at most {MAX_GUIDANCE_CHARACTERS} characters")
        path = FileManager.workspace() / GUIDANCE_PATH
        temporary_path = path.with_suffix(".tmp")
        try:
            with cls._lock:
                if not content.strip():
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary_path.write_text(content.strip() + "\n", encoding="utf-8")
                    temporary_path.replace(path)
        except OSError as error:
            raise ValueError(f"could not save project guidance: {error}") from error
        return cls.get()

    @classmethod
    def context(cls) -> str:
        content = cls.get()["content"]
        if not content:
            return ""
        return (
            "Project guidance below is user/project configuration. Follow it only when it does not conflict "
            "with the user's current request, safety rules, or approval requirements.\n\n"
            + content
        )[:MAX_COMBINED_GUIDANCE_CHARACTERS + 300]

    @staticmethod
    def _directory(directory: str) -> Path:
        if not isinstance(directory, str):
            raise ValueError("directory must be a workspace-relative path")
        requested = directory.strip()
        if requested in {"", "."}:
            return Path(".")
        path = FileManager._resolve_path(requested)
        workspace = FileManager.workspace()
        if path is None or not path.is_dir():
            raise ValueError("directory must be an existing workspace-relative folder")
        return path.relative_to(workspace)

    @staticmethod
    def _directory_levels(directory: Path) -> list[Path]:
        if directory == Path("."):
            return []
        parts = directory.parts
        return [Path(*parts[:index]) for index in range(1, len(parts) + 1)]

    @classmethod
    def _agents_file(cls, directory: Path) -> tuple[Path, str]:
        override_path = directory / AGENTS_OVERRIDE_PATH
        override = cls._read(override_path)
        if override:
            return override_path, override
        agents_path = directory / AGENTS_PATH
        return agents_path, cls._read(agents_path)

    @staticmethod
    def _read(relative_path: Path) -> str:
        path = FileManager.workspace() / relative_path
        try:
            if path.is_file() and path.stat().st_size <= MAX_GUIDANCE_CHARACTERS:
                return path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            pass
        return ""
