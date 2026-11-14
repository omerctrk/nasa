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
from app.core.config import get_settings
from app.routers import entries, health, readings
from app.schemas.common import API_PREFIX

app = FastAPI(title="ASTRA HEALTH Backend", version="0.1.0", lifespan=analysis_worker_lifespan)
install_error_handling(app)

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(entries.router, prefix=API_PREFIX)
app.include_router(readings.me, prefix=API_PREFIX)
app.include_router(readings.ground, prefix=API_PREFIX)
configure_auth(app, get_settings())
configure_analysis(app)
configure_history(app, get_settings())

# Sonraki PR'larda (HTTP öneki /api/v1):
#   Aybala: astronauts, behavioral, sans, measurements
#   Ömer:   ground, notifications (+ WebSocket /ws/v1/notifications)
# Auth/analysis kayıtlıdır; worker yalnız tüm gerçek adaptörler bağlıysa başlar.
