"""URL validation for outbound fetches (SSRF defense).

Policy, in order of application:

1. The URL must parse, use ``https``, and carry no embedded credentials.
2. The port must be the scheme default (443) unless explicitly allowlisted.
3. The host must match the domain allowlist. ``*.gov`` is allowed wholesale
   because it is a closed, government-verified TLD; every non-``.gov`` host
   (state SEA sites on ``.us``, ``.edu``, ``.org``) must be listed explicitly.
4. Every IP the host resolves to must be a public unicast address. Private,
   loopback, link-local, multicast, reserved, and unspecified ranges are
   rejected, including IPv4-mapped IPv6 forms.

Known limitation: steps 3-4 are check-then-connect, so a DNS rebinding attacker
who controls an allowlisted domain could return a public address at validation
time and a private one at connect time. The allowlist is the real mitigation;
production deployments must additionally run ingestion workers behind an egress
policy that can reach only the allowlisted hosts. This is recorded as a residual
risk in docs/THREAT_MODEL.md.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.core.errors import UnsafeUrlError

#: Government TLDs trusted wholesale. Registration is restricted to verified
#: U.S. government entities, which is exactly our sourcing policy.
TRUSTED_TLDS: frozenset[str] = frozenset({"gov", "mil"})

#: Non-.gov hosts we accept. Every entry is a deliberate decision; add a host
#: only after confirming it is the official publisher for that jurisdiction.
DEFAULT_EXTRA_ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "www.law.cornell.edu",  # LII: mirror of public-domain U.S. Code text
        "case.law",  # Caselaw Access Project (public-domain opinions)
        "static.case.law",
    }
)

ALLOWED_PORTS: frozenset[int] = frozenset({443})

#: Content types a parser is permitted to handle. Anything else is refused
#: before the body is read.
ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/html",
        "text/plain",
        "text/xml",
        "application/xml",
        "application/xhtml+xml",
        "application/json",
        "application/pdf",
    }
)


@dataclass(frozen=True, slots=True)
class UrlPolicy:
    """Configurable half of the URL policy."""

    enforce_allowlist: bool = True
    extra_allowed_hosts: frozenset[str] = field(default=DEFAULT_EXTRA_ALLOWED_HOSTS)
    allowed_ports: frozenset[int] = field(default=ALLOWED_PORTS)
    require_https: bool = True

    def with_hosts(self, hosts: frozenset[str] | set[str]) -> UrlPolicy:
        """Return a copy whose extra host allowlist is extended."""
        return UrlPolicy(
            enforce_allowlist=self.enforce_allowlist,
            extra_allowed_hosts=frozenset(self.extra_allowed_hosts | set(hosts)),
            allowed_ports=self.allowed_ports,
            require_https=self.require_https,
        )


@dataclass(frozen=True, slots=True)
class ValidatedUrl:
    """A URL that passed every check, with the addresses it resolved to."""

    url: str
    host: str
    port: int
    resolved_ips: tuple[str, ...]


def is_public_ip(raw: str) -> bool:
    """True if ``raw`` is a globally routable unicast address."""
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return False
    # Unwrap IPv4-mapped / 6to4 forms so ::ffff:127.0.0.1 cannot slip through.
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            addr = addr.ipv4_mapped
        elif addr.sixtofour is not None:
            addr = addr.sixtofour
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def host_is_allowed(host: str, policy: UrlPolicy) -> bool:
    """True if ``host`` is inside the domain allowlist."""
    host = host.lower().rstrip(".")
    if not host:
        return False
    if host in policy.extra_allowed_hosts:
        return True
    tld = host.rsplit(".", 1)[-1]
    return tld in TRUSTED_TLDS


def _resolve(host: str, port: int) -> tuple[str, ...]:
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise UnsafeUrlError(f"DNS resolution failed for {host!r}: {exc}") from exc
    ips = tuple(dict.fromkeys(str(info[4][0]) for info in infos))
    if not ips:
        raise UnsafeUrlError(f"DNS resolution returned no addresses for {host!r}")
    return ips


def validate_url(url: str, policy: UrlPolicy | None = None) -> ValidatedUrl:
    """Validate ``url`` against the outbound-fetch policy.

    Args:
        url: Absolute URL to check.
        policy: Overrides for allowlist behavior. Defaults to strict.

    Returns:
        The validated URL together with its resolved addresses.

    Raises:
        UnsafeUrlError: If any check fails. The message is safe to log.
    """
    policy = policy or UrlPolicy()
    parts = urlsplit(url)

    if parts.scheme not in {"http", "https"}:
        raise UnsafeUrlError(f"Unsupported URL scheme: {parts.scheme!r}")
    if policy.require_https and parts.scheme != "https":
        raise UnsafeUrlError("Only https:// URLs may be fetched")
    if parts.username or parts.password:
        raise UnsafeUrlError("URLs must not embed credentials")
    if not parts.hostname:
        raise UnsafeUrlError("URL has no host")

    host = parts.hostname.lower()
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:  # malformed port
        raise UnsafeUrlError(f"Invalid port in URL: {exc}") from exc

    if policy.enforce_allowlist:
        if port not in policy.allowed_ports:
            raise UnsafeUrlError(f"Port {port} is not allowlisted")
        if not host_is_allowed(host, policy):
            raise UnsafeUrlError(f"Host {host!r} is not an allowlisted official source domain")

    # A literal IP host skips DNS but still has to be public.
    try:
        ipaddress.ip_address(host)
        candidate_ips: tuple[str, ...] = (host,)
    except ValueError:
        candidate_ips = _resolve(host, port)

    unsafe = [ip for ip in candidate_ips if not is_public_ip(ip)]
    if unsafe:
        raise UnsafeUrlError(
            f"Host {host!r} resolves to non-public address(es): {', '.join(unsafe)}"
        )

    return ValidatedUrl(url=url, host=host, port=port, resolved_ips=candidate_ips)


def normalize_content_type(header_value: str | None) -> str:
    """Strip parameters from a Content-Type header, lowercased."""
    if not header_value:
        return ""
    return header_value.split(";", 1)[0].strip().lower()


def assert_content_type_allowed(header_value: str | None) -> str:
    """Return the bare content type, or raise if it is not permitted."""
    from app.core.errors import UnsupportedContentTypeError

    content_type = normalize_content_type(header_value)
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedContentTypeError(
            f"Content-Type {content_type or '(missing)'!r} is not permitted"
        )
    return content_type
