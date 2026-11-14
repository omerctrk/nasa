"""FastAPI uygulaması.

Ortak dosya (şema §11): router/lifespan kayıtlarını Aybala birleştirir; Ömer kendi
router ve worker kayıtlarını bildirir. Migration burada ÇALIŞMAZ (ayrı migrate adımı).
"""
from fastapi import FastAPI

from app.core.errors import install_error_handling
from app.core.auth_runtime import configure_auth
from app.core.analysis_runtime import configure_analysis
from app.core.worker_runtime import analysis_worker_lifespan
from app.core.history_runtime import configure_history
from app.core.pipeline_runtime import configure_pipelines
from app.core.config import get_settings
from app.realtime.notifications import install_notifications
from app.routers import alerts, entries, health, readings
from app.schemas.common import API_PREFIX

app = FastAPI(title="ASTRA HEALTH Backend", version="0.1.0", lifespan=analysis_worker_lifespan)
install_error_handling(app)

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(entries.router, prefix=API_PREFIX)
app.include_router(readings.me, prefix=API_PREFIX)
app.include_router(readings.ground, prefix=API_PREFIX)
app.include_router(alerts.me, prefix=API_PREFIX)
app.include_router(alerts.ground, prefix=API_PREFIX)
install_notifications(app)
configure_auth(app, get_settings())
configure_analysis(app)
configure_history(app, get_settings())
configure_pipelines(app, get_settings())

# Kayıtlı: auth, veri girişi, okuma, analiz işi, sonuç/alarm uçları, WebSocket bildirimleri.
# İşçi: anomali pipeline'ı (Ö4 hazırlık + Ö5 değerlendirme + Ö6 yazım) bağlıdır; SANS kapalıdır.
