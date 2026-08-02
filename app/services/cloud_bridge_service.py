"""Outbound-only bridge from a local MyCodexAI host to MyCodexAI Cloud."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import logging
import platform

from app.core.settings import settings
from app.services.agent_service import AgentService
from app.services.codebase_index_service import CodebaseIndexService
from app.workspace.file_manager import FileManager


logger = logging.getLogger(__name__)
BRIDGE_OWNER = "cloud-bridge"
TERMINAL_AGENT_STATES = {"completed", "failed", "cancelled", "awaiting_approval", "needs_input"}
ALLOWED_AGENT_MODES = {"agent", "project", "expert", "delivery", "team", "review"}


@dataclass(frozen=True)
class BridgeResult:
    status: str
    result: dict[str, Any]


class CloudBridgeService:
    """Polls for explicitly confirmed jobs without opening the computer to inbound traffic."""

    _lock = RLock()
    _stop = Event()
    _thread: Thread | None = None

    @classmethod
    def start(cls) -> bool:
        if not settings.cloud_bridge_enabled:
            return False
        with cls._lock:
            if cls._thread is not None and cls._thread.is_alive():
                return True
            cls._stop.clear()
            cls._thread = Thread(target=cls._run, name="mycodexai-cloud-bridge", daemon=True)
            cls._thread.start()
            logger.info("MyCodexAI Cloud Bridge started")
        return True

    @classmethod
    def stop(cls) -> None:
        cls._stop.set()
        with cls._lock:
            thread = cls._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)

    @classmethod
    def _run(cls) -> None:
        delay = 1
        while not cls._stop.wait(delay):
            try:
                payload = cls._request("GET", "/api/internal/bridge/poll")
                delay = int(payload.get("poll_after_seconds") or settings.cloud_bridge_poll_seconds)
                job = payload.get("job")
                if not isinstance(job, dict):
                    continue
                result = cls._execute(job)
                cls._request(
                    "POST",
                    "/api/internal/bridge/report",
                    {"job_id": str(job.get("id") or ""), "status": result.status, "result": result.result},
                )
                delay = 1
            except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as error:
                logger.warning("Cloud Bridge poll failed: %s", error)
                delay = min(max(delay * 2, 5), 60)
            except Exception:
                logger.exception("Cloud Bridge encountered an unexpected error")
                delay = 30

    @classmethod
    def _execute(cls, job: dict[str, Any]) -> BridgeResult:
        kind = str(job.get("kind") or "")
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        try:
            if kind == "health":
                return BridgeResult(
                    "completed",
                    {
                        "status": "ok",
                        "system": platform.system(),
                        "workspace": str(FileManager.workspace()),
                        "model": settings.ollama_model,
                    },
                )
            if kind == "index":
                return BridgeResult("completed", {"index": CodebaseIndexService.overview(rebuild=True)})
            if kind == "agent":
                return cls._start_agent(payload)
            if kind == "agent_control":
                return cls._control_agent(payload)
            raise ValueError("Unsupported bridge job")
        except Exception as error:
            logger.exception("Cloud Bridge job %s failed", str(job.get("id") or ""))
            return BridgeResult("failed", {"detail": str(error)[:2_000]})

    @classmethod
    def _start_agent(cls, payload: dict[str, Any]) -> BridgeResult:
        task = str(payload.get("task") or "").strip()
        if not task or len(task) > 20_000:
            raise ValueError("Remote Agent task must contain 1-20000 characters")
        requested_mode = str(payload.get("mode") or "expert").casefold()
        mode = "expert" if requested_mode == "codex" else requested_mode
        if mode not in ALLOWED_AGENT_MODES:
            mode = "expert"
        run = AgentService.start(
            task=task,
            mode=mode,
            owner_id=BRIDGE_OWNER,
            background=True,
            quota_exempt=True,
        )
        return cls._wait_for_agent(str(run["run_id"]))

    @classmethod
    def _control_agent(cls, payload: dict[str, Any]) -> BridgeResult:
        run_id = str(payload.get("run_id") or "")
        action = str(payload.get("action") or "")
        if action == "approve":
            run = AgentService.resume(run_id, True, owner_id=BRIDGE_OWNER)
        elif action == "reject":
            run = AgentService.resume(run_id, False, owner_id=BRIDGE_OWNER)
        elif action == "cancel":
            run = AgentService.cancel(run_id, owner_id=BRIDGE_OWNER)
        else:
            raise ValueError("Remote Agent control action is invalid")
        if run.get("status") in {"queued", "running", "cancelling"}:
            return cls._wait_for_agent(run_id)
        return cls._agent_result(run)

    @classmethod
    def _wait_for_agent(cls, run_id: str) -> BridgeResult:
        deadline = monotonic() + settings.cloud_bridge_job_timeout_seconds
        while monotonic() < deadline and not cls._stop.wait(2):
            run = AgentService.get(run_id, owner_id=BRIDGE_OWNER)
            if str(run.get("status")) in TERMINAL_AGENT_STATES:
                return cls._agent_result(run)
        try:
            AgentService.cancel(run_id, owner_id=BRIDGE_OWNER)
        except ValueError:
            pass
        return BridgeResult("failed", {"run_id": run_id, "detail": "Local Agent timed out"})

    @staticmethod
    def _agent_result(run: dict[str, Any]) -> BridgeResult:
        status = str(run.get("status") or "failed")
        cloud_status = status if status in {"completed", "failed", "cancelled", "awaiting_approval", "needs_input"} else "failed"
        result: dict[str, Any] = {
            "run_id": str(run.get("run_id") or ""),
            "status": status,
            "answer": str(run.get("answer") or "")[:12_000],
            "pending_action": run.get("pending_action"),
            "progress": run.get("progress"),
        }
        return BridgeResult(cloud_status, result)

    @staticmethod
    def _request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = settings.cloud_bridge_url.rstrip("/") + path
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        request = Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {settings.cloud_bridge_token}",
                "Content-Type": "application/json",
                "User-Agent": "MyCodexAI-Bridge/1.0",
            },
        )
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Cloud Bridge returned an invalid response")
        return payload
