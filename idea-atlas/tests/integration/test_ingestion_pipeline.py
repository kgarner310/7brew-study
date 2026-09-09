"""End-to-end ingestion behaviour against a real database."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuthorityType, IngestionStatus, ReviewStatus
from app.ingestion.collectors.base import CollectedDocument
from app.ingestion.collectors.http import FixtureCollector
from app.ingestion.fixtures import load_fixture_collector
from app.ingestion.pipeline import IngestionPipeline
from app.models import Authority, AuthorityVersion, IngestionRun, Source

pytestmark = pytest.mark.integration

REAL_DOC = (
    "<html><body><main><p>"
    + ("An initial evaluation must be completed under the applicable timeline. " * 8)
    + "</p></main></body></html>"
)


@pytest.fixture
def source(seeded_session: Session) -> Source:
    return seeded_session.scalars(select(Source).where(Source.slug == "ecfr-34-cfr-300")).one()


def make_collector(tmp_path: Path, body: str, name: str = "doc.html") -> FixtureCollector:
    (tmp_path / name).write_text(body, encoding="utf-8")
    document = CollectedDocument(
        url="https://www.ecfr.gov/current/title-34/section-300.301",
        canonical_citation="34 C.F.R. 300.301",
        title="Initial evaluations",
        authority_type=AuthorityType.FEDERAL_REGULATION,
        meta={"fixture_file": name, "content_type": "text/html"},
    )
    return FixtureCollector(documents=[document], fixture_root=tmp_path)


class TestFirstIngestion:
    def test_creates_authority_and_current_version(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        report = IngestionPipeline(seeded_session).run(source, make_collector(tmp_path, REAL_DOC))

        assert report.status is IngestionStatus.COMPLETED
        assert (report.new_documents, report.changed_documents, report.unchanged_documents) == (
            1,
            0,
            0,
        )

        authority = seeded_session.scalars(
            select(Authority).where(Authority.canonical_citation == "34 C.F.R. 300.301")
        ).one()
        version = seeded_session.scalars(
            select(AuthorityVersion).where(AuthorityVersion.authority_id == authority.id)
        ).one()
        assert version.is_current is True
        assert len(version.sha256) == 64
        assert version.sha256 != version.raw_sha256  # normalized vs raw
        assert "An initial evaluation" in version.normalized_text

    def test_fixture_text_is_never_marked_source_verified(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        """Reading a file off disk is not evidence about what a publisher served."""
        IngestionPipeline(seeded_session).run(source, make_collector(tmp_path, REAL_DOC))
        version = seeded_session.scalars(select(AuthorityVersion)).one()
        assert version.review_status is ReviewStatus.NEEDS_REVIEW
        assert version.meta["synthetic_fixture"] is True
        assert version.meta["retrieval"] == "fixture"

    def test_records_an_ingestion_run(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        IngestionPipeline(seeded_session, actor="pytest").run(
            source, make_collector(tmp_path, REAL_DOC)
        )
        run = seeded_session.scalars(select(IngestionRun)).one()
        assert run.status is IngestionStatus.COMPLETED
        assert run.documents_seen == 1
        assert run.triggered_by == "pytest"
        assert run.completed_at is not None
        assert run.errors is None

    def test_advances_source_last_checked_at(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        assert source.last_checked_at is None
        IngestionPipeline(seeded_session).run(source, make_collector(tmp_path, REAL_DOC))
        assert source.last_checked_at is not None


class TestChangeDetection:
    def test_unchanged_content_creates_no_new_version(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        pipeline = IngestionPipeline(seeded_session)
        pipeline.run(source, make_collector(tmp_path, REAL_DOC))
        report = pipeline.run(source, make_collector(tmp_path, REAL_DOC))

        assert report.unchanged_documents == 1
        assert report.new_documents == 0
        assert seeded_session.scalars(select(AuthorityVersion)).unique().all().__len__() == 1

    def test_cosmetic_whitespace_change_is_not_a_change(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        """Reflowed markup must not look like an amendment."""
        pipeline = IngestionPipeline(seeded_session)
        pipeline.run(source, make_collector(tmp_path, REAL_DOC))
        reflowed = REAL_DOC.replace("<p>", "<p>\n   ").replace(". ", ".    ")
        report = pipeline.run(source, make_collector(tmp_path, reflowed))
        assert report.unchanged_documents == 1

    def test_substantive_change_creates_a_new_current_version(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        pipeline = IngestionPipeline(seeded_session)
        pipeline.run(source, make_collector(tmp_path, REAL_DOC))
        amended = REAL_DOC.replace("under the applicable timeline", "within 60 days")
        report = pipeline.run(source, make_collector(tmp_path, amended))

        assert report.changed_documents == 1
        versions = seeded_session.scalars(
            select(AuthorityVersion).order_by(AuthorityVersion.retrieved_at)
        ).all()
        assert len(versions) == 2
        assert [v.is_current for v in versions] == [False, True]

    def test_reversion_reactivates_the_prior_version(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        """An agency rolling back an edit must not violate hash uniqueness."""
        pipeline = IngestionPipeline(seeded_session)
        amended = REAL_DOC.replace("under the applicable timeline", "within 60 days")

        pipeline.run(source, make_collector(tmp_path, REAL_DOC))
        pipeline.run(source, make_collector(tmp_path, amended))
        report = pipeline.run(source, make_collector(tmp_path, REAL_DOC))

        assert report.changed_documents == 1
        assert report.error_count == 0
        versions = seeded_session.scalars(select(AuthorityVersion)).all()
        assert len(versions) == 2, "reversion must reuse the stored row, not insert"
        current = [v for v in versions if v.is_current]
        assert len(current) == 1
        assert current[0].meta.get("reobservation_count") == 1


class TestDryRun:
    def test_reports_without_writing_versions(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        report = IngestionPipeline(seeded_session, dry_run=True).run(
            source, make_collector(tmp_path, REAL_DOC)
        )
        assert report.new_documents == 1
        assert seeded_session.scalars(select(AuthorityVersion)).all() == []


class TestFailureHandling:
    def test_error_page_is_rejected_and_recorded(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        body = "<html><body><main>" + ("404 Not Found. " * 40) + "</main></body></html>"
        report = IngestionPipeline(seeded_session).run(source, make_collector(tmp_path, body))

        assert report.status is IngestionStatus.FAILED
        assert report.error_count == 1
        assert seeded_session.scalars(select(AuthorityVersion)).all() == []
        run = seeded_session.scalars(select(IngestionRun)).one()
        assert run.status is IngestionStatus.FAILED
        assert run.errors is not None

    def test_missing_fixture_file_does_not_abort_the_run(
        self, seeded_session: Session, source: Source, tmp_path: Path
    ) -> None:
        """One bad document must not roll back the whole batch."""
        good = CollectedDocument(
            url="https://www.ecfr.gov/current/title-34/section-300.8",
            canonical_citation="34 C.F.R. 300.8",
            title="Child with a disability",
            authority_type=AuthorityType.FEDERAL_REGULATION,
            meta={"fixture_file": "good.html", "content_type": "text/html"},
        )
        missing = CollectedDocument(
            url="https://www.ecfr.gov/current/title-34/section-300.9",
            canonical_citation="34 C.F.R. 300.9",
            title="Consent",
            authority_type=AuthorityType.FEDERAL_REGULATION,
            meta={"fixture_file": "absent.html", "content_type": "text/html"},
        )
        (tmp_path / "good.html").write_text(REAL_DOC, encoding="utf-8")
        collector = FixtureCollector(documents=[good, missing], fixture_root=tmp_path)

        report = IngestionPipeline(seeded_session).run(source, collector)

        assert report.status is IngestionStatus.PARTIAL
        assert report.new_documents == 1
        assert report.error_count == 1
        assert len(seeded_session.scalars(select(AuthorityVersion)).all()) == 1

    def test_fixture_path_cannot_escape_the_fixture_root(self, tmp_path: Path) -> None:
        document = CollectedDocument(
            url="https://www.ecfr.gov/x",
            canonical_citation="cite",
            title="t",
            authority_type=AuthorityType.FEDERAL_REGULATION,
            meta={"fixture_file": "../../../../etc/passwd"},
        )
        collector = FixtureCollector(documents=[document], fixture_root=tmp_path)
        with pytest.raises(ValueError, match="escapes the fixture root"):
            collector.read(document)


class TestRepositoryFixtures:
    def test_shipped_fixture_set_ingests_cleanly(
        self, seeded_session: Session, source: Source
    ) -> None:
        """The documented offline path must actually work."""
        slug, collector = load_fixture_collector()
        assert slug == source.slug

        report = IngestionPipeline(seeded_session).run(source, collector)
        assert report.status is IngestionStatus.COMPLETED
        assert report.documents_seen == 3
        assert report.new_documents == 3

        citations = set(seeded_session.scalars(select(Authority.canonical_citation)).all())
        assert citations == {
            "34 C.F.R. 300.301",
            "34 C.F.R. 300.8",
            "34 C.F.R. 303.310",
        }
