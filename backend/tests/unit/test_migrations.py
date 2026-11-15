"""Migration zinciri modellerle birebir aynı DDL'i üretiyor mu? (DB gerektirmez)

`alembic upgrade head --sql` çıktısındaki her CREATE TABLE/INDEX, modelden üretilen
DDL ile satır satır karşılaştırılır. Model değişip migration unutulursa bu test kırılır.
Gerçek DB'de ayrıca: `docker compose run --rm migrate alembic check`.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401
from app.db.base import Base

BACKEND = Path(__file__).parents[2]


def sql2022():
    d = mssql.dialect()
    d.server_version_info = (16, 0)
    d._setup_version_attributes()
    return d


def _lines(stmt: str) -> frozenset[str]:
    return frozenset(
        line.strip().rstrip(",;").strip() for line in stmt.strip().splitlines() if line.strip()
    )


@pytest.fixture(scope="module")
def offline_sql() -> str:
    env = os.environ | {"DB_USER": "sa", "DB_PASSWORD": "x"}
    out = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND, env=env, capture_output=True, text=True, check=True,
    )
    return out.stdout


def _statements(sql: str, prefix: str) -> dict[str, frozenset[str]]:
    found = {}
    for stmt in sql.split("\nGO\n"):
        stmt = "\n".join(
            ln for ln in stmt.splitlines()
            if not ln.startswith("--") and ln.strip() != "BEGIN TRANSACTION;"
        ).strip()
        if prefix == "CREATE TABLE" and stmt.startswith("CREATE TABLE"):
            name = re.match(r"CREATE TABLE (\S+) \(", stmt).group(1)
            found[name.replace("[", "").replace("]", "")] = _lines(stmt)
        if prefix == "INDEX" and re.match(r"CREATE (UNIQUE )?INDEX", stmt):
            name = re.search(r"INDEX \[?(\w+)\]?", stmt).group(1)
            found[name] = _lines(stmt.rstrip(";"))
    return found


def test_every_model_table_is_created_exactly_as_modelled(offline_sql):
    migrated = _statements(offline_sql, "CREATE TABLE")
    migrated.pop("alembic_version", None)  # Alembic'in kendi tablosu
    dialect = sql2022()
    model_tables = {t.fullname: t for t in Base.metadata.sorted_tables}
    assert set(migrated) == set(model_tables), "migration ↔ model tablo listesi farklı"
    for name, table in model_tables.items():
        expected = _lines(str(CreateTable(table).compile(dialect=dialect)))
        assert migrated[name] == expected, f"{name}: {migrated[name] ^ expected}"


def test_every_model_index_is_created(offline_sql):
    migrated = _statements(offline_sql, "INDEX")
    dialect = sql2022()
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            expected = _lines(str(CreateIndex(index).compile(dialect=dialect)))
            assert migrated.get(index.name) == expected, index.name


def test_every_table_is_granted_to_app_role_with_only_knowledge_delete(offline_sql):
    grants = re.findall(r"GRANT ([A-Z, ]+) ON \[(\w+)\]\.\[(\w+)\] TO \[astra_app_role\]", offline_sql)
    granted = {f"{s}.{t}": perms for perms, s, t in grants}
    operational = {t.fullname for t in Base.metadata.sorted_tables if t.schema != "evaluation"}
    assert operational <= set(granted), operational - set(granted)
    assert "DELETE" in granted["dbo.knowledge_cards"]
    assert all("DELETE" not in p for name, p in granted.items() if name != "dbo.knowledge_cards")


def test_evaluation_is_isolated(offline_sql):
    """Eval tablosu yalnız eval rolüne verilir; app rolüne hiçbir evaluation izni verilmez."""
    assert re.search(r"GRANT [A-Z, ]+ ON \[evaluation\]\.\[gercek_durum\] TO \[astra_eval_role\]",
                     offline_sql)
    assert not re.search(r"GRANT [A-Z, ]+ ON \[evaluation\]\.\[\w+\] TO \[astra_app_role\]",
                         offline_sql)
    assert "DENY SELECT, INSERT, UPDATE, DELETE ON SCHEMA::[evaluation] TO [astra_app_role]" in offline_sql
    # eval rolü operasyonel tablolara izin almaz
    assert not re.search(r"ON \[(core|sans|anomaly|ops|behavioral)\]\.\[\w+\] TO \[astra_eval_role\]",
                         offline_sql)
    assert "DELETE ON [evaluation]" not in offline_sql
