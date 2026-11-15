import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.knowledge_card_repository import InMemoryKnowledgeCardRepository
from app.services.knowledge_card_service import KnowledgeCardService, get_knowledge_card_service


def valid_card_payload() -> dict[str, object]:
    return {
        "id": "resp-01",
        "type": "risk",
        "system": "respiratory",
        "metrics": ["spo2", "respiratory_rate"],
        "direction": "down",
        "text": "Relevant source-based health information for respiratory measurements.",
        "source": "NASA Technical Brief",
        "url": "https://example.com/source",
        "locator": "Section 2, page 4",
    }


@pytest.fixture
def client() -> TestClient:
    service = KnowledgeCardService(InMemoryKnowledgeCardRepository())
    app.dependency_overrides[get_knowledge_card_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_cards_starts_empty(client: TestClient) -> None:
    response = client.get("/api/knowledge-cards")

    assert response.status_code == 200
    assert response.json() == []


def test_create_then_get_card(client: TestClient) -> None:
    payload = valid_card_payload()

    created = client.post("/api/knowledge-cards", json=payload)
    retrieved = client.get("/api/knowledge-cards/resp-01")

    assert created.status_code == 201
    assert created.json()["id"] == "resp-01"
    assert retrieved.status_code == 200
    assert retrieved.json()["text"] == payload["text"]


def test_duplicate_card_id_is_rejected(client: TestClient) -> None:
    payload = valid_card_payload()
    client.post("/api/knowledge-cards", json=payload)

    response = client.post("/api/knowledge-cards", json=payload)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


def test_invalid_card_payload_is_rejected(client: TestClient) -> None:
    payload = valid_card_payload()
    payload["metrics"] = ["unsupported_metric"]

    response = client.post("/api/knowledge-cards", json=payload)

    assert response.status_code == 422


def test_get_missing_card_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/knowledge-cards/unknown-01")

    assert response.status_code == 404


def test_replace_existing_card(client: TestClient) -> None:
    payload = valid_card_payload()
    client.post("/api/knowledge-cards", json=payload)
    payload["text"] = "Updated source-based information."

    response = client.put("/api/knowledge-cards/resp-01", json=payload)

    assert response.status_code == 200
    assert response.json()["text"] == "Updated source-based information."


def test_replace_rejects_different_path_and_payload_ids(client: TestClient) -> None:
    response = client.put("/api/knowledge-cards/path-id", json=valid_card_payload())

    assert response.status_code == 422


def test_replace_missing_card_returns_not_found(client: TestClient) -> None:
    response = client.put("/api/knowledge-cards/resp-01", json=valid_card_payload())

    assert response.status_code == 404


def test_delete_existing_card_and_then_report_not_found(client: TestClient) -> None:
    client.post("/api/knowledge-cards", json=valid_card_payload())

    deleted = client.delete("/api/knowledge-cards/resp-01")
    missing = client.get("/api/knowledge-cards/resp-01")

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404


def test_delete_missing_card_returns_not_found(client: TestClient) -> None:
    response = client.delete("/api/knowledge-cards/unknown-01")

    assert response.status_code == 404
