from pathlib import Path

from app.services.agent_service import AgentService
from app.services.cloud_bridge_service import BridgeResult, CloudBridgeService


def test_codex_remote_job_uses_local_expert_workflow_without_bypassing_approvals(monkeypatch):
    captured = {}

    def fake_start(cls, **kwargs):
        captured.update(kwargs)
        return {"run_id": "3ad98446-3b5f-4e5e-a67e-d915ec16e115"}

    def fake_wait(cls, run_id):
        return BridgeResult("awaiting_approval", {"run_id": run_id})

    monkeypatch.setattr(AgentService, "start", classmethod(fake_start))
    monkeypatch.setattr(CloudBridgeService, "_wait_for_agent", classmethod(fake_wait))

    result = CloudBridgeService._start_agent({"task": "ตรวจและแก้บั๊ก", "mode": "codex"})

    assert result.status == "awaiting_approval"
    assert captured["mode"] == "expert"
    assert captured["background"] is True
    assert captured["quota_exempt"] is True
    assert captured["owner_id"] == "cloud-bridge"


def test_remote_approval_payload_keeps_pending_action_for_user_review():
    result = CloudBridgeService._agent_result(
        {
            "run_id": "3ad98446-3b5f-4e5e-a67e-d915ec16e115",
            "status": "awaiting_approval",
            "pending_action": {"tool": "write_files", "summary": "แก้ไฟล์หนึ่งรายการ"},
            "progress": {"completed_steps": 2},
        }
    )

    assert result.status == "awaiting_approval"
    assert result.result["pending_action"]["tool"] == "write_files"


def test_bridge_is_outbound_only_and_never_executes_raw_remote_shell():
    source = Path("app/services/cloud_bridge_service.py").read_text(encoding="utf-8")

    assert "urlopen(" in source
    assert "subprocess" not in source
    assert "shell=True" not in source
