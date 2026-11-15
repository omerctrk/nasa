from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.repositories.errors import NotFound
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
