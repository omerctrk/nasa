"""A8 demo verisi: Şule'nin 74 günlük senaryosu gerçek DB'ye yüklenir, tekrar yüklemek çift kayıt üretmez.

Uygulama hesabının DELETE izni yok; DB'de demo verisi zaten varsa ilk yükleme 0 ekler. Bu yüzden
test sayıları değil sonuçtaki durumu ve ikinci yüklemenin hiçbir şey eklememesini doğrular.
"""
from sqlalchemy import func, select

from app.models.behavioral import Checkin, CognitiveTest, WeeklyAssessment
from scripts import demo_data, seed


def test_demo_data_loads_once_onto_mission_calendar(db):
    seed.run_seed(db, "astro-pw", "kule-pw")
    first = demo_data.load(db, align=False)
    assert all(0 <= n for n in first.values())
    assert demo_data.load(db, align=False) == {"checkins": 0, "cognitive_tests": 0, "weekly_assessments": 0}
    days = set(db.scalars(select(Checkin.mission_day).where(Checkin.astronaut_id == "A007",
                                                             Checkin.source == "seed")))
    assert set(range(1, 75)) <= days
    count = lambda m: db.scalar(select(func.count()).select_from(m).where(  # noqa: E731
        m.astronaut_id == "A007", m.source == "seed"))
    assert count(CognitiveTest) >= 44 and count(WeeklyAssessment) >= 10
