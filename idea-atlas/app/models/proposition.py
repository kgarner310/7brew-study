"""Legal propositions: the jurisdiction-aware claims the platform can answer with.

A proposition is a single normative statement ("An LEA may not use MTSS to
delay an initial evaluation") scoped to a concept, a jurisdiction, and a time
window, and backed by linked authorities. A proposition with no supporting
authority is never served -- see ``SERVABLE_REVIEW_STATUSES``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    PropositionAuthorityRelation,
    PropositionAuthorityStatus,
    PropositionType,
    ReviewStatus,
)
from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum

if TYPE_CHECKING:
    from app.models.authority import Authority
    from app.models.concept import LegalConcept
    from app.models.jurisdiction import Jurisdiction


class Proposition(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """One jurisdiction-scoped legal proposition."""

    __tablename__ = "proposition"

    concept_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("legal_concept.id", ondelete="RESTRICT"), nullable=False
    )
    jurisdiction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jurisdiction.id", ondelete="RESTRICT"), nullable=True
    )
    """Null means the proposition is universal (federal floor applying everywhere)."""

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    qualifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Conditions or carve-outs that narrow the statement."""

    proposition_type: Mapped[PropositionType] = mapped_column(
        pg_enum(PropositionType, "proposition_type"), nullable=False
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    """0.0-1.0. A machine-assigned estimate, never a substitute for review status."""

    authority_status: Mapped[PropositionAuthorityStatus] = mapped_column(
        pg_enum(PropositionAuthorityStatus, "proposition_authority_status"),
        nullable=False,
        default=PropositionAuthorityStatus.UNSUPPORTED,
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        pg_enum(ReviewStatus, "review_status"),
        nullable=False,
        default=ReviewStatus.NEEDS_REVIEW,
    )

    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    """Actor identifier: a person, or ``pipeline:<name>`` / ``ai:<model>``."""
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    concept: Mapped[LegalConcept] = relationship(back_populates="propositions")
    jurisdiction: Mapped[Jurisdiction | None] = relationship()
    authority_links: Mapped[list[PropositionAuthority]] = relationship(
        back_populates="proposition", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="confidence_range"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="proposition_dates_ordered",
        ),
        CheckConstraint("length(btrim(statement)) > 0", name="statement_not_blank"),
        CheckConstraint(
            "(review_status <> 'human_reviewed' AND review_status <> 'expert_reviewed')"
            " OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="reviewed_records_name_a_reviewer",
        ),
        Index("ix_proposition_concept_jurisdiction", "concept_id", "jurisdiction_id"),
        Index("ix_proposition_review_status", "review_status"),
        Index("ix_proposition_authority_status", "authority_status"),
    )


class PropositionAuthority(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Link between a proposition and the authority that backs (or limits) it."""

    __tablename__ = "proposition_authority"

    proposition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposition.id", ondelete="CASCADE"), nullable=False
    )
    authority_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("authority.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[PropositionAuthorityRelation] = mapped_column(
        pg_enum(PropositionAuthorityRelation, "proposition_authority_relation"),
        nullable=False,
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    """Relative ordering hint, 0-100. Highest weight leads a citation list."""
    pin_cite: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """Pinpoint locator, e.g. ``Sec. 300.301(c)(1)`` or ``580 U.S. at 403``."""
    quoted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Verbatim supporting excerpt from the authority's normalized text."""
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    proposition: Mapped[Proposition] = relationship(back_populates="authority_links")
    authority: Mapped[Authority] = relationship(back_populates="proposition_links")

    __table_args__ = (
        UniqueConstraint(
            "proposition_id",
            "authority_id",
            "relationship_type",
            name="uq_proposition_authority_edge",
        ),
        CheckConstraint("weight >= 0 AND weight <= 100", name="weight_range"),
        Index("ix_proposition_authority_authority", "authority_id"),
    )
