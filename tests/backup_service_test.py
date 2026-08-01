from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.settings import settings
from app.services.auth_service import AuthenticatedUser
from app.services.backup_service import BackupService
from app.workspace import file_manager


temporary_root = TemporaryDirectory()
original_workspace = file_manager.WORKSPACE
original_state_root = settings.agent_state_root

try:
    root = Path(temporary_root.name)
    file_manager.WORKSPACE = root / "workspace"
    settings.agent_state_root = str(root / "state" / "runs")
    user = AuthenticatedUser("backup-test-user", "backup-user", "user")
    workspace = file_manager.WORKSPACE / "users" / user.id
    workspace.mkdir(parents=True)
    (workspace / "hello.txt").write_text("before", encoding="utf-8")
    (workspace / ".env").write_text("must-not-back-up", encoding="utf-8")

    backup = BackupService.create(user, "a separate backup passphrase")
    assert backup["file_count"] == 1
    assert BackupService.list(user)[0]["backup_id"] == backup["backup_id"]

    (workspace / "hello.txt").write_text("after", encoding="utf-8")
    restored = BackupService.restore(
        user,
        str(backup["backup_id"]),
        "a separate backup passphrase",
        f"RESTORE {backup['backup_id']}",
    )
    assert restored["restored"] is True
    assert (workspace / "hello.txt").read_text(encoding="utf-8") == "before"
    assert not (workspace / ".env").exists()
finally:
    file_manager.WORKSPACE = original_workspace
    settings.agent_state_root = original_state_root
    temporary_root.cleanup()

print("backup_service=ok")
