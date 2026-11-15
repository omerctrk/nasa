"""contracts/behavioral/questions.json sozlesme testleri."""
import json
from pathlib import Path

import pytest

from app.services.behavioral_scoring import SYMPTOM_CODES as SCORING_SYMPTOM_CODES

# backend/tests/behavioral/unit/test_questions_json.py -> parents[4] = proje koku
PROJECT_ROOT = Path(__file__).resolve().parents[4]
QUESTIONS_PATH = PROJECT_ROOT / "contracts" / "behavioral" / "questions.json"

# Docker'da yalnız backend/ klasörü bağlanır (/app); proje kökündeki contracts/ orada yoktur.
# Sözleşme dosyası görünmüyorsa bu testler hata yerine gerekçesiyle atlanır; yerelde
# proje kökünden çalıştırınca normal koşar.
if not QUESTIONS_PATH.exists():
    pytest.skip(f"{QUESTIONS_PATH} bu ortamda yok (contracts/ bağlı değil)", allow_module_level=True)

SYMPTOM_CODES = [
    "headache", "fatigue", "nausea", "dizziness", "blurred_vision",
    "eye_pressure", "back_pain", "cough", "shortness_of_breath",
    "sore_throat", "skin_lesion", "digestive_issue",
]
DAILY_KEYS = [
    "mood", "energy", "stress", "loneliness", "crew_relation",
    "bed_time", "wake_time", "sleep_quality", "symptoms",
]
WEEKLY_KEYS = [
    "who5_1", "who5_2", "who5_3", "who5_4", "who5_5",
    "phq2_1", "phq2_2", "gad2_1", "gad2_2",
]
OLD_CODES = [
    "bas_agrisi", "halsizlik", "bulanti", "bas_donmesi", "bulanik_gorme",
    "goz_baskisi", "sirt_agrisi", "oksuruk", "nefes_darligi",
    "bogaz_agrisi", "doku_lezyon", "sindirim",
]
TURKISH_CHARS = set("çÇğĞıİöÖşŞüÜ")


@pytest.fixture(scope="module")
def raw_text() -> str:
    return QUESTIONS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def data(raw_text) -> dict:
    return json.loads(raw_text)


@pytest.fixture(scope="module")
def daily(data) -> dict:
    return {q["key"]: q for q in data["daily_checkin"]["questions"]}


@pytest.fixture(scope="module")
def scales(data) -> dict:
    return {s["id"]: s for s in data["weekly_assessment"]["scales"]}


def test_valid_json_and_language(data):
    assert data["language"] == "en"


def test_symptom_codes_exact_order_unique(data):
    codes = [s["code"] for s in data["symptom_codes"]]
    assert codes == SYMPTOM_CODES
    assert len(set(codes)) == len(codes)


def test_daily_keys(daily):
    assert list(daily) == DAILY_KEYS
    assert "crew" not in daily


@pytest.mark.parametrize("key,lo,hi", [
    ("mood", 0, 10), ("energy", 0, 10), ("stress", 0, 10),
    ("loneliness", 0, 4), ("crew_relation", 0, 4), ("sleep_quality", 1, 5),
])
def test_daily_ranges(daily, key, lo, hi):
    q = daily[key]
    assert (q["min"], q["max"]) == (lo, hi)
    if "options" in q:
        assert {o["value"] for o in q["options"]} == set(range(lo, hi + 1))


def test_weekly_keys(scales):
    keys = [item["key"] for s in scales.values() for item in s["items"]]
    assert keys == WEEKLY_KEYS


@pytest.mark.parametrize("scale_id,values", [
    ("who5", set(range(0, 6))), ("phq2", set(range(0, 4))), ("gad2", set(range(0, 4))),
])
def test_option_values(scales, scale_id, values):
    assert {o["value"] for o in scales[scale_id]["options"]} == values


def test_every_scale_has_source(scales):
    for s in scales.values():
        assert isinstance(s.get("source"), str) and s["source"].strip()


def test_instructions_timeframe(scales):
    assert "over the last two weeks" in scales["who5"]["instructions"]
    assert "Over the last 2 weeks" in scales["phq2"]["instructions"]
    assert "Over the last 2 weeks" in scales["gad2"]["instructions"]


def test_no_turkish_characters(raw_text):
    found = sorted(TURKISH_CHARS & set(raw_text))
    assert not found, f"Turkish characters found: {found}"


def test_no_old_codes(raw_text):
    found = [c for c in OLD_CODES if c in raw_text]
    assert not found, f"Old codes found: {found}"


def test_symptom_codes_match_scoring_constant(data):
    assert [s["code"] for s in data["symptom_codes"]] == list(SCORING_SYMPTOM_CODES)
