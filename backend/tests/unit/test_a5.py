"""A5 kabul (DB'siz): VIEW içerik kuralları, DTO eşlemesi, tam repository arayüzü."""
import datetime as dt
import inspect
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.repositories.interfaces import MeasurementRepository, Repository
from app.repositories.sqlalchemy_measurements import MissingDefinition, _rows_to_dtos
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository

VIEWS = (Path(__file__).parents[2] / "migrations/versions/0006_views.py").read_text()
V = VIEWS.split("V_MEASUREMENTS = ")[1]


def test_three_views_with_select_only():
    for v in ("[sans].[gorev]", "[sans].[profil]", "[anomaly].[v_measurements]"):
        assert f"CREATE VIEW {v}" in VIEWS
    assert 'grant(view, APP_ROLE, "SELECT")' in VIEWS


def test_profil_shows_only_active_profile():
    assert "WHERE a.is_display_only = 0" in VIEWS.split("SANS_PROFIL")[1].split('"""')[1]


def test_v_measurements_sources_and_exclusions():
    for src in ("MeasurementRecords", "checkins", "cognitive_tests", "test_kaydi"):
        assert f"[{src}]" in V
    assert "weekly_assessments" not in V  # model girdisi değil
    assert "t.speed" not in V  # PVT speed formülü teyitsiz
    assert "WHEN 'seed' THEN 'synthetic'" in V
    assert "CAST(k.eye AS char(2))" in V  # OD/OS ayrı satır
    assert "CAST(NULL AS datetime2(3))" in V  # günlük kayda yapay saat yok


def test_record_id_formats():
    for prefix in ("physiological:", "checkin:", "cognitive:", "eye:"):
        assert f"'{prefix}'" in V


def row(**kw):
    base = dict(record_id="eye:1", astronaut_id="A007", mission_id="M01", module="sans",
                measurement="near_acuity", value_num=Decimal("-0.1"), value_text=None,
                unit="logMAR", protocol_version="module-v2", measured_date=dt.date(2027, 3, 20),
                measured_at=None, time_precision="date", mission_day=74, eye="OD", source="manual",
                valid=True, quality_score=Decimal("0.9"), session_id="S-A007-D074",
                metadata_json='{"original_source":"test_screen"}')
    return SimpleNamespace(_mapping=base | kw)


def test_rows_become_contract_dtos():
    (dto,) = _rows_to_dtos([row()])
    assert dto.value_num == Decimal("-0.1")  # negatif logMAR geçerli
    assert dto.metadata_json == {"original_source": "test_screen"}
    (cog,) = _rows_to_dtos([row(record_id="cognitive:8:pvt_mean_rt", module="behavioral",
                                measurement="pvt_mean_rt", eye=None, unit="ms",
                                time_precision="timestamp", session_id=None,
                                measured_at=dt.datetime(2027, 3, 20, 9, 30))])
    assert cog.model_dump(mode="json")["measured_at"] == "2027-03-20T09:30:00Z"


def test_missing_definition_is_loud():
    with pytest.raises(MissingDefinition, match="near_acuity"):
        _rows_to_dtos([row(protocol_version=None)])


def test_full_repository_contract_is_implemented():
    for name, fn in inspect.getmembers(Repository, inspect.isfunction):
        if name.startswith("_"):
            continue
        impl = getattr(SqlAlchemyRepository, name, None)
        assert impl is not None, f"eksik: {name}"
        assert list(inspect.signature(impl).parameters) == list(inspect.signature(fn).parameters), name
    assert issubclass(SqlAlchemyRepository, object) and MeasurementRepository
