"""WebSocket bildirimleri ve sonuç/alarm uçlarının DB'siz testleri."""
import time
import uuid

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.errors import ApiError
from app.realtime import notifications as ws_mod
from app.routers import alerts
from app.routers.deps import require_active_astronaut, require_ground_control
from app.schemas.common import CurrentUser, ErrorCode, Role

USER = CurrentUser(user_id=uuid.uuid4(), role=Role.ASTRONAUT, astronaut_id="A007")


def token(exp_in=3600):
    return jwt.encode({"sub": str(USER.user_id), "exp": int(time.time()) + exp_in}, "k" * 48)


class FakeAuth:
    def resolve_user(self, tok):
        if tok == "bad":
            raise ApiError(401, ErrorCode.UNAUTHORIZED, "x")
        return USER


@pytest.fixture
def client(monkeypatch):
    sent, receipts = [], []
    event = {"event_id": str(uuid.uuid4()), "type": "analysis.completed",
             "created_at": "2027-03-15T08:00:00.000Z", "payload": {"job_id": "j"}}

    def pending(user_id, already):
        assert user_id == USER.user_id
        sent.append(set(already))
        return [] if uuid.UUID(event["event_id"]) in already else [event]
    monkeypatch.setattr(ws_mod, "_pending", pending)
    monkeypatch.setattr(ws_mod, "_receipt", lambda e, u: receipts.append((e, u)))
    app = FastAPI()
    app.state.auth_service = FakeAuth()
    ws_mod.install_notifications(app)
    with TestClient(app) as c:
        yield c, event, sent, receipts


def test_authenticate_then_event_then_receipt(client):
    c, event, _, receipts = client
    with c.websocket_connect("/ws/v1/notifications") as ws:
        ws.send_json({"type": "authenticate", "access_token": token()})
        assert ws.receive_json()["type"] == "authenticated"
        assert ws.receive_json() == event
        ws.send_json({"type": "receipt", "event_id": event["event_id"]})
        ws.send_json({"type": "receipt", "event_id": str(uuid.uuid4())})  # gönderilmemiş: yok sayılır
        ws.send_json({"type": "receipt", "event_id": "bozuk"})
        time.sleep(0.2)
    assert receipts == [(uuid.UUID(event["event_id"]), USER.user_id)]


@pytest.mark.parametrize("first", [
    {"type": "authenticate", "access_token": "bad"},
    {"type": "hello"},
    {"type": "authenticate"},
])
def test_bad_authentication_closes_4401(client, first):
    c = client[0]
    with c.websocket_connect("/ws/v1/notifications") as ws:
        ws.send_json(first)
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4401


def test_expired_token_closes_4401(client):
    c = client[0]
    with c.websocket_connect("/ws/v1/notifications") as ws:
        ws.send_json({"type": "authenticate", "access_token": token(exp_in=-1)})
        assert ws.receive_json()["type"] == "authenticated"
        with pytest.raises(WebSocketDisconnect) as exc:
            for _ in range(5):
                ws.receive_json()
    assert exc.value.code == 4401


def test_alert_routes_have_role_guards():
    expected = {
        ("GET", "/me/anomaly-results"): require_active_astronaut,
        ("GET", "/me/anomaly-results/{result_id}"): require_active_astronaut,
        ("GET", "/me/alerts"): require_active_astronaut,
        ("GET", "/ground/astronauts/{astronaut_id}/anomaly-results"): require_ground_control,
        ("GET", "/ground/anomaly-results/{result_id}"): require_ground_control,
        ("GET", "/ground/alerts"): require_ground_control,
        ("POST", "/ground/alerts/{alert_id}/acknowledge"): require_ground_control,
        ("POST", "/ground/alerts/{alert_id}/resolve"): require_ground_control,
    }
    found = {}
    for router in (alerts.me, alerts.ground):
        for route in router.routes:
            for method in route.methods:
                found[(method, route.path)] = {d.call for d in route.dependant.dependencies}
    for key, guard in expected.items():
        assert guard in found[key], key


def test_main_app_registers_ws_and_alert_routes():
    from app.main import app
    assert any(getattr(r, "original_router", None) is ws_mod.router for r in app.routes)
    assert [r.path for r in ws_mod.router.routes] == ["/ws/v1/notifications"]
    paths = app.openapi()["paths"]
    assert "/api/v1/ground/alerts/{alert_id}/resolve" in paths
    assert "/api/v1/me/anomaly-results/{result_id}" in paths
