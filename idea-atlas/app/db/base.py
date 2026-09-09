"""Declarative base, shared column types, and mixins.

Conventions enforced here:

* Primary keys are UUIDs (``uuid4``), generated application-side so that
  related rows can be wired up before a flush.
* Every timestamp is timezone-aware and stored in UTC.
* Constraint names follow an explicit naming convention so Alembic autogenerate
  produces stable, reversible migrations.
* Free-form JSON lives in a ``metadata`` JSONB column, exposed on the model as
  ``meta`` (``metadata`` is reserved by SQLAlchemy's declarative API).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all IDEA Atlas models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


class UUIDPrimaryKeyMixin:
    """Adds a client-generated UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Adds UTC created/updated timestamps maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MetadataMixin:
    """Adds the free-form ``metadata`` JSONB column.

    Use this for source-specific detail that does not deserve a column. Do not
    use it for anything the API filters on -- promote that to a real column.
    """

    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
