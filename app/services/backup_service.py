"""Encrypted, owner-scoped workspace snapshots with a deliberately guarded restore."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import json
from pathlib import Path, PurePosixPath
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4
import zipfile

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser, AuthService


class BackupError(ValueError):
    """A safe backup or restore error suitable for returning to the owner."""


class BackupService:
    """Keep encrypted recovery points outside of the user workspace itself."""

    _excluded_parts = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", "venv", ".venv"}
    _excluded_names = {".env", ".env.local", ".env.production", ".env.development"}

    @classmethod
    def create(cls, user: AuthenticatedUser, passphrase: str) -> dict[str, object]:
        cls._validate_passphrase(passphrase)
        workspace = AuthService.workspace_for_user(user)
        backup_id = f"backup-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        with TemporaryDirectory(prefix="mycodexai-backup-") as temporary:
            archive_path = Path(temporary) / "snapshot.zip"
            file_count = cls._write_archive(archive_path, workspace)
            encrypted = cls._encrypt(archive_path.read_bytes(), passphrase)
        target = cls._backup_path(user.id, backup_id)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(encrypted)
        except OSError as error:
            raise BackupError("Could not save the encrypted backup") from error
        return {
            "backup_id": backup_id,
            "created_at": datetime.now(UTC).isoformat(),
            "file_count": file_count,
            "size_bytes": target.stat().st_size,
            "restore_note": "Keep the passphrase separately. MyCodexAI cannot recover it.",
        }

    @classmethod
    def list(cls, user: AuthenticatedUser) -> list[dict[str, object]]:
        directory = cls._backup_directory(user.id)
        if not directory.is_dir():
            return []
        backups: list[dict[str, object]] = []
        for path in sorted(directory.glob("backup-*.mcaibak"), key=lambda item: item.stat().st_mtime, reverse=True):
            backups.append(
                {
                    "backup_id": path.stem,
                    "created_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                    "size_bytes": path.stat().st_size,
                }
            )
        return backups[:30]

    @classmethod
    def restore(cls, user: AuthenticatedUser, backup_id: str, passphrase: str, confirmation: str) -> dict[str, object]:
        cls._validate_backup_id(backup_id)
        cls._validate_passphrase(passphrase)
        if confirmation != f"RESTORE {backup_id}":
            raise BackupError("Type the exact restore confirmation before replacing the workspace")
        try:
            encrypted_archive = cls._backup_path(user.id, backup_id).read_bytes()
        except OSError as error:
            raise BackupError("The requested backup is not available") from error
        archive = cls._decrypt(encrypted_archive, passphrase)
        workspace = AuthService.workspace_for_user(user)
        restore_root = cls._restore_directory(user.id)
        restore_point = restore_root / f"before-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        try:
            with TemporaryDirectory(prefix="mycodexai-restore-") as temporary:
                staging = Path(temporary) / "workspace"
                cls._extract_workspace(archive, staging)
                restore_root.mkdir(parents=True, exist_ok=True)
                if workspace.exists():
                    workspace.replace(restore_point)
                staging.replace(workspace)
        except BackupError:
            raise
        except (OSError, zipfile.BadZipFile) as error:
            # A moved restore point is intentionally preserved for manual recovery.
            raise BackupError("Restore failed. The previous workspace was preserved as a local restore point.") from error
        return {"backup_id": backup_id, "restore_point": restore_point.name, "restored": True}

    @classmethod
    def _write_archive(cls, archive_path: Path, workspace: Path) -> int:
        count = 0
        manifest = {"format": 1, "created_at": datetime.now(UTC).isoformat(), "contents": "workspace"}
        try:
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
                if workspace.is_dir():
                    for path in workspace.rglob("*"):
                        if not path.is_file() or not cls._include_workspace_file(workspace, path):
                            continue
                        archive.write(path, Path("workspace") / path.relative_to(workspace))
                        count += 1
        except OSError as error:
            raise BackupError("Could not read the workspace for backup") from error
        return count

    @classmethod
    def _extract_workspace(cls, archive_bytes: bytes, destination: Path) -> None:
        try:
            with zipfile.ZipFile(__import__("io").BytesIO(archive_bytes), "r") as archive:
                if "manifest.json" not in archive.namelist():
                    raise BackupError("Backup format is not recognized")
                manifest = json.loads(archive.read("manifest.json"))
                if not isinstance(manifest, dict) or manifest.get("format") != 1:
                    raise BackupError("Backup format is not supported")
                for info in archive.infolist():
                    if info.is_dir() or info.filename == "manifest.json":
                        continue
                    relative = PurePosixPath(info.filename)
                    if not relative.parts or relative.parts[0] != "workspace" or ".." in relative.parts:
                        raise BackupError("Backup contains an unsafe path")
                    target = destination / Path(*relative.parts[1:])
                    if destination not in target.resolve().parents and target.resolve() != destination.resolve():
                        raise BackupError("Backup path leaves the workspace")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, "r") as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise BackupError("Could not read the encrypted backup") from error

    @classmethod
    def _include_workspace_file(cls, root: Path, path: Path) -> bool:
        try:
            relative = path.relative_to(root)
        except ValueError:
            return False
        if any(part in cls._excluded_parts for part in relative.parts):
            return False
        return path.name not in cls._excluded_names and not path.name.startswith(".env.")

    @classmethod
    def _encrypt(cls, contents: bytes, passphrase: str) -> bytes:
        salt = __import__("os").urandom(16)
        key = cls._derive_key(passphrase, salt)
        envelope = {"format": 1, "salt": base64.urlsafe_b64encode(salt).decode("ascii"), "ciphertext": Fernet(key).encrypt(contents).decode("ascii")}
        return json.dumps(envelope, separators=(",", ":")).encode("utf-8")

    @classmethod
    def _decrypt(cls, contents: bytes, passphrase: str) -> bytes:
        try:
            envelope = json.loads(contents.decode("utf-8"))
            salt = base64.urlsafe_b64decode(envelope["salt"].encode("ascii"))
            ciphertext = envelope["ciphertext"].encode("ascii")
            return Fernet(cls._derive_key(passphrase, salt)).decrypt(ciphertext)
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, InvalidToken) as error:
            raise BackupError("Backup passphrase is incorrect or the archive is damaged") from error

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        raw = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000).derive(passphrase.encode("utf-8"))
        return base64.urlsafe_b64encode(raw)

    @classmethod
    def _backup_directory(cls, user_id: str) -> Path:
        return Path(settings.agent_state_root).expanduser().resolve().parent / "backups" / user_id

    @classmethod
    def _restore_directory(cls, user_id: str) -> Path:
        return Path(settings.agent_state_root).expanduser().resolve().parent / "restore-points" / user_id

    @classmethod
    def _backup_path(cls, user_id: str, backup_id: str) -> Path:
        cls._validate_backup_id(backup_id)
        return cls._backup_directory(user_id) / f"{backup_id}.mcaibak"

    @staticmethod
    def _validate_backup_id(backup_id: str) -> None:
        if not backup_id.startswith("backup-") or len(backup_id) > 80 or not all(char.isalnum() or char == "-" for char in backup_id):
            raise BackupError("Backup identifier is invalid")

    @staticmethod
    def _validate_passphrase(passphrase: str) -> None:
        if not isinstance(passphrase, str) or len(passphrase) < 16:
            raise BackupError("Use a separate backup passphrase with at least 16 characters")
