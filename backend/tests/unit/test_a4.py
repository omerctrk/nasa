"""A4 kabul (DB'siz): 20 fiziksel tablo, davranış kuralları, eval izolasyonu."""
from app.db.base import Base


def checks(table: str) -> str:
    return " | ".join(str(c.sqltext) for c in Base.metadata.tables[table].constraints
                      if hasattr(c, "sqltext"))


def test_twenty_physical_tables():
    assert len(Base.metadata.tables) == 20  # şema v5.0: 20 tablo + 3 VIEW (A5)


def test_checkin_unique_per_person_and_day():
    uqs = [tuple(c.name for c in u.columns) for u in Base.metadata.tables["behavioral.checkins"].constraints
           if u.__class__.__name__ == "UniqueConstraint"]
    assert ("astronaut_id", "date") in uqs


def test_cognitive_metrics_by_type():
    c = checks("behavioral.cognitive_tests")
    assert "test_type='pvt' AND accuracy IS NULL AND correct_count IS NULL" in c
    assert "(valid=1 AND invalid_reason IS NULL)" in c


def test_no_zero_fill_or_direction_assumptions():
    # speed/loneliness/crew yön ve formül teyitsiz: ek kural yok, yalnız aralık
    c = checks("behavioral.checkins")
    assert "loneliness BETWEEN 0 AND 4" in c and "crew BETWEEN 0 AND 4" in c
    t = Base.metadata.tables["behavioral.cognitive_tests"]
    for col in ("mean_rt_ms", "median_rt_ms", "speed", "lapses", "false_starts", "accuracy",
                "correct_count"):
        assert t.c[col].nullable  # uygulanmayan metrik NULL, 0 değil


def test_evaluation_has_no_operational_fk():
    assert not Base.metadata.tables["evaluation.gercek_durum"].foreign_keys
