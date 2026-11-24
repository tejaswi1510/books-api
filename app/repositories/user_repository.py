"""Read access to the users table."""
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import UserRow


class UserRepository:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def get_by_username(self, username: str) -> UserRow | None:
        with self._session_factory() as session:
            return session.scalar(select(UserRow).where(UserRow.username == username))
