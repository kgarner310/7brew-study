"""The default provider: does nothing, successfully.

This is what makes "the system must work without an LLM" true rather than
aspirational. It is the default in every environment including CI, so the test
suite exercises the no-AI path by default.
"""

from __future__ import annotations

from app.services.ai.base import (
    AISuggestion,
    CitationCandidate,
    ExtractionRequest,
    PropositionCandidate,
)


class NullProvider:
    """A provider that always abstains."""

    name = "null"
    model = ""

    @property
    def available(self) -> bool:
        return False

    def classify_concepts(self, request: ExtractionRequest) -> list[AISuggestion]:
        return []

    def extract_propositions(self, request: ExtractionRequest) -> list[PropositionCandidate]:
        return []

    def extract_citations(self, request: ExtractionRequest) -> list[CitationCandidate]:
        return []

    def summarize(self, request: ExtractionRequest) -> str:
        return ""

    def suggest_relationships(self, request: ExtractionRequest) -> list[AISuggestion]:
        return []
