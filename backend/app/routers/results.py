"""Scoped anomaly result reads."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security import current_user
from app.schemas.common import CurrentUser
from app.schemas.results import AnomalyResultOut
from app.services.results import get_anomaly_result


router = APIRouter(tags=["analysis results"])


@router.get("/anomaly/results/{result_id}", response_model=AnomalyResultOut)
def result(result_id: UUID, user: Annotated[CurrentUser, Depends(current_user)]):
    return get_anomaly_result(result_id, user)
