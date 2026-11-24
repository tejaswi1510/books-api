"""Dependency providers. This is the single place that decides which implementations are used."""
import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request, Response
from app.db import create_db_engine, create_session_factory
from app.repositories.sql_book_repository import SqlBookRepository
from app.clients.llm import LLMClient
from app.clients.openai_client import OpenAILLMClient
from app.core.config import Settings, get_settings
from app.core.rate_limit import InMemoryRateLimiter, RateLimiter
from app.exceptions import AINotConfiguredError, RateLimitExceededError
from app.repositories.base import BookRepository
from app.repositories.csv_book_repository import CsvBookRepository
from app.services.assistant_service import AssistantService
from app.services.book_service import BookService
from app.services.drift_monitor import ModelDriftMonitor

logger = logging.getLogger(__name__)


@lru_cache
def get_book_repository() -> BookRepository:
    settings = get_settings()
    if settings.database_url:
        engine = create_db_engine(settings.database_url)
        return SqlBookRepository(create_session_factory(engine))
    return CsvBookRepository(settings.books_csv_path)


def get_book_service(
    repo: Annotated[BookRepository, Depends(get_book_repository)],
) -> BookService:
    return BookService(repo)


@lru_cache
def _build_openai_client(
    api_key: str, model: str, timeout_seconds: float, max_retries: int
) -> LLMClient:
    # Cached so the underlying HTTP connection pool is reused across requests.
    return OpenAILLMClient(api_key, model, timeout_seconds, max_retries)


def get_llm_client(settings: Annotated[Settings, Depends(get_settings)]) -> LLMClient:
    # Checked per request (not at startup) so the rest of the API works without a key.
    key = settings.openai_api_key.get_secret_value().strip() if settings.openai_api_key else ""
    if not key:
        raise AINotConfiguredError()
    return _build_openai_client(
        key, settings.openai_model, settings.openai_timeout_seconds, settings.openai_max_retries
    )


@lru_cache
def get_drift_monitor() -> ModelDriftMonitor:
    # One shared instance so it remembers which model snapshots it has seen.
    return ModelDriftMonitor()


@lru_cache
def get_client_rate_limiter() -> RateLimiter:
    s = get_settings()
    return InMemoryRateLimiter(s.ai_rate_limit_requests, s.ai_rate_limit_window_seconds)


@lru_cache
def get_global_rate_limiter() -> RateLimiter:
    s = get_settings()
    return InMemoryRateLimiter(s.ai_global_rate_limit_requests, s.ai_global_rate_limit_window_seconds)


def enforce_ai_rate_limit(
    request: Request,
    response: Response,
    client_limiter: Annotated[RateLimiter, Depends(get_client_rate_limiter)],
    global_limiter: Annotated[RateLimiter, Depends(get_global_rate_limiter)],
) -> None:
    """Per-client limit first, then the global spend cap. Runs before any OpenAI call.

    Clients are identified by IP address. Behind a reverse proxy this would be the
    proxy's IP unless uvicorn is started with --proxy-headers (and trusted proxies set).
    """
    client_id = request.client.host if request.client else "unknown"

    result = client_limiter.hit(client_id)
    if not result.allowed:
        logger.warning("Rate limit exceeded: client=%s retry_after=%ss", client_id, result.retry_after)
        raise RateLimitExceededError(result.retry_after, scope="client")

    global_result = global_limiter.hit("global")
    if not global_result.allowed:
        logger.warning("GLOBAL AI rate limit exceeded: retry_after=%ss", global_result.retry_after)
        raise RateLimitExceededError(global_result.retry_after, scope="global")

    # Standard informational headers on successful responses.
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)


def get_assistant_service(
    repo: Annotated[BookRepository, Depends(get_book_repository)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    drift_monitor: Annotated[ModelDriftMonitor, Depends(get_drift_monitor)],
) -> AssistantService:
    return AssistantService(
        repo,
        llm,
        settings.ai_max_books_in_context,
        settings.ai_max_answer_chars,
        drift_monitor,
    )


BookServiceDep = Annotated[BookService, Depends(get_book_service)]
AssistantServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]
