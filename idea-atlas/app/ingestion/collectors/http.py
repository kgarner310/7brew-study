"""Concrete collectors.

``StaticUrlCollector`` drives a fixed, human-curated list of documents -- the
right shape for federal statutes and regulations, where the set of provisions
is known and stable and discovery-by-crawling would add risk without benefit.

``FixtureCollector`` reads the same document descriptors from a local fixture
directory instead of the network, so the full pipeline (parse, normalize, hash,
version, change-detect, persist) is exercised end to end in environments with
no outbound access. It is explicitly labelled as fixture-derived in the stored
metadata so fixture data can never be mistaken for live retrieval.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.ingestion.collectors.base import CollectedDocument


@dataclass(slots=True)
class StaticUrlCollector:
    """Yields a fixed list of documents for live retrieval."""

    documents: Sequence[CollectedDocument]
    name: str = "static_url"
    version: str = "1"

    def discover(self) -> Iterator[CollectedDocument]:
        yield from self.documents


@dataclass(slots=True)
class FixtureCollector:
    """Yields documents whose bodies are read from local fixture files.

    Each document's ``meta`` must carry ``fixture_file``, a path relative to
    ``fixture_root``. The pipeline detects this collector and reads bytes from
    disk instead of issuing an HTTP request.
    """

    documents: Sequence[CollectedDocument]
    fixture_root: Path
    name: str = "fixture"
    version: str = "1"

    def discover(self) -> Iterator[CollectedDocument]:
        yield from self.documents

    def read(self, document: CollectedDocument) -> tuple[bytes, str]:
        """Return ``(body, content_type)`` for ``document`` from disk."""
        relative = document.meta.get("fixture_file")
        if not relative:
            raise ValueError(
                f"Fixture document {document.canonical_citation!r} has no fixture_file"
            )
        # Contain the path inside the fixture root: fixture manifests are repo
        # data, but the same guard keeps a future user-supplied manifest safe.
        path = (self.fixture_root / str(relative)).resolve()
        root = self.fixture_root.resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Fixture path escapes the fixture root: {relative!r}")
        if not path.is_file():
            raise FileNotFoundError(f"Fixture file not found: {path}")
        content_type = str(document.meta.get("content_type", "text/html"))
        return path.read_bytes(), content_type
