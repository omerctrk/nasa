"""Exact context matching and decimal deviations; no alert/risk decisions."""

import json
from decimal import Decimal
from pathlib import Path

from app.schemas.common import MeasurementDTO
from app.schemas.history import ThresholdPolicy


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Politika dosyasında tekrarlı JSON anahtarı.")
        result[key] = value
    return result


def load_policy_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_float=Decimal,
                      object_pairs_hook=_unique_object)


def load_threshold_policy(path: Path) -> ThresholdPolicy:
    # parse_float avoids losing the team's decimal limits before comparison.
    return ThresholdPolicy.model_validate(load_policy_json(path))


def compare_threshold(record: MeasurementDTO, policy: ThresholdPolicy) -> dict:
    finding = {"record_id": record.record_id, "policy_version": policy.version,
               "status": "not_configured", "breached": None, "lower": None, "upper": None,
               "value_minus_bound": None, "absolute_deviation": None}
    if not record.valid or record.value_num is None or not record.value_num.is_finite():
        return finding | {"status": "invalid_data"}
    candidates = [rule for rule in policy.rules
                  if rule.module == record.module and rule.measurement == record.measurement]
    for attribute, status in (("eye", "eye_mismatch"), ("unit", "unit_mismatch"),
                              ("protocol_version", "protocol_mismatch")):
        if not candidates:
            return finding
        matching = [rule for rule in candidates if getattr(rule, attribute) == getattr(record, attribute)]
        if not matching:
            return finding | {"status": status}
        candidates = matching
    if not candidates:
        return finding
    rule = candidates[0]
    # Decimal strings are exact evidence. No normalization, percentage or risk score.
    finding |= {"lower": str(rule.lower) if rule.lower is not None else None,
                "upper": str(rule.upper) if rule.upper is not None else None}
    bound = None
    if rule.lower is not None and record.value_num < rule.lower:
        status, bound = "below_range", rule.lower
    elif rule.upper is not None and record.value_num > rule.upper:
        status, bound = "above_range", rule.upper
    else:
        return finding | {"status": "within_range", "breached": False,
                          "absolute_deviation": "0"}
    delta = record.value_num - bound
    return finding | {"status": status, "breached": True,
                      "value_minus_bound": str(delta), "absolute_deviation": str(abs(delta))}
