"""OpenAI implementation of LLMClient (Chat Completions API)."""
import logging

import openai
from openai import OpenAI

from app.clients.llm import LLMClient, LLMResult
from app.exceptions import AIRateLimitedError, AIServiceTimeoutError, AIUpstreamError

logger = logging.getLogger(__name__)


class OpenAILLMClient(LLMClient):
    def __init__(
        self, api_key: str, model: str, timeout_seconds: float, max_retries: int
    ) -> None:
        # The SDK handles connection pooling and retries (with backoff) for us.
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)
        self._model = model

    def complete(self, system_prompt: str, user_message: str) -> LLMResult:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
        # Order matters: APITimeoutError subclasses APIConnectionError, and
        # RateLimitError subclasses APIStatusError.
        except openai.APITimeoutError as exc:
            logger.error("OpenAI request timed out: %s", exc)
            raise AIServiceTimeoutError() from exc
        except openai.RateLimitError as exc:
            logger.error("OpenAI rate limit/quota error: %s", exc)
            raise AIRateLimitedError() from exc
        except openai.APIConnectionError as exc:
            logger.error("Could not connect to OpenAI: %s", exc)
            raise AIUpstreamError() from exc
        except openai.APIStatusError as exc:
            # Includes 401 (bad key) and 404 (unknown model). Details are logged
            # server-side only; the client just gets a generic message.
            logger.error("OpenAI returned HTTP %s: %s", exc.status_code, exc.message)
            raise AIUpstreamError() from exc
        except openai.OpenAIError as exc:
            logger.error("Unexpected OpenAI SDK error: %s", exc)
            raise AIUpstreamError() from exc

        text = response.choices[0].message.content if response.choices else None
        if not text or not text.strip():
            logger.error("OpenAI returned an empty completion (model=%s)", response.model)
            raise AIUpstreamError("The AI provider returned an empty response.")

        if response.usage:
            logger.info(
                "OpenAI usage: model=%s prompt_tokens=%s completion_tokens=%s",
                response.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )
        return LLMResult(text=text.strip(), model=response.model)
