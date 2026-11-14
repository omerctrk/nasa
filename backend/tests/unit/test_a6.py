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
    return checkin | cognitive | {"near_acuity", "contrast", "amsler"}


def test_every_view_code_is_in_seed_dictionary():
    codes = view_codes()
    assert len(codes) == 19
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


def test_no_invented_score_directions():
    for code, module, *_, direction in seed.DEFINITIONS:
        if module == "behavioral":
            assert direction == "unconfirmed", code


def test_known_constants():
    assert seed.MISSION_ID == "M01" and str(seed.MISSION_DAY0) == "2027-01-05"
    assert seed.ACTIVE_ASTRONAUT_ID == "A007"
    assert seed.DISPLAY_ASTRONAUT_ID != seed.ACTIVE_ASTRONAUT_ID


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
