"""The source registry: every place we retrieve legal text from.

Provenance starts here. A document that cannot name its source cannot be
trusted, and a source whose copyright posture is unknown must not be ingested
at scale -- see docs/LEGAL_DATA_POLICY.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    CommercialReuseStatus,
    CopyrightStatus,
    CrawlFrequency,
    CrawlStatus,
    RetrievalMethod,
    SourceType,
)
from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum

if TYPE_CHECKING:
    from app.models.authority import Authority
    from app.models.ingestion import IngestionRun
    from app.models.jurisdiction import Jurisdiction


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """A registered, retrievable publisher of primary legal material."""

    __tablename__ = "source"

    jurisdiction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jurisdiction.id", ondelete="RESTRICT"), nullable=True
    )
    """Null is permitted for cross-jurisdictional sources; federal sources
    should point at the ``us`` federal jurisdiction rather than be left null."""

    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        pg_enum(SourceType, "source_type"), nullable=False
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_method: Mapped[RetrievalMethod] = mapped_column(
        pg_enum(RetrievalMethod, "retrieval_method"), nullable=False
    )
    official_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    """True only for the government body that promulgates or publishes of record."""

    copyright_status: Mapped[CopyrightStatus] = mapped_column(
        pg_enum(CopyrightStatus, "copyright_status"),
        nullable=False,
        default=CopyrightStatus.UNKNOWN,
    )
    license_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    commercial_reuse_status: Mapped[CommercialReuseStatus] = mapped_column(
        pg_enum(CommercialReuseStatus, "commercial_reuse_status"),
        nullable=False,
        default=CommercialReuseStatus.UNKNOWN,
    )
    terms_of_service_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crawl_frequency: Mapped[CrawlFrequency] = mapped_column(
        pg_enum(CrawlFrequency, "crawl_frequency"),
        nullable=False,
        default=CrawlFrequency.ON_DEMAND,
    )
    crawl_status: Mapped[CrawlStatus] = mapped_column(
        pg_enum(CrawlStatus, "crawl_status"),
        nullable=False,
        default=CrawlStatus.NOT_STARTED,
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    jurisdiction: Mapped[Jurisdiction | None] = relationship(back_populates="sources")
    authorities: Mapped[list[Authority]] = relationship(back_populates="source")
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(back_populates="source")

    __table_args__ = (
        UniqueConstraint("jurisdiction_id", "name", name="uq_source_jurisdiction_name"),
        Index("ix_source_type_active", "source_type", "active"),
        Index("ix_source_crawl_status", "crawl_status"),
    )
