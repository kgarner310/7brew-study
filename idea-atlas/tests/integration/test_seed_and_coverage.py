"""Seeding idempotency and coverage reporting."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import CrawlStatus, ReviewStatus
from app.ingestion.fixtures import load_fixture_collector
from app.ingestion.pipeline import IngestionPipeline
from app.models import Jurisdiction, LegalConcept, Proposition, ReviewEvent, Source
from app.services.coverage import NOT_VERIFIED, build_coverage_report
from app.services.seed import seed_demo_propositions, seed_reference_data

pytestmark = pytest.mark.integration


class TestSeeding:
    def test_seeds_the_full_jurisdiction_universe(self, session: Session) -> None:
        counts = seed_reference_data(session)
        assert counts.jurisdictions == 70
        assert counts.concepts == 43
        assert counts.sources == 13

    def test_is_idempotent(self, session: Session) -> None:
        seed_reference_data(session)
        second = seed_reference_data(session)
        assert (second.jurisdictions, second.concepts, second.sources) == (0, 0, 0)
        assert session.scalar(select(Jurisdiction).where(Jurisdiction.slug == "nc")) is not None

    def test_wires_jurisdiction_parents(self, session: Session) -> None:
        seed_reference_data(session)
        nc = session.scalars(select(Jurisdiction).where(Jurisdiction.slug == "nc")).one()
        assert nc.parent is not None
        assert nc.parent.slug == "us"

    def test_wires_concept_parents(self, session: Session) -> None:
        seed_reference_data(session)
        child = session.scalars(
            select(LegalConcept).where(LegalConcept.slug == "initial-evaluation")
        ).one()
        assert child.parent is not None
        assert child.parent.slug == "evaluation"

    def test_sources_are_registered_as_unverified(self, session: Session) -> None:
        """A manifest URL nobody has checked must not look ready to crawl."""
        seed_reference_data(session)
        for source in session.scalars(select(Source)).all():
            assert source.crawl_status is CrawlStatus.URLS_UNVERIFIED
            assert source.meta["url_verified"] is False

    def test_no_commercial_publisher_is_registered(self, session: Session) -> None:
        seed_reference_data(session)
        publishers = " ".join(session.scalars(select(Source.publisher)).all()).lower()
        assert "westlaw" not in publishers
        assert "lexis" not in publishers


class TestDemoPropositions:
    def test_skipped_when_no_authority_exists(self, seeded_session: Session) -> None:
        """The seed must never invent an authority to hang a proposition on."""
        created, links = seed_demo_propositions(seeded_session)
        assert (created, links) == (0, 0)
        assert seeded_session.scalars(select(Proposition)).all() == []

    def test_created_once_authorities_are_ingested(self, seeded_session: Session) -> None:
        source = seeded_session.scalars(
            select(Source).where(Source.slug == "ecfr-34-cfr-300")
        ).one()
        _, collector = load_fixture_collector()
        IngestionPipeline(seeded_session).run(source, collector)

        created, links = seed_demo_propositions(seeded_session)
        assert created == 4
        assert links == 4

    def test_marked_unverified_with_honest_provenance(self, seeded_session: Session) -> None:
        source = seeded_session.scalars(
            select(Source).where(Source.slug == "ecfr-34-cfr-300")
        ).one()
        _, collector = load_fixture_collector()
        IngestionPipeline(seeded_session).run(source, collector)
        seed_demo_propositions(seeded_session)

        for proposition in seeded_session.scalars(select(Proposition)).all():
            assert proposition.review_status is ReviewStatus.NEEDS_REVIEW
            assert proposition.created_by == "seed:model_knowledge"
            assert proposition.confidence <= 0.25
            assert proposition.meta["verification_required"] is True
            assert proposition.reviewed_by is None

    def test_writes_a_review_trail_entry(self, seeded_session: Session) -> None:
        source = seeded_session.scalars(
            select(Source).where(Source.slug == "ecfr-34-cfr-300")
        ).one()
        _, collector = load_fixture_collector()
        IngestionPipeline(seeded_session).run(source, collector)
        seed_demo_propositions(seeded_session)

        events = seeded_session.scalars(select(ReviewEvent)).all()
        assert len(events) == 4
        assert all(event.review_status is ReviewStatus.NEEDS_REVIEW for event in events)

    def test_rerun_creates_no_duplicates(self, seeded_session: Session) -> None:
        source = seeded_session.scalars(
            select(Source).where(Source.slug == "ecfr-34-cfr-300")
        ).one()
        _, collector = load_fixture_collector()
        IngestionPipeline(seeded_session).run(source, collector)
        seed_demo_propositions(seeded_session)
        created, _ = seed_demo_propositions(seeded_session)
        assert created == 0


class TestCoverageReport:
    def test_covers_every_grantee_jurisdiction(self, seeded_session: Session) -> None:
        report = build_coverage_report(seeded_session)
        assert report.total_jurisdictions == 57
        assert report.jurisdictions_with_manifest == 57

    def test_reports_zero_data_honestly(self, seeded_session: Session) -> None:
        report = build_coverage_report(seeded_session)
        assert report.jurisdictions_with_any_data == 0
        nc = next(row for row in report.rows if row.slug == "nc")
        assert nc.display("statutes") == NOT_VERIFIED
        assert nc.display("due_process") == NOT_VERIFIED
        assert nc.total_authorities == 0

    def test_counts_appear_after_ingestion(self, seeded_session: Session) -> None:
        source = seeded_session.scalars(
            select(Source).where(Source.slug == "ecfr-34-cfr-300")
        ).one()
        _, collector = load_fixture_collector()
        IngestionPipeline(seeded_session).run(source, collector)

        report = build_coverage_report(seeded_session)
        # Federal authorities attach to the 'us' jurisdiction, which is not a
        # grantee row, so the state rows must still honestly read zero.
        assert all(row.total_authorities == 0 for row in report.rows)

    def test_every_category_is_present_for_every_row(self, seeded_session: Session) -> None:
        from app.services.coverage import COVERAGE_CATEGORIES

        report = build_coverage_report(seeded_session)
        for row in report.rows:
            assert set(row.counts) == set(COVERAGE_CATEGORIES)
