"""Host-pressure observations and quality-preserving inference backpressure."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

from app.core.settings import settings

try:  # Optional: the app still starts if psutil has not been installed yet.
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - depends on the host installation
    psutil = None


class ResourceService:
    """Avoid starting an extra Ollama response while memory is critically low."""

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        data: dict[str, Any] = {
            "guard_enabled": settings.resource_guard_enabled,
            "min_available_mb": settings.resource_guard_min_available_mb,
            "measurement_available": psutil is not None,
            "cpu_count": os.cpu_count() or 1,
        }
        if psutil is None:
            data.update({"available_memory_mb": None, "memory_percent": None, "constrained": False})
            return data
        memory = psutil.virtual_memory()
        available_mb = int(memory.available / (1024 * 1024))
        data.update(
            {
                "available_memory_mb": available_mb,
                "memory_percent": round(float(memory.percent), 1),
                "constrained": settings.resource_guard_enabled
                and available_mb < settings.resource_guard_min_available_mb,
            }
        )
        return data

    @classmethod
    def wait_for_capacity(cls, on_wait: Callable[[dict[str, Any] | None], None] | None = None) -> None:
        """Wait briefly for memory headroom instead of competing with foreground work.

        A timeout intentionally proceeds with the existing request: this guard is a
        comfort control, not an availability kill-switch that can strand a run.

        ``on_wait`` is deliberately observational.  It lets a background run
        persist a human-readable status while the guard is protecting the host;
        it never changes the inference or quality settings.
        """
        if not settings.resource_guard_enabled or psutil is None:
            if on_wait is not None:
                on_wait(None)
            return
        deadline = time.monotonic() + settings.resource_guard_max_wait_seconds
        while time.monotonic() < deadline:
            snapshot = cls.snapshot()
            if not snapshot["constrained"]:
                if on_wait is not None:
                    on_wait(None)
                return
            if on_wait is not None:
                on_wait(snapshot)
            time.sleep(settings.resource_guard_poll_seconds)
        if on_wait is not None:
            # The guard intentionally lets the already-requested inference
            # proceed after its bounded wait, but the UI should no longer look
            # silent when that happens.
            on_wait(None)
