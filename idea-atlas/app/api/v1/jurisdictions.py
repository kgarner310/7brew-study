"""Jurisdiction endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import DbSession, Pagination
from app.core.config import MANIFEST_DIR
from app.core.enums import AuthorityType, JurisdictionType
from app.core.errors import NotFoundError
from app.legal.manifests import load_jurisdiction_manifest
from app.models import Authority, Jurisdiction, Proposition, Source
from app.schemas.common import Page
from app.schemas.entities import JurisdictionDetailOut, JurisdictionOut
from app.services.coverage import COVERAGE_CATEGORIES

router = APIRouter(prefix="/jurisdictions", tags=["jurisdictions"])


@router.get("", response_model=Page[JurisdictionOut], summary="List jurisdictions")
def list_jurisdictions(
    session: DbSession,
    page: Pagination,
    jurisdiction_type: JurisdictionType | None = Query(default=None),
    active: bool | None = Query(default=None),
    q: str | None = Query(default=None, max_length=128, description="Name/slug filter."),
) -> Page[JurisdictionOut]:
    """List IDEA jurisdictions, including states, territories, DC, and BIE."""
    limit, offset = page
    filters: list[ColumnElement[bool]] = []
    if jurisdiction_type is not None:
        filters.append(Jurisdiction.jurisdiction_type == jurisdiction_type)
    if active is not None:
        filters.append(Jurisdiction.active.is_(active))
    if q:
        pattern = f"%{q.lower()}%"
        filters.append(
            or_(
                func.lower(Jurisdiction.name).like(pattern),
                func.lower(Jurisdiction.slug).like(pattern),
            )
        )

    total = session.scalar(select(func.count()).select_from(Jurisdiction).where(*filters))
    rows = session.scalars(
        select(Jurisdiction)
        .where(*filters)
        .order_by(Jurisdiction.jurisdiction_type, Jurisdiction.name)
        .limit(limit)
        .offset(offset)
    ).all()

    return Page[JurisdictionOut](
        items=[JurisdictionOut.model_validate(row) for row in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{slug}", response_model=JurisdictionDetailOut, summary="Get one jurisdiction")
def get_jurisdiction(slug: str, session: DbSession) -> JurisdictionDetailOut:
    """Get a jurisdiction with its real coverage counts.

    Coverage is reported from the database. A category with no ingested data
    reports zero; it is never inferred from the manifest.
    """
    needle = slug.strip().lower()
    jurisdiction = session.scalars(
        select(Jurisdiction).where(
            or_(Jurisdiction.slug == needle, Jurisdiction.postal_code == needle.upper())
        )
    ).first()
    if jurisdiction is None:
        raise NotFoundError(f"No jurisdiction with slug or postal code {slug!r}")

    # .tuples() gives real typed tuples rather than Row objects, so this stays
    # both readable and type-checkable.
    type_counts: dict[AuthorityType, int] = dict(
        session.execute(
            select(Authority.authority_type, func.count(Authority.id))
            .where(Authority.jurisdiction_id == jurisdiction.id)
            .group_by(Authority.authority_type)
        )
        .tuples()
        .all()
    )
    coverage = {
        category: sum(type_counts.get(t, 0) for t in types)
        for category, types in COVERAGE_CATEGORIES.items()
    }

    detail = JurisdictionDetailOut.model_validate(jurisdiction)
    detail.coverage = coverage
    detail.authority_count = sum(type_counts.values())
    detail.proposition_count = (
        session.scalar(
            select(func.count())
            .select_from(Proposition)
            .where(Proposition.jurisdiction_id == jurisdiction.id)
        )
        or 0
    )
    detail.source_count = (
        session.scalar(
            select(func.count())
            .select_from(Source)
            .where(Source.jurisdiction_id == jurisdiction.id)
        )
        or 0
    )

    manifest_path = MANIFEST_DIR / "jurisdictions" / f"{jurisdiction.slug}.yaml"
    if manifest_path.is_file():
        manifest = load_jurisdiction_manifest(manifest_path)
        detail.manifest_declared_sites = manifest.declared_site_count
        detail.manifest_verified_sites = manifest.verified_site_count
        detail.crawl_status = manifest.crawl_status

    return detail
