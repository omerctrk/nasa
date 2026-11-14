"""Durable notification reads and receipts; alert routes live in alerts.py."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security import current_user
from app.repositories.records import NotificationEventRecord
from app.schemas.common import CurrentUser
from app.schemas.notifications import ReceiptResponse
from app.services import notifications


router = APIRouter(tags=["notifications"])
User = Annotated[CurrentUser, Depends(current_user)]


@router.get("/notifications/pending", response_model=list[NotificationEventRecord])
def pending(user: User):
    return notifications.pending_events(user)


@router.post("/notifications/{event_id}/receipt", response_model=ReceiptResponse)
def receipt(event_id: UUID, user: User):
    return ReceiptResponse(recorded=notifications.receipt(event_id, user), event_id=event_id)
