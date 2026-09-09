"""Content-type to parser dispatch."""

from __future__ import annotations

from app.core.errors import UnsupportedContentTypeError
from app.ingestion.parsers.base import Parser
from app.ingestion.parsers.html import HtmlParser
from app.ingestion.parsers.plain import PlainTextParser

_REGISTRY: list[Parser] = [HtmlParser(), PlainTextParser()]


def register_parser(parser: Parser) -> None:
    """Add a parser, giving it precedence over previously registered ones."""
    _REGISTRY.insert(0, parser)


def get_parser(content_type: str) -> Parser:
    """Return the first parser that supports ``content_type``."""
    for parser in _REGISTRY:
        if parser.supports(content_type):
            return parser
    raise UnsupportedContentTypeError(f"No parser registered for {content_type!r}")


def registered_parsers() -> tuple[Parser, ...]:
    """Snapshot of the registry, for diagnostics."""
    return tuple(_REGISTRY)
