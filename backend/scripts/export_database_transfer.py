"""Create a portable, data-only AstraHealth transfer package.

Run with the source database connection variables. The package contains every
application table row but intentionally excludes SQL Server logins, passwords,
and the Alembic bookkeeping row. It is meant for a freshly migrated target.
"""
from __future__ import annotations

import argparse
import base64
import json
from collections import defaultdict, deque
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from app.core.config import get_settings

APP_SCHEMAS = ("core", "sans", "anomaly", "ops", "behavioral", "evaluation", "dbo")
FORMAT = "astrahealth-data-transfer/v1"


def table_key(schema: str, name: str) -> str:
    return f"{schema}.{name}"


def encode(value):
    if isinstance(value, datetime):
        return {"__astra_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__astra_type__": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"__astra_type__": "time", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__astra_type__": "decimal", "value": str(value)}
    if isinstance(value, UUID):
        return {"__astra_type__": "uuid", "value": str(value)}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__astra_type__": "bytes", "value": base64.b64encode(bytes(value)).decode("ascii")}
    raise TypeError(f"Cannot serialize {type(value)!r}")


def load_tables(engine):
    inspector = inspect(engine)
    metadata = MetaData()
    tables: dict[str, Table] = {}
    for schema in APP_SCHEMAS:
        for name in inspector.get_table_names(schema=schema):
            if schema == "dbo" and name == "alembic_version":
                continue
            table = Table(name, metadata, schema=schema, autoload_with=engine)
            tables[table_key(schema, name)] = table
    return tables


def dependency_order(tables: dict[str, Table]) -> list[str]:
    dependencies = {key: set() for key in tables}
    children: dict[str, set[str]] = defaultdict(set)
    for key, table in tables.items():
        for fk in table.foreign_keys:
            schema = fk.column.table.schema or "dbo"
            parent = table_key(schema, fk.column.table.name)
            if parent in tables and parent != key:
                dependencies[key].add(parent)
                children[parent].add(key)
    ready = deque(sorted(key for key, deps in dependencies.items() if not deps))
    ordered: list[str] = []
    while ready:
        key = ready.popleft()
        ordered.append(key)
        for child in sorted(children[key]):
            dependencies[child].remove(key)
            if not dependencies[child]:
                ready.append(child)
    if len(ordered) != len(tables):
        raise RuntimeError("Foreign-key cycle detected; transfer package cannot choose a safe insert order.")
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    tables = load_tables(engine)
    order = dependency_order(tables)
    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar_one()
        payload_tables = {}
        for key in order:
            rows = [dict(row) for row in conn.execute(select(tables[key])).mappings()]
            payload_tables[key] = {
                "columns": [column.name for column in tables[key].columns],
                "rows": rows,
            }
    payload = {
        "format": FORMAT,
        "source_revision": revision,
        "created_at": datetime.now(timezone.utc),
        "table_order": order,
        "tables": payload_tables,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, default=encode, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"export complete: {args.output} ({sum(len(item['rows']) for item in payload_tables.values())} rows, revision {revision})")


if __name__ == "__main__":
    main()
