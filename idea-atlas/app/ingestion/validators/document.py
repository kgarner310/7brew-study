"""Post-parse sanity checks on retrieved documents.

The failure mode these guard against is silent corruption: a source starts
returning a friendly HTML error page with HTTP 200, we hash it, store it as the
current text of 34 C.F.R. Sec. 300.301, and begin serving an empty answer with
full confidence. Better to fail the run loudly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Minimum plausible length for a real legal provision, in characters.
MIN_DOCUMENT_CHARS = 200

_ERROR_PAGE_PATTERNS = (
    re.compile(r"\b404\b.{0,40}\bnot found\b", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"\bpage (?:you requested )?(?:could not be|cannot be|was not) found\b", re.IGNORECASE
    ),
    re.compile(
        r"\bthe page you are looking for\b.{0,60}\b(?:moved|removed|unavailable)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"\baccess denied\b", re.IGNORECASE),
    re.compile(r"\bservice (?:is )?(?:temporarily )?unavailable\b", re.IGNORECASE),
    re.compile(r"\benable javascript\b.{0,80}\bcontinue\b", re.IGNORECASE | re.DOTALL),
)

#: Text that suggests the page is a paywalled or proprietary editorial product.
_PROPRIETARY_PATTERNS = (
    re.compile(r"\b(?:westlaw|lexisnexis|lexis advance|bloomberg law)\b", re.IGNORECASE),
    re.compile(r"\bheadnotes?\b.{0,40}\bcopyright\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bsubscription required\b", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class DocumentValidation:
    """Outcome of validating one parsed document."""

    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default=())

    @property
    def summary(self) -> str:
        return "; ".join(self.errors) or "ok"


def validate_document(
    text: str, *, url: str, min_chars: int = MIN_DOCUMENT_CHARS
) -> DocumentValidation:
    """Check parsed text for the common silent-corruption signatures.

    Args:
        text: Normalized document text.
        url: Source URL, used only in messages.
        min_chars: Length floor below which the document is rejected.

    Returns:
        A :class:`DocumentValidation`; ``ok`` is False when the document must
        not be persisted.
    """
    errors: list[str] = []
    warnings: list[str] = []

    stripped = text.strip()
    if not stripped:
        errors.append(f"{url}: document is empty after parsing")
    elif len(stripped) < min_chars:
        errors.append(f"{url}: document is {len(stripped)} chars, below the {min_chars} floor")

    head = stripped[:4000]
    for pattern in _ERROR_PAGE_PATTERNS:
        if pattern.search(head):
            errors.append(f"{url}: content matches an error-page signature")
            break

    for pattern in _PROPRIETARY_PATTERNS:
        if pattern.search(head):
            warnings.append(
                f"{url}: content mentions a proprietary publisher; "
                "confirm licensing before ingesting at scale"
            )
            break

    return DocumentValidation(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))
