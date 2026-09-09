"""The research endpoint."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.schemas.research import ResearchRequestIn, ResearchResponse
from app.services.research import ResearchRequest, run_research

router = APIRouter(tags=["research"])


@router.post(
    "/research",
    response_model=ResearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Answer a jurisdiction-scoped IDEA research question",
)
def research(payload: ResearchRequestIn, session: DbSession) -> ResearchResponse:
    """Answer from stored, source-linked propositions only.

    No language model participates in this path. When the knowledge base has
    nothing that clears review, the response carries
    ``sufficient_coverage=false`` and an empty answer rather than invented
    prose. That is the intended behavior, and it returns HTTP 200 because the
    request itself succeeded.
    """
    result = run_research(
        session,
        ResearchRequest(
            issue=payload.issue,
            jurisdiction=payload.jurisdiction,
            detail=payload.detail,
            token_budget=payload.token_budget,
            include_unreviewed=payload.include_unreviewed,
            as_of=payload.as_of,
        ),
    )
    return ResearchResponse.model_validate(result, from_attributes=True)
