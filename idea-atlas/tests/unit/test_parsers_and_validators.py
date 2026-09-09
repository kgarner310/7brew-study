"""Parser dispatch, HTML extraction, and document validation."""

from __future__ import annotations

import pytest

from app.core.errors import ParseError, UnsupportedContentTypeError
from app.ingestion.parsers import get_parser
from app.ingestion.parsers.html import HtmlParser
from app.ingestion.parsers.plain import PlainTextParser
from app.ingestion.validators import validate_document


class TestParserRegistry:
    @pytest.mark.parametrize(
        ("content_type", "expected"),
        [
            ("text/html", HtmlParser),
            ("application/xhtml+xml", HtmlParser),
            ("text/plain", PlainTextParser),
            ("application/xml", PlainTextParser),
        ],
    )
    def test_dispatch(self, content_type: str, expected: type) -> None:
        assert isinstance(get_parser(content_type), expected)

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(UnsupportedContentTypeError):
            get_parser("application/octet-stream")


class TestHtmlParser:
    def _parse(self, html: bytes) -> str:
        return HtmlParser().parse(html, content_type="text/html", url="https://x.gov/a").text

    def test_strips_script_content(self) -> None:
        text = self._parse(
            b"<body><main><p>Legal text here</p><script>var secret='leak';</script></main></body>"
        )
        assert "secret" not in text
        assert "Legal text here" in text

    def test_strips_style_and_nav_chrome(self) -> None:
        text = self._parse(
            b"<body><nav>Home About</nav><style>.a{}</style>"
            b"<main><p>Substance</p></main><footer>Copyright</footer></body>"
        )
        assert text == "Substance"

    def test_strips_html_comments(self) -> None:
        text = self._parse(b"<body><main><p>Text</p><!-- build 12345 --></main></body>")
        assert "12345" not in text

    def test_extracts_title(self) -> None:
        doc = HtmlParser().parse(
            b"<html><head><title>Sec. 300.301</title></head>"
            b"<body><main>Body text</main></body></html>",
            content_type="text/html",
            url="https://x.gov/a",
        )
        assert doc.title == "Sec. 300.301"

    def test_prefers_main_over_full_body(self) -> None:
        text = self._parse(b"<body><div>sidebar noise</div><main><p>Real content</p></main></body>")
        assert text == "Real content"

    def test_empty_document_raises(self) -> None:
        with pytest.raises(ParseError):
            self._parse(b"<html><body><main></main></body></html>")


class TestDocumentValidator:
    def test_accepts_a_plausible_document(self) -> None:
        result = validate_document("An initial evaluation. " * 20, url="https://x.gov/a")
        assert result.ok is True
        assert result.errors == ()

    def test_rejects_empty(self) -> None:
        result = validate_document("   ", url="https://x.gov/a")
        assert result.ok is False
        assert "empty" in result.summary

    def test_rejects_too_short(self) -> None:
        result = validate_document("Short.", url="https://x.gov/a")
        assert result.ok is False
        assert "below the" in result.summary

    @pytest.mark.parametrize(
        "body",
        [
            "404 - Not Found. " * 30,
            "The page you requested could not be found. " * 20,
            "Access Denied. " * 30,
            "Service temporarily unavailable. " * 20,
        ],
    )
    def test_rejects_error_pages(self, body: str) -> None:
        result = validate_document(body, url="https://x.gov/a")
        assert result.ok is False
        assert "error-page" in result.summary

    def test_warns_on_proprietary_publisher_markers(self) -> None:
        body = "Westlaw headnotes and analysis follow. " * 20
        result = validate_document(body, url="https://x.gov/a")
        assert result.ok is True
        assert any("proprietary" in warning for warning in result.warnings)
