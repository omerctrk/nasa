"""Import a portable AstraHealth data package into a fresh migrated database."""
from __future__ import annotations

import argparse
import base64
import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from app.core.config import get_settings

FORMAT = "astrahealth-data-transfer/v1"


def decode(value):
    if not isinstance(value, dict) or "__astra_type__" not in value:
        return value
    kind, raw = value["__astra_type__"], value["value"]
    if kind == "datetime": return datetime.fromisoformat(raw)
    if kind == "date": return date.fromisoformat(raw)
    if kind == "time": return time.fromisoformat(raw)
    if kind == "decimal": return Decimal(raw)
    if kind == "uuid": return UUID(raw)
    if kind == "bytes": return base64.b64decode(raw)
    raise ValueError(f"Unknown transfer value type: {kind}")


def qname(table: Table, engine) -> str:
    quote = engine.dialect.identifier_preparer.quote
    return f"{quote(table.schema or 'dbo')}.{quote(table.name)}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.package.read_text(encoding="utf-8"))
    if payload.get("format") != FORMAT:
        raise SystemExit("Unsupported or invalid transfer package.")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    metadata = MetaData()
    tables: dict[str, Table] = {}
    for key in payload["table_order"]:
        schema, name = key.split(".", 1)
        if name not in inspector.get_table_names(schema=schema):
            raise SystemExit(f"Target schema is missing {key}; run migrations first.")
        table = Table(name, metadata, schema=schema, autoload_with=engine)
        expected = payload["tables"][key]["columns"]
        actual = [column.name for column in table.columns]
        if expected != actual:
            raise SystemExit(f"Column mismatch in {key}; source and target migrations differ.")
        tables[key] = table

    with engine.begin() as conn:
        target_revision = conn.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar_one()
        if target_revision != payload["source_revision"]:
            raise SystemExit(f"Revision mismatch: target={target_revision}, package={payload['source_revision']}")
        for key, table in tables.items():
            if conn.execute(select(table).limit(1)).first() is not None:
                raise SystemExit(f"Target table {key} is not empty; import is allowed only into a fresh DB.")

        for key in payload["table_order"]:
            table, row_data = tables[key], payload["tables"][key]["rows"]
            if not row_data:
                continue
            rows = [{column: decode(value) for column, value in row.items()} for row in row_data]
            identity = next((column for column in table.columns if getattr(column, "identity", None) is not None), None)
            if identity is not None:
                conn.exec_driver_sql(f"SET IDENTITY_INSERT {qname(table, engine)} ON")
            try:
                conn.execute(table.insert(), rows)
            finally:
                if identity is not None:
                    conn.exec_driver_sql(f"SET IDENTITY_INSERT {qname(table, engine)} OFF")
            print(f"imported {key}: {len(rows)} rows")
    print(f"import complete: {args.package} ({payload['source_revision']})")


if __name__ == "__main__":
    main()
