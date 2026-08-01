"""Keep the ChatGPT-style workspace drawer and task history wired together."""

from pathlib import Path


root = Path(__file__).resolve().parent.parent
html = (root / "templates" / "index.html").read_text(encoding="utf-8")
script = (root / "static" / "script.js").read_text(encoding="utf-8")
css = (root / "static" / "style.css").read_text(encoding="utf-8")

for identifier in (
    "workspace-sidebar",
    "sidebar-account-anchor",
    "sidebar-menu-toggle",
    "sidebar-close",
    "sidebar-backdrop",
    "recent-runs",
):
    assert f'id="{identifier}"' in html

assert "function setWorkspaceSidebar" in script
assert "function initializeSidebarLayout" in script
assert "elements.sidebarAccountAnchor.append(elements.topbarStatus);" in script
assert "setWorkspaceSidebar(false);" in script
assert ".sidebar.is-open" in css
assert ".recent-section { order: 20;" in css
assert ".sidebar .topbar-status" in css

print("workspace_sidebar_ui=ok")
