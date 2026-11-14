"""Knowledge Card API -> SQL Server CRUD; outer test transaction rolls back."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_db
from app.main import app
from app.models.knowledge import KnowledgeCard
from app.routers.deps import require_ground_control
from app.schemas.common import CurrentUser


@pytest.fixture
def api(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_ground_control] = lambda: CurrentUser(
        user_id=uuid4(), role="GROUND_CONTROL", astronaut_id=None)
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


def test_knowledge_card_crud_persists_through_api_and_deletes(api, db):
    card_id = f"test-{uuid4()}"
    body = dict(card_id=card_id, type="risk", system="mental", metrics=["sleep_hours"],
                direction="any", text="Integration test", source="test",
                url="https://example.invalid", locator="test")
    base = "/api/v1/knowledge-cards"

    created = api.post(base, json=body)
    assert created.status_code == 201, created.text
    assert len(created.json()["content_hash"]) == 64
    assert db.scalar(select(KnowledgeCard).where(KnowledgeCard.card_id == card_id)) is not None
    assert api.post(base, json=body).status_code == 409
    assert api.get(f"{base}/{card_id}").json()["text"] == "Integration test"
    assert any(row["card_id"] == card_id for row in api.get(base).json())

    replaced = api.put(f"{base}/{card_id}", json={k: v for k, v in body.items() if k != "card_id"}
                       | {"text": "Updated evidence", "metrics": ["stress"]})
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["text"] == "Updated evidence"
    assert replaced.json()["content_hash"] != created.json()["content_hash"]
    assert api.get(f"{base}/{card_id}").json()["metrics"] == ["stress"]

    assert api.delete(f"{base}/{card_id}").status_code == 204
    assert api.get(f"{base}/{card_id}").status_code == 404
    assert api.delete(f"{base}/{card_id}").status_code == 404
    assert db.get(KnowledgeCard, card_id) is None
