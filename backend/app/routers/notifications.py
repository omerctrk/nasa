"""Ground alert management and durable notification reads/receipts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security import current_user, require_ground_control
from app.repositories.records import AlertRecord, NotificationEventRecord
from app.schemas.common import AlertStatus, CurrentUser
from app.schemas.notifications import ReceiptResponse, ResolveAlertRequest
from app.services import notifications


router = APIRouter(tags=["notifications"])
Ground = Annotated[CurrentUser, Depends(require_ground_control)]
User = Annotated[CurrentUser, Depends(current_user)]


@router.get("/ground/alerts", response_model=list[AlertRecord])
def ground_alerts(user: Ground, status: AlertStatus | None = None):
    return notifications.list_alerts(status)


@router.post("/ground/alerts/{alert_id}/acknowledge", response_model=AlertRecord)
def acknowledge(alert_id: UUID, user: Ground):
    return notifications.acknowledge_alert(alert_id, user)


@router.post("/ground/alerts/{alert_id}/resolve", response_model=AlertRecord)
def resolve(alert_id: UUID, body: ResolveAlertRequest, user: Ground):
    return notifications.resolve_alert(alert_id, user, body.note)


@router.get("/notifications/pending", response_model=list[NotificationEventRecord])
def pending(user: User):
    return notifications.pending_events(user)


@router.post("/notifications/{event_id}/receipt", response_model=ReceiptResponse)
def receipt(event_id: UUID, user: User):
    return ReceiptResponse(recorded=notifications.receipt(event_id, user), event_id=event_id)
