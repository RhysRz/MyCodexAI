"""Keep Training Lab reserved for administrators in both API and browser UI."""

from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from app.api.dependencies import require_admin


@dataclass
class _Request:
    user: object


user = type("User", (), {"role": "user"})()
admin = type("Admin", (), {"role": "admin"})()

# Patch the dependency's module-level user check to validate its authorization rule.
original_require_user = require_admin.__globals__["require_user"]
try:
    require_admin.__globals__["require_user"] = lambda request: request.user
    try:
        require_admin(_Request(user))
        raise AssertionError("non-admin must not access Training Lab")
    except HTTPException as error:
        assert error.status_code == 403
    assert require_admin(_Request(admin)) is admin
finally:
    require_admin.__globals__["require_user"] = original_require_user

root = Path(__file__).resolve().parent.parent
index = (root / "templates" / "index.html").read_text(encoding="utf-8")
script = (root / "static" / "script.js").read_text(encoding="utf-8")
learning_api = (root / "app" / "api" / "learning.py").read_text(encoding="utf-8")

assert 'id="learning-panel"' in index and "hidden" in index
assert "elements.learningPanel.hidden = user.role !== 'admin';" in script
assert "Depends(require_admin)" in learning_api

print("learning_access=ok")
