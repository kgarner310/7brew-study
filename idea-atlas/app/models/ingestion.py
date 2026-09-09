"""Ingestion run bookkeeping."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import IngestionStatus
from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum

if TYPE_CHECKING:
    from app.models.source import Source


class IngestionRun(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """One execution of a collector against one source.

    Every ingestion attempt produces a row, including failures. This table is
    the operational audit trail: it answers "when did we last successfully see
    this source, and what changed?".
    """

    __tablename__ = "ingestion_run"

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[IngestionStatus] = mapped_column(
        pg_enum(IngestionStatus, "ingestion_status"),
        nullable=False,
        default=IngestionStatus.PENDING,
    )

    documents_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Newline-delimited error summaries. Never contains response bodies."""

    triggered_by: Mapped[str] = mapped_column(String(128), nullable=False, default="cli")
    collector_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dry_run: Mapped[bool] = mapped_column(nullable=False, default=False)

    source: Mapped[Source] = relationship(back_populates="ingestion_runs")

    __table_args__ = (
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ingestion_run_times_ordered",
        ),
        CheckConstraint(
            "documents_seen >= 0 AND changed_documents >= 0 AND error_count >= 0",
            name="ingestion_run_counts_non_negative",
        ),
        Index("ix_ingestion_run_source_started", "source_id", "started_at"),
        Index("ix_ingestion_run_status", "status"),
    )
