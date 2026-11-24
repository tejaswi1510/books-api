"""Request ID middleware: tags every request with an id and returns it in a header."""
import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER_NAME = "X-Request-ID"

# Holds the id of the request currently being handled ("-" outside a request).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Only accept safe ids from callers: letters, digits, dot, dash, underscore, max 64 chars.
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # ignore non-HTTP traffic such as lifespan events
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(HEADER_NAME)
        request_id = incoming if incoming and _VALID_ID.match(incoming) else uuid.uuid4().hex[:16]
        token = request_id_ctx.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER_NAME] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_ctx.reset(token)