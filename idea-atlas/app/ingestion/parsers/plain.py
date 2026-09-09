"""Plain-text and XML passthrough parsing."""

from __future__ import annotations

from app.core.errors import ParseError
from app.ingestion.normalizers.text import normalize_text
from app.ingestion.parsers.base import ParsedDocument


class PlainTextParser:
    """Decodes and normalizes text/plain and XML payloads."""

    name = "plain"
    version = "1"

    def supports(self, content_type: str) -> bool:
        return content_type in {"text/plain", "text/xml", "application/xml"}

    def parse(self, body: bytes, *, content_type: str, url: str) -> ParsedDocument:
        text = normalize_text(body.decode("utf-8", errors="replace"))
        if not text:
            raise ParseError(f"Document at {url} produced no text")
        return ParsedDocument(text=text, parser_name=self.name, parser_version=self.version)
