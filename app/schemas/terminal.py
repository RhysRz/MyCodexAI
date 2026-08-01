from typing import Literal

from pydantic import BaseModel, Field


class TerminalJobRequest(BaseModel):
    command: list[str] = Field(min_length=1, max_length=32)
    working_directory: str = Field(default=".", min_length=1, max_length=300)


class TerminalResumeRequest(BaseModel):
    approve: bool


class TerminalJobResponse(BaseModel):
    job_id: str
    status: Literal["awaiting_approval", "running", "cancelling", "completed", "failed", "cancelled"]
    command: list[str]
    working_directory: str
    output: str
    output_truncated: bool
    exit_code: int | None = None
    reason: str | None = None
    execution_environment: str
    isolated: bool
