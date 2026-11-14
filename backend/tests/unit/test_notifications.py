from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import install_error_handling
from app.core.security import current_user
from app.repositories.errors import NotFound
from app.routers.notifications import router
from app.schemas.common import CurrentUser, Role
from app.services import notifications


def test_receipt_cannot_acknowledge_another_users_event(monkeypatch):
    own_id, other_id = uuid4(), uuid4()
    user = CurrentUser(user_id=uuid4(), role=Role.ASTRONAUT, astronaut_id="A007")
    recorded = []

    class Repo:
        def list_pending_events(self, user_id):
            assert user_id == user.user_id
            return [SimpleNamespace(event_id=own_id)]

        def record_receipt(self, event_id, user_id):
            recorded.append((event_id, user_id))
            return True

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        @contextmanager
        def begin(self):
            yield self

    monkeypatch.setattr(notifications, "SessionLocal", Session)
    monkeypatch.setattr(notifications, "SqlAlchemyRepository", lambda session: Repo())
    with pytest.raises(NotFound):
        notifications.receipt(other_id, user)
    assert recorded == []
    assert notifications.receipt(own_id, user) is True
    assert recorded == [(own_id, user.user_id)]


def test_ground_alert_route_rejects_astronaut(monkeypatch):
    app = FastAPI()
    install_error_handling(app)
    app.include_router(router, prefix="/api/v1")
    user = CurrentUser(user_id=uuid4(), role=Role.ASTRONAUT, astronaut_id="A007")
    app.dependency_overrides[current_user] = lambda: user
    monkeypatch.setattr(notifications, "list_alerts", lambda status: [])
    client = TestClient(app)
    assert client.get("/api/v1/ground/alerts").status_code == 403
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=user.user_id, role=Role.GROUND_CONTROL, astronaut_id=None)
    assert client.get("/api/v1/ground/alerts").json() == []
