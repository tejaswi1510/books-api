"""API key authentication (a FastAPI dependency)."""
import logging
import secrets
from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings
from app.exceptions import AuthenticationError, AuthNotConfiguredError

logger = logging.getLogger(__name__)

# auto_error=False lets us return our own error format instead of FastAPI's default.
api_key_header = APIKeyHeader(
    name="X-API-Key", auto_error=False, description="API key for protected endpoints"
)


def require_api_key(
    api_key: Annotated[str | None, Security(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
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