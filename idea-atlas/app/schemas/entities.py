"""Read models for the core legal entities."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    AuthorityCurrentStatus,
    AuthorityType,
    CrawlStatus,
    IdeaPart,
    JurisdictionType,
    PrecedentialStatus,
    PropositionAuthorityRelation,
    PropositionAuthorityStatus,
    PropositionType,
    ReviewStatus,
    SourceType,
)


class JurisdictionOut(BaseModel):
    """A jurisdiction."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    jurisdiction_type: JurisdictionType
    postal_code: str | None
    federal_circuit: str | None
    sea_name: str | None
    idea_part_b_applicable: bool
    idea_part_c_applicable: bool
    active: bool


class JurisdictionDetailOut(JurisdictionOut):
    """A jurisdiction plus its coverage summary."""

    authority_count: int = 0
    proposition_count: int = 0
    source_count: int = 0
    coverage: dict[str, int] = Field(default_factory=dict)
    manifest_verified_sites: int = 0
    manifest_declared_sites: int = 0
    crawl_status: CrawlStatus = CrawlStatus.NOT_STARTED


class ConceptOut(BaseModel):
    """A taxonomy concept."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str
    idea_part: IdeaPart
    parent_id: uuid.UUID | None
    aliases: list[str]


class ConceptDetailOut(ConceptOut):
    """A concept with its immediate children and proposition count."""

    parent_slug: str | None = None
    children: list[ConceptOut] = Field(default_factory=list)
    proposition_count: int = 0


class SourceOut(BaseModel):
    """A registered source."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    publisher: str
    source_type: SourceType
    base_url: str
    official_source: bool
    copyright_status: str
    commercial_reuse_status: str
    crawl_status: CrawlStatus
    last_checked_at: datetime | None


class AuthorityVersionOut(BaseModel):
    """A stored version of an authority. Text is omitted unless requested."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retrieved_at: datetime
    effective_from: date | None
    effective_to: date | None
    sha256: str
    raw_sha256: str
    byte_size: int
    parser_name: str
    parser_version: str
    is_current: bool
    review_status: ReviewStatus
    source_snapshot_url: str | None


class AuthorityOut(BaseModel):
    """An authority."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    jurisdiction_id: uuid.UUID
    source_id: uuid.UUID
    authority_type: AuthorityType
    canonical_citation: str
    title: str
    short_title: str | None
    docket_or_identifier: str | None
    court_or_agency: str | None
    idea_part: IdeaPart | None
    publication_date: date | None
    effective_date: date | None
    superseded_date: date | None
    current_status: AuthorityCurrentStatus
    precedential_status: PrecedentialStatus
    review_status: ReviewStatus
    source_url: str
    official_url: str | None


class AuthorityDetailOut(AuthorityOut):
    """An authority with its jurisdiction, versions, and optionally its text."""

    jurisdiction_slug: str
    source_slug: str
    versions: list[AuthorityVersionOut] = Field(default_factory=list)
    current_text: str | None = Field(
        default=None,
        description="Normalized text of the current version; only when include_text=true.",
    )


class PropositionAuthorityOut(BaseModel):
    """A proposition-to-authority link."""

    model_config = ConfigDict(from_attributes=True)

    authority_id: uuid.UUID
    canonical_citation: str
    relationship_type: PropositionAuthorityRelation
    weight: int
    pin_cite: str | None
    quoted_text: str | None


class PropositionOut(BaseModel):
    """A legal proposition."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    concept_id: uuid.UUID
    concept_slug: str
    jurisdiction_id: uuid.UUID | None
    jurisdiction_slug: str | None
    statement: str
    qualifier: str | None
    proposition_type: PropositionType
    effective_from: date | None
    effective_to: date | None
    confidence: float
    authority_status: PropositionAuthorityStatus
    review_status: ReviewStatus
    created_by: str
    reviewed_by: str | None
    reviewed_at: datetime | None


class PropositionDetailOut(PropositionOut):
    """A proposition with its supporting authorities."""

    authorities: list[PropositionAuthorityOut] = Field(default_factory=list)


class SearchHit(BaseModel):
    """One search result across entity types."""

    entity_type: str
    id: uuid.UUID
    slug: str | None = None
    title: str
    snippet: str | None = None
    jurisdiction_slug: str | None = None
    review_status: ReviewStatus | None = None
    score: float = 0.0
