"""Ö4 personal history and threshold snapshot; no model/provider/alert calls."""

import math
from collections import Counter, defaultdict
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from statistics import median
from typing import Protocol

from starlette.concurrency import run_in_threadpool

from app.core.snapshots import snapshot_hash
from app.repositories.records import AstronautRecord, JobRecord
from app.schemas.common import AnalysisModule, MeasurementDTO, ModuleScope, Source
from app.schemas.history import (
    DEFERRED_MEASUREMENTS, PRIVATE_MEASUREMENTS, HistoryPolicy, ThresholdPolicy,
)
from app.services.thresholds import compare_threshold, load_policy_json, load_threshold_policy


class HistoryDataError(Exception):
    """Safe preparation failure; never carries a source payload in its message."""


class HistoryRepository(Protocol):
    def get_astronaut(self, astronaut_id: str) -> AstronautRecord | None: ...

    def get_measurements(self, astronaut_id: str, start_date: date, end_date: date) -> list[MeasurementDTO]: ...


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoryDataError("UTC saat dilimi zorunlu.")
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _key(record: MeasurementDTO) -> tuple:
    return (record.module.value, record.measurement, record.unit, record.protocol_version,
            record.eye.value if record.eye else "")


def _safe_record(record: MeasurementDTO) -> dict:
    # Do not forward arbitrary A5 metadata, free text, device identifiers, checklist,
    # source profile fields or hidden evaluation data to the language model.
    result = record.model_dump(mode="json", exclude={"metadata_json", "value_text"})
    result["value_num_exact"] = str(record.value_num)
    source = (record.metadata_json or {}).get("original_source")
    result["metadata_json"] = ({"original_source": source}
                               if source in ("manual", "synthetic", "seed", "test_screen", "osdr") else None)
    return result


def _summary(records: list[MeasurementDTO], days: int, reference_date: date) -> dict:
    values = [record.value_num for record in records]
    by_day = defaultdict(list)
    for record in records:
        by_day[record.measured_date].append(record.value_num)
    first, last = min(by_day), max(by_day)
    with localcontext() as context:
        context.prec = 40
        mean = sum(values, Decimal(0)) / len(values)
        variance = sum(((value - mean) ** 2 for value in values), Decimal(0)) / len(values)
        first_mean = sum(by_day[first], Decimal(0)) / len(by_day[first])
        last_mean = sum(by_day[last], Decimal(0)) / len(by_day[last])
        stats = {"minimum": min(values), "maximum": max(values), "mean": mean,
                 "median": median(values), "population_stddev": variance.sqrt() if len(values) > 1 else None,
                 "first_day_mean": first_mean, "last_day_mean": last_mean,
                 "change_over_observed_period": last_mean - first_mean if last != first else None}
    sample = records[0]
    return {
        "module": sample.module.value, "measurement": sample.measurement, "unit": sample.unit,
        "protocol_version": sample.protocol_version, "eye": sample.eye.value if sample.eye else None,
        "record_count": len(records), "observed_days": len(by_day),
        "days_without_observations": days - len(by_day),  # NOT a missing expected daily sample count
        "first_date": first.isoformat(), "last_date": last.isoformat(),
        "span_days": (last - first).days, "latest_age_days": (reference_date - last).days,
        "statistics": {key: float(value) if value is not None else None for key, value in stats.items()},
        "statistics_exact": {key: str(value) if value is not None else None for key, value in stats.items()},
        "record_ids": [record.record_id for record in records],
        "current_record_ids": [record.record_id for record in records if record.measured_date == last],
    }


def build_history_snapshot(
    job: JobRecord, profile: AstronautRecord, records: list[MeasurementDTO],
    history: HistoryPolicy, thresholds: ThresholdPolicy, read_started_at: datetime,
    read_completed_at: datetime, reference_date: date | None = None,
) -> dict:
    if job.module != AnalysisModule.ANOMALY or job.request.module_scope is None:
        raise HistoryDataError("Anomali işi ve kapsamı zorunlu.")
    if profile.astronaut_id != job.astronaut_id or profile.is_display_only:
        raise HistoryDataError("Aktif astronot kapsamı geçersiz.")
    started, completed = _utc(read_started_at), _utc(read_completed_at)
    if completed < started:
        raise HistoryDataError("Okuma zamanları tutarsız.")
    explicit_reference = reference_date is not None
    reference = reference_date if explicit_reference else started.date()
    end = reference + timedelta(days=1)
    start, recent_start = end - timedelta(days=history.summary_days), end - timedelta(days=history.recent_days)
    # Explicit demo dates are date-only cutoffs; never manufacture a timestamp.
    timestamp_cutoff = None if explicit_reference else started
    features = {definition.key(): definition for definition in history.features}
    accepted, excluded, seen = [], [], {}
    for record in records:
        if not isinstance(record, MeasurementDTO):
            raise HistoryDataError("Repository ortak ölçüm DTO'su döndürmelidir.")
        if record.astronaut_id != profile.astronaut_id or record.mission_id != profile.mission_id:
            raise HistoryDataError("Ölçüm kişi/görev kapsamı tutarsız.")
        if record.measurement.lower() in PRIVATE_MEASUREMENTS | DEFERRED_MEASUREMENTS:
            continue  # No value, reference or diagnostic reaches the model for these sources.
        if job.request.module_scope != ModuleScope.COMBINED and record.module.value != job.request.module_scope.value:
            continue
        if not start <= record.measured_date < end:
            continue
        if timestamp_cutoff is not None and record.measured_at is not None and record.measured_at > timestamp_cutoff:
            continue
        # Duplicate source references must not inflate summaries. Conflicts fail closed.
        safe = _safe_record(record)
        if record.record_id in seen:
            if seen[record.record_id] != safe:
                raise HistoryDataError("Aynı kaynak referansında çelişkili veri.")
            continue
        seen[record.record_id] = safe
        feature = features.get(_key(record)[:4])
        reason = None
        if feature is None or not feature.definition_confirmed:
            reason = "definition_not_configured"
        elif not record.valid:
            reason = "invalid_record"
        elif record.value_num is None or not record.value_num.is_finite() or not math.isfinite(float(record.value_num)):
            reason = "numeric_value_unavailable"
        elif record.quality_score is not None and feature.minimum_quality_score is None:
            reason = "quality_policy_not_configured"
        elif feature.minimum_quality_score is not None and record.quality_score is None:
            reason = "quality_score_missing"
        elif feature.minimum_quality_score is not None and record.quality_score < feature.minimum_quality_score:
            reason = "low_quality"
        if reason:
            excluded.append({"record_id": record.record_id, "reason": reason,
                             "valid": record.valid,
                             "quality_score": str(record.quality_score) if record.quality_score is not None else None})
        else:
            accepted.append(record)
    accepted.sort(key=lambda record: (record.measured_date, record.measured_at.isoformat() if record.measured_at else "",
                                      record.record_id))
    excluded.sort(key=lambda item: (item["record_id"], item["reason"]))
    groups = defaultdict(list)
    for record in accepted:
        groups[_key(record)].append(record)
    summaries = [_summary(groups[key], history.summary_days, reference) for key in sorted(groups)]
    current_ids = {record_id for summary in summaries for record_id in summary["current_record_ids"]}
    current = [record for record in accepted if record.record_id in current_ids]
    recent = [record for record in accepted if record.measured_date >= recent_start]
    findings = [compare_threshold(record, thresholds) for record in current]
    model_input = {
        "astronaut_id": profile.astronaut_id, "mission_id": profile.mission_id,
        "module_scope": job.request.module_scope.value, "reference_date": reference.isoformat(),
        "history_window": {"start_date": start.isoformat(), "end_date_exclusive": end.isoformat(), "days": history.summary_days},
        "recent_window": {"start_date": recent_start.isoformat(), "end_date_exclusive": end.isoformat(), "days": history.recent_days},
        "summary": summaries, "current_measurements": [_safe_record(record) for record in current],
        "recent_details": [_safe_record(record) for record in recent], "threshold_findings": findings,
        "valid_threshold_breach_record_ids": [item["record_id"] for item in findings if item["breached"] is True],
        "overlap": {"recent_records_are_in_summary": True, "current_records_are_in_summary": True,
                    "recent_record_ids": [record.record_id for record in recent],
                    "current_record_ids": sorted(current_ids), "independent_sample_sets": False},
        "contains_synthetic_data": any(record.source == Source.SYNTHETIC for record in accepted),
        "history_policy_version": history.version, "threshold_policy_version": thresholds.version,
        "sufficiency": {"status": "not_configured", "baseline_status": None},
    }
    snapshot = {
        "schema_version": "anomaly-input-v1", "job_id": str(job.job_id), "module": "anomaly",
        "data_cutoff_at": _iso(started),
        "source_read": {"started_at": _iso(started), "completed_at": _iso(completed),
                        "consistency": "read_committed_not_global_snapshot",
                        "reference_mode": "explicit_date" if explicit_reference else "utc_now",
                        "measurement_timestamp_cutoff": _iso(timestamp_cutoff) if timestamp_cutoff else None},
        "history_policy": history.model_dump(mode="json"),
        "threshold_policy": thresholds.model_dump(mode="json"),
        "history_policy_hash": snapshot_hash(history.model_dump(mode="json")),
        "threshold_policy_hash": snapshot_hash(thresholds.model_dump(mode="json")),
        "history_records": [_safe_record(record) for record in accepted],
        "excluded_records": excluded,
        "exclusion_counts": dict(sorted(Counter(item["reason"] for item in excluded).items())),
        "model_input": model_input,
    }
    snapshot_hash(snapshot)  # reject non-JSON/NaN output before returning to the worker
    return snapshot


class HistoryPreparer:
    def __init__(self, sources: Callable[[], AbstractContextManager[HistoryRepository]],
                 history_policy_path: Path, threshold_policy_path: Path,
                 reference_date: date | None = None, clock: Callable[[], datetime] | None = None):
        self.sources, self.history_path, self.threshold_path = sources, history_policy_path, threshold_policy_path
        self.reference_date, self.clock = reference_date, clock or (lambda: datetime.now(UTC))

    def _prepare(self, job: JobRecord) -> dict:
        if job.module != AnalysisModule.ANOMALY or job.request.module_scope is None:
            raise HistoryDataError("Anomali işi ve kapsamı zorunlu.")
        history = HistoryPolicy.model_validate(load_policy_json(self.history_path))
        thresholds = load_threshold_policy(self.threshold_path)
        started = _utc(self.clock())
        reference = self.reference_date or started.date()
        end = reference + timedelta(days=1)
        with self.sources() as repo:
            profile = repo.get_astronaut(job.astronaut_id)
            if profile is None or profile.is_display_only:
                raise HistoryDataError("Aktif astronot profili bulunamadı.")
            records = [record.model_copy(deep=True) for record in repo.get_measurements(
                job.astronaut_id, end - timedelta(days=history.summary_days), end)]
        completed = _utc(self.clock())
        return build_history_snapshot(job, profile, records, history, thresholds, started, completed, self.reference_date)

    async def prepare(self, job: JobRecord) -> dict:
        # Open/read/close in one worker operation; summarize after the context closes.
        return await run_in_threadpool(self._prepare, job)
