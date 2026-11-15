"""Senaryo verisinin şemadaki CHECK kurallarına ve senaryo şekline uyduğunu doğrular."""
import json
import re
from statistics import mean

from app.services.behavioral_scoring import SYMPTOM_CODES
from scripts.seed_behavioral import CONFIG, generate

DATA = generate()


def test_counts():
    assert len(DATA["checkins"]) == 74
    assert len(DATA["weekly_assessments"]) == 10
    assert len(DATA["cognitive_tests"]) == 2 * sum(1 for d in range(1, 75) if d % 7 in CONFIG["test_weekdays"])


def test_deterministic():
    assert generate() == DATA


def test_last_day_is_nov_13():
    assert DATA["checkins"][-1]["date"] == "2026-11-13"
    assert DATA["checkins"][-1]["mission_day"] == 74


def test_first_day_is_mission_day_1():
    assert DATA["checkins"][0]["date"] == "2026-09-01"
    assert DATA["checkins"][0]["mission_day"] == 1


def test_mission_day_matches_date():
    from datetime import date
    start = date(2026, 9, 1)
    for r in DATA["checkins"]:
        assert (date.fromisoformat(r["date"]) - start).days + 1 == r["mission_day"]
    for kind, field in (("cognitive_tests", "taken_at"), ("weekly_assessments", "taken_at")):
        for r in DATA[kind]:
            assert (date.fromisoformat(r[field][:10]) - start).days + 1 == r["mission_day"]


def test_checkin_ranges():
    for r in DATA["checkins"]:
        assert 0 <= r["mood"] <= 10 and 0 <= r["energy"] <= 10 and 0 <= r["stress"] <= 10
        assert 0 <= r["loneliness"] <= 4 and 0 <= r["crew_relation"] <= 4
        assert 0 <= r["mood_index"] <= 100 and 1 <= r["sleep_quality"] <= 5
        assert r["sleep_hours"] >= 0 and r["source"] == "seed"
        assert r["symptoms"] is None or isinstance(json.loads(r["symptoms"]), list)


def test_cognitive_null_rules():
    for r in DATA["cognitive_tests"]:
        assert (r["valid"] and r["invalid_reason"] is None) or (not r["valid"] and r["invalid_reason"])
        if r["test_type"] == "pvt":
            assert r["accuracy"] is None and r["correct_count"] is None
        else:
            assert r["median_rt_ms"] is None and r["speed"] is None and r["lapses"] is None
            assert r["false_starts"] is None and r["correct_count"] is None


def test_scenario_shape():
    ci = DATA["checkins"]
    stable = mean(r["mood_index"] for r in ci if r["mission_day"] <= 60)
    end = mean(r["mood_index"] for r in ci if r["mission_day"] >= 70)
    assert end < stable - 15
    pvt = [r for r in DATA["cognitive_tests"] if r["test_type"] == "pvt"]
    assert mean(r["mean_rt_ms"] for r in pvt if r["mission_day"] >= 65) > \
           mean(r["mean_rt_ms"] for r in pvt if r["mission_day"] <= 60)


OLD_CODES = [
    "bas_agrisi", "halsizlik", "bulanti", "bas_donmesi", "bulanik_gorme",
    "goz_baskisi", "sirt_agrisi", "oksuruk", "nefes_darligi",
    "bogaz_agrisi", "doku_lezyon", "sindirim",
]
HHMM = re.compile(r"^\d{2}:\d{2}$")


def test_checkin_uses_crew_relation():
    for r in DATA["checkins"]:
        assert "crew" not in r
        assert "crew_relation" in r and 0 <= r["crew_relation"] <= 4


def test_symptoms_are_known_codes():
    for r in DATA["checkins"]:
        if r["symptoms"] is not None:
            assert set(json.loads(r["symptoms"])) <= set(SYMPTOM_CODES)


def test_bed_and_wake_time_format():
    for r in DATA["checkins"]:
        assert HHMM.match(r["bed_time"]) and HHMM.match(r["wake_time"])


def test_no_old_turkish_codes_in_output():
    text = json.dumps(DATA, ensure_ascii=False)
    found = [c for c in OLD_CODES if c in text]
    assert not found, f"Old codes found: {found}"


def test_symptoms_never_null():
    for r in DATA["checkins"]:
        assert r["symptoms"] is not None
        assert isinstance(json.loads(r["symptoms"]), list)
