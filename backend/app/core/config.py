"""Uygulama ayarları.

Her servis yalnız KENDİ veritabanı bağlantısını alır (iş bölümü §9):
- api / işçi  → DB_USER=astra_app,  DB_PASSWORD=$ASTRA_APP_DB_PASSWORD
- migrate     → DB_USER=sa,         DB_PASSWORD=$MSSQL_SA_PASSWORD
Bu eşleme docker-compose.yml'de yapılır; kod hangi hesapla çalıştığını bilmez.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 1433
    db_name: str = "AstraHealth"
    db_user: str = "astra_app"
    db_password: str = Field(repr=False)
    odbc_driver: str = "ODBC Driver 18 for SQL Server"

    # --- Kimlik (Ömer, sözleşme §5) ---
    jwt_secret: str | None = Field(default=None, repr=False)  # auth açılırken zorunlu
    jwt_issuer: str = "astra-health"
    jwt_audience: str = "astra-health-api"

    # --- Başlangıç çalışma ayarları (sözleşme §9) ---
    # Klinik karar DEĞİLDİR; değiştirilebilir. Kodda sabit yazılmaz, buradan okunur.
    access_token_seconds: int = 3600
    job_lease_seconds: int = 120
    job_lease_renew_seconds: int = 30
    model_connect_timeout_seconds: float = 5
    model_total_timeout_seconds: float = 60
    anomaly_auto_retries: int = 1
    anomaly_retry_delay_seconds: float = 2
    ws_auth_timeout_seconds: float = 5
    worker_poll_seconds: float = 1
    # SANS POST'u için otomatik tekrar bilerek ayar değildir: tekrar güvenliği teyit
    # edilene kadar KAPALI (sözleşme §9).

    @property
    def database_url(self) -> URL:
        # URL.create şifredeki özel karakterleri (! ; @) kendisi kaçırır
        return URL.create(
            "mssql+pyodbc",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={
                "driver": self.odbc_driver,
                "TrustServerCertificate": "yes",  # yerel container kendi imzalı sertifika kullanır
            },
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
