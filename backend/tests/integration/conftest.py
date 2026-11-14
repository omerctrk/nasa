"""Gerçek MS SQL'e karşı testler — varsayılan olarak ATLANIR.

Çalıştırmak (migrate sonrası, sınırlı astra_app hesabıyla):
    docker compose run --rm -e RUN_DB_TESTS=1 api pytest tests/integration -v

Her test kendi transaction'ında çalışır ve sonunda ROLLBACK edilir; DB'de iz kalmaz.
"""
import os
import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

if os.environ.get("RUN_DB_TESTS") != "1":
    pytest.skip("RUN_DB_TESTS=1 değil; DB testleri atlandı", allow_module_level=True)


@pytest.fixture
def db() -> Session:
    from app.db.session import engine

    conn = engine.connect()
    tx = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        tx.rollback()
        conn.close()


@pytest.fixture
def astronaut(db) -> str:
    """Geçici görev + astronot (rollback ile silinir)."""
    from app.models import Astronaut, Mission

    suffix = uuid.uuid4().hex[:8]
    mission = Mission(mission_id=f"T{suffix}", name="test", start_date=date(2027, 1, 5),
                      length_days=180)
    astro = Astronaut(astronaut_id=f"A{suffix}", display_name="Test", mission=mission)
    db.add_all([mission, astro])
    db.flush()
    return astro.astronaut_id


@pytest.fixture
def users(db, astronaut) -> dict:
    """Astronot hesabı + iki kule hesabı (rollback ile silinir)."""
    from app.models import User

    rows = {
        "astro": User(email=f"{astronaut.lower()}@test.local", password_hash="x",
                      role="ASTRONAUT", astronaut_id=astronaut),
        "ground1": User(email=f"g1-{astronaut.lower()}@test.local", password_hash="x",
                        role="GROUND_CONTROL"),
        "ground2": User(email=f"g2-{astronaut.lower()}@test.local", password_hash="x",
                        role="GROUND_CONTROL"),
    }
    db.add_all(rows.values())
    db.flush()
    return {k: v.user_id for k, v in rows.items()}
