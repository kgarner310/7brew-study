"""Nationwide coverage reporting.

Answers the question the roadmap depends on: for each jurisdiction, what do we
actually have? Counts come from the database (what is ingested) and the
manifests (what is even declared), and the two are reported separately so
"manifest exists" can never be mistaken for "data exists".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import AuthorityType, CrawlStatus
from app.legal.jurisdictions import states_and_equivalents
from app.legal.manifests import JurisdictionManifest, load_all_jurisdiction_manifests
from app.models import Authority, Jurisdiction, Source

#: Coverage categories, mapped to the authority types that satisfy them.
COVERAGE_CATEGORIES: dict[str, tuple[AuthorityType, ...]] = {
    "statutes": (AuthorityType.STATE_STATUTE, AuthorityType.FEDERAL_STATUTE),
    "regulations": (AuthorityType.STATE_REGULATION, AuthorityType.FEDERAL_REGULATION),
    "procedural_safeguards": (AuthorityType.PROCEDURAL_SAFEGUARDS_NOTICE,),
    "sea_guidance": (AuthorityType.STATE_GUIDANCE,),
    "due_process": (AuthorityType.DUE_PROCESS_DECISION,),
    "state_complaints": (AuthorityType.STATE_COMPLAINT_DECISION,),
    "federal_cases": (
        AuthorityType.SUPREME_COURT_OPINION,
        AuthorityType.CIRCUIT_COURT_OPINION,
        AuthorityType.DISTRICT_COURT_OPINION,
    ),
}

NOT_VERIFIED = "not yet verified"


@dataclass(slots=True)
class JurisdictionCoverage:
    """Coverage for one jurisdiction."""

    slug: str
    name: str
    counts: dict[str, int] = field(default_factory=dict)
    manifest_declared_sites: int = 0
    manifest_verified_sites: int = 0
    crawl_status: CrawlStatus = CrawlStatus.NOT_STARTED
    last_checked_at: datetime | None = None
    error_count: int = 0
    has_manifest: bool = False

    def display(self, category: str) -> str:
        """Cell value for the coverage table."""
        count = self.counts.get(category, 0)
        return str(count) if count else NOT_VERIFIED

    @property
    def total_authorities(self) -> int:
        return sum(self.counts.values())


@dataclass(slots=True)
class CoverageReport:
    """The nationwide picture."""

    rows: list[JurisdictionCoverage]
    generated_at: datetime

    @property
    def jurisdictions_with_any_data(self) -> int:
        return sum(1 for row in self.rows if row.total_authorities > 0)

    @property
    def jurisdictions_with_manifest(self) -> int:
        return sum(1 for row in self.rows if row.has_manifest)

    @property
    def total_jurisdictions(self) -> int:
        return len(self.rows)


def _manifest_index() -> dict[str, JurisdictionManifest]:
    try:
        return {m.jurisdiction: m for m in load_all_jurisdiction_manifests()}
    except FileNotFoundError:  # pragma: no cover - manifests ship with the repo
        return {}


def build_coverage_report(session: Session) -> CoverageReport:
    """Assemble the coverage table for every IDEA grantee jurisdiction."""
    manifests = _manifest_index()

    counts_stmt = (
        select(
            Jurisdiction.slug,
            Authority.authority_type,
            func.count(Authority.id),
        )
        .join(Authority, Authority.jurisdiction_id == Jurisdiction.id)
        .group_by(Jurisdiction.slug, Authority.authority_type)
    )
    raw_counts: dict[tuple[str, AuthorityType], int] = {
        (slug, authority_type): count
        for slug, authority_type, count in session.execute(counts_stmt)
    }

    last_checked_stmt = (
        select(Jurisdiction.slug, func.max(Source.last_checked_at))
        .join(Source, Source.jurisdiction_id == Jurisdiction.id)
        .group_by(Jurisdiction.slug)
    )
    last_checked: dict[str, datetime | None] = dict(
        session.execute(last_checked_stmt).tuples().all()
    )

    rows: list[JurisdictionCoverage] = []
    for seed in states_and_equivalents():
        manifest = manifests.get(seed.slug)
        row = JurisdictionCoverage(
            slug=seed.slug,
            name=seed.name,
            counts={
                category: sum(
                    raw_counts.get((seed.slug, authority_type), 0)
                    for authority_type in authority_types
                )
                for category, authority_types in COVERAGE_CATEGORIES.items()
            },
            last_checked_at=last_checked.get(seed.slug),
            has_manifest=manifest is not None,
        )
        if manifest is not None:
            row.manifest_declared_sites = manifest.declared_site_count
            row.manifest_verified_sites = manifest.verified_site_count
            row.crawl_status = manifest.crawl_status
        rows.append(row)

    from datetime import UTC

    return CoverageReport(rows=rows, generated_at=datetime.now(UTC))
