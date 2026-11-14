from datetime import UTC, date, datetime
from uuid import UUID

from app.repositories.records import AstronautRecord, UserRecord
from app.schemas.common import Role
from tests.fakes.auth import FakeAuthRepository


def make_auth_repository() -> FakeAuthRepository:
    cases = [(1, "astronaut", Role.ASTRONAUT, True, "A007"),
             (2, "ground", Role.GROUND_CONTROL, True, None),
             (3, "inactive", Role.GROUND_CONTROL, False, None),
             (4, "display", Role.ASTRONAUT, True, "A008"),
             (5, "unlinked", Role.ASTRONAUT, True, None),
             (6, "missing-profile", Role.ASTRONAUT, True, "MISSING")]
    return FakeAuthRepository(
        users=[UserRecord(user_id=UUID(int=n), email=f"{name}@example.test",
                          password_hash="TEST_ONLY_INVALID_HASH", role=role,
                          is_active=active, astronaut_id=aid, created_at=datetime(2027, 1, 5, tzinfo=UTC))
               for n, name, role, active, aid in cases],
        astronauts=[AstronautRecord(astronaut_id=aid, display_name="Test", mission_id="M01",
                                    mission_start_date=date(2027, 1, 5), mission_length_days=180,
                                    is_display_only=display)
                    for aid, display in [("A007", False), ("A008", True)]],
    )
