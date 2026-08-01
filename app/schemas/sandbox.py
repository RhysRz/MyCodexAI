from typing import Literal

from pydantic import BaseModel


class SandboxStatusResponse(BaseModel):
    mode: Literal["host", "docker"] | str
    ready: bool
    isolated: bool
    reason: str
