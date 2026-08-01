"""Keep the compact chat composer controls wired to the existing agent UI."""

from pathlib import Path


root = Path(__file__).resolve().parent.parent
html = (root / "templates" / "index.html").read_text(encoding="utf-8")
script = (root / "static" / "script.js").read_text(encoding="utf-8")
css = (root / "static" / "style.css").read_text(encoding="utf-8")

for identifier in ("task-input", "open-advanced-controls", "advanced-composer", "start-agent"):
    assert f'id="{identifier}"' in html
for shortcut in ("data-composer-shortcut=\"fix\"", "data-composer-shortcut=\"build\"", "data-composer-shortcut=\"review\""):
    assert shortcut in html
assert "function applyComposerShortcut" in script
assert "function setAdvancedComposer" in script
assert "setAdvancedComposer(false);" in script
assert ".chat-composer" in css
assert ".advanced-composer" in css

print("composer_ui=ok")
