from app.api.deps import get_client_rate_limiter, get_global_rate_limiter, get_llm_client
from app.core.rate_limit import InMemoryRateLimiter
from tests.fakes import FakeLLM

URL = "/api/v1/assistant/ask"
QUESTION = {"question": "How much is Dune?"}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


# ---- unit tests for the limiter itself ------------------------------------
def test_blocks_after_limit_is_reached():
    limiter = InMemoryRateLimiter(2, 60, clock=Clock())
    assert limiter.hit("a").allowed
    second = limiter.hit("a")
    assert second.allowed and second.remaining == 0
    blocked = limiter.hit("a")
    assert not blocked.allowed and blocked.retry_after == 60


def test_window_slides_and_frees_slots():
    clock = Clock()
    limiter = InMemoryRateLimiter(2, 60, clock=clock)
    limiter.hit("a")
    limiter.hit("a")
    clock.now = 61
    assert limiter.hit("a").allowed


def test_retry_after_is_based_on_oldest_hit():
    clock = Clock()
    limiter = InMemoryRateLimiter(2, 60, clock=clock)
    limiter.hit("a")        # t=0
    clock.now = 30
    limiter.hit("a")        # t=30
    clock.now = 31
    assert limiter.hit("a").retry_after == 29  # oldest hit (t=0) expires at t=60


def test_keys_are_independent():
    limiter = InMemoryRateLimiter(1, 60, clock=Clock())
    assert limiter.hit("a").allowed
    assert limiter.hit("b").allowed
    assert not limiter.hit("a").allowed


# ---- endpoint behaviour ---------------------------------------------------
def test_endpoint_returns_429_with_retry_after(client):
    client.app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    limiter = InMemoryRateLimiter(2, 60)
    client.app.dependency_overrides[get_client_rate_limiter] = lambda: limiter

    assert client.post(URL, json=QUESTION).status_code == 200
    assert client.post(URL, json=QUESTION).status_code == 200
    resp = client.post(URL, json=QUESTION)

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limit_exceeded"
    assert int(resp.headers["retry-after"]) >= 1


def test_success_responses_include_ratelimit_headers(client):
    client.app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    limiter = InMemoryRateLimiter(5, 60)
    client.app.dependency_overrides[get_client_rate_limiter] = lambda: limiter

    resp = client.post(URL, json=QUESTION)
    assert resp.headers["x-ratelimit-limit"] == "5"
    assert resp.headers["x-ratelimit-remaining"] == "4"


def test_global_limit_applies_across_clients(client):
    client.app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    global_limiter = InMemoryRateLimiter(1, 3600)
    client.app.dependency_overrides[get_global_rate_limiter] = lambda: global_limiter

    assert client.post(URL, json=QUESTION).status_code == 200
    resp = client.post(URL, json=QUESTION)
    assert resp.status_code == 429
    assert "overall" in resp.json()["error"]["message"]


def test_rate_limited_requests_never_reach_the_model(client):
    llm = FakeLLM()
    client.app.dependency_overrides[get_llm_client] = lambda: llm
    limiter = InMemoryRateLimiter(1, 60)
    client.app.dependency_overrides[get_client_rate_limiter] = lambda: limiter

    client.post(URL, json=QUESTION)
    client.post(URL, json=QUESTION)
    assert len(llm.calls) == 1
