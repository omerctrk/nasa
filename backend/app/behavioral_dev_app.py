"""Davranışsal modül için geliştirme sunucusu (bellek içi).

Çalıştırma (backend klasöründen):
    uvicorn app.behavioral_dev_app:app --reload
Seed verisiyle ve sabit demo saatiyle (PowerShell):
    $env:BEHAVIORAL_LOAD_SEED = "1"; $env:BEHAVIORAL_FIXED_NOW = "2026-11-14T09:00:00Z"
    uvicorn app.behavioral_dev_app:app --reload
Seed dosyaları önce üretilmeli:  python -m scripts.seed_behavioral seed_output
Belgeler: http://127.0.0.1:8000/docs  ("Authorize" -> A007)

Ortak main.py değil; yalnız davranışsal modülü tek başına denemek içindir.
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.behavioral_errors_http import register_behavioral_error_handlers
from app.api.deps_behavioral import get_repositories
from app.repositories.behavioral_seed_loader import load_seed_dir
from app.routers.behavioral import router

LOAD_SEED_ENV = "BEHAVIORAL_LOAD_SEED"
SEED_DIR_ENV = "BEHAVIORAL_SEED_DIR"
DEFAULT_SEED_DIR = Path(__file__).resolve().parents[1] / "seed_output"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get(LOAD_SEED_ENV) == "1":
        checkin_repo, test_repo, weekly_repo = get_repositories()
        if not checkin_repo.list("A007", None, None, 1, None):       # --reload ile iki kez yüklenmesin
            folder = Path(os.environ.get(SEED_DIR_ENV) or DEFAULT_SEED_DIR)
            counts = load_seed_dir(folder, checkin_repo, test_repo, weekly_repo)
            print(f"Behavioral seed loaded from {folder}: {counts}")   # yalnız satır sayıları
    yield


app = FastAPI(title="AstraHealth — Behavioral module (dev)", version="0.5.0", lifespan=lifespan)
app.include_router(router)
register_behavioral_error_handlers(app)
