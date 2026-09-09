"""Hardened HTTP fetching for official sources.

Controls applied to every request:

* URL validated by :mod:`app.ingestion.url_safety` before connecting.
* Redirects followed manually, revalidating **each hop** -- an allowlisted host
  cannot bounce us to an internal address.
* ``Content-Length`` rejected up front when it exceeds the cap, and the body
  streamed with a running byte counter so a lying or absent header cannot
  exhaust memory.
* ``Content-Type`` checked against an allowlist before the body is read.
* Bounded retries with exponential backoff on transport errors and 5xx only.
* No cookies, no auth headers, no credential forwarding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import Settings, get_settings
from app.core.errors import ContentTooLargeError, FetchError, UnsafeUrlError
from app.core.logging import get_logger
from app.ingestion.hashing import sha256_bytes
from app.ingestion.url_safety import UrlPolicy, assert_content_type_allowed, validate_url

logger = get_logger(__name__)

MAX_REDIRECTS = 5


@dataclass(frozen=True, slots=True)
class FetchResult:
    """A successfully retrieved document."""

    url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    raw_sha256: str
    retrieved_at: datetime
    byte_size: int
    redirect_chain: tuple[str, ...] = ()

    def text(self, fallback_encoding: str = "utf-8") -> str:
        """Decode the body, replacing undecodable bytes rather than raising."""
        return self.body.decode(fallback_encoding, errors="replace")


class _RetryableStatusError(Exception):
    """Internal signal: a 5xx or 429 that is worth retrying."""


class DocumentFetcher:
    """Fetches single documents under the outbound-request policy."""

    def __init__(
        self,
        settings: Settings | None = None,
        policy: UrlPolicy | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.policy = policy or UrlPolicy(enforce_allowlist=self.settings.ingest_enforce_allowlist)
        self._client = client
        self._owns_client = client is None

    def _outbound_headers(self) -> dict[str, str]:
        """Headers applied to every request.

        Set per-request rather than only on the client so that a caller-supplied
        client (tests, or a shared pooled client) cannot silently drop our
        identifying User-Agent.
        """
        return {
            "User-Agent": self.settings.ingest_user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(self.settings.ingest_timeout_seconds),
            follow_redirects=False,  # we revalidate every hop ourselves
            headers=self._outbound_headers(),
            cookies=None,
            trust_env=True,
        )

    def __enter__(self) -> DocumentFetcher:
        if self._client is None:
            self._client = self._build_client()
            self._owns_client = True
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = self._build_client()
            self._owns_client = True
        return self._client

    def fetch(self, url: str) -> FetchResult:
        """Retrieve ``url``, following and revalidating redirects.

        Raises:
            UnsafeUrlError: URL or a redirect target violated policy.
            ContentTooLargeError: Body exceeded the configured cap.
            UnsupportedContentTypeError: Disallowed Content-Type.
            FetchError: Transport failure or non-retryable HTTP error.
        """
        chain: list[str] = []
        current = url

        for _ in range(MAX_REDIRECTS + 1):
            validate_url(current, self.policy)
            response = self._request_with_retry(current)

            if response.is_redirect:
                location = response.headers.get("location")
                response.close()
                if not location:
                    raise FetchError(f"Redirect from {current} carried no Location")
                target = str(httpx.URL(current).join(location))
                chain.append(target)
                logger.info("ingest.redirect", from_url=current, to_url=target)
                current = target
                continue

            return self._read_response(url, current, response, tuple(chain))

        raise UnsafeUrlError(f"Exceeded {MAX_REDIRECTS} redirects starting at {url}")

    def _request_with_retry(self, url: str) -> httpx.Response:
        @retry(
            stop=stop_after_attempt(max(1, self.settings.ingest_max_retries)),
            wait=wait_exponential(multiplier=1, min=1, max=15),
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
            reraise=True,
        )
        def _attempt() -> httpx.Response:
            request = self.client.build_request("GET", url, headers=self._outbound_headers())
            response = self.client.send(request, stream=True)
            if response.status_code >= 500 or response.status_code == 429:
                status = response.status_code
                response.close()
                raise _RetryableStatusError(f"HTTP {status} from {url}")
            return response

        try:
            return _attempt()
        except _RetryableStatusError as exc:
            raise FetchError(str(exc)) from exc
        except httpx.TransportError as exc:
            raise FetchError(f"Transport error fetching {url}: {exc}") from exc

    def _read_response(
        self,
        original_url: str,
        final_url: str,
        response: httpx.Response,
        chain: tuple[str, ...],
    ) -> FetchResult:
        cap = self.settings.ingest_max_response_bytes
        try:
            if response.status_code >= 400:
                raise FetchError(f"HTTP {response.status_code} from {final_url}")

            declared = response.headers.get("content-length")
            if declared is not None and declared.isdigit() and int(declared) > cap:
                raise ContentTooLargeError(f"{final_url} declared {declared} bytes, cap is {cap}")

            content_type = assert_content_type_allowed(response.headers.get("content-type"))

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > cap:
                    raise ContentTooLargeError(f"{final_url} exceeded {cap} bytes while streaming")
                chunks.append(chunk)
            body = b"".join(chunks)
        finally:
            response.close()

        logger.info(
            "ingest.fetched",
            url=final_url,
            status=response.status_code,
            bytes=len(body),
            content_type=content_type,
        )
        return FetchResult(
            url=original_url,
            final_url=final_url,
            status_code=response.status_code,
            content_type=content_type,
            body=body,
            raw_sha256=sha256_bytes(body),
            retrieved_at=datetime.now(UTC),
            byte_size=len(body),
            redirect_chain=chain,
        )
