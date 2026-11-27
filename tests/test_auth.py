import pytest

from app.api.deps import get_llm_client
from app.core.config import Settings, get_settings
from tests.conftest import TEST_API_KEY
from tests.fakes import FakeLLM

BOOKS = "/api/v1/books"
ASK = "/api/v1/assistant/ask"
GOOD = {"X-API-Key": TEST_API_KEY}
NEW_BOOK = {
    "title": "The Left Hand of Darkness",
    "author": "Ursula K. Le Guin",
    "genre": "Science Fiction",
    "published_year": 1969,
    "price": 11.99,
    "in_stock": True,
}


def test_reading_is_public(auth_client):
    assert auth_client.get(BOOKS).status_code == 200
    assert auth_client.get(f"{BOOKS}/1").status_code == 200
    assert auth_client.get("/health").status_code == 200


def test_write_without_key_returns_401(auth_client):
    resp = auth_client.post(BOOKS, json=NEW_BOOK)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
    assert resp.headers["www-authenticate"] == "Bearer"


def test_write_with_wrong_key_returns_401(auth_client):
    resp = auth_client.post(BOOKS, json=NEW_BOOK, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_write_with_valid_key_succeeds(auth_client):
    resp = auth_client.post(BOOKS, json=NEW_BOOK, headers=GOOD)
    assert resp.status_code == 201


@pytest.mark.parametrize(
    "method,path",
    [("POST", BOOKS), ("PUT", f"{BOOKS}/1"), ("PATCH", f"{BOOKS}/1"), ("DELETE", f"{BOOKS}/1")],
)
def test_every_write_endpoint_requires_a_key(auth_client, method, path):
    assert auth_client.request(method, path, json=NEW_BOOK).status_code == 401


def test_ai_endpoint_without_key_never_reaches_the_model(auth_client):
    llm = FakeLLM()
    auth_client.app.dependency_overrides[get_llm_client] = lambda: llm
    resp = auth_client.post(ASK, json={"question": "How much is Dune?"})
    assert resp.status_code == 401
    assert llm.calls == []  # no OpenAI tokens spent


def test_ai_endpoint_with_key_works(auth_client):
    auth_client.app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    resp = auth_client.post(ASK, json={"question": "How much is Dune?"}, headers=GOOD)
    assert resp.status_code == 200


def test_no_keys_configured_fails_closed(auth_client):
    auth_client.app.dependency_overrides[get_settings] = lambda: Settings(api_keys=None)
    resp = auth_client.post(BOOKS, json=NEW_BOOK, headers=GOOD)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "auth_not_configured"


def test_multiple_keys_allow_rotation(auth_client):
    auth_client.app.dependency_overrides[get_settings] = lambda: Settings(api_keys="old-key,new-key")
    for key in ("old-key", "new-key"):
        assert auth_client.post(BOOKS, json=NEW_BOOK, headers={"X-API-Key": key}).status_code == 201