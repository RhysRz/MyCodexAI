from typing import Any

from pydantic import BaseModel, Field


class BackupRequest(BaseModel):
    passphrase: str = Field(min_length=16, max_length=1_024)


class RestoreRequest(BackupRequest):
    confirmation: str = Field(min_length=8, max_length=128)


class BackupResponse(BaseModel):
    backup_id: str
    created_at: str
    file_count: int
    size_bytes: int
    restore_note: str


class BackupListResponse(BaseModel):
    backups: list[dict[str, Any]]


class ResilienceStatusResponse(BaseModel):
    status: str
    recovery: dict[str, Any]
    resource_guard: dict[str, Any]
    sandbox: dict[str, Any]
