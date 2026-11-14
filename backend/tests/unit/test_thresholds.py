import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.history import FeatureDefinition, HistoryPolicy, ThresholdPolicy, ThresholdRule
from app.services.thresholds import compare_threshold, load_threshold_policy
from tests.fixtures.history import record, history_policy


def policy(**changes):
    rule = {"module": "physiological", "measurement": "heart_rate", "unit": "BPM",
            "protocol_version": "module-v2", "lower": "10", "upper": "20"} | changes
    return ThresholdPolicy(version="test-only", rules=(ThresholdRule(**rule),))


@pytest.mark.parametrize(("value", "status", "delta"), [
    ("9", "below_range", "-1"), ("10", "within_range", None),
    ("20", "within_range", None), ("21", "above_range", "1"),
])
def test_exact_bounds_and_deviation(value, status, delta):
    result = compare_threshold(record(value_num=value), policy())
    assert result["status"] == status
    assert result["value_minus_bound"] == delta
    assert result["breached"] == (delta is not None)


def test_decimal_comparison_does_not_round_away_breach():
    result = compare_threshold(record(value_num=Decimal("0.30000000000000000001")),
                               policy(lower=None, upper="0.3"))
    assert result["breached"] is True
    assert Decimal(result["absolute_deviation"]) == Decimal("0.00000000000000000001")


@pytest.mark.parametrize(("updates", "status"), [({"unit": "other"}, "unit_mismatch"),
                                                   ({"protocol_version": "other"}, "protocol_mismatch"),
                                                   ({"measurement": "other"}, "not_configured")])
def test_unconfigured_and_context_mismatch_are_not_normal(updates, status):
    result = compare_threshold(record(), policy(**updates))
    assert result["status"] == status and result["breached"] is None
    assert result["absolute_deviation"] is None


def test_eye_context_is_not_mixed_and_negative_values_are_valid():
    eye = record(module="sans", measurement="near_acuity", unit="logMAR", eye="OD", value_num="-0.1")
    bounds = policy(module="sans", measurement="near_acuity", unit="logMAR", eye="OS", lower="-0.2", upper="0.2")
    assert compare_threshold(eye, bounds)["status"] == "eye_mismatch"
    bounds = policy(module="sans", measurement="near_acuity", unit="logMAR", eye="OD", lower="-0.2", upper="0.2")
    assert compare_threshold(eye, bounds)["status"] == "within_range"


def test_invalid_or_missing_numeric_data_is_not_compared():
    for item in [record(valid=False), record(valid=False, value_num=None)]:
        assert compare_threshold(item, policy())["breached"] is None


@pytest.mark.parametrize("updates", [{"lower": None, "upper": None}, {"lower": "30", "upper": "20"},
                                      {"lower": "NaN"}, {"upper": "Infinity"}])
def test_invalid_threshold_configuration_is_rejected(updates):
    with pytest.raises(ValidationError):
        policy(**updates)


def test_duplicate_contexts_and_private_features_cannot_be_enabled():
    rule = policy().rules[0]
    with pytest.raises(ValidationError):
        ThresholdPolicy(version="test", rules=(rule, rule))
    for code in ["who5_score", "phq2_score", "gad2_score", "pvt_speed"]:
        with pytest.raises(ValidationError):
            policy(measurement=code)
        with pytest.raises(ValidationError):
            FeatureDefinition(module="behavioral", measurement=code, unit="score",
                              protocol_version="test", definition_confirmed=True)


def test_policy_file_preserves_decimals_and_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "thresholds.json"
    path.write_text('{"version":"test","rules":[{"module":"physiological","measurement":"heart_rate",'
                    '"unit":"BPM","protocol_version":"module-v2","upper":0.30000000000000000001}]}', encoding="utf-8")
    assert load_threshold_policy(path).rules[0].upper == Decimal("0.30000000000000000001")
    path.write_text('{"version":"one","version":"two","rules":[]}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_threshold_policy(path)


def test_shipped_configuration_has_no_invented_thresholds():
    from tests.fixtures.history import ROOT
    assert not load_threshold_policy(ROOT / "config/thresholds.json").rules
    assert history_policy().sufficiency_policy_status == "not_configured"
    with pytest.raises(ValidationError):
        HistoryPolicy(**(history_policy().model_dump() | {"sufficiency_policy_status": "ready"}))
