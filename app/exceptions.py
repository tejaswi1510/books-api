"""Domain exceptions. Services raise these; main.py maps them to HTTP responses."""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    headers: dict[str, str] | None = None  # extra HTTP headers, e.g. Retry-After

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        self.message = message
        super().__init__(message)


class BookNotFoundError(AppError):
    status_code = 404
    code = "book_not_found"

    def __init__(self, book_id: int) -> None:
        super().__init__(f"Book with id {book_id} was not found")


class AINotConfiguredError(AppError):
    status_code = 503
    code = "ai_not_configured"

    def __init__(self) -> None:
        super().__init__(
            "The AI assistant is not configured. Set APP_OPENAI_API_KEY and restart the server."
        )


class AIUpstreamError(AppError):
    status_code = 502
    code = "ai_upstream_error"

    def __init__(self, message: str = "The AI provider request failed. Please try again later.") -> None:
        super().__init__(message)


class AIServiceTimeoutError(AppError):
    status_code = 504
    code = "ai_timeout"

    def __init__(self) -> None:
        super().__init__("The AI provider took too long to respond. Please try again.")


class AIRateLimitedError(AppError):
    status_code = 429
    code = "ai_rate_limited"

    def __init__(self) -> None:
        super().__init__("The AI provider is rate limiting requests. Please retry shortly.")


class InputBlockedError(AppError):
    status_code = 400
    code = "input_blocked"

    def __init__(self) -> None:
        super().__init__(
            "Your question was blocked by input safety checks. "
            "Please rephrase it as a question about the book catalogue."
        )


class AIInvalidOutputError(AppError):
    status_code = 502
    code = "ai_invalid_output"

    def __init__(self) -> None:
        super().__init__("The AI provider returned a response in an unexpected format. Please try again.")


class RateLimitExceededError(AppError):
    """Raised by OUR rate limiter (not to be confused with the provider's AIRateLimitedError)."""

    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(self, retry_after: int, scope: str = "client") -> None:
        self.headers = {"Retry-After": str(retry_after)}
        if scope == "global":
            message = f"The AI assistant is receiving too many requests overall. Retry in {retry_after} seconds."
        else:
            message = f"Too many requests. Retry in {retry_after} seconds."
        super().__init__(message)

class AuthenticationError(AppError):
    status_code = 401
    code = "unauthorized"
    headers = {"WWW-Authenticate": "ApiKey"}

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class AuthNotConfiguredError(AppError):
    status_code = 503
    code = "auth_not_configured"

    def __init__(
        self,
        message: str = "API authentication is not configured. Set APP_API_KEYS and restart the server.",
    ) -> None:
        super().__init__(message)


class InvalidCredentialsError(AuthenticationError):
    """Wrong username or password. Deliberately vague so it never reveals which one."""

    headers = {"WWW-Authenticate": "Bearer"}

    def __init__(self) -> None:
        super().__init__("Incorrect username or password")
