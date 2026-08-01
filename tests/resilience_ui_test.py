"""Verify recovery/security controls are present in the browser shell and PWA assets."""

from pathlib import Path


root = Path(__file__).resolve().parent.parent
index = (root / "templates" / "index.html").read_text(encoding="utf-8")
remote = (root / "templates" / "remote.html").read_text(encoding="utf-8")
script = (root / "static" / "script.js").read_text(encoding="utf-8")
service_worker = (root / "static" / "service-worker.js").read_text(encoding="utf-8")

for identifier in ("create-backup", "restore-backup", "device-sessions", "revoke-other-sessions", "recovery-codes"):
    assert f'id="{identifier}"' in index
assert 'function createEncryptedBackup' in script
assert 'function showRecoveryCodes' in script
assert 'manifest.webmanifest' in index and 'manifest.webmanifest' in remote
assert "!url.pathname.startsWith('/static/')" in service_worker
assert "'/api/'" not in service_worker
assert "mycodexai-static-v2" in service_worker
assert "url.pathname.endsWith('.js')" in service_worker
assert "caches.delete(key)" in service_worker

print("resilience_ui=ok")
