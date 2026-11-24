"""Application settings, loaded from environment variables / .env (12-factor style)."""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Books API"
    app_version: str = "1.0.0"
    app_description: str = (
        "A demo REST API for managing a book catalogue, backed by a CSV file.\n\n"
        "Built with a layered structure (routes -> services -> repositories) so the "
        "CSV store can later be swapped for a real database."
    )
    environment: str = "development"
    log_level: str = "INFO"
    log_format: str = "text"  # "text" (readable in the terminal) or "json" (for CloudWatch)
    api_v1_prefix: str = "/api/v1"
    books_csv_path: Path = BASE_DIR / "data" / "books.csv"
    # PostgreSQL connection URL. When empty, the app uses the CSV file instead.
    database_url: str | None = None
    # Comma-separated list of valid API keys (several allow key rotation).
    api_keys: SecretStr | None = None

    # --- AI assistant (OpenAI) ---
    # Set APP_OPENAI_API_KEY in your environment or .env file. Never commit it.
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2
    # Upper bound on catalogue rows sent to the model as context (cost/latency guard).
    ai_max_books_in_context: int = 200

    # --- AI guardrails / rate limiting ---
    ai_max_answer_chars: int = 2000
    # Per-client limit (keyed by IP address) on POST /assistant/ask
    ai_rate_limit_requests: int = 10
    ai_rate_limit_window_seconds: int = 60
    # Global spend guard shared by ALL clients (default: 200 requests per day)
    ai_global_rate_limit_requests: int = 200
    ai_global_rate_limit_window_seconds: int = 86400

    # Every setting can be overridden with an APP_-prefixed env var, e.g. APP_LOG_LEVEL=DEBUG
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_prefix="APP_", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
