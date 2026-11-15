"""Bugün ↔ önceki günler (kişisel taban çizgisi) + anomali kararı + modelin her sapmada çağrılması."""
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.providers import kart_onerici
from app.repositories.records import JobRecord, JobRequestData
from app.schemas.common import AnalysisModule, AnomalyLevel, EvaluationStatus, JobState, ModuleScope
from app.services.anomaly import evaluate_snapshot, load_cards
from app.services.baseline import BaselinePolicy, baseline_findings, load_baseline_policy

CONFIG = Path(__file__).resolve().parents[2] / "config"
CARDS = load_cards(CONFIG / "knowledge_cards.json")
POLICY = BaselinePolicy(version="b-test", min_baseline_days=14, z_watch=Decimal("2"), z_review=Decimal("3"))
REF = date(2026, 11, 15)
NOW = datetime(2026, 11, 15, 9, tzinfo=UTC)


def rec(day_offset, value, measurement="heart_rate", unit="BPM", module="physiological", n=0):
    day = (REF - timedelta(days=day_offset)).isoformat()
    return {"record_id": f"{measurement}:{day}:{n}", "module": module, "measurement": measurement,
            "unit": unit, "protocol_version": "module-v2", "measured_date": day,
            "value_num_exact": str(value), "valid": True}


def history(values_by_offset, **kw):
    return [rec(off, v, **kw) for off, v in values_by_offset.items()]


def snap(records, findings=None, current=None):
    today = [r for r in records if r["measured_date"] == REF.isoformat()]
    return {"module": "anomaly", "data_cutoff_at": "2026-11-15T09:00:00.000Z", "history_records": records,
            "model_input": {"astronaut_id": "A007", "module_scope": "combined", "reference_date": REF.isoformat(),
                            "threshold_policy_version": "t", "current_measurements": current if current is not None else today,
                            "threshold_findings": findings or []}}


def job():
    return JobRecord(job_id=uuid.uuid4(), astronaut_id="A007", module=AnalysisModule.ANOMALY,
                     state=JobState.ANALYZING, request=JobRequestData(module=AnalysisModule.ANOMALY,
                     module_scope=ModuleScope.COMBINED), attempts=1, retry_cycle=0, has_snapshot=True,
                     evaluation_status=None, error_code=None, anomaly_result_id=None, sans_analysis_id=None,
                     created_at=NOW, updated_at=NOW)


# 20 önceki gün: 70 ve 74 dönüşümlü → ortalama 72, popülasyon std 2
PRIOR = {off: (70 if off % 2 else 74) for off in range(1, 21)}


def test_policy_file_is_valid_and_ordered():
    p = load_baseline_policy(CONFIG / "baseline-policy.json")
    assert p.z_watch <= p.z_review and p.min_baseline_days >= 2


def test_today_is_compared_with_previous_days_only():
    f = baseline_findings(snap(history(PRIOR | {0: 77})), POLICY)[0]
    assert f["baseline_days"] == 20 and f["baseline_mean"] == "72.00" and f["baseline_sd"] == "2.00"
    assert f["z"] == "2.50" and f["direction"] == "up" and f["severity"] == "watch" and f["status"] == "deviation"
    assert f["record_ids"] == [f"heart_rate:{REF}:0"]


def test_strong_deviation_is_review_and_small_is_within():
    assert baseline_findings(snap(history(PRIOR | {0: 66})), POLICY)[0]["severity"] == "review"   # z=-3
    w = baseline_findings(snap(history(PRIOR | {0: 73})), POLICY)[0]
    assert w["status"] == "within" and w["severity"] is None and w["z"] == "0.50"


def test_several_records_today_are_averaged_and_days_weighted_equally():
    records = history(PRIOR) + [rec(0, 76, n=1), rec(0, 78, n=2)] + [rec(3, 70, n=9)]  # gün 3'te ikinci kayıt
    f = baseline_findings(snap(records), POLICY)[0]
    assert f["value"] == "77.00" and f["baseline_days"] == 20  # gün sayısı kayıt sayısı değil


def test_no_record_today_means_not_evaluated_and_short_history_insufficient():
    assert baseline_findings(snap(history(PRIOR)), POLICY) == []          # eski gün "bugün" sayılmaz
    short = baseline_findings(snap(history({1: 70, 2: 74, 0: 90})), POLICY)[0]
    assert short["status"] == "insufficient_baseline" and short["z"] is None
    flat = baseline_findings(snap(history({off: 72 for off in range(1, 21)} | {0: 72})), POLICY)[0]
    assert flat["status"] == "no_variance"


def test_baseline_deviation_alone_produces_result_without_thresholds():
    ev = evaluate_snapshot(job(), snap(history(PRIOR | {0: 77})), CARDS, baseline_policy=POLICY)
    assert ev.status is EvaluationStatus.EVALUATED and ev.result.is_anomaly
    d = ev.result.drivers[0]
    assert d["kind"] == "baseline" and d["measurement"] == "heart_rate" and d["z"] == "2.50"
    assert "önceki 20 günün ortalaması 72" in ev.result.summary
    assert ev.provider_metadata["baseline"] == {"compared": 1, "deviations": 1, "insufficient": 0}


def test_strong_personal_deviation_escalates_to_review_with_reason():
    ev = evaluate_snapshot(job(), snap(history(PRIOR | {0: 80})), CARDS, baseline_policy=POLICY)  # z=4
    assert ev.result.level is AnomalyLevel.REVIEW
    assert "önceki günlerden güçlü sapma" in ev.result.recommendation


def test_within_baseline_and_no_threshold_is_normal_not_insufficient():
    ev = evaluate_snapshot(job(), snap(history(PRIOR | {0: 73})), CARDS, baseline_policy=POLICY)
    assert ev.status is EvaluationStatus.EVALUATED and ev.result.level is AnomalyLevel.NORMAL


def test_without_baseline_or_threshold_stays_insufficient():
    ev = evaluate_snapshot(job(), snap(history({1: 70, 0: 90})), CARDS, baseline_policy=POLICY)
    assert ev.status is EvaluationStatus.INSUFFICIENT_DATA
    assert ev.outcome["reason"] == "thresholds_not_configured"


def test_behavioral_metrics_use_their_own_units():
    records = history({off: (7.4 if off % 2 else 7.8) for off in range(1, 21)} | {0: 5.5},
                      measurement="sleep_hours", unit="h", module="behavioral")
    ev = evaluate_snapshot(job(), snap(records), CARDS, baseline_policy=POLICY)
    assert ev.result.drivers[0]["measurement"] == "sleep_hours" and ev.result.drivers[0]["direction"] == "down"
    assert "5.5 saat" in ev.result.summary


def test_model_is_called_even_when_no_card_explains_the_finding():
    seen = []

    def sor(mesajlar, sema, deneme=0):
        seen.append((mesajlar, sema))
        return {"summary": "Nabız önceki günlere göre belirgin yüksek.", "explanations": [],
                "unmatched_findings": ["heart_rate"]}
    ev = evaluate_snapshot(job(), snap(history(PRIOR | {0: 77})), CARDS, sor=sor, model_name="m",
                           baseline_policy=POLICY)
    assert seen, "sapma varken model çağrılmalı (kart olmasa da)"
    user = seen[0][0][1]["content"]
    assert "heart_rate: up (value=77.00, baseline=72.00, baseline_days=20, z=2.50, unit=BPM)" in user
    assert seen[0][1]["properties"]["explanations"]["maxItems"] == 0  # kartsız: yalnız yorum
    assert ev.result.summary == "Nabız önceki günlere göre belirgin yüksek."
    assert ev.provider_metadata["algorithm"] == "threshold_rules_plus_llm"


def test_no_deviation_does_not_call_model():
    def sor(*_):
        raise AssertionError("sapma yokken model çağrılmamalı")
    ev = evaluate_snapshot(job(), snap(history(PRIOR | {0: 73})), CARDS, sor=sor, model_name="m",
                           baseline_policy=POLICY)
    assert ev.result.level is AnomalyLevel.NORMAL


@pytest.mark.parametrize("deg", ["up", {"direction": "up", "value": "9", "baseline": "3", "z": "2.5"}])
def test_oner_still_accepts_v4_inputs(deg):
    out = kart_onerici.oner({"pvt_lapses": deg}, CARDS,
                            sor=lambda *a, **k: {"summary": "x", "explanations": [], "unmatched_findings": []})
    assert "summary" in out and "escalate_to_physician" in out
