"""SSRF and URL policy tests.

These are the highest-value tests in the suite: a regression here turns the
ingestion worker into a proxy into the private network.
"""

from __future__ import annotations

import pytest

from app.core.errors import UnsafeUrlError, UnsupportedContentTypeError
from app.ingestion.url_safety import (
    UrlPolicy,
    assert_content_type_allowed,
    host_is_allowed,
    is_public_ip,
    normalize_content_type,
    validate_url,
)


class TestPublicIpDetection:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",  # cloud metadata endpoint
            "0.0.0.0",  # noqa: S104 - an SSRF target under test, not a bind address
            "::1",
            "fe80::1",
            "fc00::1",
            "::ffff:127.0.0.1",  # IPv4-mapped loopback
            "::ffff:169.254.169.254",  # IPv4-mapped metadata endpoint
            "224.0.0.1",  # multicast
            "240.0.0.1",  # reserved
        ],
    )
    def test_rejects_non_public(self, address: str) -> None:
        assert is_public_ip(address) is False

    @pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2606:4700::1111"])
    def test_accepts_public(self, address: str) -> None:
        assert is_public_ip(address) is True

    def test_rejects_garbage(self) -> None:
        assert is_public_ip("not-an-ip") is False


class TestHostAllowlist:
    @pytest.mark.parametrize(
        "host", ["www.ecfr.gov", "sites.ed.gov", "uscode.house.gov", "GOVINFO.GOV"]
    )
    def test_gov_tld_allowed(self, host: str) -> None:
        assert host_is_allowed(host, UrlPolicy()) is True

    @pytest.mark.parametrize(
        "host",
        [
            "evil.com",
            "ecfr.gov.evil.com",  # suffix-confusion attempt
            "notgov",
            "",
            "localhost",
        ],
    )
    def test_non_gov_rejected(self, host: str) -> None:
        assert host_is_allowed(host, UrlPolicy()) is False

    def test_explicit_extra_host_allowed(self) -> None:
        assert host_is_allowed("static.case.law", UrlPolicy()) is True

    def test_trailing_dot_normalized(self) -> None:
        assert host_is_allowed("www.ecfr.gov.", UrlPolicy()) is True


class TestValidateUrl:
    @pytest.mark.parametrize(
        ("url", "fragment"),
        [
            ("file:///etc/passwd", "scheme"),
            ("ftp://ecfr.gov/x", "scheme"),
            ("http://www.ecfr.gov/x", "https"),
            ("https://user:pass@www.ecfr.gov/x", "credentials"),
            ("https://evil.com/x", "allowlisted"),
            ("https://www.ecfr.gov:8080/x", "Port"),
        ],
    )
    def test_rejects(self, url: str, fragment: str) -> None:
        with pytest.raises(UnsafeUrlError, match=fragment):
            validate_url(url)

    def test_rejects_private_ip_even_when_allowlist_is_off(self) -> None:
        """Disabling the allowlist must not disable the IP checks."""
        policy = UrlPolicy(enforce_allowlist=False, require_https=False)
        with pytest.raises(UnsafeUrlError, match="non-public"):
            validate_url("http://127.0.0.1:8080/admin", policy)

    def test_rejects_metadata_endpoint_with_allowlist_off(self) -> None:
        policy = UrlPolicy(enforce_allowlist=False, require_https=False)
        with pytest.raises(UnsafeUrlError, match="non-public"):
            validate_url("http://169.254.169.254/latest/meta-data/", policy)

    def test_rejects_url_without_host(self) -> None:
        with pytest.raises(UnsafeUrlError):
            validate_url("https:///nohost")


class TestContentType:
    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("text/html; charset=utf-8", "text/html"),
            ("TEXT/HTML", "text/html"),
            ("  application/pdf  ", "application/pdf"),
            (None, ""),
        ],
    )
    def test_normalize(self, header: str | None, expected: str) -> None:
        assert normalize_content_type(header) == expected

    def test_allows_expected_types(self) -> None:
        assert assert_content_type_allowed("text/html; charset=utf-8") == "text/html"

    @pytest.mark.parametrize(
        "header",
        ["application/octet-stream", "application/zip", "image/png", None, ""],
    )
    def test_rejects_others(self, header: str | None) -> None:
        with pytest.raises(UnsupportedContentTypeError):
            assert_content_type_allowed(header)
