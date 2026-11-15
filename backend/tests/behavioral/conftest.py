"""Ortak test fixture'ları: sabit saat, bellek içi repository'ler ve servisler."""
from datetime import date, datetime, timezone

import pytest

from app.repositories.behavioral_memory import (
    InMemoryCheckinRepository, InMemoryCognitiveTestRepository, InMemoryWeeklyRepository,
)
from app.services.behavioral_checkins import CheckinService
from app.services.behavioral_tests import CognitiveTestService
from app.services.behavioral_weekly import WeeklyService

MISSION_START = date(2026, 9, 1)
FIXED_NOW = datetime(2026, 11, 14, 9, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Testte elle ilerletilebilen saat."""

    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(FIXED_NOW)


@pytest.fixture
def checkin_repo() -> InMemoryCheckinRepository:
    return InMemoryCheckinRepository()


@pytest.fixture
def checkin_service(checkin_repo, clock) -> CheckinService:
    return CheckinService(checkin_repo, MISSION_START, clock)


@pytest.fixture
def cognitive_repo() -> InMemoryCognitiveTestRepository:
    return InMemoryCognitiveTestRepository()


@pytest.fixture
def cognitive_service(cognitive_repo, clock) -> CognitiveTestService:
    return CognitiveTestService(cognitive_repo, MISSION_START, clock)


@pytest.fixture
def weekly_repo() -> InMemoryWeeklyRepository:
    return InMemoryWeeklyRepository()


@pytest.fixture
def weekly_service(weekly_repo, clock) -> WeeklyService:
    return WeeklyService(weekly_repo, MISSION_START, clock)


@pytest.fixture
def today_service(checkin_repo, cognitive_repo, weekly_repo, clock):
    from app.services.behavioral_today import TodayService
    return TodayService(checkin_repo, cognitive_repo, weekly_repo, MISSION_START, clock)


@pytest.fixture
def metrics_feed(checkin_repo, cognitive_repo, clock):
    from app.services.behavioral_feed import DailyMetricsFeed
    return DailyMetricsFeed(checkin_repo, cognitive_repo, MISSION_START, clock)
