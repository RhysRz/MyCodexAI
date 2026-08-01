from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20_000)
    mode: Literal["agent", "project", "expert", "delivery", "team", "review"] = "agent"
    max_steps: int | None = Field(default=None, ge=1, le=60)
    attachments: list[str] = Field(default_factory=list, max_length=100)
    background: bool = False
    review_scope: Literal["uncommitted", "staged", "commit", "branch"] = "uncommitted"
    review_target: str = Field(default="", max_length=128)


class AgentResumeRequest(BaseModel):
    approve: bool


class AgentRunResponse(BaseModel):
    run_id: str
    task: str
    mode: Literal["agent", "project", "expert", "delivery", "team", "review"]
    background: bool = False
    review_scope: Literal["uncommitted", "staged", "commit", "branch"] = "uncommitted"
    review_target: str = ""
    workspace_id: str
    project_id: str
    status: str
    answer: str | None = None
    trace: list[dict[str, Any]]
    pending_action: dict[str, Any] | None = None
    project_plan: dict[str, Any] | None = None
    team_members: list[dict[str, Any]] = Field(default_factory=list)
    progress: dict[str, Any]
    activity: dict[str, Any] | None = None
    attachments: list[str]
    delivery_phase: str = ""


class AgentUsageResponse(BaseModel):
    date: str
    runs: int
    run_limit: int
    steps: int
    step_limit: int
    runs_limited: bool
    steps_limited: bool
    quota_exempt: bool


class AgentActivityResponse(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
