"""Davranışsal modül için 74 günlük sentetik senaryo verisi.

Kural (backend şeması v5.0): ilk 60 gün stabil, son 14 gün kademeli değişim.
Bütün değerler DEMO amaçlıdır; klinik değildir. Büyüklükler CONFIG içinde, tek yerde.

Çıktı alanları behavioral.checkins / weekly_assessments / cognitive_tests
tablolarıyla aynıdır (id hariç; IDENTITY veritabanında üretilir).
Aynı tohumla her çalıştırmada aynı veri üretilir; client_request_id de deterministiktir.

Kullanım:  python -m scripts.seed_behavioral <çıktı_klasörü>
"""
from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from app.services.behavioral_scoring import (
    mood_index, sleep_hours, score_who5, score_phq2, score_gad2,
    score_pvt, score_rotation, SYMPTOM_CODES,
)

CONFIG = {
    "astronaut_id": "A007",
    "mission_start": date(2026, 9, 1),     # görev günü 1; 74. gün = 13 Kasım 2026
    "days": 74,
    "stable_until": 60,                    # 1-60 stabil, 61-74 kademeli değişim
    "seed": 42,
    "test_weekdays": (1, 4),               # haftada iki test günü: gün % 7 bu değerlerden biriyse
    "weekly_every": 7,                     # haftalık ölçek günleri: 7, 14, ... 70
    # Stabil dönem ortalamaları
    "base": {"mood": 7, "energy": 7, "stress": 3, "loneliness": 1, "crew_relation": 3,
             "bed_min": 23 * 60, "wake_min": 6 * 60 + 45, "quality": 4,
             "pvt_rt": 270.0, "pvt_lapse_p": 0.02, "pvt_false_p": 0.02,
             "rot_acc": 0.90, "rot_rt": 1500.0},
    # Son 14 günün sonunda (74. gün) ulaşılan toplam değişim
    "drift": {"mood": -3, "energy": -3, "stress": +3, "loneliness": +1.5, "crew_relation": -1,
              "bed_min": +60, "wake_min": -30, "quality": -1.5,
              "pvt_rt": +40.0, "pvt_lapse_p": +0.06, "rot_acc": -0.12, "rot_rt": +300.0,
              "symptom_p": 0.6},
    # Senaryoda görülen belirtiler (SYMPTOM_CODES içinden); sıra RNG çağrı sırasını belirler
    "symptoms": ("fatigue", "headache"),
}
assert set(CONFIG["symptoms"]) <= set(SYMPTOM_CODES)

# Astronot profilleri: CONFIG'in üzerine yazılan alanlar. A007 = CONFIG'in kendisi (değişmez).
# A009 (demo: hesaplar arası geçiş) bambaşka ve ANİ bir senaryodur: dolaşım/solunum olayı.
# Davranış ve bilişsel testler görev boyunca stabildir (A007'deki uyku/ruh hali/tepki süresi
# bozulması burada YOK); yalnız son 4 günde baş dönmesi, nefes darlığı ve yorgunluk bildirilir.
# Fizyolojik karşılığı (SpO2, nabız ve tansiyon düşüşü): scripts/seed_physiological.py PROFILES.
PROFILES = {
    "A007": {},
    "A009": {
        "astronaut_id": "A009",
        "seed": 9007,
        "stable_until": 70,
        "base": {"mood": 8, "energy": 7, "stress": 2, "loneliness": 1, "crew_relation": 3,
                 "bed_min": 22 * 60 + 30, "wake_min": 6 * 60 + 30, "quality": 4,
                 "pvt_rt": 255.0, "pvt_lapse_p": 0.02, "pvt_false_p": 0.02,
                 "rot_acc": 0.92, "rot_rt": 1400.0},
        "drift": {"mood": 0, "energy": 0, "stress": 0, "loneliness": 0, "crew_relation": 0,
                  "bed_min": 0, "wake_min": 0, "quality": 0,
                  "pvt_rt": 0.0, "pvt_lapse_p": 0.0, "rot_acc": 0.0, "rot_rt": 0.0,
                  "symptom_p": 0.8},
        "symptoms": ("dizziness", "shortness_of_breath", "fatigue"),
    },
}
assert all(set(p.get("symptoms", ())) <= set(SYMPTOM_CODES) for p in PROFILES.values())

NS = uuid.UUID("6f1c2a52-6a4e-4f0e-9a43-0d3c5b7a9e10")
UTC = timezone.utc


def _progress(day: int) -> float:
    """0 (stabil) -> 1 (74. gün) arası kademeli değişim katsayısı."""
    s, n = CONFIG["stable_until"], CONFIG["days"]
    return 0.0 if day <= s else (day - s) / (n - s)


def _val(rng, key, p, sd, low, high):
    b, d = CONFIG["base"][key], CONFIG["drift"].get(key, 0)
    return max(low, min(high, round(rng.gauss(b + d * p, sd))))


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _rid(kind: str, day: int, test: str = "") -> str:
    return str(uuid.uuid5(NS, f"{CONFIG['astronaut_id']}:{kind}:{day}:{test}"))


def make_checkin(rng, day: int) -> dict:
    p = _progress(day)
    d = CONFIG["mission_start"] + timedelta(days=day - 1)
    mood = _val(rng, "mood", p, 0.8, 0, 10)
    energy = _val(rng, "energy", p, 0.8, 0, 10)
    stress = _val(rng, "stress", p, 0.8, 0, 10)
    bed_m = int(rng.gauss(CONFIG["base"]["bed_min"] + CONFIG["drift"]["bed_min"] * p, 20)) % 1440
    wake_m = int(rng.gauss(CONFIG["base"]["wake_min"] + CONFIG["drift"]["wake_min"] * p, 15)) % 1440
    bed, wake = time(bed_m // 60, bed_m % 60), time(wake_m // 60, wake_m % 60)
    symptoms = [s for s in CONFIG["symptoms"]
                if rng.random() < 0.03 + CONFIG["drift"]["symptom_p"] * p]
    created = datetime.combine(d, time(7, 0), UTC)
    return {
        "astronaut_id": CONFIG["astronaut_id"], "date": d.isoformat(), "mission_day": day,
        "mood": mood, "energy": energy, "stress": stress,
        "loneliness": _val(rng, "loneliness", p, 0.6, 0, 4),
        "crew_relation": _val(rng, "crew_relation", p, 0.5, 0, 4),
        "mood_index": mood_index(mood, energy, stress),
        "bed_time": bed.strftime("%H:%M"), "wake_time": wake.strftime("%H:%M"),
        "sleep_hours": sleep_hours(bed, wake),
        "sleep_quality": _val(rng, "quality", p, 0.6, 1, 5),
        "symptoms": json.dumps(symptoms),
        "source": "seed", "created_at": _iso(created), "updated_at": _iso(created),
    }


def make_pvt_trials(rng, p: float) -> list[dict]:
    b, dr = CONFIG["base"], CONFIG["drift"]
    mean_rt, lapse_p = b["pvt_rt"] + dr["pvt_rt"] * p, b["pvt_lapse_p"] + dr["pvt_lapse_p"] * p
    trials, elapsed, i = [], 0, 0
    while elapsed < 180_000:
        i += 1
        delay = rng.randint(1000, 4000)
        if rng.random() < b["pvt_false_p"]:
            trials.append({"i": i, "delay_ms": delay, "rt_ms": None, "false_start": True})
            elapsed += delay
            continue
        if rng.random() < lapse_p:
            rt = rng.randint(360, 900)
        else:
            rt = max(150, int(rng.gauss(mean_rt, 30)))
        trials.append({"i": i, "delay_ms": delay, "rt_ms": rt, "false_start": False})
        elapsed += delay + rt + 1000          # 1 sn sonuç gösterimi
    return trials


def make_rotation_trials(rng, p: float) -> list[dict]:
    b, dr = CONFIG["base"], CONFIG["drift"]
    acc, base_rt = b["rot_acc"] + dr["rot_acc"] * p, b["rot_rt"] + dr["rot_rt"] * p
    combos = [(a, m) for a in (0, 60, 120, 180) for m in (False, True)] * 2
    rng.shuffle(combos)
    trials = []
    for i, (angle, mirror) in enumerate(combos, 1):
        correct = rng.random() < acc
        truth = "mirror" if mirror else "same"
        answer = truth if correct else ("same" if mirror else "mirror")
        rt = int(rng.gauss(base_rt + 4 * angle, 200))
        trials.append({"i": i, "shape": f"s{rng.randint(1, 4)}", "angle": angle,
                       "mirror": mirror, "answer": answer, "rt_ms": max(400, rt)})
    return trials


def make_test(rng, day: int, test_type: str, trials: list[dict], minute: int) -> dict:
    d = CONFIG["mission_start"] + timedelta(days=day - 1)
    metrics = score_pvt(trials) if test_type == "pvt" else score_rotation(trials)
    return {
        "astronaut_id": CONFIG["astronaut_id"], "client_request_id": _rid("cognitive", day, test_type),
        "taken_at": _iso(datetime.combine(d, time(9, minute), UTC)), "mission_day": day,
        "test_type": test_type, "duration_s": 180 if test_type == "pvt" else 120,
        **metrics, "device": "seed-generator", "raw": json.dumps(trials), "source": "seed",
    }


def make_weekly(rng, day: int) -> dict:
    p = _progress(day)
    who = {f"who5_{i}": max(0, min(5, round(rng.gauss(3.6 - 1.6 * p, 0.5)))) for i in range(1, 6)}
    phq = {f"phq2_{i}": max(0, min(3, round(rng.gauss(0.3 + 1.0 * p, 0.4)))) for i in (1, 2)}
    gad = {f"gad2_{i}": max(0, min(3, round(rng.gauss(0.3 + 1.2 * p, 0.4)))) for i in (1, 2)}
    answers = {**who, **phq, **gad}
    d = CONFIG["mission_start"] + timedelta(days=day - 1)
    return {
        "astronaut_id": CONFIG["astronaut_id"], "client_request_id": _rid("weekly", day),
        "taken_at": _iso(datetime.combine(d, time(8, 0), UTC)), "mission_day": day,
        "answers": json.dumps(answers), "who5_score": score_who5(answers),
        "phq2_score": score_phq2(answers), "gad2_score": score_gad2(answers),
        "share_with_crew_medical": False, "source": "seed",
    }


def generate(astronaut_id: str = "A007") -> dict[str, list[dict]]:
    """Bir astronotun senaryosunu üretir. Varsayılan (A007) çıktısı profil eklenmeden öncekiyle aynıdır."""
    global CONFIG
    original = CONFIG
    CONFIG = {**original, **PROFILES[astronaut_id]}  # yardımcı fonksiyonlar CONFIG'i okur
    try:
        rng = random.Random(CONFIG["seed"])
        out = {"checkins": [], "cognitive_tests": [], "weekly_assessments": []}
        for day in range(1, CONFIG["days"] + 1):
            p = _progress(day)
            out["checkins"].append(make_checkin(rng, day))
            if day % 7 in CONFIG["test_weekdays"]:
                out["cognitive_tests"].append(make_test(rng, day, "pvt", make_pvt_trials(rng, p), 0))
                out["cognitive_tests"].append(make_test(rng, day, "rotation", make_rotation_trials(rng, p), 10))
            if day % CONFIG["weekly_every"] == 0:
                out["weekly_assessments"].append(make_weekly(rng, day))
        return out
    finally:
        CONFIG = original


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "seed_output")
    target.mkdir(parents=True, exist_ok=True)
    data = generate()
    for name, rows in data.items():
        (target / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name}: {len(rows)} satır -> {target / (name + '.json')}")


if __name__ == "__main__":
    main()
