"""API testleri: her test için taze bellek içi repository'ler ve sabit saat (2026-11-14T09:00:00Z).

Servis fixture'ları üst klasördeki conftest.py'den gelir (checkin_service, cognitive_service,
weekly_service, clock); burada yalnız dependency_overrides ile uygulamaya bağlanır.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.api.behavioral_errors_http import register_behavioral_error_handlers
from app.api.deps_behavioral import (
    get_checkin_service, get_test_service, get_today_service, get_weekly_service,
)
from app.routers.behavioral import router


class OtherBody(BaseModel):
    """Davranış dışı sahte uç noktanın gövdesi (varsayılan 422 biçimini görmek için)."""
    model_config = ConfigDict(extra="forbid")
    name: str
    count: int


@pytest.fixture
def api_app(checkin_service, cognitive_service, weekly_service, today_service) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    register_behavioral_error_handlers(app)

    @app.post("/other")
    def other(body: OtherBody) -> dict:
        return {"ok": True}

    app.dependency_overrides[get_checkin_service] = lambda: checkin_service
    app.dependency_overrides[get_test_service] = lambda: cognitive_service
    app.dependency_overrides[get_weekly_service] = lambda: weekly_service
    app.dependency_overrides[get_today_service] = lambda: today_service
    return app


@pytest.fixture
def client(api_app) -> TestClient:
    with TestClient(api_app) as c:
        yield c
