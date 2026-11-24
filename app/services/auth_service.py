"""Login logic: check the password, then issue a token."""
import logging

from app.core.config import Settings
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token
from app.exceptions import InvalidCredentialsError
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token

logger = logging.getLogger(__name__)

# Checked when the username doesn't exist, so "unknown user" and "wrong password"
# take about the same time. Otherwise response timing reveals which usernames exist.
_DUMMY_HASH = hash_password("not-a-real-password")


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def login(self, username: str, password: str) -> Token:
        user = self._users.get_by_username(username)
        if user is None:
            verify_password(password, _DUMMY_HASH)
            logger.warning("Login failed: unknown user")
            raise InvalidCredentialsError()
        if not verify_password(password, user.hashed_password) or not user.is_active:
            logger.warning("Login failed for user_id=%s", user.id)  # never log the password
            raise InvalidCredentialsError()

        token, expires_in = create_access_token(user.username, user.role, self._settings)
        logger.info("Login ok for user_id=%s role=%s", user.id, user.role)
        return Token(access_token=token, expires_in=expires_in)
