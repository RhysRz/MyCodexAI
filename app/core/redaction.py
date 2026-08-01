"""Best-effort removal of common credentials before durable local persistence."""

from __future__ import annotations

from typing import Any
import re


REDACTED = "[redacted]"
URL_CREDENTIAL_PATTERN = re.compile(r"(https?://)[^/@\s]+@")
BEARER_PATTERN = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/-]{12,}")
ASSIGNMENT_PATTERN = re.compile(
    r'''(?ix)
    (\b(?:api[_-]?key|access[_-]?key|secret|client[_-]?secret|token|password|passwd|private[_-]?key|authorization)\b
    \s*[=:]\s*["']?)
    [^\s,}\]"']{8,}
    ''',
)
OPENAI_PATTERN = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}")
GITHUB_PATTERN = re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9_]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}")
AWS_PATTERN = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
PEM_PATTERN = re.compile(r"-----BEGIN [A-Z0-9 ]+-----[\s\S]*?-----END [A-Z0-9 ]+-----")


def redact_text(value: str) -> str:
    """Replace credential-shaped text while preserving normal diagnostic context."""
    result = str(value)
    result = PEM_PATTERN.sub(REDACTED, result)
    result = URL_CREDENTIAL_PATTERN.sub(r"\1***@", result)
    result = BEARER_PATTERN.sub(r"\1" + REDACTED, result)
    result = ASSIGNMENT_PATTERN.sub(r"\1" + REDACTED, result)
    result = OPENAI_PATTERN.sub(REDACTED, result)
    result = GITHUB_PATTERN.sub(REDACTED, result)
    result = AWS_PATTERN.sub(REDACTED, result)
    return JWT_PATTERN.sub(REDACTED, result)


def redact_value(value: Any) -> Any:
    """Return a safe copy that can be serialized without retaining common secrets."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value
