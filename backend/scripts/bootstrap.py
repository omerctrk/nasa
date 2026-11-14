"""ASTRA HEALTH bootstrap (şema §8, iş bölümü §8) — tekrar çalıştırılabilir.

Yapar:  AstraHealth veritabanı + iki sınırlı login + eşleşen database USER'ları.
Yapmaz: şema, rol, üyelik, GRANT/DENY → bunlar Alembic zincirindedir.

Yalnız kontrollü kurulumda, sa ile çalışır (docker-compose `bootstrap` servisi).
SANS için SQL hesabı OLUŞTURULMAZ: SANS backend'den yalnız API ile veri alır (rev.3).

Ortam değişkenleri:
    MSSQL_SA_PASSWORD, ASTRA_APP_DB_PASSWORD, ASTRA_EVAL_DB_PASSWORD
    DB_HOST (varsayılan db), DB_PORT (1433), DB_NAME (AstraHealth)
"""
from __future__ import annotations

import os
import re
import sys

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"

# login -> (şifre ortam değişkeni, varsayılan şema)
SERVICE_LOGINS: dict[str, tuple[str, str]] = {
    "astra_app": ("ASTRA_APP_DB_PASSWORD", "core"),
    "astra_eval": ("ASTRA_EVAL_DB_PASSWORD", "evaluation"),
}

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


def safe_name(name: str) -> str:
    """Veritabanı/login adı SQL'e gömüleceği için yalnız güvenli karakterlere izin verilir."""
    if not _NAME.fullmatch(name):
        raise ValueError(f"Geçersiz ad: {name!r}")
    return name


def odbc_value(value: str) -> str:
    """ODBC bağlantı dizesinde ; veya } içeren değeri güvenle yazar."""
    return "{" + value.replace("}", "}}") + "}"


def connection_string(host: str, port: str, database: str, password: str) -> str:
    return (
        f"DRIVER={odbc_value(ODBC_DRIVER)};SERVER={host},{port};DATABASE={database};"
        f"UID=sa;PWD={odbc_value(password)};Encrypt=yes;TrustServerCertificate=yes"
    )


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        sys.exit(f"bootstrap: {name} tanımlı değil (.env)")
    return value


def main() -> None:
    import pyodbc  # ODBC sürücüsü yalnız container'da gerekir

    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "1433")
    db_name = safe_name(os.environ.get("DB_NAME", "AstraHealth"))
    sa_password = _require("MSSQL_SA_PASSWORD")
    passwords = {login: _require(env) for login, (env, _) in SERVICE_LOGINS.items()}

    # CREATE DATABASE / LOGIN transaction içinde çalışmaz → autocommit
    with pyodbc.connect(connection_string(host, port, "master", sa_password), autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute(f"IF DB_ID(N'{db_name}') IS NULL CREATE DATABASE [{db_name}]")

        for login, password in passwords.items():
            login = safe_name(login)
            # Şifre parametre olarak geçer; QUOTENAME tırnakları kaçırır (şifrede ' olabilir)
            cur.execute(
                f"""
                DECLARE @pw nvarchar(128) = ?;
                DECLARE @sql nvarchar(max);
                IF SUSER_ID(N'{login}') IS NULL
                    SET @sql = N'CREATE LOGIN [{login}] WITH PASSWORD = ' + QUOTENAME(@pw, '''')
                             + N', DEFAULT_DATABASE = [{db_name}], CHECK_POLICY = ON';
                ELSE
                    SET @sql = N'ALTER LOGIN [{login}] WITH PASSWORD = ' + QUOTENAME(@pw, '''');
                EXEC (@sql);
                """,
                password,
            )

    with pyodbc.connect(connection_string(host, port, db_name, sa_password), autocommit=True) as conn:
        cur = conn.cursor()
        for login, (_, default_schema) in SERVICE_LOGINS.items():
            cur.execute(
                f"IF USER_ID(N'{login}') IS NULL "
                f"CREATE USER [{login}] FOR LOGIN [{login}] WITH DEFAULT_SCHEMA = [{default_schema}]"
            )

    print(f"bootstrap tamam: {db_name} + {', '.join(SERVICE_LOGINS)}")


if __name__ == "__main__":
    main()
