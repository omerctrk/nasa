"""A6 kabul (DB'siz): sözlük ↔ VIEW uyumu, parola güvenliği, seed kuralları."""
import re
from pathlib import Path

import pytest

from app.core.passwords import hash_password, needs_rehash, verify_password
from scripts import seed

ROOT = Path(__file__).parents[2]
VIEW = (ROOT / "migrations/versions/0006_views.py").read_text().split("V_MEASUREMENTS = ")[1]


def view_codes() -> set[str]:
    checkin = set(re.findall(r"\('(\w+)',\s+CAST\(c\.", VIEW))
    cognitive = set(re.findall(r"\('(?:pvt|rotation|dsst)',\s+'(\w+)'", VIEW))
    # VIEW'ın göz kolu duruyor ama SANS kapatıldı: tablolar boş, kodları sözlükte yok.
    return checkin | cognitive


def test_every_view_code_is_in_seed_dictionary():
    codes = view_codes()
    assert len(codes) == 16
    assert codes == {d[0] for d in seed.DEFINITIONS}


def test_physiological_seed_matches_history_policy():
    """Ömer'in geçmiş politikası ile seed sözlüğü aynı kod/birim/protokolü kullanmalı;
    aksi halde fizyolojik ölçümler girişte reddedilir ya da analize girmez."""
    import json

    policy = json.loads((ROOT / "config/history-policy.json").read_text(encoding="utf-8"))
    confirmed = {(f["measurement"], f["unit"], f["protocol_version"]) for f in policy["features"]
                 if f["module"] == "physiological" and f.get("definition_confirmed")}
    seeded = {(c, u, seed.PHYSIOLOGICAL_PROTOCOL) for c, m, u, *_ in seed.PHYSIOLOGICAL_DEFINITIONS}
    assert seeded == confirmed
    assert all(d == "unconfirmed" for *_, d in seed.PHYSIOLOGICAL_DEFINITIONS)


def test_behavioral_policy_features_match_seed_dictionary():
    """Ekip kararı (15 Kasım 2026): 11 davranış kodu yalnız geçmiş/özet için onaylı. Kod, birim ve
    protokol sözlükle aynı olmalı; mood/energy (mood_index'in içinde), pvt_median_rt ve DSST yok."""
    import json

    policy = json.loads((ROOT / "config/history-policy.json").read_text(encoding="utf-8"))
    confirmed = {(f["measurement"], f["unit"], f["protocol_version"]) for f in policy["features"]
                 if f["module"] == "behavioral" and f.get("definition_confirmed")}
    seeded = {(c, u, seed.PROTOCOL_VERSION) for c, m, u, *_ in seed.DEFINITIONS}
    assert confirmed <= seeded
    assert {c for c, *_ in confirmed} == {
        "stress", "loneliness", "crew", "mood_index", "sleep_hours", "sleep_quality",
        "pvt_mean_rt", "pvt_lapses", "pvt_false_starts", "rotation_accuracy", "rotation_mean_rt"}
    assert all("minimum_quality_score" not in f for f in policy["features"] if f["module"] == "behavioral")


def test_no_invented_score_directions():
    for code, module, *_, direction in seed.DEFINITIONS:
        if module == "behavioral":
            assert direction == "unconfirmed", code


def test_known_constants():
    assert seed.MISSION_ID == "M01" and str(seed.MISSION_DAY0) == "2027-01-05"
    assert seed.ACTIVE_ASTRONAUT_ID == "A007"
    assert seed.DISPLAY_ASTRONAUT_ID != seed.ACTIVE_ASTRONAUT_ID
    # İkinci aktif astronot (demo: hesaplar arası geçiş): ayrı kimlik, ayrı e-posta
    assert seed.ACTIVE_ASTRONAUT_IDS == ("A007", "A009")
    assert seed.DISPLAY_ASTRONAUT_ID not in seed.ACTIVE_ASTRONAUT_IDS
    assert seed.SECOND_ASTRONAUT_EMAIL not in (seed.ASTRONAUT_EMAIL, seed.GROUND_EMAIL)


def test_passwords_are_not_in_repo():
    src = (ROOT / "scripts/seed.py").read_text(encoding="utf-8")
    assert "SEED_ASTRONAUT_PASSWORD" in src
    assert not re.search(r"password\s*=\s*['\"]\w", src, re.I)


def test_missing_passwords_stop_before_db():
    with pytest.raises(SystemExit, match="SEED_"):
        seed.run_seed(db=None, astronaut_pw="", ground_pw="x")


def test_argon2_hash_roundtrip():
    h = hash_password("gizli-parola")
    assert h.startswith("$argon2id$") and "gizli-parola" not in h
    assert verify_password(h, "gizli-parola") and not verify_password(h, "yanlis")
    assert not verify_password("bozuk", "x") and not needs_rehash(h)
    with pytest.raises(ValueError):
        hash_password("")
