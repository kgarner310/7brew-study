"""The IDEA legal-concept taxonomy."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import IdeaPart
from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum

if TYPE_CHECKING:
    from app.models.proposition import Proposition


class LegalConcept(Base, UUIDPrimaryKeyMixin, TimestampMixin, MetadataMixin):
    """A node in the IDEA subject-matter taxonomy.

    Concepts are jurisdiction-neutral: "Child Find" means the same thing as a
    topic everywhere. Jurisdiction-specific legal content hangs off
    :class:`~app.models.proposition.Proposition` instead.
    """

    __tablename__ = "legal_concept"

    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("legal_concept.id", ondelete="RESTRICT"), nullable=True
    )
    idea_part: Mapped[IdeaPart] = mapped_column(
        pg_enum(IdeaPart, "idea_part"), nullable=False, default=IdeaPart.PART_B
    )
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}"
    )
    """Search synonyms, e.g. ``MTSS`` and ``RTI`` for the evaluation-timeline concept."""

    parent: Mapped[LegalConcept | None] = relationship(
        remote_side="LegalConcept.id", back_populates="children"
    )
    children: Mapped[list[LegalConcept]] = relationship(back_populates="parent")
    propositions: Mapped[list[Proposition]] = relationship(back_populates="concept")

    __table_args__ = (
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="concept_not_own_parent"),
        Index("ix_legal_concept_part", "idea_part"),
        Index("ix_legal_concept_parent", "parent_id"),
    )
