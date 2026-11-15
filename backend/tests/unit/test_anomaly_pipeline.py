"""Ö5/Ö6 anomali pipeline'ı: karar kuralları, kart önericisi bağlantısı, kalıcı yazım, Ollama hataları."""
import io
import json
import urllib.error
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.pipeline_runtime import configure_pipelines
from app.providers import ollama
from app.repositories.records import AlertRecord, JobRecord, JobRequestData
from app.schemas.common import (
    AlertStatus,
    AnalysisModule,
    AnomalyLevel,
    Audience,
    EvaluationStatus,
    EventType,
    JobState,
    ModuleScope,
    Severity,
)
from app.services.anomaly import (
    AnomalyPipeline,
    ClosedSansPipeline,
    Evaluation,
    evaluate_snapshot,
    load_cards,
    persist_evaluation,
)
from app.workers.analysis import InvalidModelOutput, PermanentModelError, TransientModelError

CARDS = load_cards(Path(__file__).resolve().parents[2] / "config/knowledge_cards.json")
NOW = datetime(2027, 3, 15, 8, tzinfo=UTC)


def job(module=AnalysisModule.ANOMALY, astronaut="A007"):
    request = (JobRequestData(module=module, module_scope=ModuleScope.PHYSIOLOGICAL)
               if module is AnalysisModule.ANOMALY else JobRequestData(module=module, session_id="S1"))
    return JobRecord(job_id=uuid.uuid4(), astronaut_id=astronaut, module=module,
                     state=JobState.ANALYZING, request=request, attempts=1, retry_cycle=0,
                     has_snapshot=True, evaluation_status=None, error_code=None,
                     anomaly_result_id=None, sans_analysis_id=None, created_at=NOW, updated_at=NOW)


def record(rid, measurement="heart_rate", value="72", unit="BPM"):
    return {"record_id": rid, "module": "physiological", "measurement": measurement,
            "unit": unit, "value_num_exact": value, "measured_date": "2027-03-14"}


def finding(rid, status, lower="50", upper="100", delta=None):
    breached = {"within_range": False, "not_configured": None}.get(status, True)
    return {"record_id": rid, "policy_version": "t-1", "status": status, "breached": breached,
            "lower": lower, "upper": upper, "value_minus_bound": delta, "absolute_deviation": None}


def snapshot(records, findings, astronaut="A007"):
    return {"module": "anomaly", "data_cutoff_at": "2027-03-15T07:59:00.000Z",
            "model_input": {"astronaut_id": astronaut, "module_scope": "physiological",
                            "threshold_policy_version": "t-1",
                            "current_measurements": records, "threshold_findings": findings}}


def test_no_current_measurements_is_insufficient():
    ev = evaluate_snapshot(job(), snapshot([], []), CARDS)
    assert ev.status is EvaluationStatus.INSUFFICIENT_DATA and ev.result is None
    assert ev.outcome["reason"] == "no_current_measurements"


def test_all_excluded_records_are_reported_separately_from_no_data():
    frozen = snapshot([], []) | {"exclusion_counts": {"definition_not_configured": 710,
                                                      "quality_policy_not_configured": 365}}
    ev = evaluate_snapshot(job(), frozen, CARDS)
    assert ev.status is EvaluationStatus.INSUFFICIENT_DATA and ev.result is None
    assert ev.outcome["reason"] == "all_records_excluded"
    assert ev.outcome["exclusion_counts"] == frozen["exclusion_counts"]


def test_unconfigured_thresholds_are_not_normal():
    ev = evaluate_snapshot(job(), snapshot([record("r1")], [finding("r1", "not_configured")]), CARDS)
    assert ev.status is EvaluationStatus.INSUFFICIENT_DATA
    assert ev.outcome["reason"] == "thresholds_not_configured"


def test_within_range_is_normal_without_model_call():
    def sor(*_):
        raise AssertionError("ihlal yokken model çağrılmaz")
    ev = evaluate_snapshot(job(), snapshot([record("r1")], [finding("r1", "within_range")]),
                           CARDS, sor=sor, model_name="m")
    assert ev.status is EvaluationStatus.EVALUATED
    assert ev.result.level is AnomalyLevel.NORMAL and ev.result.is_anomaly is False
    assert ev.result.drivers == [] and ev.result.algorithm == "threshold_rules"


def test_breach_is_at_least_watch_and_code_summary_without_model():
    snap = snapshot([record("r1", value="112")], [finding("r1", "above_range", delta="12")])
    ev = evaluate_snapshot(job(), snap, CARDS)
    r = ev.result
    assert r.level in (AnomalyLevel.WATCH, AnomalyLevel.REVIEW) and r.is_anomaly
    assert r.drivers[0]["measurement"] == "heart_rate" and r.drivers[0]["direction"] == "up"
    assert r.drivers[-1]["type"] == "advice"
    assert "heart_rate 112 BPM" in r.summary and r.model_version is None


def test_unmatched_metric_escalates_to_review():
    # blood_glucose için kart yok → Yusuf'un kodu doktora yükseltir → review.
    snap = snapshot([record("r1", "blood_glucose", "250", "mg/dL")],
                    [finding("r1", "above_range", upper="180", delta="70")])
    ev = evaluate_snapshot(job(), snap, CARDS)
    assert ev.result.level is AnomalyLevel.REVIEW
    assert ev.result.recommendation.startswith("Uçuş hekimine bildirin")
    assert ev.provider_metadata["level_reason"].startswith("physician_escalation")


def test_model_answer_is_used_and_metadata_recorded():
    def sor(mesajlar, sema, deneme=0):
        return {"summary": "Nabız yüksek.", "explanations": [], "unmatched_findings": []}
    # Kart önerici v4: model yalnız açıklanacak risk/belirti kartı varsa çağrılır. Uçuşta
    # (bağlam "general") yüksek vücut ısısının risk kartları var; nabız kartları iniş bağlamında.
    snap = snapshot([record("r1", "body_temperature", "37.6", "°C")],
                    [finding("r1", "above_range", lower="36", upper="37.1", delta="0.5")])
    ev = evaluate_snapshot(job(), snap, CARDS, sor=sor, model_name="qwen3:14b")
    assert ev.result.summary == "Nabız yüksek."
    assert ev.result.model_version == "qwen3:14b"
    meta = ev.provider_metadata
    assert meta["algorithm"] == "threshold_rules_plus_llm" and meta["provider"] == "ollama"
    assert meta["raw_model_outputs"][0]["summary"] == "Nabız yüksek."  # ham cevap saklanır
    assert meta["prompt_version"] and meta["level_reason"]


def test_snapshot_for_other_astronaut_or_module_is_rejected():
    with pytest.raises(InvalidModelOutput):
        evaluate_snapshot(job(), snapshot([record("r1")], [], astronaut="A008"), CARDS)
    with pytest.raises(PermanentModelError):
        evaluate_snapshot(job(AnalysisModule.SANS), snapshot([], []), CARDS)
    with pytest.raises(InvalidModelOutput):  # bulgu, snapshot'ta olmayan kayda dayanamaz
        evaluate_snapshot(job(), snapshot([record("r1")], [finding("rX", "above_range")]), CARDS)


class FakeRepo:
    def __init__(self, user=uuid.uuid4()):
        self.user, self.results, self.alerts, self.events = user, [], [], []

    def save_anomaly_result(self, result):
        self.results.append(result)
        return uuid.uuid4()

    def create_alert(self, alert):
        self.alerts.append(alert)
        return AlertRecord(alert_id=uuid.uuid4(), astronaut_id=alert.astronaut_id,
                           module=alert.module, severity=alert.severity, status=AlertStatus.OPEN,
                           anomaly_result_id=alert.anomaly_result_id, sans_analysis_id=None,
                           acknowledged_by=None, acknowledged_at=None, resolved_by=None,
                           resolved_at=None, resolution_note=None, created_at=NOW)

    def get_user_for_astronaut(self, astronaut_id):
        return self.user

    def create_notification_event(self, event):
        self.events.append(event)


def test_persist_risk_creates_result_alert_and_alert_events_only():
    snap = snapshot([record("r1", value="112")], [finding("r1", "above_range", delta="12")])
    ev = evaluate_snapshot(job(), snap, CARDS)
    j, repo = job(), FakeRepo()
    out = persist_evaluation(repo, j, ev)
    assert out.evaluation_status is EvaluationStatus.EVALUATED and out.anomaly_result_id
    assert repo.alerts[0].severity is Severity.WARNING  # İş Bölümü §5: watch/review → WARNING
    # Şema §8: riskli sonuçta olay alert_id taşır; ayrıca tamamlanma olayı üretilmez.
    assert {(e.event_type, e.audience) for e in repo.events} == {
        (EventType.RISK_ALERT_CREATED, Audience.GROUND_CONTROL),
        (EventType.RISK_ALERT_CREATED, Audience.ASTRONAUT)}
    assert all(e.alert_id and e.job_id is None for e in repo.events)
    mine = next(e for e in repo.events if e.audience is Audience.ASTRONAUT)
    assert mine.target_user_id == repo.user and mine.payload["job_id"] == str(j.job_id)


@pytest.mark.parametrize("level", [AnomalyLevel.WATCH, AnomalyLevel.REVIEW])
def test_every_risky_level_maps_to_warning(level):
    from app.services.anomaly import ALERT_SEVERITY
    assert ALERT_SEVERITY[level] is Severity.WARNING
    assert AnomalyLevel.NORMAL not in ALERT_SEVERITY


def test_persist_normal_has_no_alert_and_insufficient_has_no_result():
    repo = FakeRepo()
    normal = evaluate_snapshot(job(), snapshot([record("r1")], [finding("r1", "within_range")]), CARDS)
    persist_evaluation(repo, job(), normal)
    assert len(repo.results) == 1 and repo.alerts == [] and len(repo.events) == 1
    repo = FakeRepo()
    out = persist_evaluation(repo, job(), evaluate_snapshot(job(), snapshot([], []), CARDS))
    assert out.anomaly_result_id is None and out.outcome["reason"] == "no_current_measurements"
    assert repo.results == [] and repo.events[0].payload["evaluation_status"] == "insufficient_data"
    with pytest.raises(InvalidModelOutput):
        persist_evaluation(repo, job(), {"level": "normal"})


def test_closed_sans_pipeline_fails_safely():
    import asyncio
    with pytest.raises(PermanentModelError):
        asyncio.run(ClosedSansPipeline().prepare(job(AnalysisModule.SANS)))


def test_configure_pipelines_only_with_history_preparer():
    class App:
        class state:
            pass
    settings = Settings(db_password="x")
    configure_pipelines(App, settings)
    assert App.state.analysis_pipelines is None
    App.state.history_preparer = object()
    configure_pipelines(App, settings)
    pipes = App.state.analysis_pipelines
    assert isinstance(pipes[AnalysisModule.ANOMALY], AnomalyPipeline)
    assert pipes[AnalysisModule.ANOMALY].sor is None  # LLM_BASE_URL yok → model çağrılmaz
    assert set(pipes) == {AnalysisModule.ANOMALY}


def _urlopen(response=None, error=None):
    def fake(request, timeout):
        if error:
            raise error
        return io.BytesIO(json.dumps(response).encode())
    return fake


def test_ollama_sor_parses_content(monkeypatch):
    seen = {}

    def fake(request, timeout):
        seen["body"] = json.loads(request.data)
        return io.BytesIO(json.dumps({"message": {"content": '{"summary": "x"}'}}).encode())
    monkeypatch.setattr(ollama.urllib.request, "urlopen", fake)
    sor = ollama.ollama_sor("http://ollama:11434/", "qwen3:14b", 5, 60)
    assert sor([{"role": "user", "content": "?"}], {"type": "object"}, 0) == {"summary": "x"}
    assert seen["body"]["model"] == "qwen3:14b" and seen["body"]["stream"] is False


@pytest.mark.parametrize("error, expected", [
    (urllib.error.URLError("down"), TransientModelError),
    (TimeoutError(), TransientModelError),
    (urllib.error.HTTPError("u", 503, "x", {}, None), TransientModelError),
])
def test_ollama_errors_are_classified(monkeypatch, error, expected):
    monkeypatch.setattr(ollama.urllib.request, "urlopen", _urlopen(error=error))
    with pytest.raises(expected):
        ollama.ollama_sor("http://o", "m", 5, 60)([], {}, 0)


def test_ollama_4xx_retries_with_plain_schema_then_permanent(monkeypatch):
    calls = []

    def fake(request, timeout):
        calls.append(1)
        raise urllib.error.HTTPError("u", 400, "x", {}, None)
    monkeypatch.setattr(ollama.urllib.request, "urlopen", fake)
    with pytest.raises(PermanentModelError):
        ollama.ollama_sor("http://o", "m", 5, 60)([], {"type": "object"}, 0)
    assert len(calls) == 2


def test_pipeline_evaluate_runs_in_thread():
    import asyncio
    pipe = AnomalyPipeline(preparer=None, cards=CARDS)
    ev = asyncio.run(pipe.evaluate(job(), snapshot([], [])))
    assert isinstance(ev, Evaluation) and ev.status is EvaluationStatus.INSUFFICIENT_DATA


# --- Model geri dönüşü: model yalnız açıklama yazar; hatası kararı/alarmı düşürmez ---------

def _risk_snapshot():
    # Uçuş bağlamında risk kartı olan ölçüm: model gerçekten çağrılır (kart önerici v4).
    return snapshot([record("r1", "body_temperature", "37.8", "°C")],
                    [finding("r1", "above_range", lower="36", upper="37.1", delta="0.7")])


@pytest.mark.parametrize("error, code", [
    (TransientModelError(), "MODEL_CONNECTION_ERROR"),
    (PermanentModelError(), "MODEL_REQUEST_REJECTED"),
    (TimeoutError(), "MODEL_TIMEOUT"),
])
def test_model_failure_falls_back_to_rule_decision(error, code):
    import asyncio
    calls = []

    def sor(*_):
        calls.append(1)
        raise error
    pipe = AnomalyPipeline(preparer=None, cards=CARDS, sor=sor, model_name="qwen3:14b",
                           model_budget_seconds=5)
    ev = asyncio.run(pipe.evaluate(job(), _risk_snapshot()))
    expected = evaluate_snapshot(job(), _risk_snapshot(), CARDS)  # modelsiz karar
    assert calls, "model çağrılmalıydı"
    assert ev.status is EvaluationStatus.EVALUATED
    assert ev.result.level is expected.result.level and ev.result.is_anomaly
    assert ev.result.recommendation == expected.result.recommendation
    assert ev.result.model_version is None and ev.result.algorithm == "threshold_rules"
    assert "body_temperature 37.8" in ev.result.summary  # kodla yazılan özet
    meta = ev.provider_metadata
    assert meta["llm_fallback"] == code and meta["llm_error"] is True
    assert meta["llm_model_requested"] == "qwen3:14b" and meta["algorithm"] == "threshold_rules"


def test_slow_model_is_abandoned_within_budget():
    import asyncio
    import threading
    import time
    release = threading.Event()

    def sor(*_):
        release.wait(5)  # askıda kalan model
        return {"summary": "geç", "explanations": [], "unmatched_findings": []}
    pipe = AnomalyPipeline(preparer=None, cards=CARDS, sor=sor, model_name="m",
                           model_budget_seconds=0.3)

    async def timed():
        # Süre olay döngüsü İÇİNDE ölçülür: asyncio.run kapanışta bırakılan iş parçacığını
        # bekler; uygulamada döngü yaşar, işçi beklemez.
        t0 = time.monotonic()
        try:
            return await pipe.evaluate(job(), _risk_snapshot()), time.monotonic() - t0
        finally:
            release.set()
    ev, elapsed = asyncio.run(timed())
    assert elapsed < 2
    assert ev.provider_metadata["llm_fallback"] == "MODEL_TIMEOUT"
    assert ev.result.summary != "geç" and ev.result.is_anomaly


def test_fallback_result_persists_with_alert():
    import asyncio

    def sor(*_):
        raise TransientModelError()
    pipe = AnomalyPipeline(preparer=None, cards=CARDS, sor=sor, model_name="m", model_budget_seconds=5)
    ev = asyncio.run(pipe.evaluate(job(), _risk_snapshot()))
    repo = FakeRepo()
    outcome = persist_evaluation(repo, job(), ev)
    assert outcome.state is JobState.COMPLETED and outcome.anomaly_result_id
    assert len(repo.alerts) == 1
    assert outcome.provider_metadata["llm_fallback"] == "MODEL_CONNECTION_ERROR"


def test_code_errors_are_not_masked_by_fallback():
    import asyncio

    def sor(*_):
        raise TransientModelError()
    pipe = AnomalyPipeline(preparer=None, cards=CARDS, sor=sor, model_name="m", model_budget_seconds=5)
    with pytest.raises(InvalidModelOutput):  # başka astronotun snapshot'ı: kod hatası, geri dönüş yok
        asyncio.run(pipe.evaluate(job(), snapshot([], [], astronaut="A999")))


def test_model_budget_is_shorter_than_worker_timeout():
    from app.core.pipeline_runtime import model_budget_seconds

    class App:
        class state:
            history_preparer = object()
    settings = Settings(db_password="x", llm_base_url="http://ollama:11434",
                        model_total_timeout_seconds=60)
    configure_pipelines(App, settings)
    pipe = App.state.analysis_pipelines[AnalysisModule.ANOMALY]
    assert pipe.sor is not None and pipe.model_budget_seconds == model_budget_seconds(settings) == 45
    assert pipe.model_budget_seconds < settings.model_total_timeout_seconds
