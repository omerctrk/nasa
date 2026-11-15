"""Opt-in integration coverage against the centrally migrated SQL Server table."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


pytestmark = pytest.mark.integration


@pytest.fixture
def sqlserver_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Start the API in SQL Server mode only when a secure URL is configured."""
    get_settings.cache_clear()
    configured_settings = get_settings()
    if configured_settings.collab_db_password is None:
        pytest.skip("COLLAB_DB_PASSWORD is not configured; SQL Server integration test not run.")
    if os.environ.get("ASTRA_RUN_SQLSERVER_INTEGRATION_TESTS") != "true":
        pytest.skip("ASTRA_RUN_SQLSERVER_INTEGRATION_TESTS=true is required to run this test.")

    monkeypatch.setenv("ASTRA_KNOWLEDGE_CARD_REPOSITORY", "sqlserver")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            yield client
    finally:
        get_settings.cache_clear()


def test_sqlserver_knowledge_card_crud_and_validation(sqlserver_client: TestClient) -> None:
    """Use one unique record and remove it after exercising all API CRUD paths."""
    card_id = f"sql-integration-{uuid4().hex}"
    print(f"TEST_RECORD_ID={card_id}")
    payload = {
        "id": card_id,
        "type": "risk",
        "system": "renal",
        "metrics": ["heart_rate"],
        "direction": "up",
        "text": "Temporary SQL Server integration test record for safe CRUD verification.",
        "source": "ASTRA HEALTH integration test",
        "url": "https://example.org/integration-tests/knowledge-card",
        "locator": "Automated temporary record",
    }
    try:
        created = sqlserver_client.post("/api/knowledge-cards", json=payload)
        assert created.status_code == 201
        assert created.json()["id"] == card_id

        listed = sqlserver_client.get("/api/knowledge-cards")
        assert listed.status_code == 200
        assert card_id in {item["id"] for item in listed.json()}

        retrieved = sqlserver_client.get(f"/api/knowledge-cards/{card_id}")
        assert retrieved.status_code == 200
        assert retrieved.json()["text"] == payload["text"]

        duplicate = sqlserver_client.post("/api/knowledge-cards", json=payload)
        assert duplicate.status_code == 409

        updated_payload = {**payload, "text": "Updated temporary SQL Server integration test record."}
        updated = sqlserver_client.put(f"/api/knowledge-cards/{card_id}", json=updated_payload)
        assert updated.status_code == 200
        assert updated.json()["text"] == updated_payload["text"]

        retrieved_updated = sqlserver_client.get(f"/api/knowledge-cards/{card_id}")
        assert retrieved_updated.status_code == 200
        assert retrieved_updated.json()["text"] == updated_payload["text"]

        missing = sqlserver_client.get(f"/api/knowledge-cards/{card_id}-missing")
        assert missing.status_code == 404

        invalid_payload = {**payload, "id": f"sql-integration-invalid-{uuid4().hex}", "type": "unknown"}
        invalid = sqlserver_client.post("/api/knowledge-cards", json=invalid_payload)
        assert invalid.status_code == 422
    finally:
        deleted = sqlserver_client.delete(f"/api/knowledge-cards/{card_id}")
        assert deleted.status_code in {204, 404}

    absent_after_delete = sqlserver_client.get(f"/api/knowledge-cards/{card_id}")
    assert absent_after_delete.status_code == 404
