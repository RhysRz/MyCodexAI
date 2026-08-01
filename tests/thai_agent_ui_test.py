"""Static checks for Thai live explanations in Agent mode."""

from pathlib import Path


root = Path(__file__).resolve().parents[1]
script = (root / "static" / "script.js").read_text(encoding="utf-8")

assert "function formatToolName" in script
assert "กำลังทำขั้นตอน" in script
assert "activity.detail" in script
assert "formatToolName(entry.tool)" in script

print("thai_agent_ui=ok")
