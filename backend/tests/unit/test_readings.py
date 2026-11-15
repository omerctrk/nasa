"""Okuma uçları (DB'siz): yetki bağları, aralık kuralları, hassas alan yok."""
import datetime as dt

import pytest

from app.repositories.errors import ValidationFailed
from app.routers import readings as r
from app.routers.deps import require_active_astronaut, require_ground_control
from app.schemas.readings import CognitiveDetailOut, ProfileOut
from app.services.readings import check_range


def deps(route):
    return {d.call for d in route.dependant.dependencies}


def test_me_routes_need_astronaut_and_ground_routes_need_ground_control():
    for route in r.me.routes:
        assert require_active_astronaut in deps(route), route.path
    for route in r.ground.routes:
        assert require_ground_control in deps(route), route.path


def test_range_rules():
    check_range(dt.date(2027, 3, 1), dt.date(2027, 3, 20))
    with pytest.raises(ValidationFailed):
        check_range(dt.date(2027, 3, 20), dt.date(2027, 3, 20))  # boş aralık
    with pytest.raises(ValidationFailed):
        check_range(dt.date(2026, 1, 1), dt.date(2027, 1, 1))  # 120 günden uzun


def test_no_sensitive_or_unconfirmed_fields_exposed():
    assert not {"mtrr66_g", "shmt1_1420_c", "b_vit_status", "optic_cup_vol", "age",
                "weight_kg"} & set(ProfileOut.model_fields)
    assert "speed" not in CognitiveDetailOut.model_fields  # formül teyitsiz
