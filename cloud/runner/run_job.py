"""Run one MyCodexAI Cloud Agent job on a GitHub-hosted runner.

The Worker creates a reviewed, full-file draft. This runner applies only safe repository
paths, runs fixed checks, pushes a dedicated branch and opens a pull request.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
RUN_ID = os.environ["MYCODEXAI_RUN_ID"]
CLOUD_URL = os.environ["MYCODEXAI_CLOUD_URL"].rstrip("/")
RUNNER_SECRET = os.environ["MYCODEXAI_RUNNER_SECRET"]
GH_TOKEN = os.environ["GH_TOKEN"]
REPOSITORY = os.environ["GITHUB_REPOSITORY"]
TASK = os.environ.get("MYCODEXAI_TASK", "").strip()
MODE = os.environ.get("MYCODEXAI_MODE", "agent")
ATTACHMENTS = json.loads(os.environ.get("MYCODEXAI_ATTACHMENTS", "[]"))

BLOCKED_EXACT = {".env", ".env.local", ".env.production"}
BLOCKED_PREFIXES = (".git/", ".github/workflows/", "workspace/", "venv/", ".venv/", "node_modules/")
TEXT_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss",
    ".json", ".jsonc", ".toml", ".yaml", ".yml", ".md", ".txt", ".sql", ".ps1",
    ".sh", ".dockerfile", ".ini", ".cfg", ".xml", ".svg",
}


def run(command: list[str], *, check: bool = True, timeout: int = 1_800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=check, timeout=timeout)


def request_json(path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{CLOUD_URL}{path}", data=body, method=method,
        headers={"Authorization": f"Bearer {RUNNER_SECRET}", "Content-Type": "application/json", "User-Agent": "MyCodexAI-GitHub-Runner/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:2_000]
        raise RuntimeError(f"Cloud API {error.code}: {detail}") from error


def callback(status: str, answer: str = "", **extra: Any) -> None:
    payload = {"run_id": RUN_ID, "status": status, "answer": answer, **extra}
    try:
        request_json("/api/internal/agent/callback", payload)
    except Exception as error:  # Keep the job result visible even if the callback is transiently unavailable.
        print(f"::warning::Cloud callback failed: {error}")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def safe_target(name: str) -> Path:
    normalized = name.replace("\\", "/").lstrip("./")
    if not normalized or normalized in BLOCKED_EXACT or normalized.startswith(BLOCKED_PREFIXES) or ".." in Path(normalized).parts:
        raise ValueError(f"Blocked path: {name}")
    target = (ROOT / normalized).resolve()
    if os.path.commonpath([str(ROOT), str(target)]) != str(ROOT):
        raise ValueError(f"Path escapes repository: {name}")
    return target


def repository_manifest() -> list[str]:
    output = run(["git", "ls-files"], timeout=60).stdout
    return [line.strip() for line in output.splitlines() if line.strip() and not line.startswith(BLOCKED_PREFIXES)]


def relevant_files(manifest: list[str]) -> list[dict[str, str]]:
    words = {word.lower() for word in re.findall(r"[A-Za-z0-9_\-]{3,}", TASK)}
    preferred = {"README.md", "requirements.txt", "pyproject.toml", "package.json", "wrangler.jsonc", "main.py"}

    def score(name: str) -> tuple[int, int, str]:
        lowered = name.lower()
        matches = sum(1 for word in words if word in lowered)
        source_bonus = 6 if lowered.startswith(("app/", "src/", "static/", "templates/", "cloud/")) else 0
        root_bonus = 10 if name in preferred else 0
        test_bonus = 2 if "test" in lowered else 0
        return (matches * 20 + source_bonus + root_bonus + test_bonus, -len(name), name)

    selected: list[dict[str, str]] = []
    used = 0
    for name in sorted(manifest, key=score, reverse=True):
        path = ROOT / name
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Makefile"}:
            continue
        try:
            if path.stat().st_size > 120_000:
                continue
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if used + len(content) > 210_000 or len(selected) >= 55:
            continue
        selected.append({"path": name, "content": content})
        used += len(content)
    return selected


def download_attachments() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    folder = ROOT / ".mycodexai-runner-attachments"
    folder.mkdir(exist_ok=True)
    for identifier in ATTACHMENTS[:20]:
        if not re.fullmatch(r"[a-f0-9-]{20,64}", str(identifier), re.I):
            continue
        request = urllib.request.Request(
            f"{CLOUD_URL}/api/internal/files/{identifier}",
            headers={"Authorization": f"Bearer {RUNNER_SECRET}", "User-Agent": "MyCodexAI-GitHub-Runner/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                name = urllib.parse.unquote(response.headers.get("X-MyCodexAI-File-Name", "attachment.bin"))
                data = response.read(10 * 1024 * 1024 + 1)
            if len(data) > 10 * 1024 * 1024:
                continue
            target = folder / re.sub(r"[^\w.()\-ก-๙ ]", "_", Path(name).name)
            target.write_bytes(data)
            if target.suffix.lower() in TEXT_SUFFIXES and len(data) <= 60_000:
                result.append({"path": f"ATTACHMENT/{target.name}", "content": data.decode("utf-8", "replace")})
        except Exception as error:
            print(f"::warning::Could not download attachment {identifier}: {error}")
    return result


def apply_draft(files: list[dict[str, Any]]) -> list[str]:
    changed: list[str] = []
    total = 0
    for item in files[:20]:
        name = str(item.get("path", ""))
        content = str(item.get("content", ""))
        total += len(content.encode("utf-8"))
        if total > 650_000:
            raise ValueError("Draft exceeds the 650 KB safety limit")
        target = safe_target(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        changed.append(relative(target))
    return changed


def tests() -> tuple[bool, str]:
    commands: list[list[str]] = [[sys.executable, "-m", "compileall", "-q", "app", "cloud/runner"]]
    if (ROOT / "tests").is_dir():
        commands.append([sys.executable, "-m", "pytest", "-q", "--disable-warnings", "--maxfail=1"])
    outputs: list[str] = []
    success = True
    for command in commands:
        completed = run(command, check=False, timeout=1_500)
        outputs.append(f"$ {' '.join(command)}\n{completed.stdout[-3_000:]}\n{completed.stderr[-2_000:]}")
        success = success and completed.returncode == 0
        if completed.returncode != 0:
            break
    return success, "\n".join(outputs)[-6_000:]


def github_api(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com{path}", data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "MyCodexAI-GitHub-Runner/1.0", "X-GitHub-Api-Version": "2022-11-28"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    trace: list[dict[str, str]] = [{"kind": "runner", "status": "ok", "summary": "GitHub Runner เริ่มทำงานแล้ว"}]
    callback("running", "กำลังวิเคราะห์โปรเจกต์บน GitHub Runner", trace=trace)
    branch = f"mycodexai/cloud-{RUN_ID[:12]}"
    try:
        run(["git", "config", "user.name", "MyCodexAI Cloud"])
        run(["git", "config", "user.email", "mycodexai-cloud@users.noreply.github.com"])
        run(["git", "switch", "-c", branch])
        manifest = repository_manifest()
        context_files = relevant_files(manifest) + download_attachments()
        draft = request_json("/api/internal/agent/draft", {"run_id": RUN_ID, "manifest": manifest[:500], "files": context_files})
        changed = apply_draft(list(draft.get("files") or []))
        status = run(["git", "status", "--porcelain"], timeout=60).stdout.strip()
        if not status:
            trace.append({"kind": "draft", "status": "ok", "summary": "ตรวจแล้วไม่พบไฟล์ที่เปลี่ยนแปลง"})
            callback("completed", "MyCodex ตรวจแล้วไม่พบการเปลี่ยนแปลงที่ต้องเปิด Pull Request", trace=trace)
            return 0

        trace.append({"kind": "draft", "status": "ok", "summary": f"แก้ไข {len(changed)} ไฟล์ใน branch แยก"})
        passed, test_output = tests()
        trace.append({"kind": "tests", "status": "ok" if passed else "failed", "summary": "การทดสอบผ่าน" if passed else "การทดสอบบางส่วนไม่ผ่าน โปรดดูใน Pull Request"})
        run(["git", "add", "--", *changed])
        run(["git", "commit", "-m", f"MyCodexAI Cloud: {TASK[:60] or RUN_ID}"])
        run(["git", "push", "--set-upstream", "origin", branch], timeout=300)
        body = (
            f"## งานจาก MyCodexAI Cloud\n\n{TASK}\n\n"
            f"## สรุป\n\n{str(draft.get('summary', 'เตรียมการแก้ไขแล้ว'))}\n\n"
            f"## การตรวจสอบ\n\n{'✅ ผ่าน' if passed else '⚠️ มีการทดสอบไม่ผ่าน'}\n\n"
            f"<details><summary>ผลทดสอบย่อ</summary>\n\n```text\n{test_output}\n```\n</details>\n\n"
            "กรุณาตรวจ diff และผลทดสอบก่อน Merge เสมอ"
        )
        pull = github_api(f"/repos/{REPOSITORY}/pulls", {"title": f"MyCodexAI: {TASK[:80]}", "head": branch, "base": os.environ.get("GITHUB_DEFAULT_BRANCH", "main"), "body": body, "draft": not passed})
        url = str(pull.get("html_url", ""))
        callback("needs_review", "แก้ไขและเปิด Pull Request แล้ว กรุณาตรวจสอบก่อน Merge", pull_request_url=url, branch_name=branch, trace=trace)
        print(f"Pull request: {url}")
        return 0
    except Exception as error:
        trace.append({"kind": "runner", "status": "failed", "summary": str(error)[:500]})
        callback("failed", "GitHub Runner ทำงานไม่สำเร็จ", error_detail=str(error)[:3_000], branch_name=branch, trace=trace)
        print(f"::error::{error}")
        return 1
    finally:
        attachment_folder = ROOT / ".mycodexai-runner-attachments"
        if attachment_folder.exists():
            for item in attachment_folder.iterdir():
                if item.is_file():
                    item.unlink(missing_ok=True)
            attachment_folder.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
