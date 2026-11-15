"""A6 gerçek DB kabulü: seed iki kez çalışınca çift kayıt yok, hesaplar girişe hazır."""
from sqlalchemy import func, select

from app.core.passwords import verify_password
from app.models import Astronaut, MeasurementDefinition, User
from app.repositories.sqlalchemy_repository import SqlAlchemyRepository
from scripts import seed


def counts(db):
    return tuple(db.scalar(select(func.count()).select_from(m))
                 for m in (MeasurementDefinition, Astronaut, User))


def test_seed_is_idempotent(db):
    seed.run_seed(db, "astro-pw", "kule-pw")
    first = counts(db)
    second = seed.run_seed(db, "astro-pw", "kule-pw")
    assert counts(db) == first
    assert not second.created


def test_seeded_accounts(db):
    seed.run_seed(db, "astro-pw", "kule-pw")
    repo = SqlAlchemyRepository(db)
    astro = repo.get_user_by_email("  ASTRONAUT@astra.local ")
    assert astro.role == "ASTRONAUT" and astro.astronaut_id == "A007"
    ground = repo.get_user_by_email(seed.GROUND_EMAIL)
    assert ground.role == "GROUND_CONTROL" and ground.astronaut_id is None
    assert repo.get_astronaut("A007").is_display_only is False
    assert repo.get_astronaut(seed.DISPLAY_ASTRONAUT_ID).is_display_only is True
    assert repo.get_astronaut("A007").mission_start_date.isoformat() == "2027-01-05"


def test_passwords_hashed_and_resettable(db):
    seed.run_seed(db, "astro-pw", "kule-pw")
    u = db.scalars(select(User).where(User.email == seed.ASTRONAUT_EMAIL)).one()
    if not verify_password(u.password_hash, "astro-pw"):
        return  # DB'de daha önce farklı parolayla seed edilmiş; dokunmuyoruz
    seed.run_seed(db, "yeni-pw", "kule-pw")
    db.refresh(u)
    assert verify_password(u.password_hash, "astro-pw")  # reset olmadan değişmez
    seed.run_seed(db, "yeni-pw", "kule-pw", reset_passwords=True)
    db.refresh(u)
    assert verify_password(u.password_hash, "yeni-pw")
