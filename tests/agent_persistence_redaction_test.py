"""Ensure resumable Agent state does not persist credential-shaped content."""

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.core.settings import settings
from app.services.agent_service import AgentRun, AgentService


original_root = AgentService._state_root
original_setting_root = settings.agent_state_root

with TemporaryDirectory() as temporary:
    root = Path(temporary)
    settings.agent_state_root = str(root / "runs")
    AgentService._state_root = Path(settings.agent_state_root).resolve()
    raw_secret = "ghp_abcdefghijklmnopqrstuvwxyz123456"
    run = AgentRun(
        run_id=str(uuid4()),
        task=f"Use API_KEY={raw_secret} only for this task",
        max_steps=3,
        messages=[{"role": "user", "content": f"Authorization: Bearer {raw_secret}"}],
        owner_id="user-1",
        workspace_path=str(root),
        trace=[{"tool": "read_file", "result": {"output": f"token={raw_secret}"}}],
        answer=f"Found {raw_secret}",
    )
    AgentService._save_run(run)
    persisted = (AgentService._state_root / f"{run.run_id}.json").read_text(encoding="utf-8")
    assert raw_secret not in persisted
    assert "[redacted]" in persisted
    restored = AgentService._load_run(run.run_id)
    assert restored is not None
    assert "[redacted]" in restored.task

settings.agent_state_root = original_setting_root
AgentService._state_root = original_root

print("agent_persistence_redaction=ok")
