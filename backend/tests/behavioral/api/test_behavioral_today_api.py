"""GET /today, /docs bearer şeması ve geliştirme sunucusunun seed yüklemesi."""
import json

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/behavioral"
A007 = {"Authorization": "Bearer A007"}


def test_get_today(client):
    resp = client.get(f"{BASE}/today", headers=A007)
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == "2026-11-14" and body["mission_day"] == 75
    assert body["checkin"] == {"done": False, "etag": None} and body["tests_due"] == []
    assert body["signals"]["checkin_missing"] is True


def test_get_today_without_token(client):
    resp = client.get(f"{BASE}/today")
    assert resp.status_code == 401 and resp.json()["detail"]["code"] == "unauthorized"


def test_openapi_has_bearer_scheme(client):
    spec = client.get("/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    assert any(s == {**s, "type": "http", "scheme": "bearer"} for s in schemes.values())
    assert spec["paths"][f"{BASE}/today"]["get"]["security"]


# ---------------------------------------------------------------- geliştirme sunucusu

@pytest.fixture
def fresh_dev_repos(monkeypatch):
    """Geliştirme sunucusunun modül düzeyindeki repository'lerini test için boş olanlarla değiştirir."""
    import app.api.deps_behavioral as deps
    from app.repositories.behavioral_memory import (
        InMemoryCheckinRepository, InMemoryCognitiveTestRepository, InMemoryWeeklyRepository,
    )
    monkeypatch.setattr(deps, "_checkin_repo", InMemoryCheckinRepository())
    monkeypatch.setattr(deps, "_test_repo", InMemoryCognitiveTestRepository())
    monkeypatch.setattr(deps, "_weekly_repo", InMemoryWeeklyRepository())


@pytest.fixture
def seed_dir(tmp_path):
    from scripts.seed_behavioral import generate
    for name, rows in generate().items():
        (tmp_path / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
    return tmp_path


def test_dev_app_loads_seed(fresh_dev_repos, seed_dir, monkeypatch):
    from app.behavioral_dev_app import app
    monkeypatch.setenv("BEHAVIORAL_LOAD_SEED", "1")
    monkeypatch.setenv("BEHAVIORAL_SEED_DIR", str(seed_dir))
    monkeypatch.setenv("BEHAVIORAL_FIXED_NOW", "2026-11-14T09:00:00Z")
    with TestClient(app) as client:
        checkins = client.get(f"{BASE}/checkins", headers=A007).json()
        assert len(checkins["items"]) == 30 and checkins["items"][0]["date"] == "2026-11-13"
        tests = client.get(f"{BASE}/cognitive-tests", headers=A007).json()
        assert tests["items"]
        today = client.get(f"{BASE}/today", headers=A007).json()
        assert today["signals"]["last_checkin_date"] == "2026-11-13"
        assert today["signals"]["checkin_missing"] is False


def test_dev_app_without_seed_starts_empty(fresh_dev_repos, monkeypatch):
    from app.behavioral_dev_app import app
    monkeypatch.delenv("BEHAVIORAL_LOAD_SEED", raising=False)
    with TestClient(app) as client:
        assert client.get(f"{BASE}/checkins", headers=A007).json()["items"] == []


def test_dev_app_missing_seed_files_clear_error(fresh_dev_repos, tmp_path, monkeypatch):
    from app.behavioral_dev_app import app
    monkeypatch.setenv("BEHAVIORAL_LOAD_SEED", "1")
    monkeypatch.setenv("BEHAVIORAL_SEED_DIR", str(tmp_path / "nowhere"))
    with pytest.raises(FileNotFoundError, match="python -m scripts.seed_behavioral seed_output"):
        with TestClient(app):
            pass
