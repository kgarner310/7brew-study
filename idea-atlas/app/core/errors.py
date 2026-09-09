"""Domain exceptions.

These are deliberately coarse. Each maps to exactly one HTTP status in
``app.api.errors`` so that handler wiring stays declarative.
"""

from __future__ import annotations


class IdeaAtlasError(Exception):
    """Base class for all application errors."""


class ConfigurationError(IdeaAtlasError):
    """Invalid or missing configuration detected at startup."""


class NotFoundError(IdeaAtlasError):
    """A requested entity does not exist."""


class ValidationError(IdeaAtlasError):
    """Caller-supplied data failed domain validation."""


class IngestionError(IdeaAtlasError):
    """Base class for ingestion failures."""


class UnsafeUrlError(IngestionError):
    """A URL failed SSRF / allowlist validation and was not fetched."""


class ContentTooLargeError(IngestionError):
    """A response exceeded the configured hard size cap."""


class UnsupportedContentTypeError(IngestionError):
    """A response carried a content type the parser is not allowed to handle."""


class FetchError(IngestionError):
    """The source could not be retrieved after retries."""


class ParseError(IngestionError):
    """Retrieved content could not be parsed into normalized text."""


class InsufficientCoverageError(IdeaAtlasError):
    """The knowledge base lacks validated data to answer a research request.

    This is a first-class outcome, not a bug: it is the alternative to
    inventing a legal answer.
    """
