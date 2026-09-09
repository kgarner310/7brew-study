"""Exception handlers mapping domain errors to HTTP responses.

Handlers never leak internals: the client gets a stable message and the details
go to the structured log.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.errors import (
    IdeaAtlasError,
    InsufficientCoverageError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach every domain-error handler to ``app``."""

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "not_found", "detail": str(exc)},
        )

    @app.exception_handler(ValidationError)
    async def _invalid(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "detail": str(exc)},
        )

    @app.exception_handler(InsufficientCoverageError)
    async def _coverage(request: Request, exc: InsufficientCoverageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"error": "insufficient_coverage", "detail": str(exc)},
        )

    @app.exception_handler(IdeaAtlasError)
    async def _generic(request: Request, exc: IdeaAtlasError) -> JSONResponse:
        logger.error(
            "api.unhandled_domain_error",
            path=request.url.path,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "detail": "An internal error occurred."},
        )
