from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "cloud" / "worker"


def test_cloud_platform_upgrade_bindings_and_schema() -> None:
    config = (WORKER / "wrangler.jsonc").read_text(encoding="utf-8")
    migration = (WORKER / "migrations" / "0006_cloud_platform.sql").read_text(encoding="utf-8")
    types = (WORKER / "src" / "types.ts").read_text(encoding="utf-8")
    assert '"binding": "VECTORIZE"' in config
    assert '"class_name": "UserEventHub"' in config
    assert "OBJECTS?: R2Bucket" in types
    for table in ("cloud_workspaces", "memory_documents", "memory_chunks", "user_notifications", "backup_snapshots", "hybrid_devices"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration


def test_cloud_platform_upgrade_has_realtime_rag_backup_and_bridge_routes() -> None:
    index = (WORKER / "src" / "index.ts").read_text(encoding="utf-8")
    realtime = (WORKER / "src" / "realtime.ts").read_text(encoding="utf-8")
    memory = (WORKER / "src" / "memory.ts").read_text(encoding="utf-8")
    backups = (WORKER / "src" / "backups.ts").read_text(encoding="utf-8")
    bridge = (WORKER / "src" / "bridge.ts").read_text(encoding="utf-8")
    assert "handleRealtime" in index and "UserEventHub" in index
    assert "/api/realtime" in realtime and "acceptWebSocket" in realtime
    assert "/api/memory/documents" in memory and "VECTORIZE.upsert" in memory
    assert "AES-GCM" in backups and "AUTH_ENCRYPTION_KEY" in backups
    assert "/api/internal/bridge/poll" in bridge and "confirmed !== true" in bridge


def test_codex_workflow_is_visible_and_default_on_cloud() -> None:
    page = (WORKER / "public" / "index.html").read_text(encoding="utf-8")
    app = (WORKER / "public" / "app.js").read_text(encoding="utf-8")
    agent = (WORKER / "src" / "agent.ts").read_text(encoding="utf-8")
    assert 'option value="codex"' in page
    assert 'data-view="remote"' in page
    assert 'id="remote-job-form"' in page
    assert "CODEX WORKFLOW · CLOUD AGENT" in page
    assert "agent-context" in page and "agent-done-when" in page
    assert 'payload.mode || "codex"' in agent
    assert "project_plan_json" in agent
    assert "เริ่ม Codex workflow แล้ว" in app
    assert "/api/bridge/jobs" in app
