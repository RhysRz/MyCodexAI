"""Protect mobile browsers from endless startup waits or accidental sign-out loops."""

from pathlib import Path


def test_mobile_clients_use_bounded_requests_and_no_store_api_fetches():
    root = Path(__file__).resolve().parent.parent
    script = (root / "static" / "script.js").read_text(encoding="utf-8")
    remote = (root / "static" / "remote.js").read_text(encoding="utf-8")

    assert "const { timeoutMs = 20_000, ...fetchOptions } = options;" in script
    assert "const { timeoutMs = 20_000, ...fetchOptions } = options;" in remote
    assert "window.setTimeout(() => controller.abort(), timeoutMs)" in script
    assert "window.setTimeout(() => controller.abort(), timeoutMs)" in remote
    assert "async function loadAccount()" in script
    assert "if (error.status === 401) window.location.assign('/');" in script
    assert "await Promise.allSettled" in script
    assert "cache: url.startsWith('/api/') ? 'no-store'" in script
    assert "cache: url.startsWith('/api/') ? 'no-store'" in remote
