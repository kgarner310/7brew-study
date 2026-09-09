"""Parser protocol and result type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Plain text extracted from a retrieved document."""

    text: str
    title: str | None = None
    parser_name: str = "unknown"
    parser_version: str = "0"
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Parser(Protocol):
    """Converts raw bytes into :class:`ParsedDocument`.

    Implementations must be pure and side-effect free: no network calls, no
    filesystem writes, no evaluation of embedded script content.
    """

    name: str
    version: str

    def supports(self, content_type: str) -> bool:
        """True if this parser handles ``content_type``."""
        ...

    def parse(self, body: bytes, *, content_type: str, url: str) -> ParsedDocument:
        """Extract text from ``body``."""
        ...
