"""GET /api/v1/thresholds: analizle aynı politika, ondalık metin, kimlik zorunlu."""
import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.routers.deps import current_user
from app.schemas.common import CurrentUser

POLICY = json.loads((Path(__file__).resolve().parents[2] / "config/thresholds.json").read_text(encoding="utf-8"))


def test_requires_login():
    r = TestClient(app).get("/api/v1/thresholds")
    assert r.status_code == 401


def test_returns_same_rules_as_analysis_policy_with_exact_decimals():
    app.dependency_overrides[current_user] = lambda: CurrentUser(
        user_id=uuid.uuid4(), role="ASTRONAUT", astronaut_id="A007")
    try:
        r = TestClient(app).get("/api/v1/thresholds")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["version"] == POLICY["version"] and body["boundary"] == "inclusive"
    got = {x["measurement"]: x for x in body["rules"]}
    for rule in POLICY["rules"]:
        out = got[rule["measurement"]]
        assert out["unit"] == rule["unit"] and out["module"] == rule["module"]
        for side in ("lower", "upper"):
            assert (out[side] is None) == (rule.get(side) is None)
            if rule.get(side) is not None:
                assert float(out[side]) == float(rule[side])
    assert got["spo2"]["lower"] == "95" and got["spo2"]["upper"] is None
    assert got["body_temperature"]["upper"] == "37.10"  # ondalık yuvarlanmaz
    assert got["heart_rate"]["unit"] == "BPM" and got["body_temperature"]["unit"] == "°C"
