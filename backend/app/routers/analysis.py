"""Ö2 job endpoints. All operations are restricted to the live astronaut."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.core.errors import ApiError
from app.core.security import require_active_astronaut
from app.schemas.analysis import (
    AnalysisJobRequest, JobAcceptedResponse, JobStatusResponse, RetryJobRequest,
)
from app.schemas.common import CurrentUser, ErrorCode
from app.services.analysis import AnalysisService

router = APIRouter(prefix="/analysis/jobs", tags=["analysis"])


def get_analysis_service(request: Request) -> AnalysisService:
    service = getattr(request.app.state, "analysis_service", None)
    if service is None:
        raise ApiError(503, ErrorCode.SERVICE_UNAVAILABLE,
                       "Analiz işi veri katmanı henüz hazır değil.")
    return service


@router.post("", response_model=JobAcceptedResponse, status_code=202,
             responses={200: {"model": JobAcceptedResponse, "description": "Mevcut iş"}})
def create_job(
    body: AnalysisJobRequest,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_active_astronaut)],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> JobAcceptedResponse:
    submission = service.create(user, body)
    response.status_code = 202 if submission.created else 200
    response.headers["Location"] = submission.response.status_url
    response.headers["Cache-Control"] = "no-store"
    return submission.response


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_active_astronaut)],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> JobStatusResponse:
    result = service.get(user, job_id)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/{job_id}/retry", response_model=JobAcceptedResponse, status_code=202)
def retry_job(
    job_id: UUID,
    response: Response,
    user: Annotated[CurrentUser, Depends(require_active_astronaut)],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
    body: RetryJobRequest | None = None,
) -> JobAcceptedResponse:
    result = service.retry(user, job_id)
    response.headers["Location"] = result.status_url
    response.headers["Cache-Control"] = "no-store"
    return result
