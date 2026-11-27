from fastapi import APIRouter, Depends

from app.api.deps import AssistantServiceDep, enforce_ai_rate_limit
from app.schemas.assistant import AskRequest, AskResponse
from app.schemas.common import ErrorResponse
from app.core.security import get_current_principal

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question about the book catalogue",
    # The rate limiter runs first, so over-limit callers never reach (or cost) OpenAI.
    dependencies=[Depends(get_current_principal), Depends(enforce_ai_rate_limit)],
    responses={
        400: {"model": ErrorResponse, "description": "Question blocked by input guardrails"},
        429: {
            "model": ErrorResponse,
            "description": "Rate limit exceeded (ours: has a Retry-After header) or provider rate limit",
        },
        502: {"model": ErrorResponse, "description": "AI provider failed or returned invalid output"},
        503: {"model": ErrorResponse, "description": "AI assistant not configured (missing API key)"},
        504: {"model": ErrorResponse, "description": "AI provider timed out"},
    },
)
def ask_assistant(payload: AskRequest, service: AssistantServiceDep) -> AskResponse:
    """Answer a natural-language question using the catalogue data and OpenAI.

    **Safeguards**
    - *Rate limiting*: per-client and global request limits (see `X-RateLimit-*` headers).
    - *Input rails*: obvious prompt-injection attempts are rejected with 400.
    - *Output rails*: the reply must be valid JSON, may not leak prompt text or keys,
      and every cited book id must exist in the catalogue. Otherwise the answer is
      replaced by a standard refusal (`refused: true`).

    Requires `APP_OPENAI_API_KEY` to be set on the server.
    """
    return service.ask(payload.question)
