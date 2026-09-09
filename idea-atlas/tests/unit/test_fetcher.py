"""Fetcher hardening, exercised with a mock transport (no real network)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import (
    ContentTooLargeError,
    FetchError,
    UnsafeUrlError,
    UnsupportedContentTypeError,
)
from app.ingestion.fetcher import DocumentFetcher
from app.ingestion.url_safety import UrlPolicy

SETTINGS = Settings(
    env="test",
    ingest_max_response_bytes=1024,
    ingest_timeout_seconds=1.0,
    ingest_max_retries=2,
)


def fetcher_with(
    handler: Callable[[httpx.Request], httpx.Response],
) -> DocumentFetcher:
    """A fetcher wired to a mock transport, with the allowlist still enforced."""
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return DocumentFetcher(settings=SETTINGS, policy=UrlPolicy(), client=client)


def html_response(body: bytes = b"<html><body>ok</body></html>") -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "text/html"})


class TestSuccessfulFetch:
    def test_returns_body_and_hashes(self) -> None:
        with fetcher_with(lambda request: html_response()) as fetcher:
            result = fetcher.fetch("https://www.ecfr.gov/a")
        assert result.status_code == 200
        assert result.content_type == "text/html"
        assert len(result.raw_sha256) == 64
        assert result.byte_size == len(result.body)
        assert result.retrieved_at.tzinfo is not None

    def test_sends_the_configured_user_agent(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["ua"] = request.headers["user-agent"]
            return html_response()

        with fetcher_with(handler) as fetcher:
            fetcher.fetch("https://www.ecfr.gov/a")
        assert "idea-atlas" in seen["ua"]


class TestRedirectHandling:
    def test_follows_a_redirect_within_the_allowlist(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/start":
                return httpx.Response(302, headers={"location": "https://www.ecfr.gov/final"})
            return html_response()

        with fetcher_with(handler) as fetcher:
            result = fetcher.fetch("https://www.ecfr.gov/start")
        assert result.final_url == "https://www.ecfr.gov/final"
        assert result.redirect_chain == ("https://www.ecfr.gov/final",)

    def test_revalidates_each_hop_and_blocks_an_internal_target(self) -> None:
        """An allowlisted host must not be able to bounce us into the network."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                302, headers={"location": "http://169.254.169.254/latest/meta-data/"}
            )

        with fetcher_with(handler) as fetcher, pytest.raises(UnsafeUrlError):
            fetcher.fetch("https://www.ecfr.gov/start")

    def test_blocks_a_redirect_to_an_off_allowlist_host(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://evil.com/x"})

        with fetcher_with(handler) as fetcher, pytest.raises(UnsafeUrlError, match="allowlisted"):
            fetcher.fetch("https://www.ecfr.gov/start")

    def test_rejects_a_redirect_loop(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://www.ecfr.gov/loop"})

        with fetcher_with(handler) as fetcher, pytest.raises(UnsafeUrlError, match="redirects"):
            fetcher.fetch("https://www.ecfr.gov/loop")

    def test_missing_location_header_is_an_error(self) -> None:
        with (
            fetcher_with(lambda request: httpx.Response(302)) as fetcher,
            pytest.raises(FetchError, match="Location"),
        ):
            fetcher.fetch("https://www.ecfr.gov/a")


class TestSizeLimits:
    def test_rejects_an_oversized_declared_content_length(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"x",
                headers={"content-type": "text/html", "content-length": "999999"},
            )

        with (
            fetcher_with(handler) as fetcher,
            pytest.raises(ContentTooLargeError, match="declared"),
        ):
            fetcher.fetch("https://www.ecfr.gov/a")

    def test_rejects_an_oversized_body_when_no_length_is_declared(self) -> None:
        """The streaming counter is the real limit, not the header.

        A chunked response carries no Content-Length, so the up-front check
        cannot fire and the running byte counter has to catch it.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=iter([b"x" * 900, b"x" * 900, b"x" * 900]),
                headers={"content-type": "text/html"},
            )

        with (
            fetcher_with(handler) as fetcher,
            pytest.raises(ContentTooLargeError, match="streaming"),
        ):
            fetcher.fetch("https://www.ecfr.gov/a")

    def test_accepts_a_body_at_the_limit(self) -> None:
        with fetcher_with(lambda r: html_response(b"x" * 1024)) as fetcher:
            assert fetcher.fetch("https://www.ecfr.gov/a").byte_size == 1024


class TestContentTypeEnforcement:
    def test_rejects_a_disallowed_content_type(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"MZ", headers={"content-type": "application/octet-stream"}
            )

        with fetcher_with(handler) as fetcher, pytest.raises(UnsupportedContentTypeError):
            fetcher.fetch("https://www.ecfr.gov/a")

    def test_rejects_a_missing_content_type(self) -> None:
        with (
            fetcher_with(lambda r: httpx.Response(200, content=b"data")) as fetcher,
            pytest.raises(UnsupportedContentTypeError),
        ):
            fetcher.fetch("https://www.ecfr.gov/a")


class TestErrorHandling:
    def test_4xx_is_a_fetch_error(self) -> None:
        with (
            fetcher_with(lambda r: httpx.Response(404, headers={"content-type": "text/html"})) as f,
            pytest.raises(FetchError, match="404"),
        ):
            f.fetch("https://www.ecfr.gov/a")

    def test_5xx_is_retried_then_raises(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(503, headers={"content-type": "text/html"})

        with fetcher_with(handler) as fetcher, pytest.raises(FetchError):
            fetcher.fetch("https://www.ecfr.gov/a")
        assert calls["n"] == SETTINGS.ingest_max_retries

    def test_recovers_when_a_retry_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(500, headers={"content-type": "text/html"})
            return html_response()

        with fetcher_with(handler) as fetcher:
            assert fetcher.fetch("https://www.ecfr.gov/a").status_code == 200
        assert calls["n"] == 2

    def test_transport_error_becomes_a_fetch_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        with fetcher_with(handler) as fetcher, pytest.raises(FetchError, match="Transport"):
            fetcher.fetch("https://www.ecfr.gov/a")

    def test_disallowed_url_never_reaches_the_transport(self) -> None:
        """Validation happens before any connection is attempted."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return html_response()

        with fetcher_with(handler) as fetcher, pytest.raises(UnsafeUrlError):
            fetcher.fetch("https://evil.com/a")
        assert calls["n"] == 0
