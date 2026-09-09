"""Authorities and their immutable, hash-addressed versions."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AuthorityCurrentStatus,
    AuthorityRelationType,
    AuthorityType,
    IdeaPart,
    PrecedentialStatus,
    ReviewStatus,
)
from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum

if TYPE_CHECKING:
    from app.models.jurisdiction import Jurisdiction
    from app.models.proposition import PropositionAuthority
    from app.models.source import Source


class Authority(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """A single legal authority: a statute section, regulation, opinion, or letter.

    The Authority row is the stable identity. Its *text* lives in
    :class:`AuthorityVersion`, because the same authority is amended over time
    and every historical text must remain retrievable with its effective dates.
    """

    __tablename__ = "authority"

    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdiction.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source.id", ondelete="RESTRICT"), nullable=False
    )

    authority_type: Mapped[AuthorityType] = mapped_column(
        pg_enum(AuthorityType, "authority_type"), nullable=False
    )
    canonical_citation: Mapped[str] = mapped_column(String(512), nullable=False)
    """Bluebook-style citation, e.g. ``34 C.F.R. Sec. 300.301``."""
    title: Mapped[str] = mapped_column(Text, nullable=False)
    short_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    docket_or_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    court_or_agency: Mapped[str | None] = mapped_column(String(255), nullable=True)

    idea_part: Mapped[IdeaPart | None] = mapped_column(
        pg_enum(IdeaPart, "idea_part"), nullable=True
    )

    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    current_status: Mapped[AuthorityCurrentStatus] = mapped_column(
        pg_enum(AuthorityCurrentStatus, "authority_current_status"),
        nullable=False,
        default=AuthorityCurrentStatus.UNKNOWN,
    )
    precedential_status: Mapped[PrecedentialStatus] = mapped_column(
        pg_enum(PrecedentialStatus, "precedential_status"),
        nullable=False,
        default=PrecedentialStatus.UNKNOWN,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"),
        nullable=False,
        default=ReviewStatus.NEEDS_REVIEW,
    )

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    """The URL we actually retrieved."""
    official_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    """The canonical publisher URL, when it differs from what we fetched."""

    jurisdiction: Mapped[Jurisdiction] = relationship(back_populates="authorities")
    source: Mapped[Source] = relationship(back_populates="authorities")
    versions: Mapped[list[AuthorityVersion]] = relationship(
        back_populates="authority",
        cascade="all, delete-orphan",
        order_by="AuthorityVersion.retrieved_at.desc()",
    )
    proposition_links: Mapped[list[PropositionAuthority]] = relationship(
        back_populates="authority", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "jurisdiction_id",
            "canonical_citation",
            name="uq_authority_jurisdiction_citation",
        ),
        CheckConstraint(
            "superseded_date IS NULL OR effective_date IS NULL "
            "OR superseded_date >= effective_date",
            name="authority_dates_ordered",
        ),
        Index("ix_authority_type_status", "authority_type", "current_status"),
        Index("ix_authority_jurisdiction_type", "jurisdiction_id", "authority_type"),
        Index("ix_authority_idea_part", "idea_part"),
    )

    @property
    def current_version(self) -> AuthorityVersion | None:
        """The version flagged current, if one has been ingested."""
        return next((v for v in self.versions if v.is_current), None)


class AuthorityVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """One retrieved text of an authority, addressed by SHA-256.

    Rows here are treated as append-only. Change detection compares the hash of
    freshly fetched normalized text against ``sha256``; an unchanged document
    produces no new row. A partial unique index guarantees at most one current
    version per authority.
    """

    __tablename__ = "authority_version"

    authority_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authority.id", ondelete="CASCADE"), nullable=False
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    """Bytes as retrieved, decoded. Never edited."""
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    """Whitespace- and entity-normalized plain text; what the hash covers."""
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    """Hash of the untouched response body, for byte-level integrity audits."""
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    byte_size: Mapped[int] = mapped_column(nullable=False, default=0)

    parser_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_snapshot_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    """E.g. a Wayback Machine capture, where one exists."""

    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"),
        nullable=False,
        default=ReviewStatus.SOURCE_VERIFIED,
    )

    authority: Mapped[Authority] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("authority_id", "sha256", name="uq_authority_version_hash"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        CheckConstraint("length(raw_sha256) = 64", name="raw_sha256_length"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="version_dates_ordered",
        ),
        Index(
            "uq_authority_version_one_current",
            "authority_id",
            unique=True,
            postgresql_where="is_current",
        ),
        Index("ix_authority_version_retrieved", "authority_id", "retrieved_at"),
    )


class AuthorityRelationship(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """A directed citator-style edge between two authorities."""

    __tablename__ = "authority_relationship"

    source_authority_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authority.id", ondelete="CASCADE"), nullable=False
    )
    target_authority_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authority.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[AuthorityRelationType] = mapped_column(
        pg_enum(AuthorityRelationType, "authority_relation_type"), nullable=False
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"),
        nullable=False,
        default=ReviewStatus.NEEDS_REVIEW,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_authority: Mapped[Authority] = relationship(foreign_keys=[source_authority_id])
    target_authority: Mapped[Authority] = relationship(foreign_keys=[target_authority_id])

    __table_args__ = (
        UniqueConstraint(
            "source_authority_id",
            "target_authority_id",
            "relationship_type",
            name="uq_authority_relationship_edge",
        ),
        CheckConstraint(
            "source_authority_id <> target_authority_id",
            name="authority_relationship_no_self_edge",
        ),
        Index("ix_authority_relationship_target", "target_authority_id"),
    )
