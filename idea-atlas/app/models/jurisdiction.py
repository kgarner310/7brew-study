"""Jurisdictions: every place IDEA reaches, plus the federal circuits."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import JurisdictionType
from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum

if TYPE_CHECKING:
    from app.models.authority import Authority
    from app.models.source import Source


class Jurisdiction(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """A legal jurisdiction in the IDEA coverage universe.

    Includes the 50 states, DC, Puerto Rico, the four other territories, the
    Bureau of Indian Education, the federal government itself, and the federal
    circuits (as precedent-scoping jurisdictions).
    """

    __tablename__ = "jurisdiction"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction_type: Mapped[JurisdictionType] = mapped_column(
        pg_enum(JurisdictionType, "jurisdiction_type"), nullable=False
    )
    postal_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    parent_jurisdiction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jurisdiction.id", ondelete="RESTRICT"), nullable=True
    )
    federal_circuit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """Circuit slug, e.g. ``4th`` or ``dc``. Null where no circuit applies."""

    sea_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    """State educational agency, or its equivalent for non-state jurisdictions."""

    idea_part_b_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    idea_part_c_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped[Jurisdiction | None] = relationship(
        remote_side="Jurisdiction.id", back_populates="children"
    )
    children: Mapped[list[Jurisdiction]] = relationship(back_populates="parent")
    sources: Mapped[list[Source]] = relationship(back_populates="jurisdiction")
    authorities: Mapped[list[Authority]] = relationship(back_populates="jurisdiction")

    __table_args__ = (
        CheckConstraint(
            "parent_jurisdiction_id IS NULL OR parent_jurisdiction_id <> id",
            name="jurisdiction_not_own_parent",
        ),
        CheckConstraint(
            "postal_code IS NULL OR postal_code = upper(postal_code)",
            name="postal_code_uppercase",
        ),
        Index("ix_jurisdiction_type_active", "jurisdiction_type", "active"),
        Index("ix_jurisdiction_postal_code", "postal_code"),
    )
