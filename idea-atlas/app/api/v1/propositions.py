"""Proposition endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import DbSession, Pagination
from app.core.enums import PropositionType, ReviewStatus
from app.core.errors import NotFoundError
from app.models import Jurisdiction, LegalConcept, Proposition
from app.schemas.common import Page
from app.schemas.entities import (
    PropositionAuthorityOut,
    PropositionDetailOut,
    PropositionOut,
)

router = APIRouter(prefix="/propositions", tags=["propositions"])


def _to_out(proposition: Proposition) -> PropositionOut:
    return PropositionOut(
        id=proposition.id,
        concept_id=proposition.concept_id,
        concept_slug=proposition.concept.slug,
        jurisdiction_id=proposition.jurisdiction_id,
        jurisdiction_slug=(proposition.jurisdiction.slug if proposition.jurisdiction else None),
        statement=proposition.statement,
        qualifier=proposition.qualifier,
        proposition_type=proposition.proposition_type,
        effective_from=proposition.effective_from,
        effective_to=proposition.effective_to,
        confidence=proposition.confidence,
        authority_status=proposition.authority_status,
        review_status=proposition.review_status,
        created_by=proposition.created_by,
        reviewed_by=proposition.reviewed_by,
        reviewed_at=proposition.reviewed_at,
    )


@router.get("", response_model=Page[PropositionOut], summary="List propositions")
def list_propositions(
    session: DbSession,
    page: Pagination,
    concept: str | None = Query(default=None, description="Concept slug."),
    jurisdiction: str | None = Query(
        default=None, description="Jurisdiction slug. Universal rules are always included."
    ),
    review_status: ReviewStatus | None = Query(default=None),
    proposition_type: PropositionType | None = Query(default=None),
) -> Page[PropositionOut]:
    """List propositions.

    ``review_status`` is always returned verbatim so a caller can tell verified
    content from machine-extracted content.
    """
    limit, offset = page
    filters: list[ColumnElement[bool]] = []
    if concept:
        filters.append(
            Proposition.concept_id.in_(
                select(LegalConcept.id).where(LegalConcept.slug == concept.strip().lower())
            )
        )
    if jurisdiction:
        filters.append(
            or_(
                Proposition.jurisdiction_id.in_(
                    select(Jurisdiction.id).where(Jurisdiction.slug == jurisdiction.strip().lower())
                ),
                Proposition.jurisdiction_id.is_(None),
            )
        )
    if review_status is not None:
        filters.append(Proposition.review_status == review_status)
    if proposition_type is not None:
        filters.append(Proposition.proposition_type == proposition_type)

    total = session.scalar(select(func.count()).select_from(Proposition).where(*filters))
    rows = session.scalars(
        select(Proposition)
        .where(*filters)
        .options(selectinload(Proposition.concept), selectinload(Proposition.jurisdiction))
        .order_by(Proposition.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[PropositionOut](
        items=[_to_out(row) for row in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{proposition_id}",
    response_model=PropositionDetailOut,
    summary="Get one proposition",
)
def get_proposition(proposition_id: uuid.UUID, session: DbSession) -> PropositionDetailOut:
    """Get a proposition with the authorities that support it."""
    proposition = session.scalars(
        select(Proposition)
        .where(Proposition.id == proposition_id)
        .options(
            selectinload(Proposition.concept),
            selectinload(Proposition.jurisdiction),
            selectinload(Proposition.authority_links),
        )
    ).first()
    if proposition is None:
        raise NotFoundError(f"No proposition with id {proposition_id}")

    base = _to_out(proposition)
    detail = PropositionDetailOut(**base.model_dump())
    detail.authorities = [
        PropositionAuthorityOut(
            authority_id=link.authority_id,
            canonical_citation=link.authority.canonical_citation,
            relationship_type=link.relationship_type,
            weight=link.weight,
            pin_cite=link.pin_cite,
            quoted_text=link.quoted_text,
        )
        for link in sorted(proposition.authority_links, key=lambda link: -link.weight)
    ]
    return detail
