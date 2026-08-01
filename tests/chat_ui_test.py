"""Static checks for the normal-chat selector and safe API wiring."""

from pathlib import Path


root = Path(__file__).resolve().parents[1]
template = (root / "templates" / "index.html").read_text(encoding="utf-8")
script = (root / "static" / "script.js").read_text(encoding="utf-8")
route = (root / "app" / "api" / "chat.py").read_text(encoding="utf-8")

assert '<option value="chat">Chat</option>' in template
assert "async function startChat" in script
assert "'/api/chat/history'" in script
# Streaming chat owns its AbortController directly, so keep this check tied to
# the actual 210-second timeout rather than an obsolete request() option shape.
assert "window.setTimeout(() => controller.abort(), 210_000)" in script
assert "คุยกับ MyCodex" in script
assert "MyCodex · กำลังพิมพ์คำตอบ" in script
assert "กำลังพิมพ์คำตอบ" in script
assert "ChatService.chat(request.message, owner_id=user.id)" in route
assert "def chat_history" in route

print("chat_ui=ok")
