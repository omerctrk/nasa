import pytest
from pydantic import ValidationError

from app.schemas.knowledge_card import KnowledgeCard


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


def test_valid_knowledge_card_is_accepted() -> None:
    card = KnowledgeCard.model_validate(valid_card_payload())

    assert card.id == "resp-01"
    assert card.metrics == ["spo2", "respiratory_rate"]


def test_empty_metrics_are_allowed() -> None:
    payload = valid_card_payload()
    payload["metrics"] = []

    assert KnowledgeCard.model_validate(payload).metrics == []


def test_missing_required_field_is_rejected() -> None:
    payload = valid_card_payload()
    del payload["locator"]

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)


def test_invalid_type_is_rejected() -> None:
    payload = valid_card_payload()
    payload["type"] = "diagnosis"

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)


def test_invalid_direction_is_rejected() -> None:
    payload = valid_card_payload()
    payload["direction"] = "sideways"

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)


def test_unknown_metric_is_rejected() -> None:
    payload = valid_card_payload()
    payload["metrics"] = ["unknown_metric"]

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)


def test_text_over_sixty_words_is_rejected() -> None:
    payload = valid_card_payload()
    payload["text"] = "word " * 61

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)


def test_invalid_url_is_rejected() -> None:
    payload = valid_card_payload()
    payload["url"] = "not-a-url"

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)


def test_unknown_system_is_rejected_without_remapping() -> None:
    payload = valid_card_payload()
    payload["system"] = "unapproved-system"

    with pytest.raises(ValidationError):
        KnowledgeCard.model_validate(payload)
