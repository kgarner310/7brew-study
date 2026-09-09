"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.middleware import MaxBodySizeMiddleware, RequestContextMiddleware
from app.api.v1 import health
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

DESCRIPTION = """
Jurisdiction-aware legal information infrastructure for the Individuals with
Disabilities Education Act (IDEA).

**This API returns legal information, not legal advice.** Every substantive
response reports the review status of the underlying records. Nothing below
`source_verified` is served unless explicitly requested, and machine-extracted
content is never presented as human-reviewed.
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Configure logging on startup."""
    settings = get_settings()
    configure_logging(settings)
    logger.info("api.startup", version=__version__, env=settings.env)
    yield
    logger.info("api.shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application.

    A factory rather than a module-level singleton so tests can construct an
    app bound to a test database without mutating global state.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="IDEA Atlas API",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS is deny-by-default: an empty allowlist means no cross-origin browser
    # access at all, which is correct for a machine-facing API.
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
            max_age=600,
        )

    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_router)
    return app


app = create_app()
