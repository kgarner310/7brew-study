"""Invariants over the bounded legal vocabularies."""

from __future__ import annotations

from app.core.enums import (
    REVIEW_STATUS_RANK,
    SERVABLE_REVIEW_STATUSES,
    ReviewStatus,
)


class TestReviewStatuses:
    def test_all_seven_statuses_exist(self) -> None:
        assert {status.value for status in ReviewStatus} == {
            "source_verified",
            "ai_extracted",
            "cross_validated",
            "human_reviewed",
            "expert_reviewed",
            "rejected",
            "needs_review",
        }

    def test_every_status_is_ranked(self) -> None:
        assert set(REVIEW_STATUS_RANK) == set(ReviewStatus)

    def test_ai_extracted_is_never_servable(self) -> None:
        """The core integrity rule: machine output is not verified content."""
        assert ReviewStatus.AI_EXTRACTED not in SERVABLE_REVIEW_STATUSES
        assert ReviewStatus.NEEDS_REVIEW not in SERVABLE_REVIEW_STATUSES
        assert ReviewStatus.REJECTED not in SERVABLE_REVIEW_STATUSES

    def test_verified_statuses_are_servable(self) -> None:
        assert {
            ReviewStatus.SOURCE_VERIFIED,
            ReviewStatus.CROSS_VALIDATED,
            ReviewStatus.HUMAN_REVIEWED,
            ReviewStatus.EXPERT_REVIEWED,
        } == SERVABLE_REVIEW_STATUSES

    def test_ranking_orders_assurance_correctly(self) -> None:
        assert (
            REVIEW_STATUS_RANK[ReviewStatus.REJECTED]
            < REVIEW_STATUS_RANK[ReviewStatus.NEEDS_REVIEW]
            < REVIEW_STATUS_RANK[ReviewStatus.AI_EXTRACTED]
            < REVIEW_STATUS_RANK[ReviewStatus.SOURCE_VERIFIED]
            < REVIEW_STATUS_RANK[ReviewStatus.CROSS_VALIDATED]
            < REVIEW_STATUS_RANK[ReviewStatus.HUMAN_REVIEWED]
            < REVIEW_STATUS_RANK[ReviewStatus.EXPERT_REVIEWED]
        )

    def test_every_servable_status_outranks_ai_extracted(self) -> None:
        floor = REVIEW_STATUS_RANK[ReviewStatus.AI_EXTRACTED]
        assert all(REVIEW_STATUS_RANK[s] > floor for s in SERVABLE_REVIEW_STATUSES)
