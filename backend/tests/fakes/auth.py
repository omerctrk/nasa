from collections.abc import Iterable
from uuid import UUID

from app.repositories.records import AstronautRecord, UserRecord
from app.schemas.auth import normalize_email


class FakeAuthRepository:
    def __init__(self, users: Iterable[UserRecord] = (),
                 astronauts: Iterable[AstronautRecord] = ()) -> None:
        self._users = {user.user_id: user for user in users}
        self._emails = {normalize_email(user.email): user.user_id for user in self._users.values()}
        self._astronauts = {profile.astronaut_id: profile for profile in astronauts}

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._users.get(self._emails.get(normalize_email(email)))

    def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        return self._users.get(user_id)

    def get_astronaut(self, astronaut_id: str) -> AstronautRecord | None:
        return self._astronauts.get(astronaut_id)
