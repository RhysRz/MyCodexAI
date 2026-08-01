"""Authenticated, owner-scoped endpoints for the local Music Lab."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.dependencies import require_user
from app.schemas.music import MusicAnalysisResponse, MusicSampleRenderRequest, MusicSampleRenderResponse, MusicStatusResponse, MusicTrackListResponse, MusicTrackResponse
from app.services.auth_service import AuthenticatedUser
from app.services.music_service import MusicError, MusicService
from app.services.operations_service import OperationsService


router = APIRouter(prefix="/api/music", tags=["Music"])


@router.get("/status", response_model=MusicStatusResponse)
def music_status(_user: AuthenticatedUser = Depends(require_user)):
    return MusicStatusResponse(**MusicService.status())


@router.get("/tracks", response_model=MusicTrackListResponse)
def list_tracks(user: AuthenticatedUser = Depends(require_user)):
    return MusicTrackListResponse(tracks=[MusicTrackResponse(**track) for track in MusicService.list_for(user)])


@router.post("/tracks", response_model=MusicTrackResponse)
async def upload_track(
    file: Annotated[UploadFile, File(...)],
    user: AuthenticatedUser = Depends(require_user),
):
    try:
        content = await file.read(MusicService._max_upload_bytes + 1)
        result = MusicService.create(user, file.filename or "audio.wav", content)
        OperationsService.record(user.id, "music_uploaded", mode="music", outcome="ok", detail="private WAV uploaded")
        return MusicTrackResponse(**result)
    except MusicError as error:
        OperationsService.record(user.id, "music_uploaded", mode="music", outcome="failed", detail="music upload rejected")
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()


@router.post("/{music_id}/analyze", response_model=MusicAnalysisResponse)
def analyze_track(music_id: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        analysis = MusicService.analyze(user, music_id)
        OperationsService.record(user.id, "music_analyzed", mode="music", outcome="ok", detail="local WAV analysis completed")
        return MusicAnalysisResponse(music_id=music_id, analysis=analysis)
    except MusicError as error:
        OperationsService.record(user.id, "music_analyzed", mode="music", outcome="failed", detail="local WAV analysis failed")
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{music_id}/analysis", response_model=MusicAnalysisResponse)
def get_analysis(music_id: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        return MusicAnalysisResponse(music_id=music_id, analysis=MusicService.analysis_for(user, music_id))
    except MusicError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{music_id}/sampled-audio", response_model=MusicSampleRenderResponse)
def render_sampled_audio(
    music_id: str,
    request: MusicSampleRenderRequest,
    user: AuthenticatedUser = Depends(require_user),
):
    try:
        result = MusicService.render_sampled(user, music_id, request.instrument)
        OperationsService.record(user.id, "music_sampled_rendered", mode="music", outcome="ok", detail="private sampled music render completed")
        return MusicSampleRenderResponse(
            **result,
            audio_url=f"/api/music/{music_id}/sampled-audio/{request.instrument}",
        )
    except MusicError as error:
        OperationsService.record(user.id, "music_sampled_rendered", mode="music", outcome="failed", detail="private sampled music render failed")
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{music_id}/sampled-audio/{instrument}", include_in_schema=False)
def get_sampled_audio(music_id: str, instrument: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        path = MusicService.sampled_audio_path_for(user, music_id, instrument)
    except MusicError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type="audio/wav", filename=f"mycodex-{instrument}.wav", content_disposition_type="inline")


@router.get("/{music_id}/audio", include_in_schema=False)
def get_audio(music_id: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        path = MusicService.audio_path_for(user, music_id)
    except MusicError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type="audio/wav", filename="source.wav", content_disposition_type="inline")


@router.get("/{music_id}/source", include_in_schema=False)
def get_source(music_id: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        path, media_type, filename = MusicService.source_path_for(user, music_id)
    except MusicError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type=media_type, filename=filename, content_disposition_type="inline")


@router.get("/{music_id}/downloads/{artifact}", include_in_schema=False)
def download_artifact(music_id: str, artifact: str, user: AuthenticatedUser = Depends(require_user)):
    try:
        path, media_type, filename = MusicService.artifact_for(user, music_id, artifact)
    except MusicError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return FileResponse(path, media_type=media_type, filename=filename, content_disposition_type="attachment")
