"""Token estimation and budget truncation."""

from __future__ import annotations

import pytest

from app.services.tokens import (
    estimate_payload_tokens,
    estimate_tokens,
    estimate_tokens_detailed,
    truncate_to_budget,
)


class TestEstimateTokens:
    def test_empty_is_zero(self) -> None:
        assert estimate_tokens("") == 0

    def test_monotonic_in_length(self) -> None:
        short = estimate_tokens("An initial evaluation.")
        long = estimate_tokens("An initial evaluation. " * 10)
        assert long > short

    def test_deterministic(self) -> None:
        text = "34 C.F.R. 300.301(c)(1)"
        assert estimate_tokens(text) == estimate_tokens(text)

    def test_in_plausible_range_for_prose(self) -> None:
        """Roughly 3-5 characters per token for ordinary English."""
        text = " ".join(["the quick brown fox jumps over the lazy dog"] * 20)
        tokens = estimate_tokens(text)
        assert len(text) / 5 <= tokens <= len(text) / 2

    def test_citation_dense_text_is_denser(self) -> None:
        """Punctuation- and digit-heavy citations cost more per character."""
        prose = "the quick brown fox jumps over the lazy dog again and again"
        citation = "34 C.F.R. 300.301(c)(1); 20 U.S.C. 1414(a)(1)(C)(i)."
        assert estimate_tokens(citation) / len(citation) > estimate_tokens(prose) / len(prose)

    def test_detailed_reports_inputs(self) -> None:
        estimate = estimate_tokens_detailed("one two three")
        assert estimate.words == 3
        assert estimate.characters == 13
        assert int(estimate) == estimate.tokens


class TestEstimatePayloadTokens:
    def test_none_is_zero(self) -> None:
        assert estimate_payload_tokens(None) == 0

    def test_nested_structures_counted(self) -> None:
        small = estimate_payload_tokens({"a": "x"})
        large = estimate_payload_tokens({"a": "x", "b": ["y", "z"], "c": {"d": "w"}})
        assert large > small

    def test_scalars_are_cheap(self) -> None:
        assert estimate_payload_tokens(42) == 1
        assert estimate_payload_tokens(True) == 1


class TestTruncateToBudget:
    def test_no_truncation_when_it_fits(self) -> None:
        text = "short text"
        result, truncated = truncate_to_budget(text, 1000)
        assert result == text
        assert truncated is False

    def test_truncates_when_over_budget(self) -> None:
        text = "word " * 200
        result, truncated = truncate_to_budget(text, 20)
        assert truncated is True
        assert estimate_tokens(result) <= 20
        assert len(result) < len(text)

    def test_cuts_on_word_boundary(self) -> None:
        text = "alpha beta gamma delta epsilon zeta eta theta"
        result, _ = truncate_to_budget(text, 5)
        assert all(word in text.split() for word in result.split())

    def test_zero_budget_yields_empty(self) -> None:
        result, truncated = truncate_to_budget("anything at all", 0)
        assert result == ""
        assert truncated is True

    @pytest.mark.parametrize("budget", [1, 5, 25, 100])
    def test_result_always_within_budget(self, budget: int) -> None:
        text = "An initial evaluation must be completed within the timeline. " * 30
        result, _ = truncate_to_budget(text, budget)
        assert estimate_tokens(result) <= budget
