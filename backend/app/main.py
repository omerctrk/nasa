"""FastAPI uygulaması.

Ortak dosya (şema §11): router/lifespan kayıtlarını Aybala birleştirir; Ömer kendi
router ve worker kayıtlarını bildirir. Migration burada ÇALIŞMAZ (ayrı migrate adımı).
"""
from fastapi import FastAPI

from app.core.errors import install_error_handling
from app.routers import entries, health
from app.schemas.common import API_PREFIX

app = FastAPI(title="ASTRA HEALTH Backend", version="0.1.0")
install_error_handling(app)

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(entries.router, prefix=API_PREFIX)

# Sonraki PR'larda (HTTP öneki /api/v1):
#   Aybala: astronauts, behavioral, sans, measurements
#   Ömer:   auth, analysis, ground, notifications  (+ WebSocket /ws/v1/notifications)
