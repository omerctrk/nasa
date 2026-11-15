from datetime import time

import pytest

from app.services.behavioral_scoring import (
    mood_index, sleep_hours, score_who5, score_phq2, score_gad2,
    score_pvt, score_rotation,
)


def pvt_trial(i, rt, false_start=False):
    return {"i": i, "delay_ms": 2000, "rt_ms": rt, "false_start": false_start}


# check-in ---------------------------------------------------------------

def test_mood_index_bounds():
    assert mood_index(10, 10, 0) == 100.0
    assert mood_index(0, 0, 10) == 0.0
    assert mood_index(6, 5, 6) == 50.0


def test_mood_index_rejects_out_of_range():
    with pytest.raises(ValueError):
        mood_index(14, 5, 5)


def test_sleep_hours_across_midnight():
    assert sleep_hours(time(23, 30), time(6, 45)) == 7.25
    assert sleep_hours(time(1, 0), time(8, 0)) == 7.0


# haftalık -----------------------------------------------------------------

def test_weekly_scores():
    answers = {"who5_1": 3, "who5_2": 3, "who5_3": 2, "who5_4": 2, "who5_5": 2,
               "phq2_1": 1, "phq2_2": 1, "gad2_1": 2, "gad2_2": 1}
    assert score_who5(answers) == 48
    assert score_phq2(answers) == 2
    assert score_gad2(answers) == 3


def test_who5_extremes():
    assert score_who5({f"who5_{i}": 5 for i in range(1, 6)}) == 100
    assert score_who5({f"who5_{i}": 0 for i in range(1, 6)}) == 0


# PVT ----------------------------------------------------------------------

def test_pvt_valid_session():
    trials = [pvt_trial(i, 300) for i in range(1, 41)]
    trials += [pvt_trial(41, 400), pvt_trial(42, None)]         # 2 dikkat kaybı
    trials += [pvt_trial(43, None, false_start=True)]           # 1 erken basma
    r = score_pvt(trials)
    assert r["valid"] is True
    assert r["lapses"] == 2
    assert r["false_starts"] == 1
    assert r["n_trials"] == 43
    assert r["accuracy"] is None and r["correct_count"] is None


def test_pvt_thresholds():
    r = score_pvt([pvt_trial(1, 99), pvt_trial(2, 355)])
    assert r["false_starts"] == 1      # 99 ms erken basma
    assert r["lapses"] == 1            # 355 ms dikkat kaybı


def test_pvt_too_few_responses_is_invalid():
    r = score_pvt([pvt_trial(i, 300) for i in range(1, 11)])
    assert r["valid"] is False
    assert r["invalid_reason"] == "too_few_responses"


def test_pvt_empty():
    r = score_pvt([])
    assert r["valid"] is False and r["mean_rt_ms"] is None


# döndürme -----------------------------------------------------------------

def rot(i, mirror, answer, rt=1500):
    return {"i": i, "shape": "s1", "angle": 60, "mirror": mirror, "answer": answer, "rt_ms": rt}


def test_rotation_accuracy_and_rt_from_correct_only():
    trials = [rot(1, True, "mirror", 1000), rot(2, False, "same", 2000),
              rot(3, True, "same", 9999), rot(4, False, None, None)]
    r = score_rotation(trials)
    assert r["accuracy"] == 0.5
    assert r["mean_rt_ms"] == 1500.0           # yalnızca doğru iki cevap
    assert r["valid"] is False                 # şans düzeyi
    assert r["lapses"] is None and r["speed"] is None


def test_rotation_valid():
    trials = [rot(i, i % 2 == 0, "mirror" if i % 2 == 0 else "same") for i in range(1, 17)]
    r = score_rotation(trials)
    assert r["accuracy"] == 1.0 and r["valid"] is True
