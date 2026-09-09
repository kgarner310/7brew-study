"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def pagination(
    limit: Annotated[int, Query(ge=1, le=200, description="Rows per page.")] = 50,
    offset: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0,
) -> tuple[int, int]:
    """Standard limit/offset paging, bounded so a client cannot request the world."""
    return limit, offset


Pagination = Annotated[tuple[int, int], Depends(pagination)]
