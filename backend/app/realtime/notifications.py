"""Authenticated WebSocket outbox with receipt-backed replay."""

import asyncio
from datetime import UTC
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.errors import ApiError
from app.schemas.common import CurrentUser, WS_NOTIFICATIONS_PATH
from app.services import notifications


router = APIRouter()


def _timestamp(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@router.websocket(WS_NOTIFICATIONS_PATH)
async def notification_socket(ws: WebSocket):
    await ws.accept()
    settings = ws.app.state.notification_settings
    auth = ws.app.state.auth_service
    try:
        hello = await asyncio.wait_for(ws.receive_json(), settings.ws_auth_timeout_seconds)
        if (not isinstance(hello, dict) or hello.get("type") != "authenticate"
                or not isinstance(hello.get("access_token"), str)):
            await ws.close(code=1008)
            return
        token = hello["access_token"]
        public_user = await run_in_threadpool(auth.resolve_user, token)
        user = CurrentUser(user_id=public_user.user_id, role=public_user.role,
                           astronaut_id=public_user.astronaut_id)
        sent: set[UUID] = set()
        acknowledged: set[UUID] = set()
        while True:
            # Rechecking the token and account also closes a revoked or expired session.
            await run_in_threadpool(auth.resolve_user, token)
            events = await run_in_threadpool(notifications.pending_for_delivery, user, sent)
            for event in events:
                await ws.send_json({"event_id": str(event.event_id), "type": event.event_type.value,
                                    "created_at": _timestamp(event.created_at), "payload": event.payload})
                sent.add(event.event_id)
            try:
                message = await asyncio.wait_for(ws.receive_json(), timeout=1)
            except TimeoutError:
                continue
            if (not isinstance(message, dict) or message.get("type") != "receipt"
                    or not isinstance(message.get("event_id"), str)):
                await ws.close(code=1008)
                return
            try:
                event_id = UUID(message["event_id"])
            except ValueError:
                await ws.close(code=1008)
                return
            if event_id in acknowledged:
                continue
            if event_id not in sent:
                await ws.close(code=1008)
                return
            await run_in_threadpool(notifications.receipt, event_id, user)
            sent.discard(event_id)
            acknowledged.add(event_id)
    except (TimeoutError, ValueError, ApiError):
        await ws.close(code=1008)
    except WebSocketDisconnect:
        pass
