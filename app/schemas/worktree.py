from pydantic import BaseModel, Field


class WorktreeCreateRequest(BaseModel):
    branch: str = Field(min_length=1, max_length=100)


class WorktreeResponse(BaseModel):
    id: str
    is_main: bool


class WorktreeListResponse(BaseModel):
    worktrees: list[WorktreeResponse]
