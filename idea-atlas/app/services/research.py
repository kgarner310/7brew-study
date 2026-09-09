"""Deterministic legal research assembly.

This service answers a research request from database content only. There is no
model in this path, by design:

* An answer is assembled from stored propositions and their linked authorities.
* If the knowledge base holds nothing servable, the service says so explicitly
  rather than producing prose. ``insufficient_coverage`` is a success case.
* The reported ``review_status`` is the *weakest* status among the records used.
  Statuses are never collapsed upward.
* ``confidence`` is capped by review status: unreviewed material can never be
  presented as high-confidence.

Legal-information posture: output describes what sources say. It is not legal
advice and every response carries a disclaimer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.enums import (
    REVIEW_STATUS_RANK,
    SERVABLE_REVIEW_STATUSES,
    DetailLevel,
    ReviewStatus,
)
from app.models import Jurisdiction, Proposition
from app.services.matching import ConceptMatch, match_concepts
from app.services.tokens import estimate_payload_tokens, truncate_to_budget

DISCLAIMER = (
    "IDEA Atlas provides legal information assembled from primary sources. "
    "It is not legal advice, does not create an attorney-client relationship, "
    "and must not be relied on as a substitute for a licensed attorney or "
    "advocate familiar with the specific facts."
)

#: Confidence ceilings by review status. A record can never be reported as more
#: confident than its provenance warrants.
CONFIDENCE_CEILING: dict[ReviewStatus, float] = {
    ReviewStatus.REJECTED: 0.0,
    ReviewStatus.NEEDS_REVIEW: 0.25,
    ReviewStatus.AI_EXTRACTED: 0.35,
    ReviewStatus.SOURCE_VERIFIED: 0.70,
    ReviewStatus.CROSS_VALIDATED: 0.85,
    ReviewStatus.HUMAN_REVIEWED: 0.95,
    ReviewStatus.EXPERT_REVIEWED: 0.99,
}

#: How many propositions each detail level will assemble.
DETAIL_PROPOSITION_LIMIT: dict[DetailLevel, int] = {
    DetailLevel.COMPACT: 3,
    DetailLevel.STANDARD: 8,
    DetailLevel.RESEARCH: 25,
}


@dataclass(slots=True)
class AuthorityRef:
    """An authority as it appears in a research response."""

    id: str
    canonical_citation: str
    title: str
    authority_type: str
    jurisdiction_slug: str
    current_status: str
    precedential_status: str
    source_url: str
    pin_cite: str | None = None
    relationship: str | None = None
    quoted_text: str | None = None
    effective_date: date | None = None


@dataclass(slots=True)
class PropositionRef:
    """A proposition as it appears in a research response."""

    id: str
    statement: str
    proposition_type: str
    concept_slug: str
    jurisdiction_slug: str | None
    qualifier: str | None
    review_status: str
    authority_status: str
    confidence: float
    effective_from: date | None
    effective_to: date | None
    authorities: list[AuthorityRef] = field(default_factory=list)


@dataclass(slots=True)
class ResearchResult:
    """The full outcome of a research request."""

    answer: str
    issue: str
    jurisdiction: dict[str, object] | None
    concepts: list[dict[str, object]]
    propositions: list[PropositionRef]
    authorities: list[AuthorityRef]
    review_status: str
    confidence: float
    as_of: datetime
    detail: DetailLevel
    sufficient_coverage: bool
    estimated_response_tokens: int = 0
    warnings: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    """Normalized inputs to :func:`run_research`."""

    issue: str
    jurisdiction: str | None = None
    detail: DetailLevel = DetailLevel.COMPACT
    token_budget: int = 1000
    include_unreviewed: bool = False
    as_of: date | None = None


def _resolve_jurisdiction(session: Session, slug: str | None) -> Jurisdiction | None:
    if not slug:
        return None
    needle = slug.strip().lower()
    stmt = select(Jurisdiction).where(
        or_(Jurisdiction.slug == needle, Jurisdiction.postal_code == needle.upper())
    )
    return session.scalars(stmt).first()


def _jurisdiction_payload(jurisdiction: Jurisdiction | None) -> dict[str, object] | None:
    if jurisdiction is None:
        return None
    return {
        "slug": jurisdiction.slug,
        "name": jurisdiction.name,
        "type": jurisdiction.jurisdiction_type.value,
        "postal_code": jurisdiction.postal_code,
        "federal_circuit": jurisdiction.federal_circuit,
        "sea": jurisdiction.sea_name,
    }


def _load_propositions(
    session: Session,
    matches: list[ConceptMatch],
    jurisdiction: Jurisdiction | None,
    as_of: date,
) -> list[Proposition]:
    """Fetch propositions for the matched concepts, scoped to the jurisdiction.

    Universal propositions (``jurisdiction_id IS NULL``) always apply -- they
    are the federal floor. Jurisdiction-specific ones are added on top.
    """
    concept_ids = [m.concept.id for m in matches]
    if not concept_ids:
        return []

    scope: list[ColumnElement[bool]] = [Proposition.jurisdiction_id.is_(None)]
    if jurisdiction is not None:
        scope.append(Proposition.jurisdiction_id == jurisdiction.id)

    stmt = (
        select(Proposition)
        .where(
            Proposition.concept_id.in_(concept_ids),
            or_(*scope),
            or_(Proposition.effective_from.is_(None), Proposition.effective_from <= as_of),
            or_(Proposition.effective_to.is_(None), Proposition.effective_to >= as_of),
            Proposition.review_status != ReviewStatus.REJECTED,
        )
        .options(
            selectinload(Proposition.concept),
            selectinload(Proposition.jurisdiction),
            selectinload(Proposition.authority_links),
        )
    )
    propositions = list(session.scalars(stmt).unique().all())

    # Jurisdiction-specific propositions lead; then strongest provenance.
    order = {m.concept.id: i for i, m in enumerate(matches)}
    propositions.sort(
        key=lambda p: (
            order.get(p.concept_id, 99),
            0 if p.jurisdiction_id is not None else 1,
            -REVIEW_STATUS_RANK[p.review_status],
            -p.confidence,
        )
    )
    return propositions


def _to_refs(session: Session, proposition: Proposition, detail: DetailLevel) -> PropositionRef:
    authorities: list[AuthorityRef] = []
    links = sorted(proposition.authority_links, key=lambda link: -link.weight)
    for link in links:
        authority = link.authority
        authorities.append(
            AuthorityRef(
                id=str(authority.id),
                canonical_citation=authority.canonical_citation,
                title=authority.title,
                authority_type=authority.authority_type.value,
                jurisdiction_slug=authority.jurisdiction.slug,
                current_status=authority.current_status.value,
                precedential_status=authority.precedential_status.value,
                source_url=authority.source_url,
                pin_cite=link.pin_cite,
                relationship=link.relationship_type.value,
                quoted_text=link.quoted_text if detail is DetailLevel.RESEARCH else None,
                effective_date=(
                    authority.effective_date if detail is not DetailLevel.COMPACT else None
                ),
            )
        )

    return PropositionRef(
        id=str(proposition.id),
        statement=proposition.statement,
        proposition_type=proposition.proposition_type.value,
        concept_slug=proposition.concept.slug,
        jurisdiction_slug=(proposition.jurisdiction.slug if proposition.jurisdiction else None),
        qualifier=proposition.qualifier if detail is not DetailLevel.COMPACT else None,
        review_status=proposition.review_status.value,
        authority_status=proposition.authority_status.value,
        confidence=proposition.confidence,
        effective_from=(proposition.effective_from if detail is DetailLevel.RESEARCH else None),
        effective_to=proposition.effective_to if detail is DetailLevel.RESEARCH else None,
        authorities=authorities,
    )


def _compose_answer(
    refs: list[PropositionRef], jurisdiction: Jurisdiction | None, detail: DetailLevel
) -> str:
    """Assemble prose from stored propositions. No generation, only arrangement."""
    scope = jurisdiction.name if jurisdiction else "the federal IDEA baseline"
    lines = [f"Under {scope}:"]
    for ref in refs:
        cites = ", ".join(
            f"{a.canonical_citation}{f' at {a.pin_cite}' if a.pin_cite else ''}"
            for a in ref.authorities
        )
        sentence = ref.statement.rstrip(".")
        if ref.qualifier and detail is not DetailLevel.COMPACT:
            sentence = f"{sentence} ({ref.qualifier.rstrip('.')})"
        lines.append(f"- {sentence}." + (f" [{cites}]" if cites else ""))
    return "\n".join(lines)


def run_research(session: Session, request: ResearchRequest) -> ResearchResult:
    """Answer a research request from validated database content only."""
    now = datetime.now(UTC)
    as_of = request.as_of or now.date()
    warnings: list[str] = []

    jurisdiction = _resolve_jurisdiction(session, request.jurisdiction)
    if request.jurisdiction and jurisdiction is None:
        warnings.append(
            f"Unknown jurisdiction {request.jurisdiction!r}; "
            "answered against the federal baseline only."
        )

    matches = match_concepts(session, request.issue)
    concepts_payload: list[dict[str, object]] = [
        {
            "slug": m.concept.slug,
            "name": m.concept.name,
            "idea_part": m.concept.idea_part.value,
            "score": round(m.score, 2),
            "matched_terms": list(m.matched_terms),
        }
        for m in matches
    ]

    def insufficient(reason: str, extra: list[str] | None = None) -> ResearchResult:
        result = ResearchResult(
            answer="",
            issue=request.issue,
            jurisdiction=_jurisdiction_payload(jurisdiction),
            concepts=concepts_payload,
            propositions=[],
            authorities=[],
            review_status=ReviewStatus.NEEDS_REVIEW.value,
            confidence=0.0,
            as_of=now,
            detail=request.detail,
            sufficient_coverage=False,
            warnings=[*warnings, reason, *(extra or [])],
        )
        result.estimated_response_tokens = estimate_payload_tokens(
            {"warnings": result.warnings, "concepts": concepts_payload}
        )
        return result

    if not matches:
        return insufficient(
            "insufficient_coverage: the issue did not match any concept in the "
            "IDEA taxonomy. Rephrase using IDEA terminology, or the concept is "
            "not yet modelled."
        )

    propositions = _load_propositions(session, matches, jurisdiction, as_of)
    if not propositions:
        return insufficient(
            "insufficient_coverage: no propositions have been ingested for the "
            f"matched concept(s) {', '.join(c['slug'] for c in concepts_payload)}"  # type: ignore[misc]
            f"{f' in {jurisdiction.slug}' if jurisdiction else ''}."
        )

    servable = [p for p in propositions if p.review_status in SERVABLE_REVIEW_STATUSES]
    unreviewed = [p for p in propositions if p.review_status not in SERVABLE_REVIEW_STATUSES]

    if not servable and not request.include_unreviewed:
        return insufficient(
            "insufficient_coverage: matching propositions exist but none have "
            "cleared review. Nothing is served below source_verified.",
            [
                f"{len(unreviewed)} unreviewed proposition(s) available; resend with "
                "include_unreviewed=true to inspect them as clearly-marked, "
                "non-authoritative material."
            ],
        )

    selected = servable if servable else unreviewed
    if request.include_unreviewed and unreviewed and servable:
        selected = servable + unreviewed

    if selected is unreviewed or (request.include_unreviewed and unreviewed):
        warnings.append(
            "NOT REVIEWED: this response includes propositions that have not "
            "cleared human review. They are machine-derived, may be wrong, and "
            "must not be relied on without checking the cited authority."
        )

    limit = DETAIL_PROPOSITION_LIMIT[request.detail]
    if len(selected) > limit:
        warnings.append(
            f"{len(selected) - limit} additional proposition(s) omitted at "
            f"detail={request.detail.value}; use detail=research for the full set."
        )
        selected = selected[:limit]

    unsupported = [p for p in selected if not p.authority_links]
    if unsupported:
        warnings.append(
            f"{len(unsupported)} proposition(s) have no linked authority and are "
            "reported without citation support."
        )

    refs = [_to_refs(session, p, request.detail) for p in selected]

    weakest = min(selected, key=lambda p: REVIEW_STATUS_RANK[p.review_status])
    review_status = weakest.review_status
    ceiling = CONFIDENCE_CEILING[review_status]
    confidence = round(min(min(p.confidence for p in selected), ceiling), 3)

    answer = _compose_answer(refs, jurisdiction, request.detail)

    all_authorities: list[AuthorityRef] = []
    seen: set[str] = set()
    for ref in refs:
        for authority in ref.authorities:
            if authority.id not in seen:
                seen.add(authority.id)
                all_authorities.append(authority)

    result = ResearchResult(
        answer=answer,
        issue=request.issue,
        jurisdiction=_jurisdiction_payload(jurisdiction),
        concepts=concepts_payload,
        propositions=refs,
        authorities=all_authorities,
        review_status=review_status.value,
        confidence=confidence,
        as_of=now,
        detail=request.detail,
        sufficient_coverage=bool(servable),
        warnings=warnings,
    )

    if request.token_budget > 0:
        trimmed, was_truncated = truncate_to_budget(result.answer, request.token_budget)
        if was_truncated:
            result.answer = trimmed
            result.truncated = True
            result.warnings.append(f"answer truncated to fit token_budget={request.token_budget}")

    result.estimated_response_tokens = estimate_payload_tokens(
        {
            "answer": result.answer,
            "concepts": result.concepts,
            "propositions": [
                {
                    "statement": p.statement,
                    "qualifier": p.qualifier,
                    "authorities": [a.canonical_citation for a in p.authorities],
                }
                for p in result.propositions
            ],
            "warnings": result.warnings,
        }
    )
    return result
