"""HTTP middleware: request size limiting and request-scoped logging context."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger(__name__)

Handler = Callable[[Request], Awaitable[Response]]


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before they are buffered.

    Checks the declared Content-Length. Requests without one are still bounded
    by the ASGI server's own limits; this middleware is the cheap first gate,
    not the only one.
    """

    def __init__(self, app: object, max_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            return JSONResponse(
                # 413 as a literal: Starlette renamed the constant and we do
                # not want the wire behaviour coupled to that rename.
                status_code=413,
                content={
                    "error": "request_too_large",
                    "detail": f"Request body exceeds {self.max_bytes} bytes.",
                },
            )
        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id to the logging context and echo it to the client."""

    async def dispatch(self, request: Request, call_next: Handler) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "method", "path")
        response.headers["x-request-id"] = request_id
        return response
