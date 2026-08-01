"""A compact, project-scoped codebase index for on-demand agent context."""

from collections import Counter
from pathlib import Path
from threading import RLock
from typing import Any
import ast
import json
import re

from app.workspace.file_manager import FileManager


INDEX_DIRECTORY = ".mycodexai"
INDEX_FILENAME = "codebase-index.json"
MAX_INDEXED_FILES = 5_000
MAX_INDEXED_FILE_BYTES = 1_000_000
MAX_SYMBOL_RESULTS = 50
EXCLUDED_DIRECTORIES = {".git", ".mycodexai", ".venv", "venv", "node_modules", "__pycache__"}
LANGUAGES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".json": "JSON",
    ".html": "HTML",
    ".css": "CSS",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cs": "C#",
}
SCRIPT_SYMBOL_PATTERN = re.compile(
    r"(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|type|const|let|var)\s+([A-Za-z_$][\w$]*)"
)
SCRIPT_IMPORT_PATTERN = re.compile(r"(?:from\s+|import\s+)[\"']([^\"']+)[\"']")


class CodebaseIndexService:
    _lock = RLock()

    @classmethod
    def overview(cls, rebuild: bool = False) -> dict[str, Any]:
        with cls._lock:
            index = None if rebuild else cls._load()
            if index is None:
                index = cls._build()
                cls._save(index)
            return cls._overview(index)

    @classmethod
    def search(cls, query: str) -> dict[str, Any]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            raise ValueError("query must be a non-empty string")

        with cls._lock:
            index = cls._load()
            if index is None:
                index = cls._build()
                cls._save(index)

        results = []
        for file in index["files"]:
            symbol_matches = [symbol for symbol in file["symbols"] if normalized_query in symbol.casefold()]
            import_matches = [item for item in file["imports"] if normalized_query in item.casefold()]
            path_match = normalized_query in file["path"].casefold()
            if not (symbol_matches or import_matches or path_match):
                continue
            results.append(
                {
                    "path": file["path"],
                    "language": file["language"],
                    "symbols": symbol_matches[:12],
                    "imports": import_matches[:8],
                }
            )
            if len(results) >= MAX_SYMBOL_RESULTS:
                break

        return {"query": query.strip(), "matches": results, "truncated": len(results) >= MAX_SYMBOL_RESULTS}

    @classmethod
    def invalidate(cls) -> None:
        path = cls._index_path()
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @classmethod
    def _build(cls) -> dict[str, Any]:
        workspace = FileManager.workspace()
        files: list[dict[str, Any]] = []
        language_counts: Counter[str] = Counter()
        top_level_counts: Counter[str] = Counter()
        truncated = False

        if workspace.is_dir():
            for path in workspace.rglob("*"):
                try:
                    relative = path.relative_to(workspace)
                    if any(part.casefold() in EXCLUDED_DIRECTORIES for part in relative.parts):
                        continue
                    if not path.is_file():
                        continue
                    size = path.stat().st_size
                except OSError:
                    continue

                if len(files) >= MAX_INDEXED_FILES:
                    truncated = True
                    break

                suffix = path.suffix.casefold()
                language = LANGUAGES.get(suffix, "Other")
                symbols: list[str] = []
                imports: list[str] = []
                if suffix in {".py", ".js", ".jsx", ".ts", ".tsx"} and size <= MAX_INDEXED_FILE_BYTES:
                    try:
                        source = path.read_text(encoding="utf-8", errors="replace")
                        symbols, imports = cls._extract_source_facts(source, suffix)
                    except OSError:
                        pass

                files.append(
                    {
                        "path": relative.as_posix(),
                        "language": language,
                        "size": size,
                        "symbols": symbols[:100],
                        "imports": imports[:100],
                    }
                )
                language_counts[language] += 1
                if relative.parts:
                    top_level_counts[relative.parts[0]] += 1

        entry_points = [
            file["path"]
            for file in files
            if Path(file["path"]).name.casefold()
            in {"main.py", "app.py", "index.js", "index.ts", "index.tsx", "server.js", "server.ts", "package.json", "readme.md"}
        ][:20]
        return {
            "version": 1,
            "file_count": len(files),
            "truncated": truncated,
            "languages": dict(language_counts.most_common()),
            "top_level": dict(top_level_counts.most_common(20)),
            "entry_points": entry_points,
            "files": files,
        }

    @staticmethod
    def _extract_source_facts(source: str, suffix: str) -> tuple[list[str], list[str]]:
        if suffix == ".py":
            try:
                tree = ast.parse(source)
            except SyntaxError:
                return [], []
            symbols = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or ".")
            return sorted(set(symbols)), sorted(set(imports))

        return sorted(set(SCRIPT_SYMBOL_PATTERN.findall(source))), sorted(set(SCRIPT_IMPORT_PATTERN.findall(source)))

    @classmethod
    def _index_path(cls) -> Path:
        return FileManager.workspace() / INDEX_DIRECTORY / INDEX_FILENAME

    @classmethod
    def _load(cls) -> dict[str, Any] | None:
        try:
            payload = json.loads(cls._index_path().read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("files"), list):
                return payload
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        return None

    @classmethod
    def _save(cls, index: dict[str, Any]) -> None:
        path = cls._index_path()
        temporary_path = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            temporary_path.replace(path)
        except OSError:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _overview(index: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_count": int(index.get("file_count", 0)),
            "truncated": bool(index.get("truncated", False)),
            "languages": index.get("languages", {}),
            "top_level": index.get("top_level", {}),
            "entry_points": index.get("entry_points", []),
        }
