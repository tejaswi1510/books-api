import logging
import re

from app.core.logging import RequestIDFilter
from app.core.request_id import HEADER_NAME, request_id_ctx

GENERATED = re.compile(r"[0-9a-f]{16}")


def test_response_has_a_generated_request_id(client):
    rid = client.get("/health").headers[HEADER_NAME]
    assert GENERATED.fullmatch(rid)


def test_every_request_gets_a_different_id(client):
    first = client.get("/health").headers[HEADER_NAME]
    second = client.get("/health").headers[HEADER_NAME]
    assert first != second


def test_a_valid_incoming_id_is_echoed_back(client):
    resp = client.get("/health", headers={HEADER_NAME: "my-test-123"})
    assert resp.headers[HEADER_NAME] == "my-test-123"


def test_an_unsafe_incoming_id_is_replaced(client):
    resp = client.get("/health", headers={HEADER_NAME: "bad id with spaces"})
    assert GENERATED.fullmatch(resp.headers[HEADER_NAME])


def test_an_overlong_incoming_id_is_replaced(client):
    resp = client.get("/health", headers={HEADER_NAME: "a" * 65})
    assert GENERATED.fullmatch(resp.headers[HEADER_NAME])


def test_error_responses_also_carry_the_id(client):
    resp = client.get("/api/v1/books/999")
    assert resp.status_code == 404
    assert HEADER_NAME in resp.headers


def test_the_id_is_visible_inside_the_handler_and_cleared_afterwards(client):
    seen = []

    @client.app.get("/_probe")
    def probe():  # a plain def, so it runs in a worker thread like the real handlers
        seen.append(request_id_ctx.get())
        return {}

    client.get("/_probe", headers={HEADER_NAME: "probe-1"})
    assert seen == ["probe-1"]
    assert request_id_ctx.get() == "-"  # reset once the request ended


def _record() -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)


def test_log_filter_attaches_the_current_id():
    token = request_id_ctx.set("abc123")
    try:
        record = _record()
        assert RequestIDFilter().filter(record) is True
        assert record.request_id == "abc123"
    finally:
        request_id_ctx.reset(token)


def test_log_filter_uses_a_dash_outside_a_request():
    record = _record()
    RequestIDFilter().filter(record)
    assert record.request_id == "-"