"""İşçi pipeline'larını bağlar (Ö5/Ö6; Ömer'in kalan kısmı, Aybala).

Anomali: Ö4 HistoryPreparer + eşik/kart değerlendirmesi + aynı-Session kalıcı yazım.
Model: LLM_BASE_URL verilmişse Yusuf'un kart önericisi Ollama ile çağrılır; verilmemişse
karar yine kurallarla verilir, açıklama kodla yazılır (sahte "normal" üretilmez).
SANS kapatıldı: işçi yalnız anomali işlerini sahiplenir.
Hazırlayıcı yoksa pipeline bağlanmaz → işçi başlamaz (worker_runtime kuralı).
"""
from app.core.config import Settings
from app.providers.ollama import ollama_sor
from app.schemas.common import AnalysisModule
from app.services.anomaly import AnomalyPipeline, load_cards


def configure_pipelines(app, settings: Settings) -> None:
    preparer = getattr(app.state, "history_preparer", None)
    if preparer is None:
        app.state.analysis_pipelines = None
        return
    sor = None
    if settings.llm_base_url:
        sor = ollama_sor(settings.llm_base_url, settings.llm_model,
                         settings.model_connect_timeout_seconds, settings.model_total_timeout_seconds)
    app.state.analysis_pipelines = {
        AnalysisModule.ANOMALY: AnomalyPipeline(preparer, load_cards(settings.knowledge_cards_path),
                                                sor, settings.llm_model if sor else None,
                                                model_budget_seconds(settings) if sor else None),
    }


def model_budget_seconds(settings: Settings) -> float:
    """Model bütçesi işçinin değerlendirme zaman aşımının %75'i (en az 1 sn).

    İşçi aynı süreyi (model_total_timeout_seconds) tüm değerlendirmeye uygular; model bu
    bütçeyi aşarsa pipeline modelsiz karara döner ve iş zaman aşımına düşmeden tamamlanır.
    """
    return max(1.0, settings.model_total_timeout_seconds * 0.75)
