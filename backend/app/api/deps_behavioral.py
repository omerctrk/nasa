"""Davranışsal modül FastAPI bağımlılıkları: kimlik ve servisler.

Testler bu fonksiyonları app.dependency_overrides ile değiştirir.
"""
from __future__ import annotations

import re
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.behavioral_settings import MISSION_START, utc_now
from app.repositories.behavioral_memory import (
    InMemoryCheckinRepository, InMemoryCognitiveTestRepository, InMemoryWeeklyRepository,
)
from app.services.behavioral_checkins import CheckinService
from app.services.behavioral_errors import BehavioralError
from app.services.behavioral_feed import DailyMetricsFeed
from app.services.behavioral_tests import CognitiveTestService
from app.services.behavioral_today import TodayService
from app.services.behavioral_weekly import WeeklyService

# ------------------------------------------------------------------------------------------
# TEMPORARY: backend auth gelince değiştirilecek.
# Şimdilik "Authorization: Bearer A007" başlığındaki token doğrudan astronaut_id kabul edilir.
# Gerçek auth geldiğinde yalnız get_current_astronaut_id değişir; router ve servisler aynı kalır.
# HTTPBearer, /docs'ta "Authorize" butonunu çıkarır; auto_error=False ile 401 cevabını biz üretiriz.
# ------------------------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False, description="TEMPORARY: the token is the astronaut id, e.g. A007")
_ASTRONAUT_ID = re.compile(r"^A\d{3}$")


def get_current_astronaut_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> str:
    if credentials is None or not _ASTRONAUT_ID.match(credentials.credentials):
        raise BehavioralError("unauthorized", "Missing or invalid bearer token")
    return credentials.credentials


# ------------------------------------------------------------------------------------------
# TEMPORARY: bellek içi repository'ler (süreç başına tek örnek; yeniden başlatınca boşalır).
# SQLAlchemy repository'leri gelince yalnız bu üç nesne ve aşağıdaki fabrikalar değişir.
# ------------------------------------------------------------------------------------------
_checkin_repo = InMemoryCheckinRepository()
_test_repo = InMemoryCognitiveTestRepository()
_weekly_repo = InMemoryWeeklyRepository()


def get_checkin_service() -> CheckinService:
    return CheckinService(_checkin_repo, MISSION_START, utc_now)


def get_test_service() -> CognitiveTestService:
    return CognitiveTestService(_test_repo, MISSION_START, utc_now)


def get_weekly_service() -> WeeklyService:
    return WeeklyService(_weekly_repo, MISSION_START, utc_now)


def get_today_service() -> TodayService:
    return TodayService(_checkin_repo, _test_repo, _weekly_repo, MISSION_START, utc_now)


def get_metrics_feed() -> DailyMetricsFeed:
    """Anomali modülü için (HTTP ucu yok). Haftalık repository'yi kasıtlı olarak almaz."""
    return DailyMetricsFeed(_checkin_repo, _test_repo, MISSION_START, utc_now)


def get_repositories():
    """Geliştirme sunucusunun seed yüklemesi için o anki bellek içi repository'ler."""
    return _checkin_repo, _test_repo, _weekly_repo
