"""Davranışsal ve refleks modülü: puanlama fonksiyonları.

Saf fonksiyonlar: veritabanı yok, ağ yok. Girdi alır, sonuç döner.
Hem canlı API hem senaryo (seed) verisi bu fonksiyonları kullanır.
Dönen sözlüklerin anahtarları behavioral.cognitive_tests tablosunun alan adlarıyla aynıdır.
"""
from __future__ import annotations

from datetime import time
from statistics import mean, median

# Eşikler tek yerde
PVT_LAPSE_MS = 355              # 3 dakikalık PVT (PVT-B) dikkat kaybı eşiği
PVT_FALSE_START_MS = 100        # bundan kısa tepki = erken basma
PVT_MIN_VALID_RESPONSES = 30    # geçerli test için en az geçerli tepki
PVT_MAX_FALSE_START_RATIO = 0.20
ROTATION_MIN_ACCURACY = 0.55    # şans düzeyine (%50) yakınsa geçersiz

# Belirti kodları: tek kaynak. Seed ve API doğrulaması bu sabiti kullanır;
# sıra contracts/behavioral/questions.json ile aynıdır.
SYMPTOM_CODES = (
    "headache", "fatigue", "nausea", "dizziness",
    "blurred_vision", "eye_pressure", "back_pain", "cough",
    "shortness_of_breath", "sore_throat", "skin_lesion", "digestive_issue",
)


def _check_range(name: str, value: int, low: int, high: int) -> None:
    if not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} {low}-{high} arasında tam sayı olmalı, gelen: {value!r}")


# ---------------------------------------------------------------- check-in

def mood_index(mood: int, energy: int, stress: int) -> float:
    """0-100 bileşik ruh hali puanı. Klinik değil, trend için."""
    for name, v in (("mood", mood), ("energy", energy), ("stress", stress)):
        _check_range(name, v, 0, 10)
    return round((mood + energy + (10 - stress)) / 3 * 10, 1)


def sleep_hours(bed_time: time, wake_time: time) -> float:
    """Yatış ve kalkış saatinden uyku süresi; gece yarısını geçen uykuyu doğru hesaplar."""
    bed = bed_time.hour * 60 + bed_time.minute
    wake = wake_time.hour * 60 + wake_time.minute
    if wake <= bed:
        wake += 24 * 60
    return round((wake - bed) / 60, 2)


# ---------------------------------------------------------------- haftalık

def score_who5(answers: dict) -> int:
    """WHO-5: 5 madde (0-5), ham toplam x 4 -> 0-100."""
    total = 0
    for i in range(1, 6):
        v = answers[f"who5_{i}"]
        _check_range(f"who5_{i}", v, 0, 5)
        total += v
    return total * 4


def _score_two_item(answers: dict, prefix: str) -> int:
    total = 0
    for i in (1, 2):
        v = answers[f"{prefix}_{i}"]
        _check_range(f"{prefix}_{i}", v, 0, 3)
        total += v
    return total


def score_phq2(answers: dict) -> int:
    """PHQ-2: 2 madde (0-3) -> 0-6."""
    return _score_two_item(answers, "phq2")


def score_gad2(answers: dict) -> int:
    """GAD-2: 2 madde (0-3) -> 0-6."""
    return _score_two_item(answers, "gad2")


# ---------------------------------------------------------------- bilişsel testler

def _empty_metrics(n_trials: int) -> dict:
    return {
        "n_trials": n_trials,
        "mean_rt_ms": None,
        "median_rt_ms": None,
        "speed": None,
        "lapses": None,
        "false_starts": None,
        "accuracy": None,
        "correct_count": None,
        "valid": False,
        "invalid_reason": None,
    }


def score_pvt(trials: list[dict]) -> dict:
    """PVT ham denemelerinden ölçümler.

    Her deneme: {"i": 1, "delay_ms": 2340, "rt_ms": 287 | None, "false_start": bool}
    - rt_ms None ve false_start False -> cevapsız (dikkat kaybı sayılır)
    - false_start True veya rt_ms < 100 -> erken basma
    - rt_ms >= 355 -> dikkat kaybı
    """
    out = _empty_metrics(len(trials))
    if not trials:
        out["invalid_reason"] = "no_trials"
        return out

    false_starts = 0
    lapses = 0
    responses: list[float] = []

    for t in trials:
        rt = t.get("rt_ms")
        if t.get("false_start", False) or (rt is not None and rt < PVT_FALSE_START_MS):
            false_starts += 1
            continue
        if rt is None or rt >= PVT_LAPSE_MS:
            lapses += 1
        if rt is not None:
            responses.append(float(rt))

    out["false_starts"] = false_starts
    out["lapses"] = lapses
    if responses:
        out["mean_rt_ms"] = round(mean(responses), 1)
        out["median_rt_ms"] = round(median(responses), 1)
        out["speed"] = round(mean(1000 / r for r in responses), 3)

    if len(responses) < PVT_MIN_VALID_RESPONSES:
        out["invalid_reason"] = "too_few_responses"
    elif false_starts / len(trials) > PVT_MAX_FALSE_START_RATIO:
        out["invalid_reason"] = "too_many_false_starts"
    else:
        out["valid"] = True
    return out


def score_rotation(trials: list[dict]) -> dict:
    """Zihinsel döndürme ham denemelerinden ölçümler.

    Her deneme: {"i": 1, "shape": "s3", "angle": 120, "mirror": True,
                 "answer": "same" | "mirror" | None, "rt_ms": 1840}
    Cevapsız (None) yanlış sayılır; süre yalnızca doğru cevaplardan hesaplanır.
    """
    out = _empty_metrics(len(trials))
    if not trials:
        out["invalid_reason"] = "no_trials"
        return out

    correct_rts = [
        float(t["rt_ms"])
        for t in trials
        if t.get("answer") in ("same", "mirror")
        and (t["answer"] == "mirror") == bool(t["mirror"])
        and t.get("rt_ms") is not None
    ]
    accuracy = len(correct_rts) / len(trials)
    out["accuracy"] = round(accuracy, 3)
    if correct_rts:
        out["mean_rt_ms"] = round(mean(correct_rts), 1)

    if accuracy < ROTATION_MIN_ACCURACY:
        out["invalid_reason"] = "near_chance_accuracy"
    else:
        out["valid"] = True
    return out
