"""Migration yardımcıları: nesne düzeyinde izin (şema §8).

Kural: tablo/VIEW izinleri, nesne oluşturulduğu migration'da verilir; henüz olmayan
nesneye izin verilmez. Gerekenden fazla işlem verilmez.

Kullanım (ör. A1 core migration'ının upgrade() sonunda):
    from migrations.helpers import APP_ROLE, grant, revoke
    grant("core.Missions", APP_ROLE, "SELECT")
    grant("core.Users", APP_ROLE, "SELECT, INSERT, UPDATE")

downgrade() içinde aynı satırlar revoke(...) ile geri alınır.
"""
from alembic import op

APP_ROLE = "astra_app_role"
EVAL_ROLE = "astra_eval_role"

_ALLOWED = {"SELECT", "INSERT", "UPDATE", "DELETE"}


def _object(name: str) -> str:
    schema, table = name.split(".")
    return f"[{schema}].[{table}]"


def _perms(perms: str) -> str:
    parts = [p.strip().upper() for p in perms.split(",")]
    if not parts or not set(parts) <= _ALLOWED:
        raise ValueError(f"Yalnız veri işlemleri verilebilir: {perms!r}")
    return ", ".join(parts)


def grant(obj: str, role: str, perms: str) -> None:
    op.execute(f"GRANT {_perms(perms)} ON {_object(obj)} TO [{role}]")


def revoke(obj: str, role: str, perms: str) -> None:
    op.execute(f"REVOKE {_perms(perms)} ON {_object(obj)} FROM [{role}]")
