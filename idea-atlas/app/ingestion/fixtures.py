"""Build fixture collectors from a YAML descriptor.

Lets the offline path be declared as data rather than code, so adding a fixture
never requires touching Python.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from app.core.config import FIXTURE_DIR
from app.core.enums import AuthorityType, IdeaPart
from app.ingestion.collectors.base import CollectedDocument
from app.ingestion.collectors.http import FixtureCollector


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def load_fixture_collector(
    descriptor_path: Path | None = None,
) -> tuple[str, FixtureCollector]:
    """Load a fixture descriptor.

    Returns:
        ``(source_slug, collector)`` -- the slug names the registered Source the
        documents belong to.
    """
    descriptor_path = descriptor_path or (FIXTURE_DIR / "federal" / "documents.yaml")
    data = yaml.safe_load(descriptor_path.read_text(encoding="utf-8"))

    documents = [
        CollectedDocument(
            url=entry["url"],
            canonical_citation=entry["canonical_citation"],
            title=entry["title"],
            authority_type=AuthorityType(entry["authority_type"]),
            idea_part=IdeaPart(entry["idea_part"]) if entry.get("idea_part") else None,
            court_or_agency=entry.get("court_or_agency"),
            docket_or_identifier=entry.get("docket_or_identifier"),
            publication_date=_parse_date(entry.get("publication_date")),
            effective_date=_parse_date(entry.get("effective_date")),
            official_url=entry.get("official_url"),
            meta=dict(entry.get("meta", {})),
        )
        for entry in data["documents"]
    ]

    return data["source_slug"], FixtureCollector(
        documents=documents, fixture_root=descriptor_path.parent
    )
