from typing import Literal

from pydantic import BaseModel, Field


class GitHubStatusResponse(BaseModel):
    is_git_repository: bool
    branch: str
    head: str
    dirty: bool
    remote_name: str
    remote_url: str
    repository: str
    is_github_remote: bool
    github_cli_available: bool
    github_cli_authenticated: bool
    ci_workflow_path: str
    ci_workflow_present: bool
    ci_kind: str


class GitHubPushRequest(BaseModel):
    remote: str = Field(default="origin", min_length=1, max_length=64)
    branch: str = Field(default="", max_length=128)


class GitHubRemoteRequest(BaseModel):
    remote: str = Field(default="origin", min_length=1, max_length=64)
    url: str = Field(min_length=12, max_length=500)


class GitHubPullRequestRequest(BaseModel):
    base: str = Field(default="main", min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(default="", max_length=12_000)


class GitHubPreparedActionResponse(BaseModel):
    approval_token: str
    kind: Literal["configure_remote", "push", "pull_request", "ci_workflow"]
    summary: str
    preview: str = ""
    expires_at: str


class GitHubExecuteRequest(BaseModel):
    approval_token: str = Field(min_length=16, max_length=128)


class GitHubExecuteResponse(BaseModel):
    kind: Literal["configure_remote", "push", "pull_request", "ci_workflow"]
    status: Literal["ok", "failed"]
    summary: str
    output: str = ""
