from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)


class ChatResponse(BaseModel):
    answer: str


class ChatHistoryResponse(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)
