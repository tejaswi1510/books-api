"""Authentication and authorization (FastAPI dependencies).

Two ways to prove who you are:
  * a JWT in the Authorization header (people, via POST /auth/login), or
  * an API key in the X-API-Key header (trusted machine clients).
Roles then decide what an authenticated caller may do.
"""
import logging
import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer

from app.core.config import Settings, get_settings
from app.core.tokens import decode_access_token
from app.exceptions import AuthenticationError, AuthNotConfiguredError, ForbiddenError

logger = logging.getLogger(__name__)

# auto_error=False lets us return our own error format instead of FastAPI's default.
api_key_header = APIKeyHeader(
    name="X-API-Key", auto_error=False, description="API key for protected endpoints"
)
# tokenUrl powers Swagger's Authorize button: it posts the username/password there.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
    description="Log in with username and password to get a Bearer token",
)


@dataclass(frozen=True)
class Principal:
    """Who is calling: the result of authentication."""

    username: str
    role: str  # "user" or "admin"
    via: str  # "jwt" or "api_key"


def check_api_key(api_key: str | None, settings: Settings) -> None:
    raw = settings.api_keys.get_secret_value() if settings.api_keys else ""
    valid_keys = [k.strip() for k in raw.split(",") if k.strip()]

    # Fail closed: with no keys configured, protected endpoints stay shut.
    if not valid_keys:
        logger.error("Protected endpoint called but APP_API_KEYS is not set")
        raise AuthNotConfiguredError()

    if not api_key:
        logger.warning("Auth failed: missing API key")
        raise AuthenticationError("Missing API key. Send it in the X-API-Key header.")

    # compare_digest takes constant time, so response timing can't leak the key.
    matched = False
    for valid in valid_keys:
        if secrets.compare_digest(api_key.encode(), valid.encode()):
            matched = True
    if not matched:
        logger.warning("Auth failed: invalid API key")  # never log the key itself
        raise AuthenticationError("Invalid API key.")


def require_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    check_api_key(api_key, settings)


def get_current_principal(
    token: Annotated[str | None, Security(oauth2_scheme)],
    api_key: Annotated[str | None, Security(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    """Work out who is calling. A Bearer token wins; otherwise fall back to an API key."""
    if token:
        claims = decode_access_token(token, settings)  # raises 401 if bad or expired
        return Principal(username=claims["sub"], role=claims.get("role", "user"), via="jwt")

    if api_key:
        check_api_key(api_key, settings)  # raises 401/503 if not valid
        # An API key is a trusted service credential, so it carries admin rights.
        return Principal(username="api-key-client", role="admin", via="api_key")

    raise AuthenticationError(
        "Authentication required. Log in for a Bearer token, or send an X-API-Key header.",
        scheme="Bearer",
    )


def require_admin(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> Principal:
    """Authenticated AND an admin. Logged-in non-admins get 403, not 401."""
    if principal.role != "admin":
        logger.warning("Forbidden: %s (role=%s) tried an admin-only action", principal.username, principal.role)
        raise ForbiddenError("This action needs an admin account.")
    return principal
