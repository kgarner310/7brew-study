"""Ingestion orchestration: retrieve, validate, hash, version, persist.

One pipeline serves every source. Collectors differ (they know their source's
shape); everything after discovery is identical, which is what lets the system
scale to 56+ jurisdictions without 56 bespoke programs.

Change detection is hash-based on *normalized* text. An unchanged document
creates no new version row -- it only advances ``Source.last_checked_at``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.enums import (
    AuthorityCurrentStatus,
    IngestionStatus,
    PrecedentialStatus,
    ReviewStatus,
)
from app.core.errors import IngestionError
from app.core.logging import get_logger
from app.ingestion.collectors.base import CollectedDocument, Collector
from app.ingestion.collectors.http import FixtureCollector
from app.ingestion.fetcher import DocumentFetcher
from app.ingestion.hashing import NORMALIZER_VERSION, sha256_bytes, sha256_text
from app.ingestion.parsers.registry import get_parser
from app.ingestion.validators.document import validate_document
from app.models import Authority, AuthorityVersion, IngestionRun, Source

logger = get_logger(__name__)

DocumentOutcome = Literal["new", "changed", "unchanged", "error"]


@dataclass(slots=True)
class DocumentResult:
    """What happened to one document during a run."""

    citation: str
    outcome: DocumentOutcome
    sha256: str | None = None
    message: str | None = None


@dataclass(slots=True)
class IngestionReport:
    """Aggregate outcome of one pipeline execution."""

    source_slug: str
    status: IngestionStatus
    documents_seen: int = 0
    new_documents: int = 0
    changed_documents: int = 0
    unchanged_documents: int = 0
    errors: list[str] = field(default_factory=list)
    results: list[DocumentResult] = field(default_factory=list)
    run_id: str | None = None

    @property
    def error_count(self) -> int:
        return len(self.errors)


class IngestionPipeline:
    """Runs a collector against a source and persists the results."""

    def __init__(
        self,
        session: Session,
        *,
        fetcher: DocumentFetcher | None = None,
        actor: str = "cli",
        dry_run: bool = False,
    ) -> None:
        self.session = session
        self.fetcher = fetcher
        self.actor = actor
        self.dry_run = dry_run

    def run(self, source: Source, collector: Collector) -> IngestionReport:
        """Ingest every document ``collector`` discovers for ``source``."""
        started = datetime.now(UTC)
        run = IngestionRun(
            source_id=source.id,
            started_at=started,
            status=IngestionStatus.RUNNING,
            triggered_by=self.actor,
            collector_name=collector.name,
            dry_run=self.dry_run,
            meta={"collector_version": collector.version},
        )
        self.session.add(run)
        self.session.flush()

        report = IngestionReport(
            source_slug=source.slug,
            status=IngestionStatus.RUNNING,
            run_id=str(run.id),
        )

        for document in collector.discover():
            report.documents_seen += 1
            try:
                # A savepoint per document: one bad document rolls back its own
                # writes without poisoning the transaction for the rest of the run.
                with self.session.begin_nested():
                    result = self._ingest_one(source, collector, document)
            except (IngestionError, OSError, ValueError) as exc:
                message = f"{document.canonical_citation}: {exc}"
                logger.warning(
                    "ingest.document_failed",
                    citation=document.canonical_citation,
                    error=str(exc),
                )
                report.errors.append(message)
                report.results.append(
                    DocumentResult(document.canonical_citation, "error", message=message)
                )
                continue
            except SQLAlchemyError as exc:
                # Database errors can carry the full offending row -- including
                # raw document text -- in their string form. Log the type only.
                message = (
                    f"{document.canonical_citation}: database error "
                    f"({type(exc).__name__}) while persisting; see server logs"
                )
                logger.exception(
                    "ingest.document_db_error",
                    citation=document.canonical_citation,
                    error_type=type(exc).__name__,
                )
                report.errors.append(message)
                report.results.append(
                    DocumentResult(document.canonical_citation, "error", message=message)
                )
                continue

            report.results.append(result)
            if result.outcome == "new":
                report.new_documents += 1
            elif result.outcome == "changed":
                report.changed_documents += 1
            else:
                report.unchanged_documents += 1

        report.status = self._final_status(report)

        run.completed_at = datetime.now(UTC)
        run.status = report.status
        run.documents_seen = report.documents_seen
        run.new_documents = report.new_documents
        run.changed_documents = report.changed_documents
        run.unchanged_documents = report.unchanged_documents
        run.error_count = report.error_count
        run.errors = "\n".join(report.errors) or None

        source.last_checked_at = run.completed_at
        self.session.flush()

        logger.info(
            "ingest.run_complete",
            source=source.slug,
            status=report.status.value,
            seen=report.documents_seen,
            new=report.new_documents,
            changed=report.changed_documents,
            unchanged=report.unchanged_documents,
            errors=report.error_count,
        )
        return report

    @staticmethod
    def _final_status(report: IngestionReport) -> IngestionStatus:
        if not report.errors:
            return IngestionStatus.COMPLETED
        if report.errors and report.documents_seen == report.error_count:
            return IngestionStatus.FAILED
        return IngestionStatus.PARTIAL

    def _load_body(
        self, collector: Collector, document: CollectedDocument
    ) -> tuple[bytes, str, str, str | None]:
        """Return ``(body, content_type, final_url, snapshot_url)``."""
        if isinstance(collector, FixtureCollector):
            body, content_type = collector.read(document)
            return body, content_type, document.url, None

        fetcher = self.fetcher or DocumentFetcher()
        result = fetcher.fetch(document.url)
        return result.body, result.content_type, result.final_url, None

    def _ingest_one(
        self, source: Source, collector: Collector, document: CollectedDocument
    ) -> DocumentResult:
        body, content_type, final_url, snapshot_url = self._load_body(collector, document)
        from_fixture = isinstance(collector, FixtureCollector)

        parser = get_parser(content_type)
        parsed = parser.parse(body, content_type=content_type, url=final_url)

        validation = validate_document(parsed.text, url=final_url)
        if not validation.ok:
            raise IngestionError(validation.summary)
        for warning in validation.warnings:
            logger.warning("ingest.document_warning", message=warning)

        normalized = parsed.text
        digest = sha256_text(normalized)

        authority = self._get_or_create_authority(source, document, final_url)
        current = self._current_version(authority)

        if current is not None and current.sha256 == digest:
            logger.info("ingest.unchanged", citation=document.canonical_citation, sha256=digest)
            return DocumentResult(document.canonical_citation, "unchanged", digest)

        # A hash we have stored before but which is not current means the source
        # reverted to earlier text (an agency rolls back a bad edit). That is a
        # real change, but it must reactivate the existing version rather than
        # insert a duplicate, which the (authority_id, sha256) constraint forbids.
        prior = self._version_by_hash(authority, digest)

        outcome: DocumentOutcome = "new" if current is None else "changed"

        if self.dry_run:
            return DocumentResult(
                document.canonical_citation,
                outcome,
                digest,
                message="dry run: no rows written",
            )

        if current is not None:
            # The partial unique index permits only one current version, so the
            # old flag must be cleared and flushed before the new row lands.
            current.is_current = False
            current.effective_to = document.effective_date or current.effective_to
            self.session.flush()

        if prior is not None:
            prior.is_current = True
            prior.meta = {
                **prior.meta,
                "reverted_to_at": datetime.now(UTC).isoformat(),
                "reobservation_count": int(prior.meta.get("reobservation_count", 0)) + 1,
            }
            self.session.flush()
            logger.info(
                "ingest.reverted",
                citation=document.canonical_citation,
                sha256=digest,
                note="source returned to previously stored text",
            )
            return DocumentResult(
                document.canonical_citation,
                "changed",
                digest,
                message="source reverted to a previously stored version",
            )

        version = AuthorityVersion(
            authority_id=authority.id,
            retrieved_at=datetime.now(UTC),
            effective_from=document.effective_date,
            raw_text=body.decode("utf-8", errors="replace"),
            normalized_text=normalized,
            sha256=digest,
            raw_sha256=sha256_bytes(body),
            content_type=content_type,
            byte_size=len(body),
            parser_name=parsed.parser_name,
            parser_version=f"{parsed.parser_version}+norm{NORMALIZER_VERSION}",
            source_snapshot_url=snapshot_url,
            is_current=True,
            # Fixture text was read from disk, not retrieved from the publisher,
            # so it is emphatically NOT source-verified. Only a real network
            # retrieval whose hash we computed ourselves earns that status.
            review_status=(
                ReviewStatus.NEEDS_REVIEW if from_fixture else ReviewStatus.SOURCE_VERIFIED
            ),
            meta={
                "final_url": final_url,
                "collector": collector.name,
                "retrieval": "fixture" if from_fixture else "network",
                **({"synthetic_fixture": True} if from_fixture else {}),
                **({"parsed_title": parsed.title} if parsed.title else {}),
            },
        )
        self.session.add(version)
        self.session.flush()

        logger.info(
            "ingest.version_stored",
            citation=document.canonical_citation,
            outcome=outcome,
            sha256=digest,
        )
        return DocumentResult(document.canonical_citation, outcome, digest)

    def _get_or_create_authority(
        self, source: Source, document: CollectedDocument, final_url: str
    ) -> Authority:
        if source.jurisdiction_id is None:
            raise IngestionError(
                f"Source {source.slug!r} has no jurisdiction; "
                "authorities require one for citation uniqueness"
            )

        stmt = select(Authority).where(
            Authority.jurisdiction_id == source.jurisdiction_id,
            Authority.canonical_citation == document.canonical_citation,
        )
        authority = self.session.scalars(stmt).one_or_none()
        if authority is not None:
            return authority

        authority = Authority(
            jurisdiction_id=source.jurisdiction_id,
            source_id=source.id,
            authority_type=document.authority_type,
            canonical_citation=document.canonical_citation,
            title=document.title,
            docket_or_identifier=document.docket_or_identifier,
            court_or_agency=document.court_or_agency,
            idea_part=document.idea_part,
            publication_date=document.publication_date,
            effective_date=document.effective_date,
            current_status=AuthorityCurrentStatus.IN_FORCE,
            precedential_status=PrecedentialStatus.NOT_APPLICABLE,
            review_status=ReviewStatus.NEEDS_REVIEW,
            source_url=final_url,
            official_url=document.official_url or document.url,
            meta=dict(document.meta),
        )
        self.session.add(authority)
        self.session.flush()
        return authority

    def _version_by_hash(self, authority: Authority, digest: str) -> AuthorityVersion | None:
        """Any stored version of ``authority`` whose normalized text hashes to ``digest``."""
        stmt = select(AuthorityVersion).where(
            AuthorityVersion.authority_id == authority.id,
            AuthorityVersion.sha256 == digest,
        )
        return self.session.scalars(stmt).one_or_none()

    def _current_version(self, authority: Authority) -> AuthorityVersion | None:
        stmt = select(AuthorityVersion).where(
            AuthorityVersion.authority_id == authority.id,
            AuthorityVersion.is_current.is_(True),
        )
        return self.session.scalars(stmt).one_or_none()
