"""Knowledge Card contract and access boundary without a database."""

import pytest
from pydantic import ValidationError

from app.routers.deps import require_ground_control
from app.routers.knowledge import router
from app.schemas.knowledge import KnowledgeCardCreate
from app.services.knowledge import _digest


def test_all_knowledge_routes_require_ground_control():
    for route in router.routes:
        assert require_ground_control in {dependency.call for dependency in route.dependant.dependencies}


def test_content_hash_is_canonical_and_validation_rejects_bad_metrics():
    left = {"type": "risk", "system": "mental", "metrics": ["sleep_hours"]}
    assert _digest(left) == _digest(dict(reversed(list(left.items()))))
    assert _digest(left) != _digest(left | {"metrics": ["stress"]})
    body = dict(card_id="sleep-01", type="risk", system="mental", metrics=["sleep_hours"],
                direction="any", text="Evidence", source="paper", url="https://example.invalid",
                locator="Abstract")
    assert KnowledgeCardCreate.model_validate(body).card_id == "sleep-01"
    with pytest.raises(ValidationError):
        KnowledgeCardCreate.model_validate(body | {"metrics": [""]})
