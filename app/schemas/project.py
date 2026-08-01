from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    id: str
    is_workspace: bool
    file_count: int


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class ProjectImportResponse(ProjectResponse):
    ignored_file_count: int
    secret_file_count: int


class CodebaseIndexResponse(BaseModel):
    file_count: int
    truncated: bool
    languages: dict[str, int]
    top_level: dict[str, int]
    entry_points: list[str]


class ProjectMemoryNoteRequest(BaseModel):
    note: str


class ProjectMemoryNoteResponse(BaseModel):
    id: str
    note: str
    created_at: str


class ProjectMemoryHistoryItem(BaseModel):
    run_id: str
    task: str
    status: str
    answer: str
    plan_name: str
    tools: list[str]
    created_at: str


class ProjectMemoryResponse(BaseModel):
    notes: list[ProjectMemoryNoteResponse]
    history: list[ProjectMemoryHistoryItem]


class ProjectGuidanceRequest(BaseModel):
    content: str


class ProjectGuidanceResponse(BaseModel):
    content: str
    custom_content: str
    sources: list[str] = Field(default_factory=list)


class ProjectSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=12_000)


class ProjectSkillResponse(BaseModel):
    id: str
    name: str
    description: str
    instructions: str | None = None
    path: str | None = None


class ProjectSkillListResponse(BaseModel):
    skills: list[ProjectSkillResponse]


class BrowserQaRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    viewport_width: int = Field(default=1440, ge=320, le=3840)
    viewport_height: int = Field(default=900, ge=240, le=2160)
    wait_ms: int = Field(default=800, ge=0, le=10_000)


class BrowserQaResponse(BaseModel):
    capture_id: str
    filename: str
    viewport_width: int
    viewport_height: int
    wait_ms: int
    document_title: str
    captured_at: str
    screenshot_bytes: int
    screenshot_url: str
    execution_environment: str
