"""Request-context middleware (ADR-12): request ID, access log, error boundary.

Written as pure ASGI rather than Starlette's BaseHTTPMiddleware on purpose:
BaseHTTPMiddleware re-buffers responses through a memory stream, which is
exactly the wrong thing to put in front of a Server-Sent Events endpoint.
This wrapper only observes messages passing through, so SSE frames stream
out unmodified.
"""

import logging
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.core.logging import request_id_var

logger = logging.getLogger("finsight.access")


class RequestContextMiddleware:
    """Outermost middleware. For every HTTP request:

    - assigns a request ID (honoring an inbound ``X-Request-ID`` from a proxy)
      and stores it in a ContextVar so all log lines in the request carry it;
    - echoes the ID on the response, plus baseline security headers;
    - emits one access-log line with method, path, status, and duration;
    - converts unhandled exceptions into a clean JSON 500 carrying the
      request ID as ``error_id`` — internals go to the log, never the client.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        method, path = scope["method"], scope["path"]
        started = time.perf_counter()
        status_code = 0
        response_started = False

        async def send_with_context(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception:
            # Full traceback to the log (with request ID); a generic body to
            # the client. If the response already started (mid-SSE-stream)
            # there is nothing valid left to send, so only log.
            logger.exception("Unhandled error on %s %s", method, path)
            if not response_started:
                response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error", "error_id": request_id},
                )
                await response(scope, receive, send_with_context)
            status_code = 500
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info("%s %s -> %d in %dms", method, path, status_code, duration_ms)
            request_id_var.reset(token)
