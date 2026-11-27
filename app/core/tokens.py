"""Create and verify JWT access tokens (PyJWT)."""
import logging
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings
from app.exceptions import AuthenticationError, AuthNotConfiguredError

logger = logging.getLogger(__name__)


def _secret(settings: Settings) -> str:
    # Fail closed: without a secret we cannot sign or verify anything safely.
    if not settings.jwt_secret_key:
        logger.error("JWT used but APP_JWT_SECRET_KEY is not set")
        raise AuthNotConfiguredError("Login is not configured. Set APP_JWT_SECRET_KEY and restart.")
    return settings.jwt_secret_key.get_secret_value()


def create_access_token(username: str, role: str, settings: Settings) -> tuple[str, int]:
    """Return (token, seconds until it expires)."""
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    claims = {
        "sub": username,  # who the token is for
        "role": role,  # what they may do
        "iat": now,  # issued at
        "exp": now + timedelta(seconds=expires_in),  # expiry: PyJWT enforces this on decode
    }
    return jwt.encode(claims, _secret(settings), algorithm=settings.jwt_algorithm), expires_in


def decode_access_token(token: str, settings: Settings) -> dict:
    """Verify signature and expiry; return the claims or raise 401."""
    try:
        # algorithms=[...] is required: it stops "alg: none" and algorithm-swap attacks.
        return jwt.decode(
            token,
            _secret(settings),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired. Log in again.", scheme="Bearer")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token.", scheme="Bearer")
