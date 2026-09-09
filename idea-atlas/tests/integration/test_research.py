"""Research endpoint and service behaviour.

The properties under test are integrity properties: the platform must not
answer beyond its evidence, must not overstate provenance, and must not present
machine-derived material as verified.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DetailLevel, ReviewStatus
from app.ingestion.fixtures import load_fixture_collector
from app.ingestion.pipeline import IngestionPipeline
from app.models import Proposition, Source
from app.services.matching import match_concepts
from app.services.research import ResearchRequest, run_research
from app.services.seed import seed_demo_propositions

pytestmark = pytest.mark.integration


@pytest.fixture
def populated_session(seeded_session: Session) -> Session:
    """Reference data + fixture-ingested authorities + demo propositions."""
    source = seeded_session.scalars(select(Source).where(Source.slug == "ecfr-34-cfr-300")).one()
    _, collector = load_fixture_collector()
    IngestionPipeline(seeded_session).run(source, collector)
    seed_demo_propositions(seeded_session)
    return seeded_session


@pytest.fixture
def populated_client(api_app: FastAPI, populated_session: Session) -> Iterator[TestClient]:
    with TestClient(api_app) as client:
        yield client


class TestConceptMatching:
    def test_matches_mtss_to_initial_evaluation(self, seeded_session: Session) -> None:
        matches = match_concepts(seeded_session, "Can MTSS delay an IDEA evaluation?")
        assert "initial-evaluation" in {m.concept.slug for m in matches}

    def test_longer_phrases_outrank_shorter_ones(self, seeded_session: Session) -> None:
        matches = match_concepts(seeded_session, "manifestation determination review")
        assert matches[0].concept.slug == "manifestation-determination"

    def test_is_deterministic(self, seeded_session: Session) -> None:
        issue = "prior written notice for a change of placement"
        first = [m.concept.slug for m in match_concepts(seeded_session, issue)]
        second = [m.concept.slug for m in match_concepts(seeded_session, issue)]
        assert first == second

    def test_does_not_match_on_substrings(self, seeded_session: Session) -> None:
        """'iep' must not fire inside an unrelated word."""
        matches = match_concepts(seeded_session, "the recipient was notified")
        assert "iep" not in {m.concept.slug for m in matches}

    def test_empty_issue_matches_nothing(self, seeded_session: Session) -> None:
        assert match_concepts(seeded_session, "   ") == []


class TestInsufficientCoverage:
    def test_unmatched_issue_returns_insufficient(self, seeded_session: Session) -> None:
        result = run_research(
            seeded_session, ResearchRequest(issue="How do I register a trademark?")
        )
        assert result.sufficient_coverage is False
        assert result.answer == ""
        assert any("insufficient_coverage" in w for w in result.warnings)

    def test_matched_concept_with_no_data_returns_insufficient(
        self, seeded_session: Session
    ) -> None:
        result = run_research(
            seeded_session, ResearchRequest(issue="extended school year services")
        )
        assert result.sufficient_coverage is False
        assert result.propositions == []

    def test_unreviewed_data_is_withheld_by_default(self, populated_session: Session) -> None:
        """The core rule: nothing below source_verified is served."""
        result = run_research(
            populated_session,
            ResearchRequest(issue="Can MTSS delay an IDEA evaluation?", jurisdiction="nc"),
        )
        assert result.sufficient_coverage is False
        assert result.answer == ""
        assert result.propositions == []
        assert any("cleared review" in w for w in result.warnings)

    def test_tells_the_caller_how_to_inspect_withheld_material(
        self, populated_session: Session
    ) -> None:
        result = run_research(
            populated_session, ResearchRequest(issue="initial evaluation consent")
        )
        assert any("include_unreviewed=true" in w for w in result.warnings)

    def test_never_invents_an_answer(self, populated_session: Session) -> None:
        for issue in ("Can MTSS delay an IDEA evaluation?", "what is the ESY standard"):
            result = run_research(populated_session, ResearchRequest(issue=issue))
            if not result.sufficient_coverage:
                assert result.answer == ""
                assert result.confidence == 0.0


class TestExplicitlyUnreviewedResults:
    def _run(self, session: Session, **kwargs: object) -> object:
        return run_research(
            session,
            ResearchRequest(
                issue="Can MTSS delay an IDEA evaluation?",
                jurisdiction="nc",
                include_unreviewed=True,
                **kwargs,  # type: ignore[arg-type]
            ),
        )

    def test_returns_propositions_when_explicitly_requested(
        self, populated_session: Session
    ) -> None:
        result = self._run(populated_session)
        assert result.propositions  # type: ignore[attr-defined]
        assert result.answer  # type: ignore[attr-defined]

    def test_reports_the_true_review_status(self, populated_session: Session) -> None:
        result = self._run(populated_session)
        assert result.review_status == ReviewStatus.NEEDS_REVIEW.value  # type: ignore[attr-defined]
        assert result.sufficient_coverage is False  # type: ignore[attr-defined]

    def test_carries_a_prominent_not_reviewed_warning(self, populated_session: Session) -> None:
        result = self._run(populated_session)
        assert any("NOT REVIEWED" in w for w in result.warnings)  # type: ignore[attr-defined]

    def test_confidence_is_capped_by_review_status(self, populated_session: Session) -> None:
        """Unreviewed content can never be reported as high-confidence."""
        result = self._run(populated_session)
        assert result.confidence <= 0.25  # type: ignore[attr-defined]

    def test_every_served_proposition_cites_an_authority(self, populated_session: Session) -> None:
        result = self._run(populated_session)
        for proposition in result.propositions:  # type: ignore[attr-defined]
            assert proposition.authorities
            assert all(a.canonical_citation for a in proposition.authorities)

    def test_answer_contains_the_citation(self, populated_session: Session) -> None:
        result = self._run(populated_session)
        assert "34 C.F.R. 300.301" in result.answer  # type: ignore[attr-defined]


class TestDetailLevelsAndBudget:
    def _run(self, session: Session, detail: DetailLevel, budget: int = 5000) -> object:
        return run_research(
            session,
            ResearchRequest(
                issue="Can MTSS delay an IDEA evaluation?",
                jurisdiction="nc",
                include_unreviewed=True,
                detail=detail,
                token_budget=budget,
            ),
        )

    def test_research_detail_costs_more_than_compact(self, populated_session: Session) -> None:
        compact = self._run(populated_session, DetailLevel.COMPACT)
        research = self._run(populated_session, DetailLevel.RESEARCH)
        assert research.estimated_response_tokens > compact.estimated_response_tokens  # type: ignore[attr-defined]

    def test_compact_omits_qualifiers(self, populated_session: Session) -> None:
        compact = self._run(populated_session, DetailLevel.COMPACT)
        assert all(p.qualifier is None for p in compact.propositions)  # type: ignore[attr-defined]

    def test_research_includes_qualifiers(self, populated_session: Session) -> None:
        research = self._run(populated_session, DetailLevel.RESEARCH)
        assert any(p.qualifier for p in research.propositions)  # type: ignore[attr-defined]

    def test_token_budget_truncates_and_flags(self, populated_session: Session) -> None:
        result = self._run(populated_session, DetailLevel.COMPACT, budget=15)
        assert result.truncated is True  # type: ignore[attr-defined]
        assert any("truncated" in w for w in result.warnings)  # type: ignore[attr-defined]

    def test_zero_budget_disables_truncation(self, populated_session: Session) -> None:
        result = self._run(populated_session, DetailLevel.COMPACT, budget=0)
        assert result.truncated is False  # type: ignore[attr-defined]


class TestJurisdictionScoping:
    def test_resolves_a_postal_code(self, populated_session: Session) -> None:
        result = run_research(
            populated_session,
            ResearchRequest(issue="initial evaluation", jurisdiction="NC"),
        )
        assert result.jurisdiction is not None
        assert result.jurisdiction["slug"] == "nc"
        assert result.jurisdiction["federal_circuit"] == "4th"

    def test_unknown_jurisdiction_warns_and_falls_back(self, populated_session: Session) -> None:
        result = run_research(
            populated_session,
            ResearchRequest(issue="initial evaluation", jurisdiction="atlantis"),
        )
        assert result.jurisdiction is None
        assert any("Unknown jurisdiction" in w for w in result.warnings)

    def test_federal_propositions_apply_everywhere(self, populated_session: Session) -> None:
        """A universal (federal-floor) proposition surfaces in any state."""
        for slug in ("nc", "ca", "tx"):
            result = run_research(
                populated_session,
                ResearchRequest(
                    issue="Can MTSS delay an IDEA evaluation?",
                    jurisdiction=slug,
                    include_unreviewed=True,
                ),
            )
            assert result.propositions

    def test_as_of_date_excludes_expired_propositions(self, populated_session: Session) -> None:
        proposition = populated_session.scalars(select(Proposition)).first()
        assert proposition is not None
        proposition.effective_to = datetime(2000, 1, 1, tzinfo=UTC).date()
        populated_session.flush()

        result = run_research(
            populated_session,
            ResearchRequest(
                issue="Can MTSS delay an IDEA evaluation?",
                jurisdiction="nc",
                include_unreviewed=True,
            ),
        )
        assert str(proposition.id) not in {p.id for p in result.propositions}


class TestResearchEndpoint:
    def test_returns_200_with_insufficient_coverage(self, populated_client: TestClient) -> None:
        """A coverage gap is a successful request, not an HTTP error."""
        response = populated_client.post(
            "/v1/research",
            json={"issue": "Can MTSS delay an IDEA evaluation?", "jurisdiction": "NC"},
        )
        assert response.status_code == 200
        assert response.json()["sufficient_coverage"] is False

    def test_response_always_carries_a_disclaimer(self, populated_client: TestClient) -> None:
        body = populated_client.post("/v1/research", json={"issue": "initial evaluation"}).json()
        assert "not legal advice" in body["disclaimer"].lower()

    def test_reports_estimated_tokens(self, populated_client: TestClient) -> None:
        body = populated_client.post("/v1/research", json={"issue": "initial evaluation"}).json()
        assert body["estimated_response_tokens"] > 0

    def test_rejects_an_empty_issue(self, populated_client: TestClient) -> None:
        assert populated_client.post("/v1/research", json={"issue": ""}).status_code == 422

    def test_rejects_unknown_fields(self, populated_client: TestClient) -> None:
        response = populated_client.post(
            "/v1/research", json={"issue": "evaluation", "sql": "DROP TABLE authority"}
        )
        assert response.status_code == 422

    def test_rejects_an_invalid_detail_level(self, populated_client: TestClient) -> None:
        response = populated_client.post(
            "/v1/research", json={"issue": "evaluation", "detail": "everything"}
        )
        assert response.status_code == 422

    def test_full_response_shape(self, populated_client: TestClient) -> None:
        body = populated_client.post(
            "/v1/research",
            json={
                "issue": "Can MTSS delay an IDEA evaluation?",
                "jurisdiction": "NC",
                "detail": "compact",
                "token_budget": 1000,
                "include_unreviewed": True,
            },
        ).json()
        assert {
            "answer",
            "jurisdiction",
            "concepts",
            "propositions",
            "authorities",
            "review_status",
            "confidence",
            "as_of",
            "estimated_response_tokens",
            "warnings",
            "disclaimer",
            "sufficient_coverage",
        } <= set(body)
