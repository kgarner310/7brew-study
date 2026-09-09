"""Source-manifest schema and loaders.

Manifests are the declarative registry of where legal text comes from. They are
plain YAML so that a non-programmer subject-matter expert can verify and edit a
jurisdiction's URLs without touching Python.

Every URL carries its own ``verified`` flag. Unverified URLs are never fetched
by default: ``idea-atlas verify-sources`` reports them and the ingestion CLI
refuses to run against them unless explicitly forced. That is the mechanism
that keeps "we have a manifest" from being mistaken for "we have coverage".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import MANIFEST_DIR
from app.core.enums import (
    CommercialReuseStatus,
    CopyrightStatus,
    CrawlFrequency,
    CrawlStatus,
    RetrievalMethod,
    SourceType,
)

MANIFEST_SCHEMA_VERSION = 1

#: The eight site categories every jurisdiction manifest tracks. Fixing the set
#: is what makes nationwide coverage reporting possible.
SITE_CATEGORIES: tuple[str, ...] = (
    "statutes",
    "regulations",
    "special_education",
    "procedural_safeguards",
    "due_process_decisions",
    "state_complaints",
    "guidance",
    "forms",
)


class OfficialSite(BaseModel):
    """One official URL for one category, with its verification state."""

    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    verified: bool = False
    """True only when a human confirmed this URL points at the official text."""
    verified_at: str | None = None
    verified_by: str | None = None
    notes: str | None = None

    @property
    def is_actionable(self) -> bool:
        """True when this site can actually be crawled."""
        return bool(self.url) and self.verified


class ManifestVerification(BaseModel):
    """Provenance of the manifest file itself."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["unverified", "partially_verified", "verified"] = "unverified"
    populated_by: str = "model_knowledge"
    """``model_knowledge`` means an LLM produced it and it is NOT authoritative."""
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None


class ManifestSource(BaseModel):
    """A concrete, loadable source definition (used by the federal manifest)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    publisher: str
    source_type: SourceType
    base_url: str
    retrieval_method: RetrievalMethod = RetrievalMethod.HTTP_HTML
    official_source: bool = True
    copyright_status: CopyrightStatus = CopyrightStatus.UNKNOWN
    commercial_reuse_status: CommercialReuseStatus = CommercialReuseStatus.UNKNOWN
    license_notes: str | None = None
    terms_of_service_url: str | None = None
    crawl_frequency: CrawlFrequency = CrawlFrequency.ON_DEMAND
    crawl_status: CrawlStatus = CrawlStatus.URLS_UNVERIFIED
    url_verified: bool = False
    notes: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class JurisdictionManifest(BaseModel):
    """The per-jurisdiction source manifest."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = MANIFEST_SCHEMA_VERSION
    jurisdiction: str
    """Jurisdiction slug, matching app.legal.jurisdictions.registry."""
    jurisdiction_name: str
    sea: str | None = None
    federal_circuit: str | None = None
    idea_part_b_applicable: bool = True
    idea_part_c_applicable: bool = True
    official_sites: dict[str, OfficialSite] = Field(default_factory=dict)
    sources: list[ManifestSource] = Field(default_factory=list)
    crawl_status: CrawlStatus = CrawlStatus.NOT_STARTED
    verification: ManifestVerification = Field(default_factory=ManifestVerification)
    notes: str | None = None

    @field_validator("official_sites")
    @classmethod
    def _known_categories(cls, value: dict[str, OfficialSite]) -> dict[str, OfficialSite]:
        unknown = set(value) - set(SITE_CATEGORIES)
        if unknown:
            raise ValueError(f"Unknown site categories: {sorted(unknown)}")
        return value

    @property
    def verified_site_count(self) -> int:
        return sum(1 for site in self.official_sites.values() if site.is_actionable)

    @property
    def declared_site_count(self) -> int:
        return sum(1 for site in self.official_sites.values() if site.url)


class FederalManifest(BaseModel):
    """The federal source manifest: richer, because federal sources are known."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = MANIFEST_SCHEMA_VERSION
    jurisdiction: str = "us"
    jurisdiction_name: str = "United States (Federal)"
    description: str = ""
    sources: list[ManifestSource] = Field(default_factory=list)
    verification: ManifestVerification = Field(default_factory=ManifestVerification)
    notes: str | None = None


def load_jurisdiction_manifest(path: Path) -> JurisdictionManifest:
    """Load and validate one jurisdiction manifest."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return JurisdictionManifest.model_validate(data)


def load_federal_manifest(path: Path | None = None) -> FederalManifest:
    """Load the federal manifest."""
    path = path or (MANIFEST_DIR / "federal" / "federal.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return FederalManifest.model_validate(data)


def jurisdiction_manifest_paths(root: Path | None = None) -> list[Path]:
    """Every jurisdiction manifest file, sorted by slug."""
    root = root or (MANIFEST_DIR / "jurisdictions")
    return sorted(root.glob("*.yaml"))


def load_all_jurisdiction_manifests(
    root: Path | None = None,
) -> list[JurisdictionManifest]:
    """Load and validate every jurisdiction manifest."""
    return [load_jurisdiction_manifest(p) for p in jurisdiction_manifest_paths(root)]


def dump_jurisdiction_manifest(manifest: JurisdictionManifest, path: Path) -> None:
    """Write a manifest to ``path`` as readable YAML."""
    payload = manifest.model_dump(mode="json", exclude_none=False)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
