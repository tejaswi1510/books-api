import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_book_repository, get_client_rate_limiter, get_global_rate_limiter
from app.core.config import Settings, get_settings
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import Principal, get_current_principal
from app.main import create_app
from app.repositories.csv_book_repository import CsvBookRepository

SEED_CSV = Path(__file__).resolve().parents[1] / "data" / "books.csv"
TEST_API_KEY = "test-key-1"


def _build_app(tmp_path):
    """A fresh app with its own CSV copy and generous rate limits, so tests
    never touch real data or interfere with each other."""
    csv_copy = tmp_path / "books.csv"
    shutil.copy(SEED_CSV, csv_copy)
    repo = CsvBookRepository(csv_copy)
    client_limiter = InMemoryRateLimiter(1000, 60)
    global_limiter = InMemoryRateLimiter(1000, 60)

    app = create_app()
    app.dependency_overrides[get_book_repository] = lambda: repo
    app.dependency_overrides[get_client_rate_limiter] = lambda: client_limiter
    app.dependency_overrides[get_global_rate_limiter] = lambda: global_limiter
    return app


@pytest.fixture
def client(tmp_path):
    """Auth check is bypassed, so existing tests focus on behaviour."""
    app = _build_app(tmp_path)
    app.dependency_overrides[get_current_principal] = lambda: Principal("test-admin", "admin", "test")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(tmp_path):
    """The REAL auth check is active, with a known test key configured."""
    app = _build_app(tmp_path)
    app.dependency_overrides[get_settings] = lambda: Settings(api_keys=TEST_API_KEY)
    with TestClient(app) as test_client:
        yield test_client