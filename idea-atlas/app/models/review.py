"""The review audit trail."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EntityType, ReviewStatus
from app.db.base import Base, MetadataMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum


class ReviewEvent(Base, UUIDPrimaryKeyMixin, MetadataMixin):
    """An append-only record of a review-status transition.

    Deliberately *not* a mutable status column: the history of who asserted
    what, and when, is itself part of the provenance record. Nothing in the
    application updates or deletes these rows; ``docs/SECURITY.md`` describes
    the database-level grants that enforce that in production.
    """

    __tablename__ = "review_event"

    entity_type: Mapped[EntityType] = mapped_column(
        pg_enum(EntityType, "entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    """Intentionally not a foreign key: the trail outlives the row it describes."""

    previous_status: Mapped[ReviewStatus | None] = mapped_column(
        pg_enum(ReviewStatus, "review_status"), nullable=True
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"), nullable=False
    )
    reviewer: Mapped[str] = mapped_column(String(128), nullable=False)
    """Actor identifier; ``pipeline:<name>`` or ``ai:<model>`` for machines."""
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_review_event_entity", "entity_type", "entity_id"),
        Index("ix_review_event_created", "created_at"),
    )
