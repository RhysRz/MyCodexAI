"""Owner-scoped Music Lab API models."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class MusicTrackResponse(BaseModel):
    music_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    kind: str
    file_name: str
    bytes: int
    duration_seconds: float | None = None
    analyzed: bool = False
    created_at: str
    audio_url: str | None = None
    source_url: str


class MusicTrackListResponse(BaseModel):
    tracks: list[MusicTrackResponse] = Field(default_factory=list)


class MusicStatusResponse(BaseModel):
    configured: bool
    engine: str
    supported_formats: list[str]
    separation_available: bool
    omr_available: bool = False
    sample_playback_available: bool = False
    detail: str


class MusicAnalysisResponse(BaseModel):
    music_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    analysis: dict[str, Any]


class MusicSampleRenderRequest(BaseModel):
    instrument: Literal["piano", "guitar", "bass", "strings", "flute"]


class MusicSampleRenderResponse(BaseModel):
    instrument: str
    label: str
    audio_url: str
    cached: bool
