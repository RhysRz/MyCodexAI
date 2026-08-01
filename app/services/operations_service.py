"""Small, privacy-preserving operational records for agent work.

The service deliberately records metadata rather than prompts, file contents, command
arguments, credentials, or model output.  It gives each signed-in user a clear daily
allowance and an inspectable history without turning MyCodexAI into a prompt archive.
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
import json

from app.core.settings import settings


MAX_EVENT_DETAIL_CHARS = 280


class UsageLimitError(ValueError):
    """Raised when a user has reached a configured daily safety budget."""


class OperationsService:
    _lock = RLock()

    @classmethod
    def reserve_run(cls, owner_id: str | None, quota_exempt: bool = False) -> None:
        """Reserve one agent run before any model request is made."""
        if not owner_id or quota_exempt:
            return
        with cls._lock:
            payload = cls._load()
            bucket = cls._bucket(payload, owner_id)
            limit = settings.agent_daily_run_limit
            if limit and int(bucket["runs"]) >= limit:
                raise UsageLimitError(f"Daily agent run limit reached ({limit}). Try again tomorrow or ask an administrator to raise the limit.")
            bucket["runs"] = int(bucket["runs"]) + 1
            cls._save(payload)

    @classmethod
    def consume_step(cls, owner_id: str | None, quota_exempt: bool = False) -> None:
        """Count one model decision, preventing a damaged task from looping all day."""
        if not owner_id or quota_exempt:
            return
        with cls._lock:
            payload = cls._load()
            bucket = cls._bucket(payload, owner_id)
            limit = settings.agent_daily_step_limit
            if limit and int(bucket["steps"]) >= limit:
                raise UsageLimitError(f"Daily agent step limit reached ({limit}). Review the trace and continue tomorrow or ask an administrator to raise the limit.")
            bucket["steps"] = int(bucket["steps"]) + 1
            cls._save(payload)

    @classmethod
    def reserve_image(cls, owner_id: str | None, quota_exempt: bool = False) -> None:
        """Reserve a shared image-generation credit before contacting the provider."""
        if not owner_id or quota_exempt:
            return
        with cls._lock:
            payload = cls._load()
            bucket = cls._bucket(payload, owner_id)
            limit = settings.image_daily_user_limit
            if limit and int(bucket.get("images", 0)) >= limit:
                raise UsageLimitError(f"Daily image limit reached ({limit}). Try again tomorrow.")
            bucket["images"] = int(bucket.get("images", 0)) + 1
            cls._save(payload)

    @classmethod
    def image_usage(cls, owner_id: str, quota_exempt: bool = False) -> dict[str, int | bool | None]:
        with cls._lock:
            payload = cls._load()
            bucket = cls._bucket(payload, owner_id, create=False)
        used = int(bucket.get("images", 0))
        limit = settings.image_daily_user_limit
        return {
            "used_today": used,
            "daily_limit": limit,
            "remaining_today": None if quota_exempt or not limit else max(0, limit - used),
            "quota_exempt": quota_exempt,
        }

    @classmethod
    def usage(cls, owner_id: str, quota_exempt: bool = False) -> dict[str, int | str | bool]:
        with cls._lock:
            payload = cls._load()
            bucket = cls._bucket(payload, owner_id, create=False)
        runs = int(bucket.get("runs", 0))
        steps = int(bucket.get("steps", 0))
        return {
            "date": cls._today(),
            "runs": runs,
            "run_limit": settings.agent_daily_run_limit,
            "steps": steps,
            "step_limit": settings.agent_daily_step_limit,
            "runs_limited": bool(settings.agent_daily_run_limit) and not quota_exempt,
            "steps_limited": bool(settings.agent_daily_step_limit) and not quota_exempt,
            "quota_exempt": quota_exempt,
        }

    @classmethod
    def record(
        cls,
        owner_id: str | None,
        event: str,
        *,
        run_id: str = "",
        mode: str = "",
        workspace_id: str = "",
        project_id: str = "",
        outcome: str = "",
        detail: str = "",
    ) -> None:
        if not owner_id:
            return
        clean_event = str(event).strip()[:80]
        if not clean_event:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": clean_event,
            "run_id": str(run_id)[:80],
            "mode": str(mode)[:32],
            "workspace_id": str(workspace_id)[:120],
            "project_id": str(project_id)[:120],
            "outcome": str(outcome)[:48],
            "detail": " ".join(str(detail).split())[:MAX_EVENT_DETAIL_CHARS],
        }
        with cls._lock:
            payload = cls._load()
            audit = payload.setdefault("audit", {})
            entries = audit.setdefault(owner_id, [])
            entries.insert(0, entry)
            del entries[settings.agent_audit_retention :]
            cls._save(payload)

    @classmethod
    def activity(cls, owner_id: str, limit: int = 30) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        with cls._lock:
            payload = cls._load()
            entries = payload.get("audit", {}).get(owner_id, [])
            if not isinstance(entries, list):
                return []
            return [item for item in entries[:safe_limit] if isinstance(item, dict)]

    @classmethod
    def _bucket(cls, payload: dict[str, Any], owner_id: str, create: bool = True) -> dict[str, Any]:
        usage = payload.setdefault("usage", {})
        user_usage = usage.get(owner_id)
        if not isinstance(user_usage, dict):
            user_usage = {}
            if create:
                usage[owner_id] = user_usage
        day = cls._today()
        bucket = user_usage.get(day)
        if not isinstance(bucket, dict):
            bucket = {"runs": 0, "steps": 0, "images": 0}
            if create:
                user_usage.clear()
                user_usage[day] = bucket
        return bucket

    @classmethod
    def _path(cls) -> Path:
        return Path(settings.agent_state_root).expanduser().resolve().parent / "operations.json"

    @classmethod
    def _load(cls) -> dict[str, Any]:
        try:
            payload = json.loads(cls._path().read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("usage", {})
                payload.setdefault("audit", {})
                return payload
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return {"usage": {}, "audit": {}}

    @classmethod
    def _save(cls, payload: dict[str, Any]) -> None:
        path = cls._path()
        temporary_path = path.with_suffix(".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary_path.replace(path)
        except OSError:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()
