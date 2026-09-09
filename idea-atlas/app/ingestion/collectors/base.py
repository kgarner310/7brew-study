"""Collector protocol."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol, runtime_checkable

from app.core.enums import AuthorityType, IdeaPart


@dataclass(frozen=True, slots=True)
class CollectedDocument:
    """One document a collector knows how to retrieve, with its legal identity.

    The collector supplies identity (citation, type, dates) because only it
    knows the shape of its source. The pipeline supplies retrieval, hashing,
    and persistence, which are identical everywhere.
    """

    url: str
    canonical_citation: str
    title: str
    authority_type: AuthorityType
    idea_part: IdeaPart | None = None
    court_or_agency: str | None = None
    docket_or_identifier: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    official_url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Collector(Protocol):
    """Enumerates the documents available from one source."""

    name: str
    version: str

    def discover(self) -> Iterator[CollectedDocument]:
        """Yield the documents this collector is responsible for."""
        ...
