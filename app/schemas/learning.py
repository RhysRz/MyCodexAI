from typing import Any

from pydantic import BaseModel, Field


class TrainingExampleRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=12_000)
    ideal_response: str = Field(min_length=1, max_length=48_000)
    tags: list[str] = Field(default_factory=list, max_length=8)


class TrainingEvaluationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12_000)
    required_terms: list[str] = Field(min_length=1, max_length=12)


class TrainingOverviewResponse(BaseModel):
    example_count: int
    evaluation_count: int
    latest_evaluation: dict[str, Any] | None = None
    training_policy: str
