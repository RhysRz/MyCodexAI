"""Create the free Media Bridge Space and wire its secrets into GitHub Actions."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request

from huggingface_hub import HfApi
from nacl.public import PublicKey, SealedBox


ROOT = Path(__file__).resolve().parents[2]
SPACE_FILES = Path(__file__).resolve().parent / "media-bridge"
SPACE_ID = os.environ.get("MYCODEXAI_MEDIA_BRIDGE_SPACE", "RhysRz/mycodexai-media-bridge").strip()
GITHUB_REPOSITORY = os.environ.get("MYCODEXAI_GITHUB_REPOSITORY", "RhysRz/MyCodexAI").strip()


def github_token() -> str:
    completed = subprocess.run(
        ["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, timeout=30, check=True,
    )
    values = dict(line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line)
    token = values.get("password", "")
    if not token:
        raise RuntimeError("GitHub credential was not found; sign in to Git first")
    return token


def github_request(path: str, token: str, *, method: str = "GET", payload: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(
        f"https://api.github.com{path}", method=method,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
            "Content-Type": "application/json", "User-Agent": "MyCodexAI-Media-Bridge-Setup",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def set_github_secret(name: str, value: str, token: str, public_key: dict[str, str]) -> None:
    sealed = SealedBox(PublicKey(base64.b64decode(public_key["key"]))).encrypt(value.encode("utf-8"))
    encrypted = base64.b64encode(sealed).decode("ascii")
    github_request(
        f"/repos/{GITHUB_REPOSITORY}/actions/secrets/{name}", token, method="PUT",
        payload={"encrypted_value": encrypted, "key_id": public_key["key_id"]},
    )


def main() -> int:
    hf_token = os.environ.get("HF_DEPLOY_TOKEN", "").strip()
    if not hf_token:
        raise RuntimeError("Set HF_DEPLOY_TOKEN to a Hugging Face Write token for this deployment only")
    bridge_key = secrets.token_urlsafe(48)
    api = HfApi(token=hf_token)
    api.create_repo(repo_id=SPACE_ID, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    api.add_space_secret(repo_id=SPACE_ID, key="MEDIA_BRIDGE_KEY", value=bridge_key)
    api.upload_folder(repo_id=SPACE_ID, repo_type="space", folder_path=str(SPACE_FILES), commit_message="Deploy MyCodexAI Media Bridge")

    account, space_name = SPACE_ID.split("/", 1)
    space_url = f"https://{account.lower()}-{space_name.lower()}.hf.space"
    token = github_token()
    public_key = github_request(f"/repos/{GITHUB_REPOSITORY}/actions/secrets/public-key", token)
    set_github_secret("MYCODEXAI_MEDIA_BRIDGE_URL", space_url, token, public_key)
    set_github_secret("MYCODEXAI_MEDIA_BRIDGE_KEY", bridge_key, token, public_key)
    print(f"Media Bridge deployed and GitHub Actions configured: {space_url}")
    print("The generated bridge key was stored only in Hugging Face and GitHub secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
