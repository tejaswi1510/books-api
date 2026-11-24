"""Application factory and entry point.

Run with:  uvicorn app.main:app --reload
Swagger UI: http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.v1.endpoints import health
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.exceptions import AppError
from app.core.request_id import RequestIDMiddleware

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {"name": "Books", "description": "CRUD operations on the book catalogue."},
    {
        "name": "AI Assistant",
        "description": "Ask natural-language questions about the catalogue (powered by OpenAI).",
    },
    {"name": "Health", "description": "Service status."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.environment)
    if settings.openai_api_key:
        logger.info("AI assistant enabled (model=%s)", settings.openai_model)
    else:
        logger.warning("AI assistant disabled: APP_OPENAI_API_KEY is not set")
    logger.info(
        "AI rate limits: %d req/%ds per client, %d req/%ds global",
        settings.ai_rate_limit_requests,
        settings.ai_rate_limit_window_seconds,
        settings.ai_global_rate_limit_requests,
        settings.ai_global_rate_limit_window_seconds,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    # Future middlewares (CORS, request IDs, auth, ...) are registered here.
    app.add_middleware(RequestIDMiddleware)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=exc.headers,
        )

    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
