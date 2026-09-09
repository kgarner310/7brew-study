"""Research endpoint request and response models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import DetailLevel


class ResearchRequestIn(BaseModel):
    """A research question scoped to a jurisdiction."""

    model_config = ConfigDict(extra="forbid")

    issue: str = Field(
        min_length=3,
        max_length=2000,
        description="The legal question, in plain language or IDEA terminology.",
        examples=["Can MTSS delay an IDEA evaluation?"],
    )
    jurisdiction: str | None = Field(
        default=None,
        max_length=64,
        description="Jurisdiction slug or postal code, e.g. 'nc' or 'NC'. "
        "Omit to answer against the federal baseline only.",
        examples=["NC"],
    )
    detail: DetailLevel = Field(
        default=DetailLevel.COMPACT,
        description="Response verbosity. See docs/TOKEN_EFFICIENCY.md.",
    )
    token_budget: int = Field(
        default=1000,
        ge=0,
        le=100_000,
        description="Soft cap on the assembled answer. 0 disables truncation.",
    )
    include_unreviewed: bool = Field(
        default=False,
        description=(
            "Include propositions that have not cleared review. They are "
            "returned with their true review_status and a prominent warning; "
            "they are never presented as verified."
        ),
    )
    as_of: date | None = Field(
        default=None,
        description="Answer as of this date, using effective-dated propositions.",
    )


class AuthorityRefOut(BaseModel):
    """An authority cited in a research response."""

    id: str
    canonical_citation: str
    title: str
    authority_type: str
    jurisdiction_slug: str
    current_status: str
    precedential_status: str
    source_url: str
    pin_cite: str | None = None
    relationship: str | None = None
    quoted_text: str | None = None
    effective_date: date | None = None


class PropositionRefOut(BaseModel):
    """A proposition cited in a research response."""

    id: str
    statement: str
    proposition_type: str
    concept_slug: str
    jurisdiction_slug: str | None
    qualifier: str | None
    review_status: str
    authority_status: str
    confidence: float
    effective_from: date | None = None
    effective_to: date | None = None
    authorities: list[AuthorityRefOut] = Field(default_factory=list)


class ResearchResponse(BaseModel):
    """The research result.

    ``sufficient_coverage=false`` means the knowledge base could not support an
    answer. That is a correct outcome, not an error: nothing is invented to
    fill the gap.
    """

    answer: str
    issue: str
    jurisdiction: dict[str, object] | None
    concepts: list[dict[str, object]]
    propositions: list[PropositionRefOut]
    authorities: list[AuthorityRefOut]
    review_status: str = Field(description="The WEAKEST review status among the records used.")
    confidence: float = Field(ge=0.0, le=1.0)
    as_of: datetime
    detail: DetailLevel
    sufficient_coverage: bool
    estimated_response_tokens: int
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str
