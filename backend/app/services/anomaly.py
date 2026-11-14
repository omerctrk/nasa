"""Ö5 değerlendirme + Ö6 kalıcı yazım: anomali analiz pipeline'ı (Ömer'in kalan kısmı, Aybala).

Akış (işçi çağırır, contracts/analysis-worker.md):
  prepare  → Ö4 HistoryPreparer (Ömer) donmuş snapshot'ı hazırlar.
  evaluate → bu dosya: eşik bulguları + Yusuf'un kart önericisi (isteğe bağlı Ollama).
  persist  → aynı Session'da anomaly_results + ops.Alerts + NotificationEvents; commit yok.

Karar kuralları (sayı UYDURMAZ; eşikler config/thresholds.json'dan, ekip doldurur):
  - Güncel ölçüm yoksa → insufficient_data (sonuç satırı yazılmaz).
  - Hiçbir güncel ölçüm için eşik tanımlı değilse → insufficient_data. "Bilinmeyen normal
    değildir" (history-thresholds.md).
  - Eşik ihlali yok → level=normal.
  - En az bir ihlal → en az watch (sözleşmedeki "minimum watch kuralı").
  - Kart önericisi doktora yükseltme derse (acil kart, kartsız bulgu, spo2↓ …) → review.
    Bu yükseltme kararını Yusuf'un KODU verir, model değil.
  - Alarm şiddeti (İş Bölümü §5 "tek eşleme"): anomali watch/review → WARNING; normal → alarm yok.
  - Bildirim (şema §8): riskli sonuçta olay alert_id taşır (kule + astronot); normal/sonuçsuz
    tamamlanmada astronota job_id'li analysis.completed. Riskli işe ayrıca tamamlanma olayı yok.
  - provider_metadata: sağlayıcı/model/prompt sürümü, ham model cevapları, seviye gerekçesi.
  - baseline_status=provisional: veri yeterlilik politikası yok, ready denmez.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.providers import kart_onerici
from app.providers.ollama import Sor
from app.repositories.records import (
    AlertCreate,
    AnomalyResultData,
    JobOutcome,
    JobRecord,
    NotificationEventCreate,
)
from app.schemas.common import (
    AnalysisModule,
    AnomalyLevel,
    Audience,
    BaselineStatus,
    DataQualityStatus,
    EvaluationStatus,
    EventType,
    JobState,
    ModuleScope,
    Severity,
)
from app.workers.analysis import InvalidModelOutput, PermanentModelError

# Bizim ölçüm kodlarımız ↔ kart destesindeki metrik adları (aynı olanlar listelenmez).
CARD_METRIC = {
    "pvt_mean_rt": "pvt_mean_rt_ms",
    "rotation_mean_rt": "rotation_mean_rt_ms",
    "body_temperature": "body_temp",
    "crew": "crew_relation",
}
ALERT_SEVERITY = {AnomalyLevel.WATCH: Severity.WARNING, AnomalyLevel.REVIEW: Severity.WARNING}
PROMPT_VERSION = "kart_onerici@401648d"  # Yusuf'un LLM dalındaki sürüm
CONFIGURED = {"within_range", "below_range", "above_range"}
DIRECTION = {"above_range": "up", "below_range": "down"}


@dataclass(frozen=True)
class Evaluation:
    status: EvaluationStatus
    result: AnomalyResultData | None = None
    outcome: dict[str, Any] | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)


def load_cards(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _breaches(model_input: dict) -> list[dict]:
    current = {r["record_id"]: r for r in model_input.get("current_measurements", [])}
    drivers = []
    for finding in model_input.get("threshold_findings", []):
        if finding.get("breached") is not True:
            continue
        record = current.get(finding["record_id"])
        if record is None:
            raise InvalidModelOutput()  # bulgu, snapshot'taki güncel kayda dayanmalı
        drivers.append({
            "record_id": record["record_id"], "module": record["module"],
            "measurement": record["measurement"], "unit": record["unit"],
            "value": record["value_num_exact"], "measured_date": record["measured_date"],
            "status": finding["status"], "direction": DIRECTION[finding["status"]],
            "lower": finding["lower"], "upper": finding["upper"],
            "value_minus_bound": finding["value_minus_bound"],
            "threshold_policy_version": finding["policy_version"],
        })
    return drivers


def _deviations(drivers: list[dict]) -> dict:
    """Kart önericisinin girdisi: {metrik: {direction, value, baseline?, unit}}."""
    out: dict[str, dict] = {}
    for d in drivers:
        metric = CARD_METRIC.get(d["measurement"], d["measurement"])
        bound = d["upper"] if d["direction"] == "up" else d["lower"]
        out.setdefault(metric, {"direction": d["direction"], "value": d["value"],
                                "limit": bound, "unit": d["unit"]})
    return out


def _advice(deviations: dict, cards: list[dict], sor: Sor | None, raw: list) -> dict:
    if sor is not None:
        def recording_sor(mesajlar, sema, deneme=0):
            answer = sor(mesajlar, sema, deneme)
            raw.append(answer)  # ham model cevabı yalnız provider_metadata'ya gider
            return answer
        return kart_onerici.oner(deviations, cards, sor=recording_sor)
    # Model bağlı değil: Yusuf'un kod kararları (kart seçimi, acil kart, yükseltme) yine çalışır.
    bos = {"summary": "", "explanations": [], "recommendations": [], "unmatched_findings": []}
    unmatched = kart_onerici.eslesmeyenler(deviations, cards)
    selected, emergency = kart_onerici.kart_sec(deviations, cards)
    no_action = kart_onerici.aksiyonsuzlar(deviations, selected)
    return kart_onerici.dogrula(bos, deviations, selected, emergency, unmatched, no_action)


def _code_summary(drivers: list[dict]) -> str:
    parts = []
    for d in drivers:
        side = "üst sınır" if d["direction"] == "up" else "alt sınır"
        limit = d["upper"] if d["direction"] == "up" else d["lower"]
        parts.append(f"{d['measurement']} {d['value']} {d['unit']} ({side} {limit})")
    return "Eşik dışı ölçüm: " + "; ".join(parts) + "."


def evaluate_snapshot(job: JobRecord, snapshot: dict, cards: list[dict],
                      sor: Sor | None = None, model_name: str | None = None) -> Evaluation:
    if job.module != AnalysisModule.ANOMALY or snapshot.get("module") != "anomaly":
        raise PermanentModelError()
    model_input = snapshot["model_input"]
    if model_input.get("astronaut_id") != job.astronaut_id:
        raise InvalidModelOutput()
    meta = {"algorithm": "threshold_rules", "provider": None, "model": None,
            "threshold_policy_version": model_input.get("threshold_policy_version")}
    if not model_input.get("current_measurements"):
        return Evaluation(EvaluationStatus.INSUFFICIENT_DATA,
                          outcome={"reason": "no_current_measurements",
                                   "message": "Analiz penceresinde güncel ölçüm yok."},
                          provider_metadata=meta)
    findings = model_input.get("threshold_findings", [])
    if not any(f.get("status") in CONFIGURED for f in findings):
        return Evaluation(EvaluationStatus.INSUFFICIENT_DATA,
                          outcome={"reason": "thresholds_not_configured",
                                   "message": "Güncel ölçümler için tanımlı eşik yok; "
                                              "karar verilmedi (bilinmeyen normal sayılmaz)."},
                          provider_metadata=meta)

    drivers = _breaches(model_input)
    summary, recommendation, level = "Güncel ölçümler tanımlı eşikler içinde.", "", AnomalyLevel.NORMAL
    meta["level_reason"] = "no_threshold_breach"
    if drivers:
        raw: list = []
        advice = _advice(_deviations(drivers), cards, sor, raw)
        level = AnomalyLevel.REVIEW if advice["escalate_to_physician"] else AnomalyLevel.WATCH
        meta["level_reason"] = ("physician_escalation: " + "; ".join(advice["escalation_reasons"])
                                if advice["escalate_to_physician"] else "threshold_breach_minimum_watch")
        summary = advice["summary"].strip() or _code_summary(drivers)
        actions = [r["action"] for r in advice["recommendations"]]
        if advice["escalate_to_physician"]:
            actions.insert(0, "Uçuş hekimine bildirin: " + "; ".join(advice["escalation_reasons"]) + ".")
        recommendation = "\n".join(actions)
        drivers.append({"type": "advice", "disclaimer": advice["disclaimer"],
                        "explanations": advice["explanations"],
                        "recommendations": advice["recommendations"],
                        "emergency": advice["emergency"],
                        "unmatched_findings": advice["unmatched_findings"],
                        "escalation_reasons": advice["escalation_reasons"]})
        if sor is not None:
            meta |= {"algorithm": "threshold_rules_plus_llm", "provider": "ollama",
                     "model": model_name, "prompt_version": PROMPT_VERSION,
                     "raw_model_outputs": raw,
                     "llm_attempts": advice.get("attempts"),
                     "llm_dropped": len(advice.get("dropped", [])),
                     "llm_error": bool(advice.get("error"))}
    result = AnomalyResultData(
        astronaut_id=job.astronaut_id, mission_day=None,
        module_scope=ModuleScope(model_input["module_scope"]),
        algorithm=meta["algorithm"], model_version=model_name if sor is not None and drivers else None,
        is_anomaly=level is not AnomalyLevel.NORMAL, level=level,
        summary=summary[:4000], drivers=drivers,
        baseline_status=BaselineStatus.PROVISIONAL,
        data_quality_status=DataQualityStatus.VALID,
        recommendation=recommendation[:2000],
        data_cutoff_at=datetime.fromisoformat(snapshot["data_cutoff_at"].replace("Z", "+00:00")),
    )
    return Evaluation(EvaluationStatus.EVALUATED, result=result, provider_metadata=meta)


def persist_evaluation(repo, job: JobRecord, evaluation: Evaluation) -> JobOutcome:
    """Ö6: aynı Session; sonuç → alarm → olaylar. Commit/dış çağrı yok."""
    if not isinstance(evaluation, Evaluation):
        raise InvalidModelOutput()
    result_id, alert = None, None
    if evaluation.status is EvaluationStatus.EVALUATED:
        result_id = repo.save_anomaly_result(evaluation.result)
        severity = ALERT_SEVERITY.get(evaluation.result.level)
        if severity is not None:
            alert = repo.create_alert(AlertCreate(
                astronaut_id=job.astronaut_id, module=AnalysisModule.ANOMALY,
                severity=severity, anomaly_result_id=result_id))
    astronaut_user = repo.get_user_for_astronaut(job.astronaut_id)
    if alert is not None:
        # Riskli sonuç: olay alert_id taşır; kule ve (varsa) astronot hesabı alır.
        payload = {"alert_id": str(alert.alert_id), "astronaut_id": job.astronaut_id,
                   "module": "anomaly", "severity": alert.severity.value,
                   "level": evaluation.result.level.value, "job_id": str(job.job_id),
                   "anomaly_result_id": str(result_id)}
        repo.create_notification_event(NotificationEventCreate(
            event_type=EventType.RISK_ALERT_CREATED, audience=Audience.GROUND_CONTROL,
            target_user_id=None, alert_id=alert.alert_id, payload=payload))
        if astronaut_user is not None:
            repo.create_notification_event(NotificationEventCreate(
                event_type=EventType.RISK_ALERT_CREATED, audience=Audience.ASTRONAUT,
                target_user_id=astronaut_user, alert_id=alert.alert_id, payload=payload))
    elif astronaut_user is not None:
        # Normal veya sonuçsuz tamamlanma: job_id'li tek tamamlanma olayı.
        repo.create_notification_event(NotificationEventCreate(
            event_type=EventType.ANALYSIS_COMPLETED, audience=Audience.ASTRONAUT,
            target_user_id=astronaut_user, job_id=job.job_id,
            payload={"module": "anomaly", "job_id": str(job.job_id),
                     "evaluation_status": evaluation.status.value,
                     "anomaly_result_id": str(result_id) if result_id else None,
                     "level": evaluation.result.level.value if evaluation.result else None}))
    return JobOutcome(state=JobState.COMPLETED, evaluation_status=evaluation.status,
                      anomaly_result_id=result_id, outcome=evaluation.outcome,
                      provider_metadata=evaluation.provider_metadata or None)


class AnomalyPipeline:
    def __init__(self, preparer, cards: list[dict], sor: Sor | None = None,
                 model_name: str | None = None):
        self.preparer, self.cards, self.sor, self.model_name = preparer, cards, sor, model_name

    async def prepare(self, job: JobRecord) -> dict:
        return await self.preparer.prepare(job)

    async def evaluate(self, job: JobRecord, snapshot: dict) -> Evaluation:
        return await run_in_threadpool(evaluate_snapshot, job, snapshot, self.cards,
                                       self.sor, self.model_name)

    def persist(self, repo, job: JobRecord, result: object) -> JobOutcome:
        return persist_evaluation(repo, job, result)


class ClosedSansPipeline:
    """SANS kapatıldı: API SANS işi almaz. Eski bir SANS işi kalmışsa güvenle FAILED olur."""

    async def prepare(self, job: JobRecord) -> dict:
        raise PermanentModelError()

    async def evaluate(self, job: JobRecord, snapshot: dict) -> object:
        raise PermanentModelError()

    def persist(self, repo, job: JobRecord, result: object) -> JobOutcome:
        raise InvalidModelOutput()
