"""Liveness and readiness."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Service health."""

    status: str
    version: str
    database: str
    time: datetime


@router.get("/health", response_model=HealthResponse, summary="Service health")
def health(session: DbSession) -> HealthResponse:
    """Report service and database status.

    Returns 200 with ``database='unavailable'`` rather than failing, so a load
    balancer can distinguish "process up, DB down" from "process down".
    """
    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        version=__version__,
        database=database,
        time=datetime.now(UTC),
    )
