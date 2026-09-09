"""Legal-concept taxonomy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DbSession, Pagination
from app.core.enums import IdeaPart
from app.core.errors import NotFoundError
from app.models import LegalConcept, Proposition
from app.schemas.common import Page
from app.schemas.entities import ConceptDetailOut, ConceptOut

router = APIRouter(prefix="/concepts", tags=["concepts"])


@router.get("", response_model=Page[ConceptOut], summary="List concepts")
def list_concepts(
    session: DbSession,
    page: Pagination,
    idea_part: IdeaPart | None = Query(default=None),
    root_only: bool = Query(default=False, description="Only top-level concepts."),
) -> Page[ConceptOut]:
    """List the IDEA subject-matter taxonomy."""
    limit, offset = page
    filters = []
    if idea_part is not None:
        filters.append(LegalConcept.idea_part == idea_part)
    if root_only:
        filters.append(LegalConcept.parent_id.is_(None))

    total = session.scalar(select(func.count()).select_from(LegalConcept).where(*filters))
    rows = session.scalars(
        select(LegalConcept).where(*filters).order_by(LegalConcept.name).limit(limit).offset(offset)
    ).all()
    return Page[ConceptOut](
        items=[ConceptOut.model_validate(row) for row in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{slug}", response_model=ConceptDetailOut, summary="Get one concept")
def get_concept(slug: str, session: DbSession) -> ConceptDetailOut:
    """Get a concept with its children and proposition count."""
    concept = session.scalars(
        select(LegalConcept).where(LegalConcept.slug == slug.strip().lower())
    ).first()
    if concept is None:
        raise NotFoundError(f"No concept with slug {slug!r}")

    detail = ConceptDetailOut.model_validate(concept)
    detail.parent_slug = concept.parent.slug if concept.parent else None
    detail.children = [ConceptOut.model_validate(child) for child in concept.children]
    detail.proposition_count = (
        session.scalar(
            select(func.count())
            .select_from(Proposition)
            .where(Proposition.concept_id == concept.id)
        )
        or 0
    )
    return detail
