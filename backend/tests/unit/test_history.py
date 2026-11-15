import json
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core.snapshots import snapshot_hash
from app.schemas.history import HistoryPolicy
from app.services.history import HistoryDataError, build_history_snapshot
from tests.fixtures.history import EYE_PROTOCOL_VERSION, NOW, history_policy, job, profile, record, thresholds


def build(records, **changes):
    args = dict(job=job(), profile=profile(), records=records, history=history_policy(),
                thresholds=thresholds(), read_started_at=NOW, read_completed_at=NOW + timedelta(seconds=1))
    return build_history_snapshot(**(args | changes))


def test_74_day_summary_recent_details_and_overlap():
    rows = [record(n, value_num=n, measured_date=NOW.date() - timedelta(days=74-n)) for n in range(1, 75)]
    result = build(rows)
    model = result["model_input"]
    summary = model["summary"][0]
    assert summary["record_count"] == 74 and summary["observed_days"] == 74
    assert summary["statistics"]["mean"] == 37.5
    assert summary["statistics"]["change_over_observed_period"] == 73
    assert summary["days_without_observations"] == 0
    assert len(model["recent_details"]) == 7 and len(model["current_measurements"]) == 1
    assert model["current_measurements"][0]["value_num"] == 74
    assert model["overlap"]["independent_sample_sets"] is False
    assert set(model["overlap"]["recent_record_ids"]) <= set(summary["record_ids"])
    assert model["sufficiency"] == {"status": "not_configured", "baseline_status": None}
    assert all(finding["status"] == "not_configured" for finding in model["threshold_findings"])


def test_sparse_and_single_day_records_do_not_invent_daily_samples_or_trends():
    result = build([record(measured_date=NOW.date() - timedelta(days=10))])
    group = result["model_input"]["summary"][0]
    assert group["observed_days"] == 1 and group["days_without_observations"] == 73
    assert group["statistics"]["change_over_observed_period"] is None
    assert group["statistics"]["population_stddev"] is None
    assert group["latest_age_days"] == 10
    assert not result["model_input"]["recent_details"]


def test_dates_keep_precision_and_future_timestamps_do_not_enter_snapshot():
    daily = record()
    future = record(2, time_precision="timestamp", measured_at=NOW + timedelta(seconds=1), value_num=999)
    old = record(3, measured_date=NOW.date() - timedelta(days=74))
    result = build([old, future, daily])
    assert len(result["history_records"]) == 1
    assert result["history_records"][0]["measured_at"] is None
    assert result["history_records"][0]["time_precision"] == "date"
    assert result["source_read"]["consistency"] == "read_committed_not_global_snapshot"


def test_explicit_demo_date_is_not_a_fabricated_timestamp():
    actual = NOW.replace(year=2026)
    result = build([record()], read_started_at=actual, read_completed_at=actual,
                   reference_date=NOW.date())
    assert len(result["history_records"]) == 1
    assert result["source_read"]["reference_mode"] == "explicit_date"
    assert result["source_read"]["measurement_timestamp_cutoff"] is None
    assert result["data_cutoff_at"].startswith("2026-")
    implicit = build([record()], read_started_at=actual, read_completed_at=actual)
    assert not implicit["history_records"]


def test_private_metrics_and_arbitrary_metadata_never_reach_snapshot():
    safe = record(metadata_json={"original_source": "seed", "hidden_label": "DO-NOT-SEND",
                                 "genetic": "DO-NOT-SEND", "weekly_answer": "DO-NOT-SEND"})
    weekly = record(2, module="behavioral", measurement="who5_score", value_num=999)
    speed = record(3, module="behavioral", measurement="pvt_speed", value_num=888)
    result = build([safe, weekly, speed], profile=profile(mtrr66_g=2, b_vit_status=Decimal("987654")))
    text = json.dumps(result)
    assert "DO-NOT-SEND" not in text and "who5" not in text and "pvt_speed" not in text
    assert "987654" not in text and "mtrr66_g" not in text
    assert result["history_records"][0]["metadata_json"] == {"original_source": "seed"}


@pytest.mark.parametrize("changes", [{"astronaut_id": "A008"}, {"mission_id": "OTHER"}])
def test_cross_person_or_mission_data_fails_closed(changes):
    with pytest.raises(HistoryDataError):
        build([record(**changes)])


def test_display_profile_is_rejected():
    with pytest.raises(HistoryDataError):
        build([record()], profile=profile(is_display_only=True))


def test_duplicate_reference_is_counted_once_but_conflict_is_rejected():
    item = record()
    assert len(build([item, item.model_copy(deep=True)])["history_records"]) == 1
    with pytest.raises(HistoryDataError):
        build([item, record(value_num=999)])


def test_unknown_definitions_and_invalid_data_are_excluded_without_zeros():
    result = build([record(valid=False), record(2, valid=False, value_num=None),
                    record(3, module="behavioral", measurement="mood_index", unit="score_0_100")])
    assert not result["model_input"]["summary"] and not result["history_records"]
    assert result["exclusion_counts"] == {"definition_not_configured": 1, "invalid_record": 2}


def eye_policy(minimum="0.8"):
    # SANS/göz kapatıldı: gerçek history-policy.json'da göz satırı yok. İşleyicinin
    # (kapalı ama silinmemiş) göz yolu yalnız bu test ayarıyla sınanır.
    data = history_policy().model_dump(mode="json")
    data["features"].append({"module": "sans", "measurement": "near_acuity", "unit": "logMAR",
                             "protocol_version": EYE_PROTOCOL_VERSION, "definition_confirmed": True,
                             "minimum_quality_score": minimum})
    return HistoryPolicy.model_validate(data)


def eye(number=1, **changes):
    return record(number, **({"module": "sans", "measurement": "near_acuity", "unit": "logMAR",
                              "protocol_version": EYE_PROTOCOL_VERSION, "eye": "OD",
                              "quality_score": "0.9", "value_num": "-0.1"} | changes))


def test_quality_policy_must_be_configured_and_low_quality_is_not_sent():
    assert build([eye()])["exclusion_counts"] == {"definition_not_configured": 1}  # SANS kapalı
    result = build([eye()], history=eye_policy(minimum=None))
    assert result["exclusion_counts"] == {"quality_policy_not_configured": 1}
    rows = [eye(1, quality_score="0.7"), eye(2, quality_score=None), eye(3, quality_score="0.8")]
    result = build(rows, history=eye_policy())
    assert len(result["history_records"]) == 1
    assert result["history_records"][0]["record_id"] == rows[2].record_id
    assert result["exclusion_counts"] == {"low_quality": 1, "quality_score_missing": 1}


def test_eyes_units_and_protocols_are_separate_groups():
    config = eye_policy().model_dump(mode="json")
    config["features"].append(config["features"][0] | {"protocol_version": "test-v3"})
    config["features"].append(config["features"][0] | {"unit": "test-other-unit"})
    rows = [eye(1), eye(2, eye="OS", value_num="-0.2"), record(3),
            record(4, protocol_version="test-v3"), record(5, unit="test-other-unit")]
    result = build(rows, history=HistoryPolicy.model_validate(config))
    assert len(result["model_input"]["summary"]) == 5
    assert {group["eye"] for group in result["model_input"]["summary"] if group["module"] == "sans"} == {"OD", "OS"}


def test_scope_filter_and_multiple_current_samples_preserve_identity():
    result = build([record(1), record(2, value_num=0), eye(3)], job=job("physiological"))
    assert len(result["model_input"]["current_measurements"]) == 2
    assert {item["value_num"] for item in result["model_input"]["current_measurements"]} == {0, 42}


def test_snapshot_freezes_exact_values_policy_and_source_copies():
    item = record(value_num="999999999999.123456")
    result = build([item])
    before = deepcopy(result)
    digest = snapshot_hash(result)
    item.metadata_json = {"changed": "later"}
    assert result == before and snapshot_hash(result) == digest
    assert result["history_records"][0]["value_num_exact"] == "999999999999.123456"
    assert len(result["threshold_policy_hash"]) == 64


def test_model_sees_normal_values_as_well_as_valid_threshold_breaches():
    from app.schemas.history import ThresholdPolicy
    bounds = ThresholdPolicy.model_validate({"version": "test-only", "rules": [{
        "module": "physiological", "measurement": "heart_rate", "unit": "BPM",
        "protocol_version": "module-v2", "upper": "50"}]})
    result = build([record(1, value_num=42), record(2, value_num=60)], thresholds=bounds)
    assert len(result["model_input"]["current_measurements"]) == 2
    assert result["model_input"]["valid_threshold_breach_record_ids"] == ["physiological:2"]
