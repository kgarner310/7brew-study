"""HTML to text.

Uses lxml via BeautifulSoup. Script, style, and chrome elements are dropped
before text extraction -- both to reduce hash noise and because script content
must never reach a parser, a log, or a model prompt.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Comment

from app.core.errors import ParseError
from app.ingestion.normalizers.text import normalize_text
from app.ingestion.parsers.base import ParsedDocument

#: Removed wholesale: never legal text, always hash noise.
_STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "iframe",
    "nav",
    "header",
    "footer",
    "form",
    "button",
)

#: Preferred containers for the substantive body of a government page, tried in
#: order before falling back to <body>.
_CONTENT_SELECTORS = (
    "main",
    "article",
    "div#content",
    "div.content",
    "div#main-content",
    "div.field--name-body",
)


class HtmlParser:
    """Extracts readable text from HTML documents."""

    name = "html"
    version = "1"

    def supports(self, content_type: str) -> bool:
        return content_type in {"text/html", "application/xhtml+xml"}

    def parse(self, body: bytes, *, content_type: str, url: str) -> ParsedDocument:
        try:
            soup = BeautifulSoup(body, "lxml")
        except Exception as exc:
            raise ParseError(f"Failed to parse HTML from {url}: {exc}") from exc

        for tag_name in _STRIP_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()
        for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
            comment.extract()

        title = soup.title.get_text(strip=True) if soup.title else None

        container = None
        for selector in _CONTENT_SELECTORS:
            container = soup.select_one(selector)
            if container is not None:
                break
        if container is None:
            container = soup.body or soup

        text = normalize_text(container.get_text("\n"))
        if not text:
            raise ParseError(f"HTML at {url} produced no text")

        return ParsedDocument(
            text=text,
            title=title,
            parser_name=self.name,
            parser_version=self.version,
            extra={"selector_used": "body" if container is soup.body else "content"},
        )
