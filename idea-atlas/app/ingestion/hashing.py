"""Content hashing and change detection."""

from __future__ import annotations

import hashlib

#: Bumped whenever normalization changes in a way that alters output for
#: unchanged input. Stored on every AuthorityVersion so historical hashes stay
#: interpretable after a normalizer change.
NORMALIZER_VERSION = "1"


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Hex SHA-256 of text, encoded UTF-8.

    Use on *normalized* text so that cosmetic markup churn -- a changed nav bar,
    a rotating session id in a footer -- does not read as a legal amendment.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_changed(previous_sha256: str | None, new_sha256: str) -> bool:
    """True when ``new_sha256`` represents content we have not stored before."""
    return previous_sha256 != new_sha256
