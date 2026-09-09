"""Idempotent database seeding.

Seeds three layers, each independently re-runnable:

1. **Reference data** -- jurisdictions and the concept taxonomy. Structural,
   uncontroversial, and safe to seed anywhere.
2. **Source registry** -- sources from the federal manifest. Registered with
   ``crawl_status=urls_unverified`` because their URLs have not been confirmed.
3. **Demo propositions** -- a handful of legal propositions so the research
   endpoint has something to retrieve.

Layer 3 is deliberately marked ``review_status=needs_review`` and
``created_by='seed:model_knowledge'``. These statements were written from model
knowledge, not extracted from ingested primary text. They are NOT verified law,
and the research endpoint will refuse to serve them unless the caller explicitly
asks for unreviewed material. Promoting them requires a real human review event.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    CrawlStatus,
    EntityType,
    PropositionAuthorityRelation,
    PropositionAuthorityStatus,
    PropositionType,
    ReviewStatus,
)
from app.core.logging import get_logger
from app.legal.jurisdictions import ALL_JURISDICTIONS
from app.legal.manifests import load_federal_manifest
from app.legal.taxonomy import IDEA_CONCEPTS
from app.models import (
    Authority,
    Jurisdiction,
    LegalConcept,
    Proposition,
    PropositionAuthority,
    ReviewEvent,
    Source,
)

logger = get_logger(__name__)

SEED_ACTOR = "seed:model_knowledge"


@dataclass(slots=True)
class SeedCounts:
    """What a seed run created."""

    jurisdictions: int = 0
    concepts: int = 0
    sources: int = 0
    propositions: int = 0
    proposition_links: int = 0

    def __str__(self) -> str:
        return (
            f"jurisdictions={self.jurisdictions} concepts={self.concepts} "
            f"sources={self.sources} propositions={self.propositions} "
            f"links={self.proposition_links}"
        )


def seed_jurisdictions(session: Session) -> int:
    """Insert every jurisdiction that is not already present."""
    existing = set(session.scalars(select(Jurisdiction.slug)))
    created = 0

    # Two passes: parents must exist before children reference them.
    for seed in ALL_JURISDICTIONS:
        if seed.slug in existing:
            continue
        session.add(
            Jurisdiction(
                slug=seed.slug,
                name=seed.name,
                jurisdiction_type=seed.jurisdiction_type,
                postal_code=seed.postal_code,
                federal_circuit=seed.federal_circuit,
                sea_name=seed.sea_name,
                idea_part_b_applicable=seed.idea_part_b_applicable,
                idea_part_c_applicable=seed.idea_part_c_applicable,
                active=True,
                meta={
                    "verification_required": seed.verification_required,
                    **({"notes": seed.notes} if seed.notes else {}),
                },
            )
        )
        created += 1
    session.flush()

    by_slug = {j.slug: j for j in session.scalars(select(Jurisdiction))}
    for seed in ALL_JURISDICTIONS:
        if seed.parent_slug and seed.slug in by_slug:
            child = by_slug[seed.slug]
            parent = by_slug.get(seed.parent_slug)
            if parent is not None and child.parent_jurisdiction_id is None:
                child.parent_jurisdiction_id = parent.id
    session.flush()
    return created


def seed_concepts(session: Session) -> int:
    """Insert the IDEA taxonomy, wiring parents after all nodes exist."""
    existing = set(session.scalars(select(LegalConcept.slug)))
    created = 0

    for seed in IDEA_CONCEPTS:
        if seed.slug in existing:
            continue
        session.add(
            LegalConcept(
                slug=seed.slug,
                name=seed.name,
                description=seed.description,
                idea_part=seed.idea_part,
                aliases=list(seed.aliases),
            )
        )
        created += 1
    session.flush()

    by_slug = {c.slug: c for c in session.scalars(select(LegalConcept))}
    for seed in IDEA_CONCEPTS:
        if seed.parent_slug and seed.slug in by_slug:
            child = by_slug[seed.slug]
            parent = by_slug.get(seed.parent_slug)
            if parent is not None and child.parent_id is None:
                child.parent_id = parent.id
    session.flush()
    return created


def seed_sources(session: Session) -> int:
    """Register federal sources from the manifest."""
    federal = session.scalars(select(Jurisdiction).where(Jurisdiction.slug == "us")).one()
    existing = set(session.scalars(select(Source.slug)))
    manifest = load_federal_manifest()
    created = 0

    for entry in manifest.sources:
        if entry.slug in existing:
            continue
        session.add(
            Source(
                jurisdiction_id=federal.id,
                slug=entry.slug,
                name=entry.name,
                publisher=entry.publisher,
                source_type=entry.source_type,
                base_url=entry.base_url,
                retrieval_method=entry.retrieval_method,
                official_source=entry.official_source,
                copyright_status=entry.copyright_status,
                license_notes=entry.license_notes,
                commercial_reuse_status=entry.commercial_reuse_status,
                terms_of_service_url=entry.terms_of_service_url,
                crawl_frequency=entry.crawl_frequency,
                # Never inherit "verified" from a manifest that says otherwise.
                crawl_status=(
                    entry.crawl_status if entry.url_verified else CrawlStatus.URLS_UNVERIFIED
                ),
                active=True,
                meta={
                    "url_verified": entry.url_verified,
                    "manifest_notes": entry.notes or "",
                    **entry.meta,
                },
            )
        )
        created += 1
    session.flush()
    return created


# (concept_slug, statement, qualifier, type, citation, pin_cite)
_DEMO_PROPOSITIONS: tuple[tuple[str, str, str | None, PropositionType, str, str | None], ...] = (
    (
        "initial-evaluation",
        "A public agency must obtain informed parental consent before conducting "
        "an initial evaluation to determine whether a child is a child with a "
        "disability",
        "Consent for evaluation is not consent for the initial provision of "
        "special education and related services, which requires separate consent",
        PropositionType.REQUIREMENT,
        "34 C.F.R. 300.301",
        "300.300(a)",
    ),
    (
        "initial-evaluation",
        "A multi-tiered system of supports or response-to-intervention process "
        "may not be used to delay or deny an initial evaluation of a child "
        "suspected of having a disability",
        "This is the position stated in U.S. Department of Education guidance; "
        "confirm the current controlling guidance document and any state-law "
        "overlay before relying on it",
        PropositionType.PROHIBITION,
        "34 C.F.R. 300.301",
        None,
    ),
    (
        "eligibility",
        "A child is eligible under Part B only if the child has a qualifying "
        "disability and, by reason of that disability, needs special education "
        "and related services",
        "Both prongs must be satisfied; a diagnosis alone does not establish eligibility",
        PropositionType.STANDARD,
        "34 C.F.R. 300.8",
        "300.8(a)(1)",
    ),
    (
        "part-c-to-part-b-transition",
        "Part C sets a post-referral timeline within which the initial "
        "evaluation, assessment, and initial IFSP meeting must be completed",
        "Exceptional family circumstances may extend the timeline; the specific "
        "number of days must be confirmed against the current regulation",
        PropositionType.DEADLINE,
        "34 C.F.R. 303.310",
        None,
    ),
)


def seed_demo_propositions(session: Session) -> tuple[int, int]:
    """Create demo propositions linked to ingested authorities.

    Skips silently when the referenced authority has not been ingested: the
    seed must never invent an authority to hang a proposition on.
    """
    concepts = {c.slug: c for c in session.scalars(select(LegalConcept))}
    authorities = {a.canonical_citation: a for a in session.scalars(select(Authority))}
    existing_statements = set(session.scalars(select(Proposition.statement)))

    created = links = 0
    for concept_slug, statement, qualifier, prop_type, citation, pin in _DEMO_PROPOSITIONS:
        if statement in existing_statements:
            continue
        concept = concepts.get(concept_slug)
        authority = authorities.get(citation)
        if concept is None or authority is None:
            logger.info(
                "seed.proposition_skipped",
                concept=concept_slug,
                citation=citation,
                reason="concept or authority not present; ingest first",
            )
            continue

        proposition = Proposition(
            concept_id=concept.id,
            jurisdiction_id=None,  # federal floor: applies everywhere
            statement=statement,
            qualifier=qualifier,
            proposition_type=prop_type,
            confidence=0.25,
            authority_status=PropositionAuthorityStatus.BINDING_AUTHORITY,
            review_status=ReviewStatus.NEEDS_REVIEW,
            created_by=SEED_ACTOR,
            meta={
                "provenance": "written from model knowledge during initial seeding",
                "verification_required": True,
                "warning": "NOT verified against primary source text",
            },
        )
        session.add(proposition)
        session.flush()

        session.add(
            PropositionAuthority(
                proposition_id=proposition.id,
                authority_id=authority.id,
                relationship_type=PropositionAuthorityRelation.PRIMARY_SUPPORT,
                weight=100,
                pin_cite=pin,
                notes="Seed link. Pin cite unverified against official text.",
            )
        )
        session.add(
            ReviewEvent(
                entity_type=EntityType.PROPOSITION,
                entity_id=proposition.id,
                previous_status=None,
                review_status=ReviewStatus.NEEDS_REVIEW,
                reviewer=SEED_ACTOR,
                notes=(
                    "Created by seeding from model knowledge. Requires review "
                    "against ingested primary source text before it can be served."
                ),
            )
        )
        created += 1
        links += 1

    session.flush()
    return created, links


def seed_reference_data(session: Session) -> SeedCounts:
    """Seed jurisdictions, concepts, and the federal source registry."""
    counts = SeedCounts()
    counts.jurisdictions = seed_jurisdictions(session)
    counts.concepts = seed_concepts(session)
    counts.sources = seed_sources(session)
    logger.info("seed.reference_complete", counts=str(counts))
    return counts
