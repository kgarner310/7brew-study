"""Bounded vocabularies for the legal data model.

Every enum here is persisted as a native PostgreSQL enum type so the database
itself rejects out-of-vocabulary values. Adding a member therefore requires an
Alembic migration -- that friction is deliberate: these vocabularies encode
legal meaning and must not drift silently.
"""

from __future__ import annotations

from enum import StrEnum


class JurisdictionType(StrEnum):
    """Kind of jurisdiction, not its IDEA obligations (see the part flags)."""

    FEDERAL = "federal"
    STATE = "state"
    DISTRICT = "district"
    """The District of Columbia."""
    TERRITORY = "territory"
    """Puerto Rico, Guam, USVI, American Samoa, CNMI."""
    OUTLYING_AREA = "outlying_area"
    """Freely Associated States and similar, where IDEA reaches them."""
    FEDERAL_AGENCY = "federal_agency"
    """E.g. the Department of the Interior / Bureau of Indian Education."""
    FEDERAL_CIRCUIT = "federal_circuit"
    """A U.S. Court of Appeals circuit, used for precedent scoping."""


class SourceType(StrEnum):
    """What a registered source publishes."""

    STATUTE = "statute"
    REGULATION = "regulation"
    GUIDANCE = "guidance"
    POLICY_LETTER = "policy_letter"
    COURT_OPINION = "court_opinion"
    DUE_PROCESS_DECISION = "due_process_decision"
    STATE_COMPLAINT_DECISION = "state_complaint_decision"
    PROCEDURAL_SAFEGUARDS = "procedural_safeguards"
    FORM = "form"
    DATASET = "dataset"
    OTHER = "other"


class RetrievalMethod(StrEnum):
    """How a collector obtains documents from a source."""

    HTTP_HTML = "http_html"
    HTTP_PDF = "http_pdf"
    HTTP_JSON = "http_json"
    API = "api"
    BULK_DOWNLOAD = "bulk_download"
    MANUAL = "manual"
    """Human-mediated retrieval; used where terms of service require it."""


class CopyrightStatus(StrEnum):
    """Copyright posture of the retrieved text itself.

    Note the distinction between federal works (no copyright under 17 U.S.C.
    Sec. 105) and state edicts (uncopyrightable under the government edicts
    doctrine, ``Georgia v. Public.Resource.Org``, 590 U.S. 255 (2020)).
    """

    US_GOVERNMENT_PUBLIC_DOMAIN = "us_government_public_domain"
    GOVERNMENT_EDICT = "government_edict"
    PUBLIC_DOMAIN_OTHER = "public_domain_other"
    PROPRIETARY = "proprietary"
    MIXED = "mixed"
    """Primary text is free but the container carries proprietary annotations."""
    UNKNOWN = "unknown"


class CommercialReuseStatus(StrEnum):
    """Whether we may redistribute the text commercially."""

    PERMITTED = "permitted"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"
    REQUIRES_LEGAL_REVIEW = "requires_legal_review"
    UNKNOWN = "unknown"


class CrawlFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"


class AuthorityType(StrEnum):
    """The kind of legal authority a document represents.

    Ordering is not significance; use :class:`PrecedentialStatus` and the
    jurisdiction to reason about weight.
    """

    FEDERAL_STATUTE = "federal_statute"
    FEDERAL_REGULATION = "federal_regulation"
    FEDERAL_GUIDANCE = "federal_guidance"
    OSEP_POLICY_LETTER = "osep_policy_letter"
    OSEP_MEMORANDUM = "osep_memorandum"
    DEAR_COLLEAGUE_LETTER = "dear_colleague_letter"
    OCR_GUIDANCE = "ocr_guidance"
    SUPREME_COURT_OPINION = "supreme_court_opinion"
    CIRCUIT_COURT_OPINION = "circuit_court_opinion"
    DISTRICT_COURT_OPINION = "district_court_opinion"
    STATE_STATUTE = "state_statute"
    STATE_REGULATION = "state_regulation"
    STATE_GUIDANCE = "state_guidance"
    STATE_COURT_OPINION = "state_court_opinion"
    PROCEDURAL_SAFEGUARDS_NOTICE = "procedural_safeguards_notice"
    DUE_PROCESS_DECISION = "due_process_decision"
    STATE_COMPLAINT_DECISION = "state_complaint_decision"
    OTHER = "other"


class AuthorityCurrentStatus(StrEnum):
    """Whether the authority is still operative."""

    IN_FORCE = "in_force"
    AMENDED = "amended"
    REPEALED = "repealed"
    SUPERSEDED = "superseded"
    PROPOSED = "proposed"
    WITHDRAWN = "withdrawn"
    """Used heavily for rescinded federal guidance."""
    UNKNOWN = "unknown"


class PrecedentialStatus(StrEnum):
    BINDING = "binding"
    PERSUASIVE = "persuasive"
    NON_PRECEDENTIAL = "non_precedential"
    UNPUBLISHED = "unpublished"
    NOT_APPLICABLE = "not_applicable"
    """Statutes and regulations: precedential status is not a meaningful axis."""
    UNKNOWN = "unknown"


class IdeaPart(StrEnum):
    """Which part of the IDEA a concept or provision belongs to."""

    PART_A = "part_a"
    """General provisions and definitions."""
    PART_B = "part_b"
    """Assistance for education of all children with disabilities (ages 3-21)."""
    PART_C = "part_c"
    """Infants and toddlers with disabilities (birth through age 2)."""
    PART_D = "part_d"
    """National activities to improve education of children with disabilities."""
    CROSS_CUTTING = "cross_cutting"
    """Applies across parts, or to IDEA-adjacent law such as Section 504."""


class PropositionType(StrEnum):
    """The logical shape of a legal proposition."""

    REQUIREMENT = "requirement"
    PROHIBITION = "prohibition"
    DEFINITION = "definition"
    EXCEPTION = "exception"
    DEADLINE = "deadline"
    PROCEDURE = "procedure"
    STANDARD = "standard"
    """A legal test, e.g. the ``Endrew F.`` FAPE standard."""
    FACTOR_TEST = "factor_test"
    ALLOCATION = "allocation"
    """Who bears a burden, cost, or duty."""


class PropositionAuthorityStatus(StrEnum):
    """How strong the legal backing for a proposition is."""

    BINDING_AUTHORITY = "binding_authority"
    PERSUASIVE_AUTHORITY = "persuasive_authority"
    AGENCY_INTERPRETATION = "agency_interpretation"
    """Non-binding but entitled to respect; e.g. OSEP policy letters."""
    CONTESTED = "contested"
    """Circuits split, or state law conflicts with federal guidance."""
    UNSUPPORTED = "unsupported"
    """No linked authority yet. Never serve these as answers."""


class ReviewStatus(StrEnum):
    """Provenance of a record's *content*, in ascending order of assurance.

    These are never collapsed. ``ai_extracted`` must never be presented to a
    user as though it were ``human_reviewed``.
    """

    NEEDS_REVIEW = "needs_review"
    AI_EXTRACTED = "ai_extracted"
    """Produced by a language model. Not authoritative on its own."""
    SOURCE_VERIFIED = "source_verified"
    """Text provably matches the retrieved official source (hash-checked)."""
    CROSS_VALIDATED = "cross_validated"
    """Corroborated by an independent source or a second extraction method."""
    HUMAN_REVIEWED = "human_reviewed"
    EXPERT_REVIEWED = "expert_reviewed"
    """Reviewed by a qualified special-education legal professional."""
    REJECTED = "rejected"


#: Review statuses that may back a substantive answer served to a user.
#: ``ai_extracted`` is deliberately absent -- see docs/LEGAL_DATA_POLICY.md.
SERVABLE_REVIEW_STATUSES: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.SOURCE_VERIFIED,
        ReviewStatus.CROSS_VALIDATED,
        ReviewStatus.HUMAN_REVIEWED,
        ReviewStatus.EXPERT_REVIEWED,
    }
)

#: Ranking used when we must report the weakest link in a set of records.
REVIEW_STATUS_RANK: dict[ReviewStatus, int] = {
    ReviewStatus.REJECTED: -1,
    ReviewStatus.NEEDS_REVIEW: 0,
    ReviewStatus.AI_EXTRACTED: 1,
    ReviewStatus.SOURCE_VERIFIED: 2,
    ReviewStatus.CROSS_VALIDATED: 3,
    ReviewStatus.HUMAN_REVIEWED: 4,
    ReviewStatus.EXPERT_REVIEWED: 5,
}


class PropositionAuthorityRelation(StrEnum):
    """How an authority relates to a proposition."""

    PRIMARY_SUPPORT = "primary_support"
    SUPPORTS = "supports"
    INTERPRETS = "interprets"
    LIMITS = "limits"
    CONTRADICTS = "contradicts"
    BACKGROUND = "background"


class AuthorityRelationType(StrEnum):
    """How one authority relates to another (citator-style graph edges)."""

    CITES = "cites"
    INTERPRETS = "interprets"
    SUPERSEDES = "supersedes"
    OVERRULES = "overrules"
    DISTINGUISHES = "distinguishes"
    APPLIES = "applies"
    IMPLEMENTS = "implements"
    ABROGATES = "abrogates"


class IngestionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    """Finished, but at least one document failed."""
    FAILED = "failed"
    SKIPPED = "skipped"


class CrawlStatus(StrEnum):
    """Operational state of a source in the registry / manifest."""

    NOT_STARTED = "not_started"
    URLS_UNVERIFIED = "urls_unverified"
    """Manifest exists but the URLs have not been confirmed by a human."""
    URLS_VERIFIED = "urls_verified"
    ACTIVE = "active"
    BLOCKED = "blocked"
    """Robots.txt, terms of service, or access controls prevent ingestion."""
    ERROR = "error"


class DetailLevel(StrEnum):
    """Response verbosity for machine consumers. See docs/TOKEN_EFFICIENCY.md."""

    COMPACT = "compact"
    STANDARD = "standard"
    RESEARCH = "research"


class EntityType(StrEnum):
    """Entities that can carry a review trail."""

    AUTHORITY = "authority"
    AUTHORITY_VERSION = "authority_version"
    PROPOSITION = "proposition"
    PROPOSITION_AUTHORITY = "proposition_authority"
    AUTHORITY_RELATIONSHIP = "authority_relationship"
    SOURCE = "source"
    LEGAL_CONCEPT = "legal_concept"
