from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import require_admin
from app.schemas.learning import TrainingEvaluationRequest, TrainingExampleRequest, TrainingOverviewResponse
from app.services.auth_service import AuthenticatedUser
from app.services.operations_service import OperationsService
from app.services.training_service import TrainingError, TrainingService


router = APIRouter(prefix="/api/learning", tags=["Training"])


@router.get("/overview", response_model=TrainingOverviewResponse)
def overview(user: AuthenticatedUser = Depends(require_admin)):
    return TrainingOverviewResponse(**TrainingService.overview(user))


@router.post("/examples")
def add_example(request: TrainingExampleRequest, user: AuthenticatedUser = Depends(require_admin)):
    try:
        result = TrainingService.add_example(user, request.instruction, request.ideal_response, request.tags)
        OperationsService.record(user.id, "training_example_added", outcome="ok", detail="manual approved example")
        return result
    except TrainingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/evaluations")
def add_evaluation(request: TrainingEvaluationRequest, user: AuthenticatedUser = Depends(require_admin)):
    try:
        return TrainingService.add_evaluation(user, request.prompt, request.required_terms)
    except TrainingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/evaluations/run")
def run_evaluations(user: AuthenticatedUser = Depends(require_admin)):
    try:
        report = TrainingService.run_evaluations(user)
        OperationsService.record(user.id, "training_evaluation_run", outcome="ok", detail=f"score {report['score_percent']} percent")
        return report
    except TrainingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/exports")
def export_jsonl(user: AuthenticatedUser = Depends(require_admin)):
    try:
        result = TrainingService.export_jsonl(user)
        OperationsService.record(user.id, "training_export_created", outcome="ok", detail="chat jsonl export")
        return result
    except TrainingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/exports/{file_name}")
def download_export(file_name: str, user: AuthenticatedUser = Depends(require_admin)):
    try:
        path = TrainingService.export_path(user, file_name)
        return FileResponse(path, media_type="application/jsonl", filename=file_name)
    except TrainingError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
