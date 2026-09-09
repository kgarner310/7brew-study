"""Cross-entity keyword search.

Implemented with SQL ``ILIKE`` over indexed text columns rather than full-text
search or embeddings. That is a deliberate first step: it is exact, explainable,
requires no extra infrastructure, and the initial corpus is small. Postgres
full-text (and optionally pgvector) is a Phase 3 upgrade -- see docs/ROADMAP.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.models import Authority, LegalConcept, Proposition
from app.schemas.entities import SearchHit

router = APIRouter(tags=["search"])

SNIPPET_CHARS = 240


def _snippet(text: str, needle: str) -> str:
    """A window of ``text`` around the first case-insensitive hit."""
    lowered = text.lower()
    index = lowered.find(needle.lower())
    if index < 0:
        return text[:SNIPPET_CHARS]
    start = max(0, index - SNIPPET_CHARS // 3)
    end = min(len(text), start + SNIPPET_CHARS)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


@router.get("/search", response_model=list[SearchHit], summary="Keyword search")
def search(
    session: DbSession,
    q: str = Query(min_length=2, max_length=256, description="Search terms."),
    limit: int = Query(default=25, ge=1, le=100),
) -> list[SearchHit]:
    """Search concepts, authorities, and propositions by keyword.

    Results are ordered concepts first (the taxonomy is the map), then
    propositions, then authorities.
    """
    pattern = f"%{q.lower()}%"
    hits: list[SearchHit] = []

    concepts = session.scalars(
        select(LegalConcept)
        .where(
            or_(
                func.lower(LegalConcept.name).like(pattern),
                func.lower(LegalConcept.description).like(pattern),
                func.lower(LegalConcept.slug).like(pattern),
            )
        )
        .order_by(LegalConcept.name)
        .limit(limit)
    ).all()
    hits.extend(
        SearchHit(
            entity_type="concept",
            id=concept.id,
            slug=concept.slug,
            title=concept.name,
            snippet=_snippet(concept.description, q) if concept.description else None,
            score=3.0,
        )
        for concept in concepts
    )

    remaining = max(0, limit - len(hits))
    if remaining:
        propositions = session.scalars(
            select(Proposition)
            .where(func.lower(Proposition.statement).like(pattern))
            .options(
                selectinload(Proposition.jurisdiction),
                selectinload(Proposition.concept),
            )
            .order_by(Proposition.confidence.desc())
            .limit(remaining)
        ).all()
        hits.extend(
            SearchHit(
                entity_type="proposition",
                id=proposition.id,
                slug=proposition.concept.slug,
                title=proposition.statement[:120],
                snippet=_snippet(proposition.statement, q),
                jurisdiction_slug=(
                    proposition.jurisdiction.slug if proposition.jurisdiction else None
                ),
                review_status=proposition.review_status,
                score=2.0,
            )
            for proposition in propositions
        )

    remaining = max(0, limit - len(hits))
    if remaining:
        authorities = session.scalars(
            select(Authority)
            .where(
                or_(
                    func.lower(Authority.title).like(pattern),
                    func.lower(Authority.canonical_citation).like(pattern),
                )
            )
            .options(selectinload(Authority.jurisdiction))
            .order_by(Authority.canonical_citation)
            .limit(remaining)
        ).all()
        hits.extend(
            SearchHit(
                entity_type="authority",
                id=authority.id,
                slug=None,
                title=f"{authority.canonical_citation} - {authority.title}",
                snippet=None,
                jurisdiction_slug=authority.jurisdiction.slug,
                review_status=authority.review_status,
                score=1.0,
            )
            for authority in authorities
        )

    return hits[:limit]
