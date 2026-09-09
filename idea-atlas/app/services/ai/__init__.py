"""Optional AI assistance.

The platform is fully functional with no provider configured. Nothing here is
authoritative: every AI output is written with review_status=ai_extracted and
must carry source references.
"""

from app.services.ai.base import (
    AIProvider,
    AISuggestion,
    CitationCandidate,
    ExtractionRequest,
    PropositionCandidate,
    wrap_untrusted_document,
)
from app.services.ai.null import NullProvider
from app.services.ai.registry import get_provider, register_provider

__all__ = [
    "AIProvider",
    "AISuggestion",
    "CitationCandidate",
    "ExtractionRequest",
    "NullProvider",
    "PropositionCandidate",
    "get_provider",
    "register_provider",
    "wrap_untrusted_document",
]
