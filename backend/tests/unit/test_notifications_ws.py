from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.realtime.notifications import router
from app.schemas.common import EventType, Role
from app.services import notifications


def test_websocket_auth_delivery_and_receipt(monkeypatch):
    user_id, event_id = uuid4(), uuid4()
    event = SimpleNamespace(event_id=event_id, event_type=EventType.ANALYSIS_COMPLETED,
                            created_at=datetime(2026, 11, 15, tzinfo=UTC), payload={"job_id": "test"})
    app = FastAPI()
    app.include_router(router)
    app.state.notification_settings = SimpleNamespace(ws_auth_timeout_seconds=1)
    app.state.auth_service = SimpleNamespace(resolve_user=lambda token: SimpleNamespace(
        user_id=user_id, role=Role.ASTRONAUT, astronaut_id="A007") if token == "valid" else None)
    receipts = []
    monkeypatch.setattr(notifications, "pending_for_delivery",
                        lambda user, sent: [event] if event_id not in sent and event_id not in receipts else [])
    monkeypatch.setattr(notifications, "receipt", lambda identity, user: receipts.append(identity))
    with TestClient(app).websocket_connect("/ws/v1/notifications") as ws:
        ws.send_json({"type": "authenticate", "access_token": "valid"})
        message = ws.receive_json()
        assert message == {"event_id": str(event_id), "type": "analysis.completed",
                           "created_at": "2026-11-15T00:00:00Z", "payload": {"job_id": "test"}}
        ws.send_json({"type": "receipt", "event_id": str(event_id)})
        ws.send_json({"type": "receipt", "event_id": str(event_id)})
        ws.send_json({"type": "receipt", "event_id": str(uuid4())})
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 1008
    assert receipts == [event_id]
