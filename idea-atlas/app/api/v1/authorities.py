"""Authority endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import DbSession, Pagination
from app.core.enums import AuthorityType, IdeaPart
from app.core.errors import NotFoundError
from app.models import Authority, AuthorityVersion, Jurisdiction
from app.schemas.common import Page
from app.schemas.entities import AuthorityDetailOut, AuthorityOut, AuthorityVersionOut

router = APIRouter(prefix="/authorities", tags=["authorities"])


@router.get("", response_model=Page[AuthorityOut], summary="List authorities")
def list_authorities(
    session: DbSession,
    page: Pagination,
    jurisdiction: str | None = Query(default=None, description="Jurisdiction slug."),
    authority_type: AuthorityType | None = Query(default=None),
    idea_part: IdeaPart | None = Query(default=None),
    citation: str | None = Query(default=None, max_length=512),
) -> Page[AuthorityOut]:
    """List authorities, filtered by jurisdiction, type, IDEA part, or citation."""
    limit, offset = page
    filters: list[ColumnElement[bool]] = []
    if jurisdiction:
        filters.append(
            Authority.jurisdiction_id.in_(
                select(Jurisdiction.id).where(Jurisdiction.slug == jurisdiction.strip().lower())
            )
        )
    if authority_type is not None:
        filters.append(Authority.authority_type == authority_type)
    if idea_part is not None:
        filters.append(Authority.idea_part == idea_part)
    if citation:
        filters.append(func.lower(Authority.canonical_citation).like(f"%{citation.lower()}%"))

    total = session.scalar(select(func.count()).select_from(Authority).where(*filters))
    rows = session.scalars(
        select(Authority)
        .where(*filters)
        .order_by(Authority.canonical_citation)
        .limit(limit)
        .offset(offset)
    ).all()
    return Page[AuthorityOut](
        items=[AuthorityOut.model_validate(row) for row in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{authority_id}", response_model=AuthorityDetailOut, summary="Get one authority")
def get_authority(
    authority_id: uuid.UUID,
    session: DbSession,
    include_text: bool = Query(
        default=False,
        description="Include the normalized text of the current version. "
        "Off by default: full statutory text is large and rarely needed.",
    ),
) -> AuthorityDetailOut:
    """Get an authority with its version history."""
    authority = session.scalars(
        select(Authority)
        .where(Authority.id == authority_id)
        .options(
            selectinload(Authority.versions),
            selectinload(Authority.jurisdiction),
            selectinload(Authority.source),
        )
    ).first()
    if authority is None:
        raise NotFoundError(f"No authority with id {authority_id}")

    detail = AuthorityDetailOut.model_validate(authority)
    detail.jurisdiction_slug = authority.jurisdiction.slug
    detail.source_slug = authority.source.slug
    detail.versions = [
        AuthorityVersionOut.model_validate(version) for version in authority.versions
    ]

    if include_text:
        current = session.scalars(
            select(AuthorityVersion).where(
                AuthorityVersion.authority_id == authority.id,
                AuthorityVersion.is_current.is_(True),
            )
        ).first()
        detail.current_text = current.normalized_text if current else None

    return detail
