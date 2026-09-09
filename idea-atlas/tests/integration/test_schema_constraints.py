"""Database-level integrity.

These assert that the *database* rejects bad data, not merely that the
application avoids writing it. Constraints are the last line of defence when a
future script or a manual `psql` session bypasses the ORM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    AuthorityRelationType,
    AuthorityType,
    EntityType,
    JurisdictionType,
    PropositionAuthorityRelation,
    PropositionType,
    RetrievalMethod,
    ReviewStatus,
    SourceType,
)
from app.models import (
    Authority,
    AuthorityRelationship,
    AuthorityVersion,
    Jurisdiction,
    LegalConcept,
    Proposition,
    PropositionAuthority,
    ReviewEvent,
    Source,
)

pytestmark = pytest.mark.integration


def make_jurisdiction(session: Session, slug: str = "tj") -> Jurisdiction:
    jurisdiction = Jurisdiction(
        slug=slug, name=f"Test {slug}", jurisdiction_type=JurisdictionType.STATE
    )
    session.add(jurisdiction)
    session.flush()
    return jurisdiction


def make_source(session: Session, jurisdiction: Jurisdiction) -> Source:
    source = Source(
        jurisdiction_id=jurisdiction.id,
        slug=f"src-{uuid.uuid4().hex[:8]}",
        name="Test source",
        publisher="Test publisher",
        source_type=SourceType.REGULATION,
        base_url="https://example.gov/",
        retrieval_method=RetrievalMethod.HTTP_HTML,
    )
    session.add(source)
    session.flush()
    return source


def make_authority(
    session: Session, jurisdiction: Jurisdiction, source: Source, citation: str
) -> Authority:
    authority = Authority(
        jurisdiction_id=jurisdiction.id,
        source_id=source.id,
        authority_type=AuthorityType.FEDERAL_REGULATION,
        canonical_citation=citation,
        title="Test authority",
        source_url="https://example.gov/a",
    )
    session.add(authority)
    session.flush()
    return authority


def make_version(authority: Authority, digest: str, *, current: bool = True) -> AuthorityVersion:
    return AuthorityVersion(
        authority_id=authority.id,
        retrieved_at=datetime.now(UTC),
        raw_text="raw",
        normalized_text="normalized",
        sha256=digest,
        raw_sha256=digest,
        parser_name="test",
        parser_version="1",
        is_current=current,
    )


class TestJurisdictionConstraints:
    def test_slug_is_unique(self, session: Session) -> None:
        make_jurisdiction(session, "dup")
        with pytest.raises(IntegrityError):
            make_jurisdiction(session, "dup")

    def test_cannot_be_its_own_parent(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        jurisdiction.parent_jurisdiction_id = jurisdiction.id
        with pytest.raises(IntegrityError):
            session.flush()

    def test_postal_code_must_be_uppercase(self, session: Session) -> None:
        session.add(
            Jurisdiction(
                slug="lower",
                name="Lower",
                jurisdiction_type=JurisdictionType.STATE,
                postal_code="nc",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


class TestAuthorityConstraints:
    def test_citation_unique_within_jurisdiction(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        source = make_source(session, jurisdiction)
        make_authority(session, jurisdiction, source, "34 C.F.R. 300.1")
        with pytest.raises(IntegrityError):
            make_authority(session, jurisdiction, source, "34 C.F.R. 300.1")

    def test_same_citation_allowed_in_different_jurisdictions(self, session: Session) -> None:
        first = make_jurisdiction(session, "j1")
        second = make_jurisdiction(session, "j2")
        make_authority(session, first, make_source(session, first), "Same Cite")
        make_authority(session, second, make_source(session, second), "Same Cite")
        session.flush()  # must not raise

    def test_superseded_date_cannot_precede_effective_date(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        authority.effective_date = date(2020, 1, 1)
        authority.superseded_date = date(2019, 1, 1)
        with pytest.raises(IntegrityError):
            session.flush()


class TestAuthorityVersionConstraints:
    def test_only_one_current_version_per_authority(self, session: Session) -> None:
        """The partial unique index is what makes 'current text' unambiguous."""
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        session.add(make_version(authority, "a" * 64, current=True))
        session.add(make_version(authority, "b" * 64, current=True))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_many_non_current_versions_allowed(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        session.add(make_version(authority, "a" * 64, current=False))
        session.add(make_version(authority, "b" * 64, current=False))
        session.add(make_version(authority, "c" * 64, current=True))
        session.flush()  # must not raise

    def test_hash_unique_per_authority(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        session.add(make_version(authority, "a" * 64, current=False))
        session.add(make_version(authority, "a" * 64, current=True))
        with pytest.raises(IntegrityError):
            session.flush()

    @pytest.mark.parametrize("bad", ["", "abc", "a" * 63, "a" * 65])
    def test_sha256_must_be_64_chars(self, session: Session, bad: str) -> None:
        """Short hashes trip the CHECK; over-long ones trip varchar(64)."""
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        session.add(make_version(authority, bad))
        with pytest.raises(DatabaseError):
            session.flush()


class TestAuthorityRelationships:
    def test_creates_a_typed_edge(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        source = make_source(session, jurisdiction)
        a = make_authority(session, jurisdiction, source, "cite-a")
        b = make_authority(session, jurisdiction, source, "cite-b")
        session.add(
            AuthorityRelationship(
                source_authority_id=a.id,
                target_authority_id=b.id,
                relationship_type=AuthorityRelationType.INTERPRETS,
            )
        )
        session.flush()
        assert session.query(AuthorityRelationship).count() == 1

    def test_rejects_self_edges(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        a = make_authority(session, jurisdiction, make_source(session, jurisdiction), "cite-a")
        session.add(
            AuthorityRelationship(
                source_authority_id=a.id,
                target_authority_id=a.id,
                relationship_type=AuthorityRelationType.CITES,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()

    def test_rejects_duplicate_edges_of_the_same_type(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        source = make_source(session, jurisdiction)
        a = make_authority(session, jurisdiction, source, "cite-a")
        b = make_authority(session, jurisdiction, source, "cite-b")
        for _ in range(2):
            session.add(
                AuthorityRelationship(
                    source_authority_id=a.id,
                    target_authority_id=b.id,
                    relationship_type=AuthorityRelationType.OVERRULES,
                )
            )
        with pytest.raises(IntegrityError):
            session.flush()

    def test_allows_different_relationship_types_between_the_same_pair(
        self, session: Session
    ) -> None:
        jurisdiction = make_jurisdiction(session)
        source = make_source(session, jurisdiction)
        a = make_authority(session, jurisdiction, source, "cite-a")
        b = make_authority(session, jurisdiction, source, "cite-b")
        for relation in (AuthorityRelationType.CITES, AuthorityRelationType.DISTINGUISHES):
            session.add(
                AuthorityRelationship(
                    source_authority_id=a.id,
                    target_authority_id=b.id,
                    relationship_type=relation,
                )
            )
        session.flush()  # must not raise


class TestPropositionConstraints:
    def _concept(self, session: Session) -> LegalConcept:
        concept = LegalConcept(slug="c1", name="Concept", description="d")
        session.add(concept)
        session.flush()
        return concept

    def _proposition(self, session: Session, **kwargs: object) -> Proposition:
        defaults: dict[str, object] = {
            "concept_id": self._concept(session).id,
            "statement": "A statement",
            "proposition_type": PropositionType.REQUIREMENT,
            "confidence": 0.5,
            "created_by": "test",
        }
        defaults.update(kwargs)
        proposition = Proposition(**defaults)
        session.add(proposition)
        return proposition

    @pytest.mark.parametrize("confidence", [-0.1, 1.1, 2.0])
    def test_confidence_must_be_a_probability(self, session: Session, confidence: float) -> None:
        self._proposition(session, confidence=confidence)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_statement_cannot_be_blank(self, session: Session) -> None:
        self._proposition(session, statement="   ")
        with pytest.raises(IntegrityError):
            session.flush()

    def test_effective_dates_must_be_ordered(self, session: Session) -> None:
        self._proposition(session, effective_from=date(2020, 1, 1), effective_to=date(2019, 1, 1))
        with pytest.raises(IntegrityError):
            session.flush()

    def test_human_reviewed_requires_a_named_reviewer(self, session: Session) -> None:
        """A record cannot claim human review without saying who reviewed it."""
        self._proposition(session, review_status=ReviewStatus.HUMAN_REVIEWED)
        with pytest.raises(IntegrityError):
            session.flush()

    def test_human_reviewed_with_a_reviewer_is_accepted(self, session: Session) -> None:
        self._proposition(
            session,
            review_status=ReviewStatus.HUMAN_REVIEWED,
            reviewed_by="jane.doe",
            reviewed_at=datetime.now(UTC),
        )
        session.flush()  # must not raise

    def test_ai_extracted_needs_no_reviewer(self, session: Session) -> None:
        self._proposition(session, review_status=ReviewStatus.AI_EXTRACTED)
        session.flush()  # must not raise

    def test_authority_link_weight_is_bounded(self, session: Session) -> None:
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        proposition = self._proposition(session)
        session.flush()
        session.add(
            PropositionAuthority(
                proposition_id=proposition.id,
                authority_id=authority.id,
                relationship_type=PropositionAuthorityRelation.SUPPORTS,
                weight=101,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


class TestReviewTrail:
    def test_records_a_status_transition(self, session: Session) -> None:
        entity_id = uuid.uuid4()
        session.add(
            ReviewEvent(
                entity_type=EntityType.PROPOSITION,
                entity_id=entity_id,
                previous_status=ReviewStatus.AI_EXTRACTED,
                review_status=ReviewStatus.HUMAN_REVIEWED,
                reviewer="jane.doe",
                notes="Checked against 34 C.F.R. 300.301",
            )
        )
        session.flush()
        event = session.query(ReviewEvent).one()
        assert event.previous_status is ReviewStatus.AI_EXTRACTED
        assert event.review_status is ReviewStatus.HUMAN_REVIEWED
        assert event.created_at is not None

    def test_trail_survives_the_entity_it_describes(self, session: Session) -> None:
        """entity_id is deliberately not a foreign key."""
        jurisdiction = make_jurisdiction(session)
        authority = make_authority(
            session, jurisdiction, make_source(session, jurisdiction), "cite"
        )
        authority_id = authority.id
        session.add(
            ReviewEvent(
                entity_type=EntityType.AUTHORITY,
                entity_id=authority_id,
                review_status=ReviewStatus.SOURCE_VERIFIED,
                reviewer="pipeline:test",
            )
        )
        session.flush()
        session.delete(authority)
        session.flush()
        assert session.query(ReviewEvent).filter_by(entity_id=authority_id).count() == 1
